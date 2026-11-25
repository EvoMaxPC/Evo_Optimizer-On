using Evo.Catalog;
using Evo.Catalog.Model;
using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Core.System;
using Evo.Engine;
using Evo.Engine.Execution;
using Evo.Testing;
using Microsoft.Win32;
using Xunit;

namespace Evo.Engine.Tests;

/// <summary>
/// Ejercita el motor con las capacidades REALES de la oleada 3 (sección 9) sobre
/// los fakes en memoria. Ningún test toca el sistema: todo pasa por
/// <see cref="FakeRegistryAccessor"/>, <see cref="FakeServiceAccessor"/> y sus
/// diarios.
/// </summary>
public sealed class Wave3EngineTests
{
    private const string GameBar = @"Software\Microsoft\GameBar";
    private const string Mouse = @"Control Panel\Mouse";
    private const string SessionManager = @"SYSTEM\CurrentControlSet\Control\Session Manager";
    private const string MemoryManagement = SessionManager + @"\Memory Management";
    private const string CrashControl = @"SYSTEM\CurrentControlSet\Control\CrashControl";
    private const string Power = @"SYSTEM\CurrentControlSet\Control\Power";
    private const string PoliciesExplorer =
        @"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer";
    private const string TimeZone = @"SYSTEM\CurrentControlSet\Control\TimeZoneInformation";

    private static IReadOnlyList<CapabilityDefinition> LoadAll()
    {
        var directory = Path.Combine(AppContext.BaseDirectory, "capabilities");
        Assert.True(Directory.Exists(directory), $"No existe el directorio de catálogo: {directory}");
        return new CatalogLoader().LoadDirectory(directory)
            .SelectMany(d => d.Capabilities)
            .Where(d => d.SectionId == 9)
            .ToList();
    }

    private static CapabilityDefinition Definition(string id) =>
        LoadAll().SingleOrDefault(d => d.Id == id)
        ?? throw new InvalidOperationException($"No está '{id}' en el catálogo de la sección 9.");

    private static CapabilityContract Contract(string id) => Definition(id).ToContract();

    private static ExecutionPlan Plan(string id)
    {
        var definition = Definition(id);
        return new ExecutionPlan(definition.ToContract(), definition.Actions
            .OrderBy(a => a.Order)
            .Select(a => new PlannedStep
            {
                Order = a.Order,
                Description = a.Description,
                Action = a,
            }));
    }

    private static TestHarness Harness(int build = 26100) =>
        TestHarness.Create(
            admin: true,
            build: build,
            catalog: LoadAll().Select(d => d.ToContract()).ToList());

    private static int MutationCount(TestHarness h) =>
        h.Registry.MutationCount + h.Services.MutationCount + h.Tasks.MutationCount;

    /// <summary>Compara los VALORES existentes de dos snapshots: el rollback deja
    /// atrás claves creadas vacías y una clave vacía no es un cambio de estado.</summary>
    private static void AssertSameValues(
        IReadOnlyDictionary<string, IReadOnlyDictionary<string, RegistryEntry>> expected,
        IReadOnlyDictionary<string, IReadOnlyDictionary<string, RegistryEntry>> actual)
    {
        static Dictionary<string, RegistryEntry> Flatten(
            IReadOnlyDictionary<string, IReadOnlyDictionary<string, RegistryEntry>> snapshot) =>
            snapshot
                .SelectMany(key => key.Value
                    .Where(value => value.Value.Exists)
                    .Select(value => new KeyValuePair<string, RegistryEntry>(
                        $"{key.Key}\\{value.Key}", value.Value)))
                .ToDictionary(pair => pair.Key, pair => pair.Value,
                    StringComparer.OrdinalIgnoreCase);

        var left = Flatten(expected);
        var right = Flatten(actual);
        Assert.Equal(left.Keys.OrderBy(k => k, StringComparer.Ordinal),
            right.Keys.OrderBy(k => k, StringComparer.Ordinal));
        foreach (var (key, entry) in left)
        {
            Assert.Equal(entry.Kind, right[key].Kind);
            Assert.Equal(entry.Value, right[key].Value);
        }
    }

