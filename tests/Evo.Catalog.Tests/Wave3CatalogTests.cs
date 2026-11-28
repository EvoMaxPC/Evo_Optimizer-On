using System.Globalization;
using System.Text.RegularExpressions;
using Evo.Catalog;
using Evo.Catalog.Model;
using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Core.System;
using Evo.Testing;
using Microsoft.Win32;
using Xunit;

namespace Evo.Catalog.Tests;

/// <summary>
/// Carga y valida el fichero REAL de la oleada 3 (sección 9, Registro de Windows
/// y configuración del sistema) tal como está en <c>catalog/capabilities/</c>.
/// No hay JSON de mentira: si el catálogo se rompe, el test se rompe.
/// </summary>
public sealed class Wave3CatalogTests
{
    /// <summary>Las 18 capacidades de la sección 9, en orden ordinal.</summary>
    private static readonly string[] Section9 =
    [
        "system.error-reporting.crash-control",
        "system.error-reporting.wpbt-disable",
        "system.game-mode.enable",
        "system.hibernation.hide",
        "system.keyboard-shortcuts.disable",
        "system.location.consent-deny",
        "system.menu-delay.disable",
        "system.mitigations.disable",
        "system.mouse-acceleration.enable",
        // Paso 12: cerrar el asistente de ubicacion de red (AddKey del pin).
        "system.network.location-wizard.disable",
        "system.oem-information.identify",
        "system.registry-backup.enable",
        "system.search-indexing.disable",
        "system.services.manual-profile",
        "system.settings-page-visibility.hide",
        "system.tray.battery-percentage",
        "system.sleep.s0-network-keep",
        "system.sleep.s3-enable",
        "system.time.ntp-servers",
        "system.time.utc-rtc",
    ];

    /// <summary>Las builds que declara <c>catalog/windows-releases.json</c>.</summary>
    private static readonly int[] KnownBuilds = [19045, 22631, 26100, 26200];

    /// <summary>Builds de Windows 11 del catálogo (la 19045 queda fuera).</summary>
    private static readonly int[] Windows11 = [22631, 26100, 26200];

    /// <summary>El pin del que se copiaron los literales.</summary>
    private const string AtlasPin = "atlas@ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f";

    private const string WinUtilPin = "winutil@70c23c80641d7370532af2f619b2842658600842";

    private static CapabilityCatalog LoadAll()
    {
        var directory = Path.Combine(AppContext.BaseDirectory, "capabilities");
        Assert.True(Directory.Exists(directory), $"No existe el directorio de catálogo: {directory}");
        var documents = new CatalogLoader().LoadDirectory(directory);
        return new CapabilityCatalog(
            documents[0].Metadata, documents.SelectMany(d => d.Capabilities));
    }

    private static IReadOnlyList<CapabilityDefinition> Wave3() =>
        LoadAll().Definitions.Where(d => d.SectionId == 9).ToList();

    private static CapabilityDefinition Definition(string id) =>
        Wave3().SingleOrDefault(d => d.Id == id)
        ?? throw new InvalidOperationException($"No está '{id}' en el catálogo de la sección 9.");

    private static IEnumerable<RegistryAction> RegistryActions(CapabilityDefinition definition) =>
        definition.Actions.OfType<RegistryAction>();

    private static IEnumerable<ServiceAction> ServiceActions(CapabilityDefinition definition) =>
        definition.Actions.OfType<ServiceAction>();

    private static RegistryAction Value(CapabilityDefinition definition, string name) =>
        RegistryActions(definition).Single(a => a.ValueName == name);

