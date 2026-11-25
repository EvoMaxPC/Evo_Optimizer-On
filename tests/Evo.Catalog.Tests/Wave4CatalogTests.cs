using Evo.Catalog;
using Evo.Catalog.Model;
using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Models;
using Xunit;

namespace Evo.Catalog.Tests;

/// <summary>
/// Paso 11 — el validador conoce las acciones nuevas (ADR-0005) y las
/// capacidades que se cerraron siguen cumpliendo ADR-0003.
/// </summary>
/// <remarks>
/// Los rechazos se comprueban contra <see cref="CatalogValidator"/> con
/// definiciones construidas en memoria: no se toca el catálogo real, y cada
/// campo obligatorio tiene su caso. La carga y la aceptación se comprueban
/// contra los ficheros reales de <c>catalog/capabilities/</c>.
/// </remarks>
public sealed class Wave4CatalogTests
{
    private static readonly int[] KnownBuilds = [19045, 22631, 26100, 26200];

    private static IReadOnlyList<CapabilityDefinition> LoadAll() =>
        new CatalogLoader()
            .LoadDirectory(Path.Combine(AppContext.BaseDirectory, "capabilities"))
            .SelectMany(d => d.Capabilities)
            .ToList();

    private static CapabilityDefinition Definition(string id) =>
        LoadAll().SingleOrDefault(d => d.Id == id)
        ?? throw new InvalidOperationException($"No está '{id}' en el catálogo.");

    // ------------------------------------------------------------- validador
    /// <summary>T4: el validador RECHAZA los borrados de clave mal declarados
    /// (sin ruta o con comodines) y ACEPTA el del catálogo real.</summary>
    [Fact]
    public void TestWave4Catalog_ValidatorRejectsMalformedKeyDeletions()
    {
        var withoutPath = Validate(Single(DeleteKey(keyPath: " ")));
        Assert.Contains(withoutPath.Errors, e => e.Message.Contains("sin 'keyPath'", StringComparison.Ordinal));

        var wildcard = Validate(Single(DeleteKey(keyPath: @"SOFTWARE\Evo\*")));
        Assert.Contains(wildcard.Errors, e => e.Message.Contains("comodín", StringComparison.Ordinal));

        var ok = Validate(Single(DeleteKey(keyPath: @"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Desktop\NameSpace\{f874310e-b6b7-47dc-bc84-b9e6b38f5903}")));
        Assert.True(ok.IsValid, ok.ErrorSummary);

        // Y el del catálogo real pasa el validador.
        var real = Definition("explorer.home.hide").Actions.OfType<RegistryDeleteKeyAction>().Single();
        Assert.False(real.Recursive);
        Assert.StartsWith(@"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Desktop\NameSpace",
            real.KeyPath, StringComparison.Ordinal);
        Assert.True(new CatalogValidator(KnownBuilds).Validate(CatalogOf(Definition("explorer.home.hide"))).IsValid);
    }

    /// <summary>T4: el validador RECHAZA las tareas incompletas o con
    /// desencadenantes/horas/niveles que el motor no sabe aplicar.</summary>
    [Theory]
    [InlineData("execute")]
    [InlineData("taskName")]
    [InlineData("userId")]
    [InlineData("runLevel")]
    [InlineData("trigger")]
    public void TestWave4Catalog_ValidatorRejectsIncompleteTasks(string field)
    {
        var action = NewTask();
        action = field switch
        {
            "execute" => action with { Execute = " " },
            "taskName" => action with { TaskName = "" },
            "userId" => action with { UserId = " " },
            "runLevel" => action with { RunLevel = "" },
            _ => action with { Trigger = "" },
        };

        var report = Validate(Single(action));
        Assert.False(report.IsValid);
        Assert.Contains(report.Errors, e => e.Rule == "R-ACTION");
    }

