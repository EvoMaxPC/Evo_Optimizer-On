using System.Linq;
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

/// <summary>Comportamiento atómico de cada ejecutor por separado.</summary>
public sealed class ExecutorTests
{
    private const string KeyPath = @"SOFTWARE\Evo\Unit";

    private static ActionContext ContextFor(TestHarness harness, ExecutionMode mode = ExecutionMode.Execute, UndoJournal? journal = null) => new()
    {
        Registry = harness.Registry,
        Services = harness.Services,
        Tasks = harness.Tasks,
        Processes = harness.Processes,
        Commands = harness.Commands,
        Mode = mode,
        Journal = journal ?? new UndoJournal(),
        CapabilityId = "unit.capability",
    };

    [Fact]
    public async Task RegistryExecutorRecordsNewValueAsDeleteOnRollback()
    {
        var harness = TestHarness.Create();
        var journal = new UndoJournal();
        var action = new RegistryAction
        {
            Order = 1,
            Description = "crear",
            Hive = RegistryHiveKind.CurrentUser,
            KeyPath = KeyPath,
            ValueName = "New",
            Operation = RegistryOperation.Set,
            ValueType = RegistryValueType.String,
            Value = "x",
        };

        var result = await new RegistryActionExecutor().ExecuteAsync(action, ContextFor(harness, journal: journal));

        Assert.True(result.Success);
        Assert.Null(result.PreviousState);
        Assert.Equal("x", result.NewState);
        var entry = Assert.IsType<RegistryUndoEntry>(Assert.Single(journal.Entries));
        Assert.False(entry.ExistedBefore);
        Assert.Equal(RegistryHive.CurrentUser, entry.Hive);
        Assert.Equal("x", harness.Registry.GetValue(RegistryHive.CurrentUser, KeyPath, "New"));

        await journal.RollbackAsync(new UndoContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands));