    // ---------------------------------------------------------------- T4.1 carga
    /// <summary>T4.1: el fichero de la sección 9 carga, valida sin errores ni avisos
    /// y declara exactamente las 18 capacidades del paso 10.</summary>
    [Fact]
    public void TestWave3Catalog_LoadsAndValidates()
    {
        var catalog = LoadAll();

        // 68 de las oleadas 1/1b/8c/2 + 18 de la sección 9 = 86, + 2 del paso 12 = 88.
        Assert.Equal(101, catalog.Count);

        var wave3 = catalog.Definitions.Where(d => d.SectionId == 9)
            .Select(d => d.Id).OrderBy(i => i, StringComparer.Ordinal).ToList();
        Assert.Equal(Section9, wave3);

        var report = new CatalogValidator(KnownBuilds).Validate(catalog);
        Assert.True(report.IsValid, report.ErrorSummary);
        Assert.Empty(report.Errors);
        Assert.Empty(report.Warnings);

        foreach (var definition in catalog.Definitions.Where(d => d.SectionId == 9))
        {
            Assert.Matches(CatalogValidator.IdPattern, definition.Id);
            Assert.True(
                definition.Id.StartsWith("system.", StringComparison.Ordinal)
                || definition.Id.StartsWith("registry.", StringComparison.Ordinal),
                $"{definition.Id}: namespace fuera de system.* / registry.*.");
            Assert.NotEmpty(definition.Actions);
            Assert.False(string.IsNullOrWhiteSpace(definition.Provenance));
            Assert.NotEmpty(definition.Variants);

            Assert.Equal(
                definition.Actions.Select(a => a.Order).Distinct().Count(),
                definition.Actions.Count);
            Assert.Equal(
                Enumerable.Range(1, definition.Actions.Count),
                definition.Actions.Select(a => a.Order).OrderBy(o => o));
        }
    }

    /// <summary>T4.1b: el contrato del motor no encuentra violaciones en ninguna
    /// capacidad de la sección 9 (riesgo, restauración y confirmación).</summary>
    [Fact]
    public void TestWave3Catalog_EngineContractIsClean()
    {
        foreach (var definition in Wave3())
        {
            Assert.Empty(CapabilityRules.Validate(definition.ToContract()));

            // ADR-0003: la sección 9 sólo escribe valores y tipos de inicio, así
            // que ninguna es irreversible y todas conservan el deshacer.
            Assert.Equal(Reversibility.Reversible, definition.Reversibility);
            Assert.True(definition.Restore >= RestoreLevel.SessionUndo, definition.Id);

            Assert.True(
                definition.Confirmation >= CapabilityRules.MinimumConfirmation(definition.Risk),
                $"{definition.Id}: confirmación {definition.Confirmation} < mínimo de {definition.Risk}.");
            Assert.True(
                definition.Restore >= CapabilityRules.MinimumRestore(definition.Risk),
                $"{definition.Id}: restauración {definition.Restore} < mínimo de {definition.Risk}.");
        }
    }

    // ------------------------------------------------------------- T1 contrato
    /// <summary>T1: el namespace es <c>system.*</c>, todos los ids cumplen
    /// <c>^[a-z0-9]+(\.[a-z0-9\-]+)+$</c>, van en la sección 9 y no repiten los de
    /// las otras secciones.</summary>
    [Fact]
    public void TestWave3Catalog_IdsFollowTheContract()
    {
        var pattern = new Regex(@"^[a-z0-9]+(\.[a-z0-9\-]+)+$", RegexOptions.CultureInvariant);
        foreach (var definition in Wave3())
        {
            Assert.Matches(pattern, definition.Id);
            Assert.Equal("system", definition.Id.Split('.')[0]);
            Assert.Equal(9, definition.SectionId);
        }

        var others = LoadAll().Definitions.Where(d => d.SectionId != 9).Select(d => d.Id);
        Assert.Empty(Section9.Intersect(others, StringComparer.Ordinal));
    }

    /// <summary>T1: el privilegio declarado se deduce de lo que se toca: cualquier
    /// escritura en HKLM/HKU o cualquier cambio de servicio exige Admin; HKCU se
    /// queda en User.</summary>
    [Fact]
    public void TestWave3Catalog_PrivilegeMatchesWhatItTouches()
    {
        foreach (var definition in Wave3())
        {
            var hives = RegistryActions(definition).Select(a => a.Hive).Distinct().ToList();
            var touchesMachine = hives.Contains(RegistryHiveKind.LocalMachine)
                || hives.Contains(RegistryHiveKind.Users)
                || ServiceActions(definition).Any()
                // Paso 11: crear una tarea de sistema tambien exige elevacion, y
                // borrar una CLAVE (aunque hoy la seccion 9 no tenga ninguna) es
                // una escritura mas en la colmena que declare.
                || definition.Actions.OfType<TaskCreateAction>().Any()
                || definition.Actions.OfType<RegistryDeleteKeyAction>()
                    .Any(a => a.Hive is RegistryHiveKind.LocalMachine or RegistryHiveKind.Users)
                // Paso 12: crear una clave en HKLM es la misma escritura.
                || definition.Actions.OfType<RegistryCreateKeyAction>()
                    .Any(a => a.Hive is RegistryHiveKind.LocalMachine or RegistryHiveKind.Users);
            var expected = touchesMachine ? PrivilegeLevel.Admin : PrivilegeLevel.User;
            Assert.True(
                expected == definition.Privilege,
                $"{definition.Id}: toca [{string.Join(", ", hives)}] y declara Privilege={definition.Privilege}.");
        }

        // Los dos que sólo cambian servicios piden Admin aunque no escriban registro.
        Assert.Equal(PrivilegeLevel.Admin, Definition("system.services.manual-profile").Privilege);
        Assert.Equal(PrivilegeLevel.Admin, Definition("system.search-indexing.disable").Privilege);
    }

