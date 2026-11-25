using Evo.Catalog;
using Evo.Catalog.Model;
using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.System;
using Evo.Engine.Execution;
using Evo.Engine.Executors;
using Evo.Engine.Undo;
using Evo.Testing;
using Microsoft.Win32;
using Xunit;

namespace Evo.Engine.Tests;

/// <summary>
/// Paso 11 — expresividad del motor (ADR-0005): borrado de clave completa,
/// creación de tareas y arranque/parada de servicios con deshacer exacto.
/// </summary>
/// <remarks>
/// Todo se ejecuta contra los fakes: ningún test toca el sistema. Los límites
/// del snapshot y los fallos a mitad se provocan a propósito para comprobar que
/// el motor falla CERRADO (no borra, no deja a medias y revierte lo aplicado).
/// </remarks>
public sealed class Wave4EngineTests
{
    private const string KeyPath = @"SOFTWARE\Evo\Wave4";

    /// <summary>Rama del subárbol SIN valores: el deshacer también la recrea.</summary>
    private const string EmptyKey = @"HKLM\SOFTWARE\Evo\Wave4\Child\Empty";

    // ------------------------------------------------------------ DeleteKey
    /// <summary>T1: la clave se borra y el deshacer la recrea con sus valores,
    /// sus tipos y sus subclaves, recursivamente.</summary>
    [Fact]
    public async Task DeleteKey_RestoresTheWholeSubtreeWithTypesAndData()
    {
        var harness = TestHarness.Create();
        SeedTree(harness);
        var before = harness.Registry.Snapshot();
        var journal = new UndoJournal();

        var result = await new RegistryDeleteKeyExecutor().ExecuteAsync(
            DeleteKeyAction(recursive: true), ContextFor(harness, journal));

        Assert.True(result.Success, result.ErrorMessage);
        Assert.True(result.Applied);
        Assert.False(harness.Registry.KeyExists(RegistryHive.LocalMachine, KeyPath));
        Assert.False(harness.Registry.KeyExists(
            RegistryHive.LocalMachine, KeyPath + @"\Child"));
        Assert.Single(journal.Entries);

        var entry = Assert.IsType<RegistryDeleteKeyUndoEntry>(journal.Entries[0]);
        Assert.True(entry.ExistedBefore);
        // 4 claves (Wave4, Child, Grand y Empty) y 5 valores con sus 4 tipos.
        Assert.Equal("4 claves / 5 valores", entry.PreviousState);

        await journal.RollbackAsync(UndoContextFor(harness));

        AssertSameRegistry(before, harness.Registry.Snapshot());
        Assert.Equal("texto", harness.Registry.GetValue(
            RegistryHive.LocalMachine, KeyPath, "Str"));
        Assert.Equal(RegistryValueKind.ExpandString, harness.Registry.GetKind(
            RegistryHive.LocalMachine, KeyPath, "Expand"));
        Assert.Equal(7L, harness.Registry.GetValue(
            RegistryHive.LocalMachine, KeyPath + @"\Child\Grand", "Q"));
        // La rama sin valores también vuelve a existir.
        Assert.True(harness.Registry.KeyExists(
            RegistryHive.LocalMachine, KeyPath + @"\Child\Empty"));
    }

    /// <summary>T1: si la clave no existe, es un no-op registrado y el deshacer
    /// no crea nada.</summary>
    [Fact]
    public async Task DeleteKey_MissingKeyIsANoOpAndUndoCreatesNothing()
    {
        var harness = TestHarness.Create();
        var journal = new UndoJournal();

        var result = await new RegistryDeleteKeyExecutor().ExecuteAsync(
            DeleteKeyAction(recursive: false), ContextFor(harness, journal));

        Assert.True(result.Success);
        Assert.False(result.Applied);
        Assert.Equal("absent", result.PreviousState);
        Assert.Empty(journal.Entries);
        Assert.Equal(0, harness.Registry.MutationCount);
        Assert.False(harness.Registry.KeyExists(RegistryHive.LocalMachine, KeyPath));
    }