        Assert.Null(harness.Registry.GetValue(RegistryHive.CurrentUser, KeyPath, "New"));
    }

    [Fact]
    public async Task RegistryExecutorSupportsAllValueTypes()
    {
        var harness = TestHarness.Create();
        var executor = new RegistryActionExecutor();
        var cases = new (RegistryValueType Type, string Value, object Expected)[]
        {
            (RegistryValueType.String, "hola", "hola"),
            (RegistryValueType.DWord, "42", 42),
            (RegistryValueType.QWord, "9999999999", 9999999999L),
            (RegistryValueType.Binary, Convert.ToBase64String([1, 2, 3]), new byte[] { 1, 2, 3 }),
            (RegistryValueType.MultiString, "a\u001fb", new[] { "a", "b" }),
            (RegistryValueType.ExpandString, "%TEMP%", "%TEMP%"),
        };

        var order = 1;
        foreach (var (type, value, expected) in cases)
        {
            var action = new RegistryAction
            {
                Order = order++,
                Description = type.ToString(),
                Hive = RegistryHiveKind.LocalMachine,
                KeyPath = KeyPath,
                ValueName = type.ToString(),
                Operation = RegistryOperation.Set,
                ValueType = type,
                Value = value,
            };

            var result = await executor.ExecuteAsync(action, ContextFor(harness));

            Assert.True(result.Success, result.ErrorMessage);
            Assert.Equal(RegistryActionExecutor.ToRegistryKind(type),
                harness.Registry.GetKind(RegistryHive.LocalMachine, KeyPath, type.ToString()));
            Assert.Equal(expected, harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, type.ToString()));
        }
    }

    [Fact]
    public async Task ServiceExecutorRestoresStatusAndStartup()
    {
        var harness = TestHarness.Create();
        harness.Services.Seed("TextInput", ServiceStatus.Running, ServiceStartupType.Manual);
        var executor = new ServiceActionExecutor();
        var journal = new UndoJournal();

        await executor.ExecuteAsync(new ServiceAction
        {
            Order = 1,
            Description = "stop",
            ServiceName = "TextInput",
            Operation = ServiceOperation.Stop,
        }, ContextFor(harness, journal: journal));

        await executor.ExecuteAsync(new ServiceAction
        {
            Order = 2,
            Description = "disabled",
            ServiceName = "TextInput",
            Operation = ServiceOperation.SetStartupType,
            StartupType = "Disabled",
        }, ContextFor(harness, journal: journal));

        Assert.Equal(ServiceStatus.Stopped, harness.Services.GetStatus("TextInput"));
        Assert.Equal(ServiceStartupType.Disabled, harness.Services.GetStartupType("TextInput"));

        await journal.RollbackAsync(new UndoContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands));

        Assert.Equal(ServiceStatus.Running, harness.Services.GetStatus("TextInput"));
        Assert.Equal(ServiceStartupType.Manual, harness.Services.GetStartupType("TextInput"));
    }

    [Fact]
    public async Task TaskExecutorTogglesAndRestores()
    {
        var harness = TestHarness.Create();
        harness.Tasks.Seed(@"\Microsoft\Windows\AppID", "PolicyConverter", true);
        var journal = new UndoJournal();

        var result = await new TaskActionExecutor().ExecuteAsync(new TaskAction
        {
            Order = 1,
            Description = "disable",
            TaskPath = @"\Microsoft\Windows\AppID",
            TaskName = "PolicyConverter",
            Enabled = false,
        }, ContextFor(harness, journal: journal));

        Assert.True(result.Success);
        Assert.False(harness.Tasks.IsTaskEnabled(@"\Microsoft\Windows\AppID", "PolicyConverter"));
        Assert.Single(journal.Entries);

        await journal.RollbackAsync(new UndoContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands));

        Assert.True(harness.Tasks.IsTaskEnabled(@"\Microsoft\Windows\AppID", "PolicyConverter"));
    }

    [Fact]
    public async Task TaskExecutorFailsOnMissingTask()
    {
        var harness = TestHarness.Create();

        var result = await new TaskActionExecutor().ExecuteAsync(new TaskAction
        {
            Order = 1,
            Description = "falta",
            TaskPath = @"\Nope",
            TaskName = "NoExiste",
            Enabled = false,
        }, ContextFor(harness));

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.Contains("no existe", result.ErrorMessage, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ProcessExecutorSkipsWhenNotRunning()
    {
        var harness = TestHarness.Create();
        harness.Processes.Seed("explorer", running: false);

        var result = await new ProcessActionExecutor().ExecuteAsync(new ProcessAction
        {
            Order = 1,
            Description = "explorer",
            ProcessName = "explorer",
        }, ContextFor(harness));

        Assert.Equal(ActionStatus.Skipped, result.Status);
        Assert.Empty(harness.Processes.Terminated);
    }

    [Fact]
    public async Task ProcessExecutorTerminatesAndLogs()
    {
        var harness = TestHarness.Create();
        harness.Processes.Seed("SearchHost", running: true);

        var result = await new ProcessActionExecutor().ExecuteAsync(new ProcessAction
        {
            Order = 1,
            Description = "SearchHost",
            ProcessName = "SearchHost",
        }, ContextFor(harness));

        Assert.True(result.Success);
        Assert.Equal("Running", result.PreviousState);
        Assert.Single(harness.Processes.Terminated);
        Assert.False(harness.Processes.IsRunning("SearchHost"));
    }

    [Fact]
    public async Task CommandExecutorRespectsAllowedExitCodes()
    {
        var harness = TestHarness.Create();
        harness.Commands.Respond("fltmc.exe filters", exitCode: 1, stdout: "no admin");

        var failing = await new CommandActionExecutor().ExecuteAsync(new CommandAction
        {
            Order = 1,
            Description = "fltmc",
            FileName = "fltmc.exe",
            Arguments = ["filters"],
        }, ContextFor(harness));

        Assert.Equal(ActionStatus.Failed, failing.Status);
        Assert.Contains("devolvió 1", failing.ErrorMessage, StringComparison.Ordinal);

        harness.Commands.Respond("fltmc.exe filters", exitCode: 1, stdout: "no admin");
        var tolerated = await new CommandActionExecutor().ExecuteAsync(new CommandAction
        {
            Order = 2,
            Description = "fltmc tolerado",
            FileName = "fltmc.exe",
            Arguments = ["filters"],
            IgnoreExitCode = true,
        }, ContextFor(harness));

        Assert.True(tolerated.Success);
        Assert.Equal(2, harness.Commands.Executed.Count);
    }

    [Fact]
    public async Task CommandExecutorDoesNotRunInDryRun()
    {
        var harness = TestHarness.Create();

        var result = await new CommandActionExecutor().ExecuteAsync(new CommandAction
        {
            Order = 1,
            Description = "winget",
            FileName = "winget.exe",
            Arguments = ["list"],
        }, ContextFor(harness, ExecutionMode.DryRun));

        Assert.True(result.Success);
        Assert.False(result.Applied);
        Assert.Empty(harness.Commands.Executed);
        Assert.StartsWith("would-run:", result.NewState, StringComparison.Ordinal);
    }

    [Fact]
    public async Task RollbackIsLifoAndContinuesAfterError()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "X", 1);
        var journal = new UndoJournal();
        var context = ContextFor(harness, journal: journal);

        await new RegistryActionExecutor().ExecuteAsync(new RegistryAction
        {
            Order = 1,
            Description = "X=5",
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = KeyPath,
            ValueName = "X",
            Operation = RegistryOperation.Set,
            ValueType = RegistryValueType.DWord,
            Value = "5",
        }, context);

        // Entrada que falla a propósito para comprobar que el rollback sigue.
        journal.Add(new ThrowingEntry
        {
            CapabilityId = "unit.capability",
            ActionKey = "throw",
            Description = "falla",
            PreviousState = null,
        });

        var rollback = await journal.RollbackAsync(new UndoContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands));

        Assert.False(rollback.Success);
        Assert.Single(rollback.Errors);
        Assert.Single(rollback.Restored);
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "X"));
    }

    // ---------------- H3: Procesos honestos ----------------

    /// <summary>
    /// H3.1: Terminate=false llama a StopProcess, detiene el proceso, retorna Ok
    /// y la entrada del journal es NotReversible.
    /// </summary>
    [Fact]
    public async Task ProcessTerminateFalse_LlamaStop_YVerifica()
    {
        var harness = TestHarness.Create();
        harness.Processes.Seed("notepad", running: true);
        var journal = new UndoJournal();

        var result = await new ProcessActionExecutor().ExecuteAsync(new ProcessAction
        {
            Order = 1,
            Description = "notepad",
            ProcessName = "notepad",
            Terminate = false,
        }, ContextFor(harness, journal: journal));

        Assert.True(result.Success);
        Assert.True(harness.Processes.Stopped.Contains("notepad"));
        Assert.DoesNotContain("notepad", harness.Processes.Terminated);
        Assert.False(harness.Processes.IsRunning("notepad"));
        Assert.Single(journal.Entries);
        var entry = Assert.IsType<ProcessUndoEntry>(Assert.Single(journal.Entries));
        var outcome = entry.Restore(new UndoContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands));
        Assert.Equal(UndoRestoreResult.NotReversible, outcome.Result);
    }

    /// <summary>
    /// H3.2: Terminate=true llama a TerminateProcess, detiene el proceso, retorna Ok
    /// y la entrada del journal es NotReversible.
    /// </summary>
    [Fact]
    public async Task ProcessTerminateTrue_LlamaTerminate_YVerifica()
    {
        var harness = TestHarness.Create();
        harness.Processes.Seed("SearchHost", running: true);
        var journal = new UndoJournal();

        var result = await new ProcessActionExecutor().ExecuteAsync(new ProcessAction
        {
            Order = 1,
            Description = "SearchHost",
            ProcessName = "SearchHost",
            Terminate = true,
        }, ContextFor(harness, journal: journal));

        Assert.True(result.Success);
        Assert.DoesNotContain("SearchHost", harness.Processes.Stopped);
        Assert.Contains("SearchHost", harness.Processes.Terminated);
        Assert.False(harness.Processes.IsRunning("SearchHost"));
        Assert.Single(journal.Entries);
    }

    /// <summary>
    /// H3.3: Terminate=false y StopProcess no detiene el proceso → Failed, nunca Ok.
    /// </summary>
    [Fact]
    public async Task ProcessNoSeDetieneConStop_TerminateFalse_Failed()
    {
        var accessor = new StubbornProcessAccessor();
        accessor.Seed("zombie", running: true);
        var journal = new UndoJournal();
        var context = new ActionContext
        {
            Registry = new FakeRegistryAccessor(),
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = accessor,
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new ProcessActionExecutor().ExecuteAsync(new ProcessAction
        {
            Order = 1,
            Description = "zombie",
            ProcessName = "zombie",
            Terminate = false,
        }, context);

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.Contains("no se detuvo con Stop", result.ErrorMessage);
        Assert.True(accessor.Stopped.Contains("zombie"));
        Assert.True(accessor.IsRunning("zombie")); // Sigue corriendo: Stop no detuvo nada
        Assert.Empty(journal.Entries); // No se añade journal entry en fallo
    }

    /// <summary>
    /// H3.4: Terminate=true y TerminateProcess no detiene el proceso → Failed, nunca Ok.
    /// </summary>
    [Fact]
    public async Task ProcessNoSeDetieneConTerminate_TerminateTrue_Failed()
    {
        var accessor = new StubbornProcessAccessor();
        accessor.Seed("zombie2", running: true);
        var journal = new UndoJournal();
        var context = new ActionContext
        {
            Registry = new FakeRegistryAccessor(),
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = accessor,
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new ProcessActionExecutor().ExecuteAsync(new ProcessAction
        {
            Order = 1,
            Description = "zombie2",
            ProcessName = "zombie2",
            Terminate = true,
        }, context);

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.Contains("no se pudo detener", result.ErrorMessage);
        Assert.True(accessor.Terminated.Contains("zombie2"));
        Assert.True(accessor.IsRunning("zombie2")); // Sigue corriendo
        Assert.Empty(journal.Entries);
    }

    /// <summary>
    /// H3.5: Proceso inexistente → Skip (applied=false), sin journal entry.
    /// </summary>
    [Fact]
    public async Task ProcessInexistente_SkipSinJournal()
    {
        var harness = TestHarness.Create();
        // No se semea ningún proceso: IsRunning devuelve false.
        var journal = new UndoJournal();

        var result = await new ProcessActionExecutor().ExecuteAsync(new ProcessAction
        {
            Order = 1,
            Description = "noexiste",
            ProcessName = "NoExiste",
            Terminate = true,
        }, ContextFor(harness, journal: journal));

        Assert.Equal(ActionStatus.Skipped, result.Status);
        Assert.False(result.Applied);
        Assert.Empty(journal.Entries);
        Assert.Empty(harness.Processes.Terminated);
        Assert.Empty(harness.Processes.Stopped);
    }

    // ---------------- H4: Tareas con definición completa ----------------

    /// <summary>
    /// H4.1: TaskCreate con tarea nueva → journal entry con TaskDefinition completa
    /// → Restore borra la tarea.
    /// </summary>
    [Fact]
    public async Task TaskCreateNueva_JournalConDefinition_RestoreBorraTarea()
    {
        var harness = TestHarness.Create();
        var journal = new UndoJournal();

        var result = await new TaskCreateExecutor().ExecuteAsync(new TaskCreateAction
        {
            Order = 1,
            TaskPath = @"\Microsoft\Windows\Test",
            TaskName = "TestTask",
            Execute = "cmd.exe",
            Arguments = "/c echo hola",
            Trigger = "OnLogon",
            UserId = "System",
            RunLevel = "Highest",
            TaskDescription = "Tarea de prueba",
        }, ContextFor(harness, journal: journal));

        Assert.True(result.Success);
        Assert.True(harness.Tasks.Exists(@"\Microsoft\Windows\Test", "TestTask"));

        var entry = Assert.Single(journal.Entries);
        var tce = Assert.IsType<TaskCreateUndoEntry>(entry);
        Assert.False(tce.ExistedBefore);
        Assert.NotNull(tce.Definition);
        Assert.Equal("cmd.exe", tce.Definition.Execute);
        Assert.Equal("OnLogon", tce.Definition.Trigger);
        Assert.Equal("System", tce.Definition.UserId);

        // Rollback: borra la tarea creada.
        var report = await journal.RollbackAsync(new UndoContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands));

        Assert.True(report.Success);
        Assert.Single(report.Restored);
        Assert.False(harness.Tasks.Exists(@"\Microsoft\Windows\Test", "TestTask"));
    }

    /// <summary>
    /// H4.2: TaskCreate con tarea existente (Overwrite=true) → journal entry con
    /// WasEnabled + TaskDefinition → Restore restaura definición y estado.
    /// </summary>
    [Fact]
    public async Task TaskCreateExistente_JournalConWasEnabledYDefinition_RestoreRestaura()
    {
        var harness = TestHarness.Create();
        harness.Tasks.Seed(@"\Microsoft\Windows\Test", "ExistingTask", enabled: true);
        var journal = new UndoJournal();

        var result = await new TaskCreateExecutor().ExecuteAsync(new TaskCreateAction
        {
            Order = 1,
            TaskPath = @"\Microsoft\Windows\Test",
            TaskName = "ExistingTask",
            Execute = "powershell.exe",
            Trigger = "Daily",
            TriggerAt = "08:00",
            UserId = "Admin",
            RunLevel = "Limited",
            Overwrite = true,
        }, ContextFor(harness, journal: journal));

        Assert.True(result.Success);
        var entry = Assert.Single(journal.Entries);
        var tce = Assert.IsType<TaskCreateUndoEntry>(entry);
        Assert.True(tce.ExistedBefore);
        Assert.True(tce.WasEnabled);
        Assert.NotNull(tce.Definition);
        Assert.Equal("powershell.exe", tce.Definition.Execute);

        // Rollback: CreateTask(Definition) + mantener WasEnabled (true = habilitada).
        var report = await journal.RollbackAsync(new UndoContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands));

        Assert.True(report.Success);
        Assert.Single(report.Restored);
        Assert.True(harness.Tasks.Exists(@"\Microsoft\Windows\Test", "ExistingTask"));
        Assert.True(harness.Tasks.IsTaskEnabled(@"\Microsoft\Windows\Test", "ExistingTask"));
        var restored = harness.Tasks.Snapshot().Values
            .FirstOrDefault(t => t.Path == @"\Microsoft\Windows\Test" && t.Name == "ExistingTask");
        Assert.NotNull(restored);
        Assert.NotNull(restored.Definition);
        Assert.Equal("powershell.exe", restored.Definition.Execute);
    }

    /// <summary>
    /// H4.3: TaskCreate sin TaskDefinition guardada → Restore → NotReversible.
    /// </summary>
    [Fact]
    public async Task TaskCreateSinDefinition_RestoreNotReversible()
    {
        var journal = new UndoJournal();
        journal.Add(new TaskCreateUndoEntry
        {
            CapabilityId = "c",
            ActionKey = "task",
            Description = "task",
            TaskPath = @"\Microsoft\Windows\Test",
            TaskName = "TestTask",
            ExistedBefore = true,
            WasEnabled = true,
            Definition = null,
            PreviousState = null,
        });

        var report = await journal.RollbackAsync(new UndoContext(
            new FakeRegistryAccessor(), new FakeServiceAccessor(), new FakeTaskAccessor(),
            new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.True(report.Success); // NotReversible no marca Success=false
        Assert.Single(report.NotReversible);
        Assert.Equal("task", report.NotReversible[0].ActionKey);
        Assert.Contains("TaskDefinition no se guardo", report.NotReversible[0].FailureMessage);
    }

    // ---------------- H5: RegistryDeleteKey con interfaz correcta ----------------

    /// <summary>
    /// H5.1: RegistryDeleteKey con clave que existe → snapshot → Restore recrea
    /// la clave con valores y subclaves.
    /// </summary>
    [Fact]
    public async Task RegistryDeleteKey_ClaveExiste_SnapshotYRestoreRecrea()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test", "Val1", 1);
        harness.Registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test\Sub", "Val2", 2);
        var journal = new UndoJournal();

        var result = await new RegistryDeleteKeyExecutor().ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"SOFTWARE\Evo\Test",
            Recursive = true,
        }, ContextFor(harness, journal: journal));

        Assert.True(result.Success);
        Assert.False(harness.Registry.KeyExists(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test"));
        Assert.Single(journal.Entries);

        var report = await journal.RollbackAsync(new UndoContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands));

        Assert.True(report.Success);
        Assert.Single(report.Restored);
        Assert.True(harness.Registry.KeyExists(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test"));
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test", "Val1"));
    }

    /// <summary>
    /// H5.2: RegistryDeleteKey con clave inexistente → no-op, sin journal entry.
    /// </summary>
    [Fact]
    public async Task RegistryDeleteKey_ClaveInexistente_NoOpSinJournal()
    {
        var harness = TestHarness.Create();
        var journal = new UndoJournal();

        var result = await new RegistryDeleteKeyExecutor().ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"SOFTWARE\Evo\NoExiste",
        }, ContextFor(harness, journal: journal));

        Assert.True(result.Success);
        Assert.False(result.Applied);
        Assert.Empty(journal.Entries);
    }

    // ---------------- H7: Límites de snapshot ----------------

    /// <summary>
    /// H7.1: Snapshot con profundidad <= 64 no se trunca (Truncated=false).
    /// </summary>
    [Fact]
    public async Task SnapshotProfundidadBaja64_NoTruncado()
    {
        var reader = new TestTreeReader(path => path.Split('\\').Length > 5 ? [] : ["Child"]);
        var snapshot = RegistryDeleteKeyExecutor.TakeSnapshot(
            reader, RegistryHive.LocalMachine, @"ROOT");

        Assert.False(snapshot.Truncated);
        Assert.Null(snapshot.TruncationMessage);
    }

    /// <summary>
    /// H7.2: Snapshot con profundidad > 64 se trunca (Truncated=true).
    /// </summary>
    [Fact]
    public async Task SnapshotProfundidadMayor64_SeTrunca_TruncatedTrue()
    {
        var reader = new TestTreeReader(_ => ["Child"]); // Siempre tiene hijo → alcanza depth 64
        var snapshot = RegistryDeleteKeyExecutor.TakeSnapshot(
            reader, RegistryHive.LocalMachine, @"ROOT");

        Assert.True(snapshot.Truncated);
        Assert.NotNull(snapshot.TruncationMessage);
    }

    /// <summary>
    /// H7.3: Snapshot con más de 1000 subclaves por nivel se trunca (solo la
    /// raíz tiene 2000 subclaves; el resto de niveles está vacío para evitar
    /// explosión combinatoria).
    /// </summary>
    [Fact]
    public async Task SnapshotConMasDe1000SubclavesPorNivel_SeTrunca()
    {
        var reader = new TestTreeReader(path =>
            path == @"ROOT"
                ? Enumerable.Range(0, 2000).Select(i => $"Key{i}").ToList()
                : []);
        var snapshot = RegistryDeleteKeyExecutor.TakeSnapshot(
            reader, RegistryHive.LocalMachine, @"ROOT");

        Assert.True(snapshot.Truncated);
        Assert.Equal(1000, snapshot.Root.Children.Count);
    }

    /// <summary>
    /// H7.4: Restore de snapshot truncado restaura lo que hay.
    /// </summary>
    [Fact]
    public async Task RestoreSnapshotTruncado_RestauraLoQueHay()
    {
        var reader = new TestTreeReader(_ => ["Child"]);
        var snapshot = RegistryDeleteKeyExecutor.TakeSnapshot(
            reader, RegistryHive.LocalMachine, @"ROOT");

        Assert.True(snapshot.Truncated);

        var registry = new FakeRegistryAccessor();
        var entry = new RegistryDeleteKeyUndoEntry
        {
            CapabilityId = "c",
            ActionKey = "del",
            Description = "del",
            Hive = RegistryHive.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
            ExistedBefore = true,
            Snapshot = snapshot,
            PreviousState = null,
        };

        var outcome = entry.Restore(new UndoContext(
            registry, new FakeServiceAccessor(), new FakeTaskAccessor(),
            new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.Equal(UndoRestoreResult.Restored, outcome.Result);
        Assert.True(registry.KeyExists(RegistryHive.LocalMachine, @"ROOT"));
    }

    // ---------------- Helpers H3/H7 ----------------

    /// <summary>
    /// Accesor de proceso que nunca detiene: StopProcess y TerminateProcess
    /// devuelven false, IsRunning siempre devuelve true para procesos sembrados.
    /// </summary>
    private sealed class StubbornProcessAccessor : IProcessAccessor
    {
        private readonly FakeProcessAccessor _inner = new();

        public List<string> Stopped => _inner.Stopped;
        public List<string> Terminated => _inner.Terminated;

        public void Seed(string name, bool running = true) => _inner.Seed(name, running);

        public bool IsRunning(string processName) => _inner.IsRunning(processName);
        public bool TerminateProcess(string processName) => false;
        public bool StopProcess(string processName) => false;
        public int StartProcess(string fileName, IReadOnlyList<string> arguments) => _inner.StartProcess(fileName, arguments);
    }

    /// <summary>
    /// IRegistryTreeReader de prueba controlado por delegado.
    /// </summary>
    private sealed class TestTreeReader : IRegistryTreeReader
    {
        private readonly Func<string, IReadOnlyList<string>> _subKeys;
        public TestTreeReader(Func<string, IReadOnlyList<string>> subKeys) => _subKeys = subKeys;

        public IReadOnlyList<string> GetSubKeyNames(RegistryHive hive, string keyPath) => _subKeys(keyPath);
        public IReadOnlyList<string> GetValueNames(RegistryHive hive, string keyPath) => [];
    }

    private sealed record ThrowingEntry : UndoJournalEntry
    {
        public override UndoEntryOutcome Restore(IUndoContext context) =>
            new()
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.Failed,
                FailureMessage = "rollback imposible",
            };
    }
}