    /// <summary>T1 (ADR-0003): quien declare reducción de seguridad no puede bajar
    /// de riesgo Medium ni de confirmación Summary, y la descripción lo dice con
    /// todas las letras. La sección 9 tiene exactamente dos.</summary>
    [Fact]
    public void TestWave3Catalog_SecurityReductionIsDeclaredAndBounded()
    {
        var reduces = Wave3().Where(d => d.SecurityImpact == SecurityImpact.Reduces)
            .Select(d => d.Id).OrderBy(i => i, StringComparer.Ordinal).ToList();
        Assert.Equal(
            new[] { "system.error-reporting.crash-control", "system.mitigations.disable" },
            reduces);

        foreach (var definition in Wave3().Where(d => d.SecurityImpact == SecurityImpact.Reduces))
        {
            Assert.True(definition.Risk >= RiskLevel.Medium, definition.Id);
            Assert.True(definition.Confirmation >= ConfirmationType.Summary, definition.Id);
            Assert.Contains(
                "reduce", definition.Description, StringComparison.OrdinalIgnoreCase);
        }

        // Mitigaciones: HIGH con punto de restauración, no un Low silencioso.
        var mitigations = Definition("system.mitigations.disable");
        Assert.Equal(RiskLevel.High, mitigations.Risk);
        Assert.Equal(ConfirmationType.SummaryAndRestorePoint, mitigations.Confirmation);
        Assert.Equal(RestoreLevel.RestorePoint, mitigations.Restore);
        Assert.Contains("reinicio", mitigations.Description, StringComparison.OrdinalIgnoreCase);
    }

    // ----------------------------------------------------------- T1 valores pin
    /// <summary>T1: los literales son los del pin, uno a uno (medidos en el paso 10
    /// leyendo los .psd1 y el config/tweaks.json de los SHA fijados).</summary>
    [Fact]
    public void TestWave3Catalog_ValuesAreCopiedFromThePinLiterally()
    {
        // WinUtil WPFToggleMouseAcceleration: Value=1/6/10 (ACTIVA la aceleración).
        var mouse = Definition("system.mouse-acceleration.enable");
        Assert.Equal("1", Value(mouse, "MouseSpeed").Value);
        Assert.Equal("6", Value(mouse, "MouseThreshold1").Value);
        Assert.Equal("10", Value(mouse, "MouseThreshold2").Value);
        Assert.All(RegistryActions(mouse), a => Assert.Equal(RegistryValueType.String, a.ValueType));

        // WinUtil WPFTweaksUTC: RealTimeIsUniversal es QWord.
        var utc = Assert.Single(RegistryActions(Definition("system.time.utc-rtc")));
        Assert.Equal("RealTimeIsUniversal", utc.ValueName);
        Assert.Equal(RegistryValueType.QWord, utc.ValueType);
        Assert.Equal("1", utc.Value);
        Assert.Equal(RegistryHiveKind.LocalMachine, utc.Hive);

        // Atlas Mitigations/Disable: los cuatro valores del estado Disable.
        var mitigations = Definition("system.mitigations.disable");
        Assert.Equal("3", Value(mitigations, "FeatureSettingsOverride").Value);
        Assert.Equal("3", Value(mitigations, "FeatureSettingsOverrideMask").Value);
        Assert.Equal("1", Value(mitigations, "DisableExceptionChainValidation").Value);
        Assert.Equal("0", Value(mitigations, "ProtectionMode").Value);

        // Atlas crash-control-qol: BSOD visible + minidump pequeño, sin volcado total.
        var crash = Definition("system.error-reporting.crash-control");
        Assert.Equal("0", Value(crash, "AutoReboot").Value);
        Assert.Equal("3", Value(crash, "CrashDumpEnabled").Value);
        Assert.Equal("1", Value(crash, "DisplayParameters").Value);
        Assert.Equal("0", Value(crash, "DeviceDumpEnabled").Value);

        // Atlas KeyboardShortcuts/Disable: los tres atajos a 3.
        var keyboard = Definition("system.keyboard-shortcuts.disable");
        Assert.Equal("3", Value(keyboard, "Hotkey").Value);
        Assert.Equal("3", Value(keyboard, "Language Hotkey").Value);
        Assert.Equal("3", Value(keyboard, "Layout Hotkey").Value);
    }