    // -------------------------------------------------------------- T4.2 DryRun
    /// <summary>T4.2: en DryRun el plan se informa entero y los fakes no cambian,
    /// tampoco para las capacidades que mueven servicios.</summary>
    [Fact]
    public async Task TestWave3Catalog_DryRun_NoSystemMutation()
    {
        var ids = new[]
        {
            "system.game-mode.enable",
            "system.mitigations.disable",
            "system.services.manual-profile",
            "system.search-indexing.disable",
            "system.settings-page-visibility.hide",
            "system.time.ntp-servers",
        };

        foreach (var id in ids)
        {
            var harness = Harness();
            harness.Services.Seed("DiagTrack", ServiceStatus.Running, ServiceStartupType.Automatic);

            var snapshot = harness.Registry.Snapshot();
            var servicesBefore = harness.Services.Snapshot();
            var mutationsBefore = MutationCount(harness);

            var summary = await harness.Coordinator.ExecuteAsync(
                Plan(id), ExecutionMode.DryRun, harness.Context(ExecutionMode.DryRun));

            Assert.True(summary.Succeeded > 0, $"{id}: {summary.BlockedReason}");
            Assert.Equal(0, summary.Failed);
            Assert.False(summary.Mutated);
            Assert.Empty(summary.UndoJournalEntry);
            Assert.Equal(Definition(id).Actions.Count, summary.PlannedActions.Count);
            Assert.All(summary.Results, r => Assert.False(r.Applied));

            Assert.Equal(mutationsBefore, MutationCount(harness));
            AssertSameValues(snapshot, harness.Registry.Snapshot());
            Assert.Equal(
                ServiceStartupType.Automatic,
                harness.Services.GetStartupType("DiagTrack"));
            Assert.Equal(servicesBefore.Count, harness.Services.Snapshot().Count);
        }
    }

    // ------------------------------------------------- T4.3 Execute + deshacer
    /// <summary>T4.3: Execute escribe los valores del pin y el rollback del diario
    /// devuelve el registro exactamente al estado anterior, incluido el caso en que
    /// el valor no existía (AutoGameModeEnabled vuelve a no existir).</summary>
    [Fact]
    public async Task TestWave3Catalog_ExecuteAndRollback_RestoresState()
    {
        var harness = Harness();
        harness.Registry.Seed(RegistryHive.CurrentUser, GameBar, "AllowAutoGameMode", 0);
        harness.Registry.Seed(RegistryHive.CurrentUser, Mouse, "MouseSpeed", "0",
            RegistryValueKind.String);
        var before = harness.Registry.Snapshot();

        foreach (var id in new[]
                 {
                     "system.game-mode.enable",
                     "system.mouse-acceleration.enable",
                     "system.menu-delay.disable",
                 })
        {
            var summary = await harness.Coordinator.ExecuteAsync(
                Plan(id), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));
            Assert.Equal(0, summary.Failed);
            Assert.True(summary.Mutated);
            Assert.NotEmpty(summary.UndoJournalEntry);
        }