    /// <summary>T4: desencadenante desconocido, Daily sin hora, hora mal formada
    /// y nivel de ejecución inventado se rechazan con su mensaje propio.</summary>
    [Fact]
    public void TestWave4Catalog_ValidatorRejectsBadTriggersAndTimes()
    {
        var cases = new (TaskCreateAction Action, string Fragment)[]
        {
            (NewTask() with { Trigger = "Weekly" }, "sólo Daily y OnLogon"),
            (NewTask() with { TriggerAt = null }, "sin 'triggerAt'"),
            (NewTask() with { TriggerAt = "25:00" }, "'triggerAt' inválido"),
            (NewTask() with { TriggerAt = "00-30" }, "'triggerAt' inválido"),
            (NewTask() with { RunLevel = "System" }, "'runLevel'"),
        };

        foreach (var (action, fragment) in cases)
        {
            var report = Validate(Single(action));
            Assert.False(report.IsValid);
            Assert.Contains(report.Errors, e => e.Message.Contains(fragment, StringComparison.Ordinal));
        }

        // Las dos formas legítimas (Daily con hora y OnLogon sin hora) pasan.
        Assert.True(Validate(Single(NewTask())).IsValid);
        var logon = NewTask() with { Trigger = "OnLogon", TriggerAt = null, RunLevel = "Limited" };
        Assert.True(Validate(Single(logon)).IsValid);
    }

    /// <summary>T1: un servicio declara UNA cosa. Cambiar el arranque exige
    /// 'startupType'; arrancar o parar no lo admite (serían dos efectos con un
    /// solo deshacer).</summary>
    [Fact]
    public void TestWave4Catalog_ValidatorKeepsServiceOperationsSeparate()
    {
        var withoutStartup = Validate(Single(new ServiceAction
        {
            Order = 1,
            Description = "lfsvc",
            ServiceName = "lfsvc",
            Operation = ServiceOperation.SetStartupType,
        }));
        Assert.False(withoutStartup.IsValid);
        Assert.Contains(withoutStartup.Errors, e => e.Message.Contains("sin 'startupType'", StringComparison.Ordinal));

        var startWithStartup = Validate(Single(new ServiceAction
        {
            Order = 1,
            Description = "w32time",
            ServiceName = "w32time",
            Operation = ServiceOperation.Start,
            StartupType = "Automatic",
        }));
        Assert.False(startWithStartup.IsValid);
        Assert.Contains(startWithStartup.Errors, e => e.Message.Contains("no cambia el tipo de inicio", StringComparison.Ordinal));

        var ok = Validate(Single(new ServiceAction
        {
            Order = 1,
            Description = "w32time",
            ServiceName = "w32time",
            Operation = ServiceOperation.Start,
        }));
        Assert.True(ok.IsValid, ok.ErrorSummary);
    }