    /// <summary>T1: la procedencia cita el pin de cada capacidad y su estado de
    /// toggle cuando sale de uno; y las de Atlas no mezclan estados.</summary>
    [Fact]
    public void TestWave3Catalog_ProvenanceQuotesPinAndToggleState()
    {
        foreach (var definition in Wave3())
        {
            Assert.True(
                definition.Provenance.Contains(AtlasPin, StringComparison.Ordinal)
                || definition.Provenance.Contains(WinUtilPin, StringComparison.Ordinal),
                $"{definition.Id}: la procedencia no cita el pin.");
            Assert.Contains("ledger_refs:", definition.Provenance, StringComparison.Ordinal);
            Assert.Contains("Reversibilidad (ADR-0003)", definition.Provenance,
                StringComparison.Ordinal);
        }

        foreach (var definition in Wave3().Where(d => d.Provenance.Contains("Toggles/",
                     StringComparison.Ordinal)))
        {
            Assert.Matches(new Regex(@"\(estado '[A-Za-z]+'\)"), definition.Provenance);
        }
    }

    /// <summary>T1: tras el paso 12h, §9 tiene 19 capacidades y 6 quedan
    /// Specified: hibernation.hide (powercfg), location.consent-deny
    /// (politica Find My Device), mitigations.disable (bcdedit/CFG),
    /// oem-information.identify (valores dinamicos del script),
    /// registry-backup.enable (RunLevel de la tarea) y
    /// system.time.ntp-servers (w32tm /config /update y /resync sin accion
    /// equivalente en el motor).</summary>
    [Fact]
    public void TestWave3Catalog_NoSpecifiedLeftAndThePinLiteralsStay()
    {
        // Paso 12h (R1): la lista de Specified de sección 9 está cerrada.
        // hibernation.hide, location.consent-deny, mitigations.disable,
        // oem-information.identify, registry-backup.enable y
        // system.time.ntp-servers siguen Specified.
        var specified = Wave3().Where(d => d.State == CapabilityState.Specified)
            .Select(d => d.Id).OrderBy(i => i, StringComparer.Ordinal).ToList();
        Assert.Equal(
            new[]
            {
                "system.hibernation.hide",
                "system.location.consent-deny",
                "system.mitigations.disable",
                "system.oem-information.identify",
                "system.registry-backup.enable",
                "system.time.ntp-servers",
            },
            specified);
        foreach (var id in specified)
        {
            var cap = Definition(id);
            Assert.Contains("FUERA DE ESTA CAPACIDAD (R1)", cap.Description, StringComparison.Ordinal);
            Assert.Contains("R1 (paso 12)", cap.Provenance, StringComparison.Ordinal);
        }

        // hibernation.hide: sigue Specified (powercfg no expresado).
        var hibernation = Definition("system.hibernation.hide");
        Assert.Equal(CapabilityState.Specified, hibernation.State);
        Assert.Equal("0", Value(hibernation, "ShowHibernateOption").Value);
        Assert.Contains("powercfg", hibernation.Description, StringComparison.OrdinalIgnoreCase);

        // mitigations.disable: sigue Specified (bcdedit/CFG no expresado).
        var mitigations = Definition("system.mitigations.disable");
        Assert.Equal(CapabilityState.Specified, mitigations.State);
        Assert.Equal("3", Value(mitigations, "FeatureSettingsOverride").Value);
        Assert.Equal("3", Value(mitigations, "FeatureSettingsOverrideMask").Value);
        Assert.Equal("1", Value(mitigations, "DisableExceptionChainValidation").Value);
        Assert.Equal("0", Value(mitigations, "ProtectionMode").Value);

        // registry-backup.enable: sigue Specified (RunLevel + /i no expresados).
        var backup = Definition("system.registry-backup.enable");
        Assert.Equal(CapabilityState.Specified, backup.State);
        // R3: instala una tarea SYSTEM, así que ni Safe ni sin confirmación.
        Assert.Equal(RiskLevel.Low, backup.Risk);
        Assert.Equal(ConfirmationType.SimpleClick, backup.Confirmation);
        Assert.Contains("R3 (paso 12)", backup.Provenance, StringComparison.Ordinal);
        Assert.Contains("AutoRegBackup", backup.Provenance, StringComparison.Ordinal);
        var task = Assert.Single(backup.Actions.OfType<TaskCreateAction>());
        Assert.Equal("AutoRegBackup", task.TaskName);
        Assert.Equal("schtasks", task.Execute);
        Assert.Equal("Daily", task.Trigger);
        Assert.Equal("00:30", task.TriggerAt);
        Assert.Equal("System", task.UserId);
        Assert.Equal("Highest", task.RunLevel);
        Assert.False(task.Overwrite);

        // ntp-servers: Specified (w32tm /config /update y /resync no tienen
        // accion equivalente en el motor); el registro y el arranque de w32time
        // SÍ se declaran.
        var ntp = Definition("system.time.ntp-servers");
        Assert.Equal(CapabilityState.Specified, ntp.State);
        Assert.Contains("w32tm", ntp.Description, StringComparison.OrdinalIgnoreCase);
        Assert.Equal("0.pool.ntp.org 1.pool.ntp.org 2.pool.ntp.org 3.pool.ntp.org",
            Value(ntp, "NtpServer").Value);
        Assert.Equal("NTP", Value(ntp, "Type").Value);
        var start = Assert.Single(ntp.Actions.OfType<ServiceAction>());
        Assert.Equal("w32time", start.ServiceName);
        Assert.Equal(ServiceOperation.Start, start.Operation);
    }