        // --- Mutó de verdad, con los valores del pin ---
        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, GameBar, "AllowAutoGameMode")!);
        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, GameBar, "AutoGameModeEnabled")!);
        Assert.Equal("1",
            (string?)harness.Registry.GetValue(RegistryHive.CurrentUser, Mouse, "MouseSpeed"));
        Assert.Equal("0",
            (string?)harness.Registry.GetValue(RegistryHive.CurrentUser, @"Control Panel\Desktop", "MenuShowDelay"));

        // --- Rollback ---
        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        Assert.Empty(rollback.Errors);

        Assert.Equal(0, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, GameBar, "AllowAutoGameMode")!);
        Assert.Null(harness.Registry.GetValue(
            RegistryHive.CurrentUser, GameBar, "AutoGameModeEnabled"));
        Assert.Equal("0",
            (string?)harness.Registry.GetValue(RegistryHive.CurrentUser, Mouse, "MouseSpeed"));
        AssertSameValues(before, harness.Registry.Snapshot());
    }

    /// <summary>T4.3b: el control de fallos (cinco acciones, todas en HKLM) se
    /// ejecuta entero, incluido el punto de restauración que exige Medium+ADR-0003,
    /// y se deshace entero.</summary>
    [Fact]
    public async Task TestWave3Catalog_LargestCapability_RoundTrips()
    {
        var definition = Definition("system.error-reporting.crash-control");
        Assert.Equal(5, definition.Actions.Count);
        Assert.Equal(RestoreLevel.RestorePoint, definition.Restore);
        Assert.True(EngineCoordinator.RequiresRestorePoint(Contract(definition.Id)));

        var harness = Harness();
        var before = harness.Registry.Snapshot();

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan(definition.Id), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));
        Assert.Equal(0, summary.Failed);
        Assert.Equal(5, summary.Succeeded);
        Assert.Equal(5, summary.Results.Count(r => r.Applied));
        Assert.Contains(harness.RestorePoints.Calls, c => c.StartsWith("create:", StringComparison.Ordinal));

        Assert.Equal(0, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, CrashControl, "AutoReboot")!);
        Assert.Equal(3, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, CrashControl, "CrashDumpEnabled")!);

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        AssertSameValues(before, harness.Registry.Snapshot());
    }

    // --------------------------------------------------------- T1 filtro previo
    /// <summary>T1: una capacidad Medium+Reversible con Restore=RestorePoint NO
    /// aplica si no hay punto de restauración disponible: el motor falla cerrado
    /// (fail-closed) y no toca el registro.</summary>
    [Fact]
    public async Task TestWave3Catalog_RestorePointIsRequiredBeforeTouchingHklm()
    {
        var harness = TestHarness.Create(
            admin: true,
            build: 26100,
            catalog: LoadAll().Select(d => d.ToContract()).ToList(),
            restorePointAvailable: false);
        var before = harness.Registry.Snapshot();
        var mutationsBefore = MutationCount(harness);

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("system.mitigations.disable"), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));

        // El motor falla CERRADO: aborta antes de la primera escritura.
        Assert.True(summary.Aborted, summary.AbortedReason);
        Assert.Contains("restauración", summary.AbortedReason, StringComparison.OrdinalIgnoreCase);
        Assert.False(summary.Mutated);
        Assert.Empty(summary.UndoJournalEntry);
        Assert.Equal(mutationsBefore, MutationCount(harness));
        AssertSameValues(before, harness.Registry.Snapshot());
    }

    /// <summary>T1: en una build no soportada el motor bloquea ANTES de tocar nada
    /// (el menú de energía de la clave FlyoutMenuSettings es de Windows 11).</summary>
    [Fact]
    public async Task TestWave3Catalog_UnsupportedBuildIsBlockedBeforeMutating()
    {
        var harness = Harness(build: 19045);
        var before = harness.Registry.Snapshot();
        var mutationsBefore = MutationCount(harness);

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("system.hibernation.hide"), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));

        Assert.True(summary.Blocked, "en 19045 el preflight debe rechazarla");
        Assert.Contains("19045", summary.BlockedReason, StringComparison.Ordinal);
        Assert.False(summary.Mutated);
        Assert.Equal(mutationsBefore, MutationCount(harness));
        AssertSameValues(before, harness.Registry.Snapshot());

        // Y en 26100 la misma capacidad sí se aplica.
        var supported = Harness(build: 26100);
        var applied = await supported.Coordinator.ExecuteAsync(
            Plan("system.hibernation.hide"), ExecutionMode.Execute,
            supported.Context(ExecutionMode.Execute));
        Assert.Equal(0, applied.Failed);
        Assert.True(applied.Mutated);
        Assert.Equal(0, (int?)supported.Registry.GetValue(
            RegistryHive.LocalMachine,
            @"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FlyoutMenuSettings",
            "ShowHibernateOption")!);
    }

    // ------------------------------------------------------- T1 privilegios HKLM
    /// <summary>T1: las capacidades que escriben HKLM o cambian servicios declaran
    /// Admin y, sin elevación, el motor las bloquea sin mutar nada.</summary>
    [Fact]
    public async Task TestWave3Catalog_AdminCapabilityRequiresElevation()
    {
        var profile = Definition("system.services.manual-profile");
        Assert.Equal(PrivilegeLevel.Admin, profile.Privilege);

        foreach (var id in new[] { "system.services.manual-profile", "system.search-indexing.disable" })
        {
            var harness = TestHarness.Create(
                admin: false,
                build: 26100,
                catalog: LoadAll().Select(d => d.ToContract()).ToList());
            harness.Services.Seed("DiagTrack", ServiceStatus.Running, ServiceStartupType.Automatic);
            var mutationsBefore = MutationCount(harness);

            var summary = await harness.Coordinator.ExecuteAsync(
                Plan(id), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));

            Assert.True(summary.Blocked, $"{id}: sin elevación debe bloquear");
            Assert.Contains("privilegio", summary.BlockedReason, StringComparison.OrdinalIgnoreCase);
            Assert.False(summary.Mutated);
            Assert.Empty(summary.UndoJournalEntry);
            Assert.Equal(mutationsBefore, MutationCount(harness));
            Assert.Equal(ServiceStartupType.Automatic, harness.Services.GetStartupType("DiagTrack"));
        }
    }

    // ------------------------------------------------------------- servicios
    /// <summary>T1/T2: los cinco servicios del perfil se aplican con su tipo exacto
    /// y el rollback devuelve el tipo previo de cada uno (DiagTrack sigue corriendo
    /// porque el motor sólo cambia el inicio, no para el servicio).</summary>
    [Fact]
    public async Task TestWave3Catalog_ServicesChangeStartupAndRollBack()
    {
        var harness = Harness();
        harness.Services.Seed("CscService", ServiceStatus.Running, ServiceStartupType.Manual);
        harness.Services.Seed("DiagTrack", ServiceStatus.Running, ServiceStartupType.Automatic);
        harness.Services.Seed("MapsBroker", ServiceStatus.Running, ServiceStartupType.Automatic);
        harness.Services.Seed("StorSvc", ServiceStatus.Running, ServiceStartupType.Automatic);
        harness.Services.Seed("SharedAccess", ServiceStatus.Stopped, ServiceStartupType.Automatic);

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("system.services.manual-profile"), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));
        Assert.Equal(0, summary.Failed);
        Assert.Equal(5, summary.Succeeded);

        Assert.Equal(ServiceStartupType.Disabled, harness.Services.GetStartupType("CscService"));
        Assert.Equal(ServiceStartupType.Disabled, harness.Services.GetStartupType("DiagTrack"));
        Assert.Equal(ServiceStartupType.Manual, harness.Services.GetStartupType("MapsBroker"));
        Assert.Equal(ServiceStartupType.Manual, harness.Services.GetStartupType("StorSvc"));
        Assert.Equal(ServiceStartupType.Disabled, harness.Services.GetStartupType("SharedAccess"));
        // Cambiar el inicio no para el servicio.
        Assert.Equal(ServiceStatus.Running, harness.Services.GetStatus("DiagTrack"));

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        Assert.Equal(ServiceStartupType.Manual, harness.Services.GetStartupType("CscService"));
        Assert.Equal(ServiceStartupType.Automatic, harness.Services.GetStartupType("DiagTrack"));
        Assert.Equal(ServiceStartupType.Automatic, harness.Services.GetStartupType("MapsBroker"));
        Assert.Equal(ServiceStartupType.Automatic, harness.Services.GetStartupType("StorSvc"));
        Assert.Equal(ServiceStartupType.Automatic, harness.Services.GetStartupType("SharedAccess"));
    }

    /// <summary>T1: la indización desactiva y PARA WSearch, que es lo que hace el pin
    /// (`Stop-Service -Name WSearch`), y el diario restaura las dos cosas.</summary>
    [Fact]
    public async Task TestWave3Catalog_SearchIndexingDisablesWSearch()
    {
        var harness = Harness();
        harness.Services.Seed("WSearch", ServiceStatus.Running, ServiceStartupType.Automatic);

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("system.search-indexing.disable"), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));
        Assert.Equal(0, summary.Failed);
        Assert.Equal(ServiceStartupType.Disabled, harness.Services.GetStartupType("WSearch"));
        // Paso 12 (R1): el pin PARA el servicio en su InvokeScript, así que la
        // capacidad declara también `Stop`; desactivar el arranque no lo detiene.
        Assert.Equal(ServiceStatus.Stopped, harness.Services.GetStatus("WSearch"));
        // Y las dos operaciones se aplican EN ESE ORDEN (parar y después
        // deshabilitar): el diario es LIFO y así el deshacer devuelve el arranque
        // antes de arrancar el servicio. Al revés el rollback da 1058.
        var applied = harness.Services.Log;
        var stopAt = applied.FindIndex(a => a.StartsWith("stop ", StringComparison.Ordinal));
        var typeAt = applied.FindIndex(a => a.StartsWith("startup ", StringComparison.Ordinal));
        Assert.True(stopAt >= 0 && typeAt >= 0, string.Join(", ", applied));
        Assert.True(stopAt < typeAt, string.Join(", ", applied));

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        Assert.Equal(ServiceStartupType.Automatic, harness.Services.GetStartupType("WSearch"));
        // El diario devuelve también el estado de ejecución previo.
        Assert.Equal(ServiceStatus.Running, harness.Services.GetStatus("WSearch"));
    }

    // ------------------------------------------------------- T1 valores del pin
    /// <summary>T1: los valores con tipo QWord y String se escriben con su tipo y
    /// el deshacer los devuelve con el mismo tipo.</summary>
    [Fact]
    public async Task TestWave3Catalog_TypedValuesAreWrittenAndRestored()
    {
        var harness = Harness();
        harness.Registry.Seed(RegistryHive.LocalMachine, TimeZone, "RealTimeIsUniversal",
            0L, RegistryValueKind.QWord);
        harness.Registry.Seed(RegistryHive.LocalMachine, SessionManager, "DisableWpbtExecution",
            0, RegistryValueKind.DWord);

        foreach (var id in new[] { "system.time.utc-rtc", "system.error-reporting.wpbt-disable" })
        {
            var summary = await harness.Coordinator.ExecuteAsync(
                Plan(id), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));
            Assert.Equal(0, summary.Failed);
        }

        Assert.Equal(1L, harness.Registry.GetValue(
            RegistryHive.LocalMachine, TimeZone, "RealTimeIsUniversal"));
        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, SessionManager, "DisableWpbtExecution")!);

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        Assert.Equal(0L, harness.Registry.GetValue(
            RegistryHive.LocalMachine, TimeZone, "RealTimeIsUniversal"));
        Assert.Equal(0, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, SessionManager, "DisableWpbtExecution")!);
    }

    /// <summary>T1: el reposo S3 (HKLM\…\Control\Power) y la visibilidad de
    /// páginas de Configuración (política del Explorador en HKLM) se aplican con
    /// sus valores exactos y se deshacen enteros.</summary>
    [Fact]
    public async Task TestWave3Catalog_PowerAndSettingsPolicyRoundTrip()
    {
        var harness = Harness();
        var before = harness.Registry.Snapshot();

        foreach (var id in new[] { "system.sleep.s3-enable", "system.settings-page-visibility.hide" })
        {
            var summary = await harness.Coordinator.ExecuteAsync(
                Plan(id), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));
            Assert.Equal(0, summary.Failed);
        }

        Assert.Equal(0, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, Power, "PlatformAoAcOverride")!);
        var visibility = (string?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, PoliciesExplorer, "SettingsPageVisibility");
        Assert.NotNull(visibility);
        Assert.StartsWith("hide:", visibility, StringComparison.Ordinal);
        Assert.Contains("workplace", visibility, StringComparison.Ordinal);

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        AssertSameValues(before, harness.Registry.Snapshot());
    }

    // ------------------------------------------------------------ T1 mitigaciones
    /// <summary>T1: la capacidad que más reduce la seguridad escribe los cuatro
    /// valores del estado Disable y exige confirmación reforzada; el motor la aplica
    /// con punto de restauración y la deshace sin dejar restos.</summary>
    [Fact]
    public async Task TestWave3Catalog_MitigationsWritesAllFourValues()
    {
        var harness = Harness();
        var before = harness.Registry.Snapshot();

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("system.mitigations.disable"), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));
        Assert.Equal(0, summary.Failed);
        Assert.Equal(4, summary.Succeeded);

        Assert.Equal(3, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, MemoryManagement, "FeatureSettingsOverride")!);
        Assert.Equal(3, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, MemoryManagement, "FeatureSettingsOverrideMask")!);
        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, SessionManager + @"\kernel",
            "DisableExceptionChainValidation")!);
        Assert.Equal(0, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, SessionManager, "ProtectionMode")!);

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        AssertSameValues(before, harness.Registry.Snapshot());
    }

    /// <summary>Paso 12: el orden de las DOS acciones de servicio de la capacidad
    /// de indización es el que el motor necesita para poder deshacer: parar y
    /// después deshabilitar. Con el orden inverso el rollback no puede arrancar
    /// el servicio (1058) y el plan entero se cae.</summary>
    [Fact]
    public async Task SearchIndexing_StopsBeforeDisablingSoUndoCanRestart()
    {
        var harness = Harness();
        harness.Services.Seed("WSearch", ServiceStatus.Running, ServiceStartupType.Automatic);

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("system.search-indexing.disable"), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));

        Assert.Equal(0, summary.Failed);
        var log = harness.Services.Log;
        Assert.Equal(new[] { "stop WSearch", "startup WSearch=Disabled" }, log.ToArray());

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));

        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        Assert.Equal(ServiceStartupType.Automatic, harness.Services.GetStartupType("WSearch"));
        Assert.Equal(ServiceStatus.Running, harness.Services.GetStatus("WSearch"));
    }
}