    // ----------------------------------------------------- capacidades cerradas
    /// <summary>T2: `system.registry-backup.enable` declara registro + tarea y
    /// sigue cumpliendo ADR-0003. Paso 12 (R1/R3): el pin ejecuta el script con
    /// `-RunLevel Highest` y el motor no expresa el nivel de la tarea, así que la
    /// capacidad vuelve a Specified y sube de Safe a Low con SimpleClick.</summary>
    [Fact]
    public void TestWave4Catalog_RegistryBackupDeclaresItsTaskAndStaysSpecified()
    {
        var definition = Definition("system.registry-backup.enable");

        Assert.Equal(CapabilityState.Specified, definition.State);
        Assert.Contains("FUERA DE ESTA CAPACIDAD (R1)", definition.Description, StringComparison.Ordinal);
        Assert.Equal(Reversibility.Reversible, definition.Reversibility);
        Assert.Equal(RestoreLevel.SessionUndo, definition.Restore);
        Assert.Empty(CapabilityRules.Validate(definition.ToContract()));

        // R3: instala una tarea como SYSTEM; nunca Safe ni sin confirmación.
        Assert.NotEqual(RiskLevel.Safe, definition.Risk);
        Assert.NotEqual(ConfirmationType.None, definition.Confirmation);

        // 2 valores + 1 tarea, en ese orden y con órdenes consecutivas.
        Assert.Equal(new[] { 1, 2, 3 }, definition.Actions.Select(a => a.Order).ToArray());
        Assert.Equal(2, definition.Actions.OfType<RegistryAction>().Count());
        var task = Assert.Single(definition.Actions.OfType<TaskCreateAction>());
        Assert.Equal(@"\", task.TaskPath);
        Assert.Equal("AutoRegBackup", task.TaskName);
        Assert.Equal("System", task.UserId);
        Assert.Equal("Highest", task.RunLevel);
        Assert.Contains("RegIdleBackup", task.Arguments, StringComparison.Ordinal);
        Assert.Equal(PrivilegeLevel.Admin, definition.Privilege);
    }

    /// <summary>T2: `system.time.ntp-servers` arranca w32time y declara en la
    /// descripción lo que sigue sin declararse (w32tm), sin llamarse Specified.</summary>
    [Fact]
    public void TestWave4Catalog_TimeServersStartTheServiceAndSayWhatIsLeftOut()
    {
        var definition = Definition("system.time.ntp-servers");

        Assert.Equal(CapabilityState.Implemented, definition.State);
        var start = Assert.Single(definition.Actions.OfType<ServiceAction>());
        Assert.Equal("w32time", start.ServiceName);
        Assert.Equal(ServiceOperation.Start, start.Operation);
        Assert.Null(start.StartupType);

        // Lo que NO se declara sigue escrito (REQ-002: no se calla un hueco).
        Assert.Contains("w32tm /config /update", definition.Description, StringComparison.Ordinal);
        Assert.Contains("w32tm /resync", definition.Description, StringComparison.Ordinal);
        Assert.Contains("sin inversa", definition.Provenance, StringComparison.Ordinal);
        Assert.Empty(CapabilityRules.Validate(definition.ToContract()));
    }

    /// <summary>T0-d/T2: la ubicación declara el tipo de inicio y la parada de
    /// lfsvc y MapsBroker (ambas expresables), y su privilegio sigue en Admin.</summary>
    [Fact]
    public void TestWave4Catalog_LocationDeclaresStartupTypeAndStop()
    {
        var definition = Definition("system.location.consent-deny");
        var services = definition.Actions.OfType<ServiceAction>().ToList();

        Assert.Equal(4, services.Count);
        Assert.Equal(new[] { "lfsvc", "lfsvc", "MapsBroker", "MapsBroker" },
            services.Select(s => s.ServiceName).ToArray());
        // Orden elegido por el deshacer LIFO: tipo de inicio después de la parada.
        Assert.Equal(
            new[]
            {
                ServiceOperation.Stop, ServiceOperation.SetStartupType,
                ServiceOperation.Stop, ServiceOperation.SetStartupType,
            },
            services.Select(s => s.Operation).ToArray());
        Assert.All(
            services.Where(s => s.Operation == ServiceOperation.SetStartupType),
            s => Assert.Equal("Disabled", s.StartupType));
        Assert.Equal(PrivilegeLevel.Admin, definition.Privilege);
        Assert.Equal(Reversibility.Reversible, definition.Reversibility);
        Assert.Equal(RestoreLevel.SessionUndo, definition.Restore);
        Assert.Empty(CapabilityRules.Validate(definition.ToContract()));
        // La procedencia cita la línea medida del pin, no una impresión.
        Assert.Contains("Atlas.Privacy/Domain/Location.ps1:113", definition.Provenance,
            StringComparison.Ordinal);
    }

    /// <summary>T1/T2: el JSON de las acciones nuevas se deserializa con el
    /// discriminador exacto que espera el motor, y sólo con esos campos.</summary>
    [Fact]
    public void TestWave4Catalog_NewActionTypesRoundTripThroughTheLoader()
    {
        const string json = """
        {
          "metadata": { "version": "1.0.0", "schemaVersion": 1, "provenance": "test", "generatedBy": "test" },
          "capabilities": [
            {
              "id": "test.wave4.roundtrip",
              "name": "Prueba",
              "description": "prueba",
              "sectionId": 9,
              "risk": "Safe",
              "securityImpact": "Neutral",
              "privilege": "Admin",
              "restore": "SessionUndo",
              "reversibility": "Reversible",
              "confirmation": "None",
              "state": "Implemented",
              "variants": ["Evo"],
              "supportedBuilds": [19045],
              "actions": [
                { "type": "registryDeleteKey", "order": 1, "description": "borrar", "hive": "LocalMachine", "keyPath": "SOFTWARE\\Evo\\X", "recursive": false },
                { "type": "taskCreate", "order": 2, "description": "crear", "taskPath": "\\", "taskName": "T", "execute": "schtasks", "arguments": "/run", "trigger": "Daily", "triggerAt": "00:30", "userId": "System", "runLevel": "Highest", "overwrite": true }
              ]
            }
          ]
        }
        """;

        var document = new CatalogLoader().LoadFromText(json);
        var actions = document.Capabilities.Single().Actions;

        var deleteKey = Assert.IsType<RegistryDeleteKeyAction>(actions[0]);
        Assert.Equal(ActionKind.RegistryDeleteKey, deleteKey.Kind);
        Assert.Equal(RegistryHiveKind.LocalMachine, deleteKey.Hive);
        Assert.False(deleteKey.Recursive);

        var task = Assert.IsType<TaskCreateAction>(actions[1]);
        Assert.Equal(ActionKind.TaskCreate, task.Kind);
        Assert.True(task.Overwrite);
        Assert.Equal("00:30", task.TriggerAt);

        // El cargador ignora propiedades desconocidas (política documentada en
        // CatalogLoader): una acción nueva no puede colarse como si existiera.
        var unknown = json.Replace("\"recursive\": false", "\"recursive\": false, \"line\": 42",
            StringComparison.Ordinal);
        var again = new CatalogLoader().LoadFromText(unknown);
        Assert.IsType<RegistryDeleteKeyAction>(again.Capabilities.Single().Actions[0]);
    }

    /// <summary>
    /// Barrido de TODO el catálogo (88). Existe porque cada oleada enumera sólo
    /// sus ids: si una capacidad se colara fuera de las listas (o una oleada
    /// dejara de enumerar la suya), ningún test se enteraría. Aquí se exige que
    /// las 88 cumplan lo mismo, sin listas de ids de por medio.
    /// </summary>
    [Fact]
    public void TestWave4Catalog_EveryCapabilityInTheCatalogMeetsTheSameInvariants()
    {
        var all = LoadAll();
        Assert.Equal(88, all.Count);

        // Las cinco secciones cerradas, ni una capacidad fuera de ellas.
        var sections = all.Select(d => d.SectionId).Distinct().OrderBy(s => s).ToArray();
        Assert.Equal(new[] { 1, 2, 3, 9, 10 }, sections);

        var report = new CatalogValidator(KnownBuilds).Validate(
            new CapabilityCatalog(new CatalogMetadata { Version = "1.0.0", SchemaVersion = 1 }, all));
        Assert.True(report.IsValid, report.ErrorSummary);

        foreach (var definition in all)
        {
            Assert.Contains(definition.State,
                new[] { CapabilityState.Implemented, CapabilityState.Specified });
            Assert.NotEmpty(definition.Actions);
            Assert.NotNull(definition.Reversibility);
            Assert.False(string.IsNullOrWhiteSpace(definition.Provenance));
            Assert.Empty(CapabilityRules.Validate(definition.ToContract()));
            Assert.Equal(
                Enumerable.Range(1, definition.Actions.Count),
                definition.Actions.Select(a => a.Order).OrderBy(o => o));
        }
    }

    // ------------------------------------------------------------ CreateKey
    /// <summary>T5: el validador RECHAZA las creaciones de clave mal declaradas
    /// (sin ruta o con comodines) y ACEPTA la del catálogo real.</summary>
    [Fact]
    public void TestWave4Catalog_ValidatorRejectsMalformedKeyCreations()
    {
        var withoutPath = Validate(Single(CreateKey(keyPath: " ")));
        Assert.Contains(withoutPath.Errors, e => e.Message.Contains("sin 'keyPath'", StringComparison.Ordinal));

        var wildcard = Validate(Single(CreateKey(keyPath: @"SOFTWARE\Evo\*")));
        Assert.Contains(wildcard.Errors, e => e.Message.Contains("comodín", StringComparison.Ordinal));

        var ok = Validate(Single(CreateKey(keyPath: @"SYSTEM\CurrentControlSet\Control\Network\NewNetworkWindowOff")));
        Assert.True(ok.IsValid, ok.ErrorSummary);

        // Y el del catálogo real pasa el validador, con la ruta del pin.
        var real = Assert.Single(Definition("system.network.location-wizard.disable")
            .Actions.OfType<RegistryCreateKeyAction>());
        Assert.Equal(@"SYSTEM\CurrentControlSet\Control\Network\NewNetworkWindowOff",
            real.KeyPath);
        Assert.Equal(RegistryHiveKind.LocalMachine, real.Hive);
        Assert.True(new CatalogValidator(KnownBuilds).Validate(
            CatalogOf(Definition("system.network.location-wizard.disable"))).IsValid);
    }

    /// <summary>T5: el cargador acepta el discriminante <c>registryCreateKey</c> y
    /// lo materializa como <see cref="RegistryCreateKeyAction"/>.</summary>
    [Fact]
    public void TestWave4Catalog_LoaderReadsKeyCreationActions()
    {
        const string json = """
        {
          "metadata": { "version": "1.0.0", "schemaVersion": 1 },
          "capabilities": [
            {
              "id": "test.wave4.createkey",
              "name": "Prueba",
              "description": "prueba",
              "sectionId": 9,
              "risk": "Safe",
              "securityImpact": "Neutral",
              "privilege": "Admin",
              "restore": "SessionUndo",
              "reversibility": "Reversible",
              "confirmation": "None",
              "state": "Implemented",
              "variants": ["Evo"],
              "supportedBuilds": [19045],
              "actions": [
                { "type": "registryCreateKey", "order": 1, "description": "crear", "hive": "LocalMachine", "keyPath": "SOFTWARE\\Evo\\Y" }
              ]
            }
          ]
        }
        """;

        var document = new CatalogLoader().LoadFromText(json);
        var action = Assert.IsType<RegistryCreateKeyAction>(
            document.Capabilities.Single().Actions.Single());
        Assert.Equal(ActionKind.RegistryCreateKey, action.Kind);
        Assert.Equal(RegistryHiveKind.LocalMachine, action.Hive);
        Assert.Equal(@"SOFTWARE\Evo\Y", action.KeyPath);
    }

    // ---------------------------------------------------------------- ayuda
    private static RegistryCreateKeyAction CreateKey(string keyPath) => new()
    {
        Order = 1,
        Description = "crear",
        Hive = RegistryHiveKind.LocalMachine,
        KeyPath = keyPath,
    };

    private static IReadOnlyList<CapabilityDefinition> Single(CapabilityAction action) =>
    [
        new CapabilityDefinition
        {
            Id = "test.wave4.capability",
            Name = "Prueba",
            Description = "prueba",
            SectionId = 9,
            Risk = RiskLevel.Safe,
            SecurityImpact = SecurityImpact.Neutral,
            Privilege = PrivilegeLevel.Admin,
            Restore = RestoreLevel.SessionUndo,
            Reversibility = Reversibility.Reversible,
            Confirmation = ConfirmationType.None,
            State = CapabilityState.Implemented,
            Variants = [Variant.Evo],
            SupportedBuilds = [19045],
            Actions = [action],
        },
    ];

    private static CapabilityCatalog CatalogOf(IEnumerable<CapabilityDefinition> definitions) =>
        new(new CatalogMetadata { Version = "1.0.0", SchemaVersion = 1 }, definitions);

    private static CapabilityCatalog CatalogOf(CapabilityDefinition definition) =>
        CatalogOf([definition]);

    private static ValidationReport Validate(IReadOnlyList<CapabilityDefinition> definitions) =>
        new CatalogValidator(KnownBuilds).Validate(CatalogOf(definitions));

    private static RegistryDeleteKeyAction DeleteKey(string keyPath) => new()
    {
        Order = 1,
        Description = "borrar",
        Hive = RegistryHiveKind.LocalMachine,
        KeyPath = keyPath,
    };

    private static TaskCreateAction NewTask() => new()
    {
        Order = 1,
        Description = "crear",
        TaskPath = @"\",
        TaskName = "AutoRegBackup",
        Execute = "schtasks",
        Arguments = "/run /i /tn \"\\Microsoft\\Windows\\Registry\\RegIdleBackup\"",
        Trigger = "Daily",
        TriggerAt = "00:30",
        UserId = "System",
        RunLevel = "Highest",
    };
}