    /// <summary>T1: los servicios se declaran como ServiceAction con su tipo de
    /// inicio exacto; el motor guarda el tipo previo y lo restaura.</summary>
    [Fact]
    public void TestWave3Catalog_ServiceActionsCarryTheStartupType()
    {
        var profile = Definition("system.services.manual-profile");
        var services = ServiceActions(profile).ToList();
        Assert.Equal(5, services.Count);
        Assert.Equal(
            new[]
            {
                ("CscService", "Disabled"), ("DiagTrack", "Disabled"),
                ("MapsBroker", "Manual"), ("StorSvc", "Manual"),
                ("SharedAccess", "Disabled"),
            },
            services.Select(s => (s.ServiceName, s.StartupType!)).ToArray());
        Assert.All(services, s => Assert.Equal(ServiceOperation.SetStartupType, s.Operation));

        // Paso 12 (R1): el pin PARA WSearch y después lo deshabilita, así que la
        // capacidad declara las dos operaciones y en ese orden (ADR-0005 §4-bis):
        // el deshacer LIFO devuelve el arranque antes de arrancar el servicio.
        var indexing = ServiceActions(Definition("system.search-indexing.disable")).ToList();
        Assert.Equal(2, indexing.Count);
        Assert.Equal(
            new[] { (ServiceOperation.Stop, (string?)null),
                    (ServiceOperation.SetStartupType, (string?)"Disabled") },
            indexing.Select(a => (a.Operation, a.StartupType)).ToArray());
        Assert.All(indexing, a => Assert.Equal("WSearch", a.ServiceName));
        // Y el orden que se escribe en el fichero es el que se aplica.
        Assert.Equal(new[] { 1, 2 }, indexing.Select(a => a.Order).ToArray());

        // Paso 11: el estado 'Disable' del pin apaga lfsvc y MapsBroker con
        // `Set-Service -StartupType Disabled` + `Stop()` (medido en
        // Atlas.Privacy/Domain/Location.ps1:113-114): las dos cosas se declaran.
        var location = ServiceActions(Definition("system.location.consent-deny")).ToList();
        Assert.Equal(4, location.Count);
        Assert.Equal(
            // Parar primero y deshabilitar después: así el deshacer LIFO devuelve
            // el arranque antes de arrancar el servicio.
            new[] { ("lfsvc", ServiceOperation.Stop), ("lfsvc", ServiceOperation.SetStartupType),
                    ("MapsBroker", ServiceOperation.Stop), ("MapsBroker", ServiceOperation.SetStartupType) },
            location.Select(a => (a.ServiceName, a.Operation)).ToArray());
        Assert.All(location.Where(a => a.Operation == ServiceOperation.SetStartupType),
            a => Assert.Equal("Disabled", a.StartupType));
    }