    /// <summary>T1: DryRun informa de lo que borraría y no muta nada.</summary>
    [Fact]
    public async Task DeleteKey_DryRunSaysWhatItWouldDelete()
    {
        var harness = TestHarness.Create();
        SeedTree(harness);
        var mutationsBefore = harness.Registry.MutationCount;
        var journal = new UndoJournal();

        var result = await new RegistryDeleteKeyExecutor().ExecuteAsync(
            DeleteKeyAction(recursive: true),
            ContextFor(harness, journal, ExecutionMode.DryRun));

        Assert.True(result.Success);
        Assert.False(result.Applied);
        Assert.StartsWith("would-delete:", result.NewState, StringComparison.Ordinal);
        Assert.Contains("recursive=true", result.NewState, StringComparison.Ordinal);
        Assert.Empty(journal.Entries);
        Assert.Equal(mutationsBefore, harness.Registry.MutationCount);
        Assert.True(harness.Registry.KeyExists(RegistryHive.LocalMachine, KeyPath));
    }

    /// <summary>T1 fail-closed: si el accesor no sabe enumerar el árbol, el motor
    /// NO borra (no promete un deshacer que no sabe hacer).</summary>
    [Fact]
    public async Task DeleteKey_AccessorWithoutTreeReaderAbortsWithoutDeleting()
    {
        var harness = TestHarness.Create();
        SeedTree(harness);
        var blind = new TreeBlindRegistry(harness.Registry);

        var result = await new RegistryDeleteKeyExecutor().ExecuteAsync(
            DeleteKeyAction(recursive: true),
            ContextFor(harness, new UndoJournal(), registry: blind));

        Assert.False(result.Success);
        Assert.Contains("no sabe enumerar el árbol", result.ErrorMessage, StringComparison.Ordinal);
        Assert.True(harness.Registry.KeyExists(RegistryHive.LocalMachine, KeyPath));
        Assert.Equal(0, blind.DeleteKeyCalls);
    }

    /// <summary>T1 fail-closed: si la instantánea lanza, el motor aborta sin borrar.</summary>
    [Fact]
    public async Task DeleteKey_FailingSnapshotAbortsWithoutDeleting()
    {
        var harness = TestHarness.Create();
        var failing = new FailingTreeReader(harness.Registry);
        // La clave existe (si no, la acción sería un no-op y no se llegaría a la
        // instantánea): se siembra a través del accesor que envuelve al fake.
        failing.SetValue(RegistryHive.LocalMachine, KeyPath, "Str", "texto",
            RegistryValueKind.String);

        var result = await new RegistryDeleteKeyExecutor().ExecuteAsync(
            DeleteKeyAction(recursive: true),
            ContextFor(harness, new UndoJournal(), registry: failing));

        Assert.False(result.Success);
        Assert.Contains("No se pudo tomar la instantánea", result.ErrorMessage, StringComparison.Ordinal);
        Assert.True(harness.Registry.KeyExists(RegistryHive.LocalMachine, KeyPath));
        Assert.Equal(0, failing.DeleteKeyCalls);
    }

    /// <summary>T1 fail-closed: si la instantánea supera el límite documentado
    /// (valores/profundidad), el motor aborta sin borrar.</summary>
    [Fact]
    public async Task DeleteKey_SnapshotOverTheLimitAbortsWithoutDeleting()
    {
        var harness = TestHarness.Create();
        SeedTree(harness);
        var limits = new RegistrySnapshotLimits { MaxDepth = 16, MaxValues = 2, MaxKeys = 1024 };

        var result = await new RegistryDeleteKeyExecutor(limits).ExecuteAsync(
            DeleteKeyAction(recursive: true), ContextFor(harness, new UndoJournal()));

        Assert.False(result.Success);
        Assert.Contains("supera el límite", result.ErrorMessage, StringComparison.Ordinal);
        Assert.True(harness.Registry.KeyExists(RegistryHive.LocalMachine, KeyPath));
    }