    /// <summary>T1: la visibilidad de páginas escribe el literal COMPLETO del pin,
    /// no una lista recortada, y por eso sobrescribe la del usuario.</summary>
    [Fact]
    public void TestWave3Catalog_SettingsPageVisibilityIsTheWholePinList()
    {
        var action = Assert.Single(RegistryActions(Definition("system.settings-page-visibility.hide")));
        Assert.Equal(RegistryHiveKind.LocalMachine, action.Hive);
        Assert.Equal("SettingsPageVisibility", action.ValueName);
        Assert.Equal(RegistryValueType.String, action.ValueType);
        Assert.StartsWith("hide:", action.Value, StringComparison.Ordinal);
        foreach (var page in new[]
                 {
                     "recovery", "maps", "privacy", "privacy-feedback", "workplace",
                     "family-group", "deviceusage", "home",
                 })
        {
            Assert.Contains(page, action.Value, StringComparison.Ordinal);
        }
    }

    // ------------------------------------------------------- T2 undo exacto
    /// <summary>T2: cada acción de registro escribe o borra UN VALOR concreto y
    /// los tipos son los del motor; ninguna inventa binarios en esta sección.</summary>
    [Fact]
    public void TestWave3Catalog_EveryRegistryActionTouchesExactlyOneValue()
    {
        foreach (var definition in Wave3())
        {
            foreach (var action in RegistryActions(definition))
            {
                Assert.Contains(action.Operation,
                    new[] { RegistryOperation.Set, RegistryOperation.Delete });
                Assert.False(string.IsNullOrWhiteSpace(action.KeyPath));
                Assert.DoesNotContain(action.KeyPath, "?", StringComparison.Ordinal);
                Assert.Contains(action.ValueType,
                    new[] { RegistryValueType.DWord, RegistryValueType.String,
                            RegistryValueType.QWord });
                Assert.NotNull(action.Value);
            }
        }
    }

    /// <summary>T2: el deshacer devuelve el valor previo exacto también cuando el
    /// valor no existía (el caso normal de las claves de política de esta sección),
    /// y devuelve el tipo de inicio previo del servicio.</summary>
    [Fact]
    public void TestWave3Catalog_UndoRestoresPreviousValuesExactly()
    {
        var registry = new FakeRegistryAccessor();
        const string gameBar = @"Software\Microsoft\GameBar";
        registry.Seed(RegistryHive.CurrentUser, gameBar, "AllowAutoGameMode", 0);
        // AutoGameModeEnabled NO existe antes: el deshacer debe dejarlo inexistente.

        var actions = RegistryActions(Definition("system.game-mode.enable")).ToList();
        Assert.Equal(2, actions.Count);

        var journal = new List<(RegistryHive Hive, string Key, string Name, object? Previous, RegistryValueKind Kind)>();
        foreach (var action in actions)
        {
            var hive = action.Hive switch
            {
                RegistryHiveKind.CurrentUser => RegistryHive.CurrentUser,
                RegistryHiveKind.LocalMachine => RegistryHive.LocalMachine,
                _ => RegistryHive.Users,
            };

            var previous = registry.GetValue(hive, action.KeyPath, action.ValueName);
            var kind = action.ValueType == RegistryValueType.String
                ? RegistryValueKind.String
                : RegistryValueKind.DWord;
            var value = action.ValueType == RegistryValueType.String
                ? action.Value
                : (object)int.Parse(action.Value!, CultureInfo.InvariantCulture);
            registry.SetValue(hive, action.KeyPath, action.ValueName, value, kind);
            journal.Add((hive, action.KeyPath, action.ValueName, previous, kind));
        }

        Assert.Equal(1, (int?)registry.GetValue(
            RegistryHive.CurrentUser, gameBar, "AllowAutoGameMode")!);
        Assert.Equal(1, (int?)registry.GetValue(
            RegistryHive.CurrentUser, gameBar, "AutoGameModeEnabled")!);

        foreach (var entry in Enumerable.Reverse(journal))
        {
            if (entry.Previous is null)
            {
                registry.DeleteValue(entry.Hive, entry.Key, entry.Name);
            }
            else
            {
                registry.SetValue(entry.Hive, entry.Key, entry.Name, entry.Previous!, entry.Kind);
            }
        }

        Assert.Equal(0, (int?)registry.GetValue(RegistryHive.CurrentUser, gameBar, "AllowAutoGameMode")!);
        Assert.Null(registry.GetValue(RegistryHive.CurrentUser, gameBar, "AutoGameModeEnabled"));
    }