    /// <summary>T1: en Execute el borrado NO se hace sin instantánea, y con ella
    /// el diario queda con UNA entrada; el coordinador la expone al llamante.</summary>
    [Fact]
    public async Task DeleteKey_ThroughTheCoordinator_RollsBackCompletely()
    {
        var harness = TestHarness.Create();
        SeedTree(harness);
        var before = harness.Registry.Snapshot();

        var action = DeleteKeyAction(recursive: true, order: 1);
        var contract = TestHarness.Contract([action], risk: RiskLevel.Safe,
            restore: RestoreLevel.SessionUndo);
        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, [action]), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));

        Assert.Equal(0, summary.Failed);
        Assert.Single(summary.UndoJournalEntry);
        Assert.False(harness.Registry.KeyExists(RegistryHive.LocalMachine, KeyPath));

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        AssertSameRegistry(before, harness.Registry.Snapshot());
    }

    // -------------------------------------------------------------- tareas
    /// <summary>T1: crear una tarea y deshacer = borrarla (no queda rastro).</summary>
    [Fact]
    public async Task TaskCreate_CreatesAndUndoDeletes()
    {
        var harness = TestHarness.Create();
        var journal = new UndoJournal();

        var result = await new TaskCreateExecutor().ExecuteAsync(
            CreateTask("AutoRegBackup"), ContextFor(harness, journal));

        Assert.True(result.Success, result.ErrorMessage);
        Assert.Equal("absent", result.PreviousState);
        Assert.True(harness.Tasks.Exists(@"\", "AutoRegBackup"));
        Assert.True(harness.Tasks.IsTaskEnabled(@"\", "AutoRegBackup"));
        var created = Assert.Single(harness.Tasks.Created);
        Assert.Equal("schtasks", created.Execute);
        Assert.Equal("Daily", created.Trigger);
        Assert.Equal("00:30", created.TriggerAt);
        Assert.Equal("Highest", created.RunLevel);

        await journal.RollbackAsync(UndoContextFor(harness));

        Assert.False(harness.Tasks.Exists(@"\", "AutoRegBackup"));
        Assert.Empty(harness.Tasks.Snapshot());
    }

    /// <summary>T1: si la tarea ya existía y la acción no admite sobrescribir,
    /// falla sin tocar nada (no se pisa una tarea ajena en silencio).</summary>
    [Fact]
    public async Task TaskCreate_ExistingTaskWithoutOverwriteFailsUntouched()
    {
        var harness = TestHarness.Create();
        harness.Tasks.Seed(@"\", "AutoRegBackup", enabled: false);
        var mutationsBefore = harness.Tasks.MutationCount;

        var result = await new TaskCreateExecutor().ExecuteAsync(
            CreateTask("AutoRegBackup"), ContextFor(harness, new UndoJournal()));

        Assert.False(result.Success);
        Assert.Contains("ya existe", result.ErrorMessage, StringComparison.Ordinal);
        Assert.False(harness.Tasks.IsTaskEnabled(@"\", "AutoRegBackup"));
        Assert.Equal(mutationsBefore, harness.Tasks.MutationCount);
        Assert.Empty(harness.Tasks.Created);
    }

    /// <summary>T1: con <c>overwrite</c> el estado previo se captura y se
    /// restaura: la tarea vuelve a como estaba, no se borra.</summary>
    [Fact]
    public async Task TaskCreate_ExistingTaskWithOverwriteRestoresPreviousState()
    {
        var harness = TestHarness.Create();
        harness.Tasks.Seed(@"\", "AutoRegBackup", enabled: false);
        var journal = new UndoJournal();

        var result = await new TaskCreateExecutor().ExecuteAsync(
            CreateTask("AutoRegBackup") with { Overwrite = true }, ContextFor(harness, journal));

        Assert.True(result.Success, result.ErrorMessage);
        Assert.Equal("Disabled", result.PreviousState);
        Assert.True(harness.Tasks.IsTaskEnabled(@"\", "AutoRegBackup"));

        await journal.RollbackAsync(UndoContextFor(harness));

        Assert.True(harness.Tasks.Exists(@"\", "AutoRegBackup"));
        Assert.False(harness.Tasks.IsTaskEnabled(@"\", "AutoRegBackup"));
    }

    /// <summary>T1: un desencadenante no soportado o una hora mal formada se
    /// rechazan antes de crear nada (contrato cerrado de la acción).</summary>
    [Fact]
    public async Task TaskCreate_RejectsUnsupportedTriggersAndBadTimes()
    {
        var harness = TestHarness.Create();
        var executor = new TaskCreateExecutor();
        var cases = new[]
        {
            CreateTask("A") with { Trigger = "Weekly" },
            CreateTask("B") with { TriggerAt = null },
            CreateTask("C") with { Execute = " " },
        };

        foreach (var action in cases)
        {
            var result = await executor.ExecuteAsync(action, ContextFor(harness, new UndoJournal()));
            Assert.False(result.Success);
        }

        Assert.Empty(harness.Tasks.Snapshot());
        Assert.Equal(0, harness.Tasks.MutationCount);
    }

    /// <summary>T1: si el accesor falla al crear la tarea, la acción falla y el
    /// diario no recibe una entrada que prometa un deshacer inexistente.</summary>
    [Fact]
    public async Task TaskCreate_CreationFailureLeavesNoJournalEntry()
    {
        var harness = TestHarness.Create();
        harness.Tasks.FailCreateWith = "El servicio de tareas no responde.";
        var journal = new UndoJournal();

        var result = await new TaskCreateExecutor().ExecuteAsync(
            CreateTask("AutoRegBackup"), ContextFor(harness, journal));

        Assert.False(result.Success);
        Assert.Empty(journal.Entries);
        Assert.False(harness.Tasks.Exists(@"\", "AutoRegBackup"));
    }

    // ------------------------------------------------------------ servicios
    /// <summary>T1: arrancar un servicio parado y deshacer = volver a pararlo.</summary>
    [Fact]
    public async Task ServiceStart_UndoStopsItAgain()
    {
        var harness = TestHarness.Create();
        harness.Services.Seed("w32time", ServiceStatus.Stopped, ServiceStartupType.Manual);
        var journal = new UndoJournal();

        var result = await new ServiceActionExecutor().ExecuteAsync(new ServiceAction
        {
            Order = 1,
            Description = "w32time: iniciar",
            ServiceName = "w32time",
            Operation = ServiceOperation.Start,
        }, ContextFor(harness, journal));

        Assert.True(result.Success, result.ErrorMessage);
        Assert.Equal(ServiceStatus.Running, harness.Services.GetStatus("w32time"));

        await journal.RollbackAsync(UndoContextFor(harness));

        Assert.Equal(ServiceStatus.Stopped, harness.Services.GetStatus("w32time"));
        Assert.Equal(ServiceStartupType.Manual, harness.Services.GetStartupType("w32time"));
    }

    /// <summary>T1: cambiar el arranque no toca el estado de ejecución; el diario
    /// sólo devuelve el tipo previo (no arranca ni para nada).</summary>
    [Fact]
    public async Task ServiceSetStartup_DoesNotTouchTheRuntimeStatus()
    {
        var harness = TestHarness.Create();
        harness.Services.Seed("lfsvc", ServiceStatus.Stopped, ServiceStartupType.Automatic);
        var journal = new UndoJournal();

        await new ServiceActionExecutor().ExecuteAsync(new ServiceAction
        {
            Order = 1,
            Description = "lfsvc -> Disabled",
            ServiceName = "lfsvc",
            Operation = ServiceOperation.SetStartupType,
            StartupType = "Disabled",
        }, ContextFor(harness, journal));

        var entry = Assert.IsType<ServiceUndoEntry>(Assert.Single(journal.Entries));
        Assert.True(entry.StartupTypeChanged);
        Assert.False(entry.StatusChanged);

        await journal.RollbackAsync(UndoContextFor(harness));

        Assert.Equal(ServiceStartupType.Automatic, harness.Services.GetStartupType("lfsvc"));
        Assert.Equal(ServiceStatus.Stopped, harness.Services.GetStatus("lfsvc"));
    }

    /// <summary>T1: si arrancar falla, la acción falla y la capacidad entera
    /// revierte lo ya aplicado (el coordinador corre el rollback LIFO).</summary>
    [Fact]
    public async Task ServiceStartFailure_RollsBackTheWholeCapability()
    {
        var harness = TestHarness.Create();
        harness.Services.Seed("w32time", ServiceStatus.Stopped, ServiceStartupType.Manual);
        harness.Services.FailStartWith = "w32time";

        var actions = new CapabilityAction[]
        {
            new RegistryAction
            {
                Order = 1,
                Description = "NtpServer",
                Hive = RegistryHiveKind.LocalMachine,
                KeyPath = @"SYSTEM\CurrentControlSet\Services\W32Time\Parameters",
                ValueName = "NtpServer",
                Operation = RegistryOperation.Set,
                ValueType = RegistryValueType.String,
                Value = "0.pool.ntp.org",
            },
            new ServiceAction
            {
                Order = 2,
                Description = "w32time: iniciar",
                ServiceName = "w32time",
                Operation = ServiceOperation.Start,
            },
        };

        var contract = TestHarness.Contract(actions, risk: RiskLevel.Safe,
            restore: RestoreLevel.SessionUndo);
        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));

        Assert.Equal(1, summary.Failed);
        Assert.Contains("No se pudo iniciar", summary.Results[^1].ErrorMessage, StringComparison.Ordinal);
        // El valor de registro escrito antes se revierte: el estado es el inicial.
        Assert.Null(harness.Registry.GetValue(
            RegistryHive.LocalMachine,
            @"SYSTEM\CurrentControlSet\Services\W32Time\Parameters",
            "NtpServer"));
        Assert.Equal(ServiceStatus.Stopped, harness.Services.GetStatus("w32time"));
        Assert.True(harness.Coordinator.Journal.IsEmpty);
    }

    /// <summary>T1/T2: la capacidad real `system.location.consent-deny` apaga
    /// lfsvc y MapsBroker y el rollback devuelve arranque Y estado de cada uno.</summary>
    [Fact]
    public async Task LocationCapability_StopsServicesAndRestoresBothStates()
    {
        var harness = Harness();
        harness.Services.Seed("lfsvc", ServiceStatus.Running, ServiceStartupType.Automatic);
        harness.Services.Seed("MapsBroker", ServiceStatus.Running, ServiceStartupType.Automatic);

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("system.location.consent-deny"), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));

        Assert.Equal(0, summary.Failed);
        Assert.Equal(ServiceStartupType.Disabled, harness.Services.GetStartupType("lfsvc"));
        Assert.Equal(ServiceStartupType.Disabled, harness.Services.GetStartupType("MapsBroker"));
        Assert.Equal(ServiceStatus.Stopped, harness.Services.GetStatus("lfsvc"));
        Assert.Equal(ServiceStatus.Stopped, harness.Services.GetStatus("MapsBroker"));

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        foreach (var name in new[] { "lfsvc", "MapsBroker" })
        {
            Assert.Equal(ServiceStartupType.Automatic, harness.Services.GetStartupType(name));
            Assert.Equal(ServiceStatus.Running, harness.Services.GetStatus(name));
        }
    }

    /// <summary>T2: la capacidad de copia de seguridad crea la tarea del pin y el
    /// rollback la borra junto con los dos valores del registro.</summary>
    [Fact]
    public async Task RegistryBackupCapability_CreatesTheTaskAndRollsItBack()
    {
        var harness = Harness();
        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("system.registry-backup.enable"), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));

        Assert.Equal(0, summary.Failed);
        Assert.True(harness.Tasks.Exists(@"\", "AutoRegBackup"));
        var created = Assert.Single(harness.Tasks.Created);
        Assert.Equal("00:30", created.TriggerAt);

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        Assert.False(harness.Tasks.Exists(@"\", "AutoRegBackup"));
        Assert.Null(harness.Registry.GetValue(
            RegistryHive.LocalMachine,
            @"SYSTEM\CurrentControlSet\Control\Session Manager\Configuration Manager",
            "EnablePeriodicBackup"));
    }

    /// <summary>T1: el borrado de clave pasa por la puerta de punto de
    /// restauración como cualquier otra acción que muta.</summary>
    [Fact]
    public async Task DeleteKey_GoesThroughTheRestorePointGate()
    {
        var harness = TestHarness.Create(restorePointAvailable: false);
        SeedTree(harness);
        var mutationsBefore = harness.Registry.MutationCount;

        var action = DeleteKeyAction(recursive: true);
        var contract = TestHarness.Contract([action], risk: RiskLevel.Medium,
            restore: RestoreLevel.RestorePoint);
        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, [action]), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));

        Assert.True(summary.Aborted);
        Assert.Contains("Protección del sistema", summary.AbortedReason, StringComparison.Ordinal);
        Assert.Equal(mutationsBefore, harness.Registry.MutationCount);
        Assert.True(harness.Registry.KeyExists(RegistryHive.LocalMachine, KeyPath));
    }

    // ------------------------------------------------------------- ayuda
    private static RegistryDeleteKeyAction DeleteKeyAction(int order = 1, bool recursive = false) => new()
    {
        Order = order,
        Description = "borrar clave",
        Hive = RegistryHiveKind.LocalMachine,
        KeyPath = KeyPath,
        Recursive = recursive,
    };

    private static TaskCreateAction CreateTask(string name) => new()
    {
        Order = 1,
        Description = $"crear {name}",
        TaskPath = @"\",
        TaskName = name,
        Execute = "schtasks",
        Arguments = "/run /i /tn \"\\Microsoft\\Windows\\Registry\\RegIdleBackup\"",
        Trigger = "Daily",
        TriggerAt = "00:30",
        UserId = "System",
        RunLevel = "Highest",
        TaskDescription = "Create System Registry Backups",
    };

    private static void SeedTree(TestHarness harness)
    {
        // Valores de tipos distintos (el deshacer debe devolver el TIPO, no sólo el dato).
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "Str", "texto",
            RegistryValueKind.String);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "Dword", 42,
            RegistryValueKind.DWord);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "Expand", "%TEMP%",
            RegistryValueKind.ExpandString);
        // Subárbol con una rama con valor y otra VACÍA (una clave sin valores).
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath + @"\Child", "Bin",
            new byte[] { 1, 2, 3 }, RegistryValueKind.Binary);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath + @"\Child\Grand", "Q", 7L,
            RegistryValueKind.QWord);
        harness.Registry.EnsureKey(EmptyKey);
        harness.Registry.ClearLog();
    }

    private static ActionContext ContextFor(
        TestHarness harness,
        UndoJournal journal,
        ExecutionMode mode = ExecutionMode.Execute,
        IRegistryAccessor? registry = null) => new()
        {
            Registry = registry ?? harness.Registry,
            Services = harness.Services,
            Tasks = harness.Tasks,
            Processes = harness.Processes,
            Commands = harness.Commands,
            Mode = mode,
            Journal = journal,
            CapabilityId = "wave4.capability",
        };

    private static UndoContext UndoContextFor(TestHarness harness) => new(
        harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands);

    private static void AssertSameRegistry(
        IReadOnlyDictionary<string, IReadOnlyDictionary<string, RegistryEntry>> expected,
        IReadOnlyDictionary<string, IReadOnlyDictionary<string, RegistryEntry>> actual)
    {
        Assert.Equal(expected.Keys.OrderBy(k => k, StringComparer.OrdinalIgnoreCase),
            actual.Keys.OrderBy(k => k, StringComparer.OrdinalIgnoreCase));

        foreach (var (key, values) in expected)
        {
            foreach (var (name, entry) in values)
            {
                Assert.True(actual[key].ContainsKey(name), $"{key}\\{name} no volvió");
                Assert.Equal(entry.Kind, actual[key][name].Kind);
                if (entry.Value is byte[] expectedBytes)
                {
                    Assert.Equal(expectedBytes, Assert.IsType<byte[]>(actual[key][name].Value));
                }
                else
                {
                    Assert.Equal(entry.Value, actual[key][name].Value);
                }
            }
        }

        // Y ninguna clave de más: el árbol recreado es el mismo, no uno más gordo.
        // (Child\Empty es una clave SIN valores: se comprueba por existencia.)
        Assert.True(actual.ContainsKey(EmptyKey));
    }

    /// <summary>Accesor que sabe leer valores pero NO enumerar el árbol.</summary>
    private sealed class TreeBlindRegistry : IRegistryAccessor
    {
        private readonly FakeRegistryAccessor _inner;

        public TreeBlindRegistry(FakeRegistryAccessor inner) => _inner = inner;

        public int DeleteKeyCalls { get; private set; }

        public object? GetValue(RegistryHive hive, string keyPath, string valueName) =>
            _inner.GetValue(hive, keyPath, valueName);

        public void SetValue(RegistryHive hive, string keyPath, string valueName, object value,
            RegistryValueKind kind) =>
            _inner.SetValue(hive, keyPath, valueName, value, kind);

        public bool DeleteValue(RegistryHive hive, string keyPath, string valueName) =>
            _inner.DeleteValue(hive, keyPath, valueName);

        public bool KeyExists(RegistryHive hive, string keyPath) => _inner.KeyExists(hive, keyPath);

        public bool DeleteKey(RegistryHive hive, string keyPath, bool recursive)
        {
            DeleteKeyCalls++;
            return _inner.DeleteKey(hive, keyPath, recursive);
        }
    }

    /// <summary>Accesor cuya enumeración del árbol falla (instantánea imposible).</summary>
    private sealed class FailingTreeReader : IRegistryAccessor, IRegistryTreeReader
    {
        private readonly FakeRegistryAccessor _inner;

        public FailingTreeReader(FakeRegistryAccessor inner) => _inner = inner;

        public int DeleteKeyCalls { get; private set; }

        public object? GetValue(RegistryHive hive, string keyPath, string valueName) =>
            _inner.GetValue(hive, keyPath, valueName);

        public void SetValue(RegistryHive hive, string keyPath, string valueName, object value,
            RegistryValueKind kind) =>
            _inner.SetValue(hive, keyPath, valueName, value, kind);

        public bool DeleteValue(RegistryHive hive, string keyPath, string valueName) =>
            _inner.DeleteValue(hive, keyPath, valueName);

        public bool KeyExists(RegistryHive hive, string keyPath) => _inner.KeyExists(hive, keyPath);

        public bool DeleteKey(RegistryHive hive, string keyPath, bool recursive)
        {
            DeleteKeyCalls++;
            return _inner.DeleteKey(hive, keyPath, recursive);
        }

        public IReadOnlyList<string> GetSubKeyNames(RegistryHive hive, string keyPath) =>
            throw new InvalidOperationException("El registro no responde.");

        public IReadOnlyList<string> GetValueNames(RegistryHive hive, string keyPath) =>
            throw new InvalidOperationException("El registro no responde.");
    }

    private static IReadOnlyList<CapabilityDefinition> LoadAll()
    {
        var directory = Path.Combine(AppContext.BaseDirectory, "capabilities");
        Assert.True(Directory.Exists(directory), $"No existe el directorio de catálogo: {directory}");
        return new CatalogLoader().LoadDirectory(directory)
            .SelectMany(d => d.Capabilities)
            .ToList();
    }

    private static CapabilityDefinition Definition(string id) =>
        LoadAll().SingleOrDefault(d => d.Id == id)
        ?? throw new InvalidOperationException($"No está '{id}' en el catálogo.");

    private static TestHarness Harness() => TestHarness.Create(
        catalog: LoadAll().Select(d => d.ToContract()).ToList());

    private static ExecutionPlan Plan(string id)
    {
        var definition = Definition(id);
        return new ExecutionPlan(
            definition.ToContract(),
            definition.Actions.Select(a => new PlannedStep
            {
                Order = a.Order,
                Description = a.Description,
                Action = a,
            }));
    }
}