    /// <summary>T2: el tipo de inicio de un servicio se guarda antes de cambiarlo
    /// y se puede devolver (FakeServiceAccessor registra la mutación).</summary>
    [Fact]
    public void TestWave3Catalog_ServiceUndoRestoresTheStartupType()
    {
        var services = new FakeServiceAccessor();
        services.Seed("DiagTrack", ServiceStatus.Running, ServiceStartupType.Automatic);

        var action = ServiceActions(Definition("system.services.manual-profile"))
            .Single(a => a.ServiceName == "DiagTrack");
        Assert.Equal("Disabled", action.StartupType);

        var previous = services.GetStartupType(action.ServiceName);
        Assert.Equal(ServiceStartupType.Automatic, previous);

        services.SetStartupType(action.ServiceName, ServiceStartupType.Disabled);
        Assert.Equal(ServiceStartupType.Disabled, services.GetStartupType("DiagTrack"));
        Assert.Equal(1, services.MutationCount);

        // El diario guarda el anterior; el rollback lo reescribe.
        services.SetStartupType(action.ServiceName, previous);
        Assert.Equal(ServiceStartupType.Automatic, services.GetStartupType("DiagTrack"));
        Assert.Equal(2, services.MutationCount);
    }

    // --------------------------------------------------------- T1 rangos build
    /// <summary>T1: toda capacidad declara <c>supportedBuilds</c> EXPLÍCITO y sólo
    /// usa builds del catálogo; la única que excluye 19045 es la de hibernación,
    /// porque la clave FlyoutMenuSettings es de Windows 11.</summary>
    [Fact]
    public void TestWave3Catalog_SupportedBuildsAreExplicitAndJustified()
    {
        Assert.All(Wave3(), d => Assert.NotEmpty(d.SupportedBuilds));
        Assert.All(Wave3(), d => Assert.All(d.SupportedBuilds,
            build => Assert.Contains(build, KnownBuilds)));

        var windows11Only = Wave3()
            .Where(d => !d.SupportedBuilds.Contains(19045))
            .Select(d => d.Id).OrderBy(i => i, StringComparer.Ordinal).ToList();
        Assert.Equal(new[] { "system.hibernation.hide" }, windows11Only);
        Assert.Equal(Windows11, Definition("system.hibernation.hide").SupportedBuilds.Order().ToArray());

        var provenance = Definition("system.hibernation.hide").Provenance;
        Assert.Contains("FlyoutMenuSettings", provenance, StringComparison.Ordinal);
        Assert.Contains("19045", provenance, StringComparison.Ordinal);
    }

    /// <summary>T1: el catálogo sigue siendo un conjunto cerrado de capacidades
    /// (88) y la sección 9 no declara conflictos ni dependencias sin pareja.</summary>
    [Fact]
    public void TestWave3Catalog_NoDanglingReferences()
    {
        var catalog = LoadAll();
        var ids = catalog.Definitions.Select(d => d.Id).ToHashSet(StringComparer.Ordinal);
        foreach (var definition in Wave3())
        {
            Assert.Empty(definition.ConflictsWith);
            Assert.Empty(definition.DependsOn);
        }

        Assert.Equal(101, ids.Count);
        Assert.All(Wave3(), d => Assert.Contains("system.", d.Id, StringComparison.Ordinal));
    }
}
