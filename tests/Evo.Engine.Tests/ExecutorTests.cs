using System.Collections.Generic;
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

    // ---------------- H3: Procesos (reporte honesto) ----------------

    /// <summary>
    /// H3.1: Proceso no corriendo → Skipped, sin journal.
    /// </summary>
    [Fact]
    public async Task ProcessNoCorriendo_SkipSinJournal()
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
    }

    /// <summary>
    /// H3.2: Corriendo + Terminate=false → sin mutación, sin journal, Skipped
    /// con mensaje "el proceso esta activo; la acción no solicita terminarlo".
    /// </summary>
    [Fact]
    public async Task ProcessCorriendo_TerminateFalse_SkipSinMutar()
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

        Assert.Equal(ActionStatus.Skipped, result.Status);
        Assert.False(result.Applied);
        Assert.Equal("Running", result.PreviousState);
        Assert.Contains("no solicita terminarlo", result.ErrorMessage);
        Assert.Empty(journal.Entries);
        Assert.True(harness.Processes.IsRunning("notepad")); // No se detuvo nada
        Assert.Empty(harness.Processes.Terminated);
    }

    /// <summary>
    /// H3.3: Corriendo + Terminate=true → TerminateProcess, se detiene → Ok,
    /// journal entry ProcessUndoEntry (NotReversible).
    /// </summary>
    [Fact]
    public async Task ProcessCorriendo_TerminateTrue_SeDetiene_OkNotReversible()
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
        Assert.True(result.Applied);
        Assert.Contains("SearchHost", harness.Processes.Terminated);
        Assert.False(harness.Processes.IsRunning("SearchHost"));
        Assert.Single(journal.Entries);
        var entry = Assert.IsType<ProcessUndoEntry>(Assert.Single(journal.Entries));
        var outcome = entry.Restore(new UndoContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands));
        Assert.Equal(UndoRestoreResult.NotReversible, outcome.Result);
    }

    /// <summary>
    /// H3.4: Corriendo + Terminate=true → TerminateProcess pero NO se detiene → Failed, sin journal.
    /// </summary>
    [Fact]
    public async Task ProcessCorriendo_TerminateTrue_NoSeDetiene_FailedSinJournal()
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
            Terminate = true,
        }, context);

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.Contains("no se pudo detener", result.ErrorMessage);
        Assert.True(accessor.Terminated.Contains("zombie"));
        Assert.True(accessor.IsRunning("zombie")); // Sigue corriendo
        Assert.Empty(journal.Entries);
    }

    /// <summary>
    /// H3.5: DryRun → sin mutación, sin journal.
    /// </summary>
    [Fact]
    public async Task ProcessDryRun_SinMutacion()
    {
        var harness = TestHarness.Create();
        harness.Processes.Seed("notepad", running: true);
        var journal = new UndoJournal();
        var context = ContextFor(harness, ExecutionMode.DryRun, journal: journal);

        var result = await new ProcessActionExecutor().ExecuteAsync(new ProcessAction
        {
            Order = 1,
            Description = "notepad",
            ProcessName = "notepad",
            Terminate = true,
        }, context);

        Assert.True(result.Success);
        Assert.False(result.Applied);
        Assert.Empty(journal.Entries);
        Assert.True(harness.Processes.IsRunning("notepad")); // No se detuvo nada
        Assert.Empty(harness.Processes.Terminated);
    }

    // ---------------- H4: Tareas con definición ORIGINAL ----------------

    /// <summary>
    /// H4.1: TaskCreate con tarea nueva → journal entry con PreviousDefinition=null
    /// (no existía antes) → Restore borra la tarea.
    /// </summary>
    [Fact]
    public async Task TaskCreateNueva_PreviousDefinitionNull_RestoreBorraTarea()
    {
        var harness = TestHarness.Create();
        var journal = new UndoJournal();

        var result = await new TaskCreateExecutor().ExecuteAsync(new TaskCreateAction
        {
            Order = 1,
            TaskPath = @"\\Microsoft\Windows\\Test",
            TaskName = "TestTask",
            Execute = "cmd.exe",
            Arguments = "/c echo hola",
            Trigger = "OnLogon",
            UserId = "System",
            RunLevel = "Highest",
            TaskDescription = "Tarea de prueba",
        }, ContextFor(harness, journal: journal));

        Assert.True(result.Success);
        Assert.True(harness.Tasks.Exists(@"\\Microsoft\Windows\\Test", "TestTask"));

        var entry = Assert.Single(journal.Entries);
        var tce = Assert.IsType<TaskCreateUndoEntry>(entry);
        Assert.False(tce.ExistedBefore);
        Assert.Null(tce.PreviousDefinition);

        var report = await journal.RollbackAsync(new UndoContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands));

        Assert.True(report.Success);
        Assert.Single(report.Restored);
        Assert.False(harness.Tasks.Exists(@"\\Microsoft\Windows\\Test", "TestTask"));
    }

    /// <summary>
    /// H4.2: TaskCreate sobre tarea existente (Overwrite=true) → guarda
    /// PreviousDefinition (la ORIGINAL) → Restore restaura definición original
    /// y WasEnabled original.
    /// </summary>
    [Fact]
    public async Task TaskCreateExistente_PreviousDefinitionOriginal_RestoreRestauraOriginal()
    {
        var harness = TestHarness.Create();
        var definicionOriginal = new TaskDefinition
        {
            TaskPath = @"\\Microsoft\Windows\\Test",
            TaskName = "ExistingTask",
            Execute = "orig.exe",
            Arguments = "/orig",
            Trigger = "Daily",
            TriggerAt = "08:00",
            UserId = "System",
            RunLevel = "Highest",
            Description = "Original",
        };
        harness.Tasks.Seed(@"\\Microsoft\Windows\\Test", "ExistingTask", enabled: false, definition: definicionOriginal);
        var journal = new UndoJournal();

        var result = await new TaskCreateExecutor().ExecuteAsync(new TaskCreateAction
        {
            Order = 1,
            TaskPath = @"\\Microsoft\Windows\\Test",
            TaskName = "ExistingTask",
            Execute = "nuevo.exe",
            Arguments = "/nuevo",
            Trigger = "OnLogon",
            UserId = "Admin",
            RunLevel = "Limited",
            TaskDescription = "Nueva",
            Overwrite = true,
        }, ContextFor(harness, journal: journal));

        Assert.True(result.Success);
        var entry = Assert.Single(journal.Entries);
        var tce = Assert.IsType<TaskCreateUndoEntry>(entry);
        Assert.True(tce.ExistedBefore);
        Assert.False(tce.WasEnabled);
        Assert.NotNull(tce.PreviousDefinition);
        Assert.Equal("orig.exe", tce.PreviousDefinition.Execute);
        Assert.Equal("Daily", tce.PreviousDefinition.Trigger);
        Assert.Equal("System", tce.PreviousDefinition.UserId);
        Assert.Equal("/orig", tce.PreviousDefinition.Arguments);

        var report = await journal.RollbackAsync(new UndoContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands));

        Assert.True(report.Success);
        Assert.Single(report.Restored);
        Assert.True(harness.Tasks.Exists(@"\\Microsoft\Windows\\Test", "ExistingTask"));
        Assert.False(harness.Tasks.IsTaskEnabled(@"\\Microsoft\Windows\\Test", "ExistingTask"));
        var restored = harness.Tasks.Snapshot().Values
            .FirstOrDefault(t => t.Path == @"\\Microsoft\Windows\\Test" && t.Name == "ExistingTask");
        Assert.NotNull(restored);
        Assert.NotNull(restored.Definition);
        Assert.Equal("orig.exe", restored.Definition.Execute);
        Assert.Equal("Daily", restored.Definition.Trigger);
        Assert.Equal("System", restored.Definition.UserId);
    }

    /// <summary>
    /// H4.3: GetDefinition devuelve null → Fail sin mutar, tarea intacta.
    /// </summary>
    [Fact]
    public async Task TaskCreateExistente_GetDefinitionNull_FailSinMutar()
    {
        var harness = TestHarness.Create();
        harness.Tasks.Seed(@"\\Microsoft\Windows\\Test", "SinDef", enabled: true);
        var journal = new UndoJournal();

        var result = await new TaskCreateExecutor().ExecuteAsync(new TaskCreateAction
        {
            Order = 1,
            TaskPath = @"\\Microsoft\Windows\\Test",
            TaskName = "SinDef",
            Execute = "nuevo.exe",
            Trigger = "OnLogon",
            UserId = "Admin",
            RunLevel = "Limited",
            Overwrite = true,
        }, ContextFor(harness, journal: journal));

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.Contains("no es legible", result.ErrorMessage);
        Assert.True(harness.Tasks.Exists(@"\\Microsoft\Windows\\Test", "SinDef"));
        Assert.Empty(journal.Entries);
    }

    /// <summary>
    /// H4.4: GetDefinition lanza → Fail sin mutar.
    /// </summary>
    [Fact]
    public async Task TaskCreateExistente_GetDefinitionLanza_FailSinMutar()
    {
        var harness = TestHarness.Create();
        harness.Tasks.Seed(@"\\Microsoft\Windows\\Test", "Fallida", enabled: true);
        harness.Tasks.FailGetDefinitionWith = "error de lectura";
        var journal = new UndoJournal();

        var result = await new TaskCreateExecutor().ExecuteAsync(new TaskCreateAction
        {
            Order = 1,
            TaskPath = @"\\Microsoft\Windows\\Test",
            TaskName = "Fallida",
            Execute = "nuevo.exe",
            Trigger = "OnLogon",
            UserId = "Admin",
            RunLevel = "Limited",
            Overwrite = true,
        }, ContextFor(harness, journal: journal));

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.Contains("error de lectura", result.ErrorMessage);
        Assert.True(harness.Tasks.Exists(@"\\Microsoft\Windows\\Test", "Fallida"));
        Assert.Empty(journal.Entries);
    }

    /// <summary>
    /// H4.5: ExistedBefore=true + PreviousDefinition=null → Restore → NotReversible.
    /// </summary>
    [Fact]
    public async Task TaskCreateSinPreviousDefinition_RestoreNotReversible()
    {
        var journal = new UndoJournal();
        journal.Add(new TaskCreateUndoEntry
        {
            CapabilityId = "c",
            ActionKey = "task",
            Description = "task",
            TaskPath = @"\\Microsoft\Windows\\Test",
            TaskName = "TestTask",
            ExistedBefore = true,
            WasEnabled = true,
            PreviousDefinition = null,
            PreviousState = null,
        });

        var report = await journal.RollbackAsync(new UndoContext(
            new FakeRegistryAccessor(), new FakeServiceAccessor(), new FakeTaskAccessor(),
            new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.True(report.Success);
        Assert.Single(report.NotReversible);
        Assert.Equal("task", report.NotReversible[0].ActionKey);
        Assert.Contains("TaskDefinition no se guardo", report.NotReversible[0].FailureMessage);
    }

    /// <summary>
    /// H4.6: CreateTask lanza durante rollback → Failed, entrada conservada.
    /// </summary>
    [Fact]
    public async Task TaskCreateCreateTaskLanzaDuranteRollback_FailedEntradaConservada()
    {
        var journal = new UndoJournal();
        var definicionOriginal = new TaskDefinition
        {
            TaskPath = @"\\Microsoft\Windows\\Test",
            TaskName = "TestTask",
            Execute = "orig.exe",
            Trigger = "OnLogon",
            UserId = "System",
            RunLevel = "Highest",
        };
        journal.Add(new TaskCreateUndoEntry
        {
            CapabilityId = "c",
            ActionKey = "task",
            Description = "task",
            TaskPath = @"\\Microsoft\Windows\\Test",
            TaskName = "TestTask",
            ExistedBefore = true,
            WasEnabled = true,
            PreviousDefinition = definicionOriginal,
            PreviousState = null,
        });

        var tasks = new FakeTaskAccessor();
        tasks.FailCreateWith = "error al crear";

        var report = await journal.RollbackAsync(new UndoContext(
            new FakeRegistryAccessor(), new FakeServiceAccessor(), tasks,
            new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.False(report.Success);
        Assert.Single(report.Failed);
        Assert.Equal("task", report.Failed[0].ActionKey);
        Assert.Single(journal.Entries);
        Assert.Equal("task", journal.Entries[0].ActionKey);
    }

    // ---------------- H5: RegistryDeleteKey fail-closed ----------------

    /// <summary>
    /// H5.1: Clave con valores y subclaves → snapshot → rollback restaura árbol completo.
    /// </summary>
    [Fact]
    public async Task RegistryDeleteKey_ArbolCompleto_RestoreRecreaTodo()
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
    /// H5.2: Clave inexistente → no-op, sin journal entry.
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

    /// <summary>
    /// H5.3: Accesor sin IRegistryKeyCreator → acción falla y la clave queda intacta.
    /// </summary>
    [Fact]
    public async Task RegistryDeleteKey_SinIRegistryKeyCreator_FailSinMutar()
    {
        var registry = new RegistryAccessorSinKeyCreator();
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test", "Val1", 1);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor().ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"SOFTWARE\Evo\Test",
            Recursive = true,
        }, ctx);

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.Contains("no sabe crear claves", result.ErrorMessage);
        Assert.True(registry.KeyExists(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test"));
        Assert.Empty(journal.Entries);
    }

    /// <summary>
    /// H5.4: !ExistedBefore con clave ausente → Restored.
    /// </summary>
    [Fact]
    public async Task RegistryDeleteKey_NoExistedBefore_ClaveAusente_Restored()
    {
        var journal = new UndoJournal();
        var snapshot = new RegistryKeySnapshot(
            new RegistryKeyNode(@"ROOT", [], []));
        var entry = new RegistryDeleteKeyUndoEntry
        {
            CapabilityId = "c",
            ActionKey = "del",
            Description = "del",
            Hive = RegistryHive.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
            ExistedBefore = false,
            Snapshot = snapshot,
            PreviousState = null,
        };

        var outcome = entry.Restore(new UndoContext(
            new FakeRegistryAccessor(), new FakeServiceAccessor(), new FakeTaskAccessor(),
            new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.Equal(UndoRestoreResult.Restored, outcome.Result);
    }

    /// <summary>
    /// H5.5: !ExistedBefore con clave existente → Failed con mensaje explícito.
    /// </summary>
    [Fact]
    public async Task RegistryDeleteKey_NoExistedBefore_ClaveExiste_Failed()
    {
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"ROOT", "Val1", 1);
        var journal = new UndoJournal();
        var snapshot = new RegistryKeySnapshot(
            new RegistryKeyNode(@"ROOT", [], []));
        var entry = new RegistryDeleteKeyUndoEntry
        {
            CapabilityId = "c",
            ActionKey = "del",
            Description = "del",
            Hive = RegistryHive.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
            ExistedBefore = false,
            Snapshot = snapshot,
            PreviousState = null,
        };

        var outcome = entry.Restore(new UndoContext(
            registry, new FakeServiceAccessor(), new FakeTaskAccessor(),
            new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.Equal(UndoRestoreResult.Failed, outcome.Result);
        Assert.Contains("ya existe y no debería", outcome.FailureMessage);
    }

    /// <summary>
    /// H5.6: SetValue lanza durante restauración → Failed, entrada conservada.
    /// </summary>
    [Fact]
    public async Task RegistryDeleteKey_SetValueLanzaRestauracion_FailedEntradaConservada()
    {
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test", "Val1", 1);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor().ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"SOFTWARE\Evo\Test",
            Recursive = true,
        }, ctx);

        Assert.True(result.Success);
        Assert.Single(journal.Entries);

        // Rollback con un registry que falla en SetValue (sin Seed: Seed llama
        // a SetValue internamente y consumiría el contador de fallo).
        var failingRegistry = new FailingRegistryAccessor();

        var report = await journal.RollbackAsync(new UndoContext(
            failingRegistry, new FakeServiceAccessor(), new FakeTaskAccessor(),
            new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.False(report.Success);
        Assert.Single(report.Failed);
        Assert.Single(journal.Entries);
    }

    /// <summary>
    /// H5.7: EnsureKey lanza durante restauración de árbol → Failed, entrada conservada.
    /// </summary>
    [Fact]
    public async Task RegistryDeleteKey_EnsureKeyLanzaRestauracion_FailedEntradaConservada()
    {
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test", "Val1", 1);
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test\Sub", "Val2", 2);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor().ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"SOFTWARE\Evo\Test",
            Recursive = true,
        }, ctx);

        Assert.True(result.Success);
        Assert.Single(journal.Entries);

        // Rollback con un registry que falla en EnsureKey (primera llamada).
        var failingRegistry = new FailingEnsureKeyRegistryAccessor();
        failingRegistry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test", "Val1", 1);
        failingRegistry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test\Sub", "Val2", 2);

        var report = await journal.RollbackAsync(new UndoContext(
            failingRegistry, new FakeServiceAccessor(), new FakeTaskAccessor(),
            new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.False(report.Success);
        Assert.Single(report.Failed);
        Assert.Single(journal.Entries); // Entrada conservada para reintento
    }

    // ---------------- H7: Límites del snapshot ----------------

    /// <summary>
    /// H7.1: Snapshot exactamente en el límite MaxValues (1 valor) → se borra.
    /// </summary>
    [Fact]
    public async Task SnapshotEnLimiteMaxValues_SeBorra()
    {
        var reader = new TestTreeReader(_ => []);
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"ROOT", "V1", 1);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor(
            new RegistrySnapshotLimits { MaxDepth = 16, MaxValues = 1, MaxKeys = 1024 }
        ).ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
        }, ctx);

        Assert.True(result.Success);
        Assert.False(registry.KeyExists(RegistryHive.LocalMachine, @"ROOT"));
        Assert.Single(journal.Entries);
    }

    /// <summary>
    /// H7.2: Snapshot excede MaxValues (2 valores, límite 1) → Fail, clave intacta.
    /// </summary>
    [Fact]
    public async Task SnapshotExcedeMaxValues_FailClaveIntacta()
    {
        var reader = new TestTreeReader(_ => []);
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"ROOT", "V1", 1);
        registry.Seed(RegistryHive.LocalMachine, @"ROOT", "V2", 2);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor(
            new RegistrySnapshotLimits { MaxDepth = 16, MaxValues = 1, MaxKeys = 1024 }
        ).ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
        }, ctx);

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.True(registry.KeyExists(RegistryHive.LocalMachine, @"ROOT"));
        Assert.Empty(journal.Entries);
    }

    /// <summary>
    /// H7.3: Snapshot excede MaxDepth (profundidad > límite) → Fail, clave intacta.
    /// Con MaxDepth=0, un hijo directo (profundidad 1) ya excede el límite.
    /// </summary>
    [Fact]
    public async Task SnapshotExcedeMaxDepth_FailClaveIntacta()
    {
        var registry = new CountingRegistryAccessor();
        registry.SeedSubKey(@"ROOT", @"ROOT\Child");
        registry.Seed(RegistryHive.LocalMachine, @"ROOT", "V", 1);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor(
            new RegistrySnapshotLimits { MaxDepth = 0, MaxValues = 4096, MaxKeys = 1024 }
        ).ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
        }, ctx);

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.True(registry.KeyExists(RegistryHive.LocalMachine, @"ROOT"));
        Assert.Empty(journal.Entries);
    }

    /// <summary>
    /// H7.4: Snapshot exactamente en el límite MaxDepth (0) → se borra, sin hijos.
    /// </summary>
    [Fact]
    public async Task SnapshotEnLimiteMaxDepth_SeBorra()
    {
        var registry = new CountingRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"ROOT", "V", 1);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor(
            new RegistrySnapshotLimits { MaxDepth = 0, MaxValues = 4096, MaxKeys = 1024 }
        ).ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
        }, ctx);

        Assert.True(result.Success);
        Assert.False(registry.KeyExists(RegistryHive.LocalMachine, @"ROOT"));
        Assert.Single(journal.Entries);
    }

    /// <summary>
    /// H7.5: Snapshot excede MaxKeys (1025 claves, límite 1024) → Fail, clave intacta.
    /// </summary>
    [Fact]
    public async Task SnapshotExcedeMaxKeys_FailClaveIntacta()
    {
        var registry = new CountingRegistryAccessor();
        // Crear 1025 subclaves directas de ROOT (más la raíz = 1026 claves > 1024).
        for (int i = 0; i < 1025; i++)
            registry.Seed(RegistryHive.LocalMachine, $@"ROOT\Clave{i}", "V", 1);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor(
            new RegistrySnapshotLimits { MaxDepth = 16, MaxValues = 4096, MaxKeys = 1024 }
        ).ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
        }, ctx);

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.True(registry.KeyExists(RegistryHive.LocalMachine, @"ROOT"));
        Assert.Empty(journal.Entries);
    }

    /// <summary>
    /// H7.6: Snapshot exactamente en el límite MaxKeys (1024 claves totales) → se borra.
    /// </summary>
    [Fact]
    public async Task SnapshotEnLimiteMaxKeys_SeBorra()
    {
        var registry = new CountingRegistryAccessor();
        // 1023 subclaves + la raíz = 1024 claves totales = límite exacto.
        for (int i = 0; i < 1023; i++)
            registry.Seed(RegistryHive.LocalMachine, $@"ROOT\Clave{i}", "V", 1);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor(
            new RegistrySnapshotLimits { MaxDepth = 16, MaxValues = 4096, MaxKeys = 1024 }
        ).ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
        }, ctx);

        Assert.True(result.Success);
        Assert.False(registry.KeyExists(RegistryHive.LocalMachine, @"ROOT"));
        Assert.Single(journal.Entries);
    }

    /// <summary>
    /// H7.7: MaxDepth límite+1 con contador → lecturas estrictamente menores que el total.
    /// </summary>
    [Fact]
    public async Task SnapshotExcedeMaxDepth_ConContador_LecturasParciales()
    {
        var registry = new CountingRegistryAccessor();
        // Árbol grande: cadena de 20 niveles (mucho más que MaxDepth=0).
        var path = @"ROOT";
        for (int i = 1; i <= 20; i++)
            path = $"{path}\\Nivel{i}";
        registry.Seed(RegistryHive.LocalMachine, path, "V", 1);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor(
            new RegistrySnapshotLimits { MaxDepth = 0, MaxValues = 4096, MaxKeys = 1024 }
        ).ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
        }, ctx);

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.True(registry.KeyExists(RegistryHive.LocalMachine, @"ROOT"));
        Assert.Empty(journal.Entries);

        // Lecturas necesarias para leer TODO el árbol: 21 GetSubKeyNames (una por nivel)
        // más 21 GetValueNames (una por nodo). Con aborto temprano en profundidad 1,
        // se leen mucho menos.
        var totalNecesarias = 21 + 21;
        Assert.True(registry.SubKeyReads < totalNecesarias,
            $"SubKeyReads={registry.SubKeyReads} debería ser < {totalNecesarias}");
        Assert.True(registry.ValueReads < totalNecesarias,
            $"ValueReads={registry.ValueReads} debería ser < {totalNecesarias}");
    }

    /// <summary>
    /// H7.8: MaxKeys límite+1 con contador → lecturas estrictamente menores que el total.
    /// </summary>
    [Fact]
    public async Task SnapshotExcedeMaxKeys_ConContador_LecturasParciales()
    {
        var registry = new CountingRegistryAccessor();
        // 2000 subclaves directas (mucho más que MaxKeys=1024).
        for (int i = 0; i < 2000; i++)
            registry.Seed(RegistryHive.LocalMachine, $@"ROOT\Clave{i}", "V", 1);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor(
            new RegistrySnapshotLimits { MaxDepth = 16, MaxValues = 4096, MaxKeys = 1024 }
        ).ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
        }, ctx);

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.True(registry.KeyExists(RegistryHive.LocalMachine, @"ROOT"));
        Assert.Empty(journal.Entries);

        // Para leer TODO el árbol haría falta 1 GetSubKeyNames(ROOT) + 2000 GetValueNames.
        // Con aborto temprano al llegar a 1025 claves, se leen mucho menos.
        var totalNecesarias = 1 + 2000;
        Assert.True(registry.SubKeyReads < totalNecesarias,
            $"SubKeyReads={registry.SubKeyReads} debería ser < {totalNecesarias}");
    }

    /// <summary>
    /// H7.9: MaxValues límite+1 con contador → lecturas estrictamente menores que el total.
    /// </summary>
    [Fact]
    public async Task SnapshotExcedeMaxValues_ConContador_LecturasParciales()
    {
        var registry = new CountingRegistryAccessor();
        // 5000 valores en ROOT (mucho más que MaxValues=4096).
        for (int i = 0; i < 5000; i++)
            registry.Seed(RegistryHive.LocalMachine, @"ROOT", $"Val{i}", i);
        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = registry,
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "unit.capability",
        };

        var result = await new RegistryDeleteKeyExecutor(
            new RegistrySnapshotLimits { MaxDepth = 16, MaxValues = 4096, MaxKeys = 1024 }
        ).ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.LocalMachine,
            KeyPath = @"ROOT",
            Recursive = true,
        }, ctx);

        Assert.Equal(ActionStatus.Failed, result.Status);
        Assert.True(registry.KeyExists(RegistryHive.LocalMachine, @"ROOT"));
        Assert.Empty(journal.Entries);

        // Para leer TODO el árbol haría falta 1 GetSubKeyNames(ROOT) + 5000 GetValueNames.
        // Con aborto temprano al llegar a 4097 valores, se leen mucho menos.
        var totalNecesarias = 1 + 5000;
        Assert.True(registry.ValueReads < totalNecesarias,
            $"ValueReads={registry.ValueReads} debería ser < {totalNecesarias}");
    }

    // ---------------- PASO 1: Rollback por identidad ----------------

    /// <summary>
    /// PASO 1: Rollback por identidad — dos entradas con el mismo ActionKey,
    /// una Restored y otra Failed → RollbackAsync conserva solo la entrada
    /// fallida (por índice), la exitosa se elimina del diario.
    /// </summary>
    [Fact]
    public async Task RollbackPorIdentidad_SoloEntradaFallida_SeConserva()
    {
        var journal = new UndoJournal();
        var definicionOriginal = new TaskDefinition
        {
            TaskPath = @"\\Microsoft\Windows\\Test",
            TaskName = "TestTask",
            Execute = "orig.exe",
            Trigger = "OnLogon",
            UserId = "System",
            RunLevel = "Highest",
        };

        // Entrada 1: ExistedBefore=false → DeleteTask → siempre exitoso → Restored
        journal.Add(new TaskCreateUndoEntry
        {
            CapabilityId = "c",
            ActionKey = "task",
            Description = "task",
            TaskPath = @"\\Microsoft\Windows\\Test",
            TaskName = "TestTask",
            ExistedBefore = false,
            WasEnabled = false,
            PreviousDefinition = null,
            PreviousState = null,
        });

        // Entrada 2: mismo ActionKey, ExistedBefore=true + PreviousDefinition → CreateTask → falla
        journal.Add(new TaskCreateUndoEntry
        {
            CapabilityId = "c",
            ActionKey = "task",
            Description = "task",
            TaskPath = @"\\Microsoft\Windows\\Test",
            TaskName = "OtraTarea",
            ExistedBefore = true,
            WasEnabled = true,
            PreviousDefinition = definicionOriginal,
            PreviousState = null,
        });

        var tasks = new FakeTaskAccessor();
        tasks.FailCreateWith = "error al crear"; // La segunda falla (CreateTask), la primera no (DeleteTask)

        var report = await journal.RollbackAsync(new UndoContext(
            new FakeRegistryAccessor(), new FakeServiceAccessor(), tasks,
            new FakeProcessAccessor(), new FakeCommandRunner()));

        // Hay una entrada Fallida, así que Success es false.
        Assert.False(report.Success);
        Assert.Single(report.Restored);
        Assert.Single(report.Failed);
        Assert.Equal("task", report.Restored[0].ActionKey);
        Assert.Equal("task", report.Failed[0].ActionKey);

        // Solo la entrada fallida se conserva (por índice); la exitosa se elimina.
        Assert.Single(journal.Entries);
        var entradaConservada = Assert.IsType<TaskCreateUndoEntry>(journal.Entries[0]);
        Assert.Equal("task", entradaConservada.ActionKey);
        Assert.Equal("OtraTarea", entradaConservada.TaskName); // la que falló

        // Segundo RollbackAsync: la entrada restaurada NO se reprocesa (ya salió del diario).
        // Si la fallida ahora funciona, el diario queda vacío.
        tasks.FailCreateWith = null;
        var report2 = await journal.RollbackAsync(new UndoContext(
            new FakeRegistryAccessor(), new FakeServiceAccessor(), tasks,
            new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.True(report2.Success);
        Assert.Single(report2.Restored);
        Assert.Empty(report2.Failed);
        Assert.True(journal.IsEmpty);
    }

    // ---------------- Helpers ----------------

    /// <summary>
    /// Accesor de proceso que nunca detiene: TerminateProcess devuelve false,
    /// IsRunning siempre devuelve true para procesos sembrados.
    /// </summary>
    private sealed class StubbornProcessAccessor : IProcessAccessor
    {
        private readonly FakeProcessAccessor _inner = new();

        public List<string> Terminated => _inner.Terminated;

        public void Seed(string name, bool running = true) => _inner.Seed(name, running);

        public bool IsRunning(string processName) => _inner.IsRunning(processName);
        public bool TerminateProcess(string processName)
        {
            _inner.Terminated.Add(processName);
            return false;
        }
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

    /// <summary>
    /// IRegistryAccessor que NO implementa IRegistryKeyCreator.
    /// </summary>
    private sealed class RegistryAccessorSinKeyCreator : IRegistryAccessor, IRegistryTreeReader
    {
        private readonly FakeRegistryAccessor _inner = new();

        public void Seed(RegistryHive hive, string keyPath, string valueName, object value,
            RegistryValueKind kind = RegistryValueKind.DWord)
        {
            _inner.Seed(hive, keyPath, valueName, value, kind);
        }

        public bool KeyExists(RegistryHive hive, string keyPath) => _inner.KeyExists(hive, keyPath);
        public bool DeleteKey(RegistryHive hive, string keyPath, bool recursive) => _inner.DeleteKey(hive, keyPath, recursive);
        public object? GetValue(RegistryHive hive, string keyPath, string valueName) => _inner.GetValue(hive, keyPath, valueName);
        public void SetValue(RegistryHive hive, string keyPath, string valueName, object value, RegistryValueKind kind) => _inner.SetValue(hive, keyPath, valueName, value, kind);
        public bool DeleteValue(RegistryHive hive, string keyPath, string valueName) => _inner.DeleteValue(hive, keyPath, valueName);
        public IReadOnlyList<string> GetSubKeyNames(RegistryHive hive, string keyPath) => _inner.GetSubKeyNames(hive, keyPath);
        public IReadOnlyList<string> GetValueNames(RegistryHive hive, string keyPath) => _inner.GetValueNames(hive, keyPath);
    }

    /// <summary>
    /// FakeRegistryAccessor que lanza en la primera llamada a SetValue.
    /// (FakeRegistryAccessor es sealed, así que se usa composición.)
    /// </summary>
    private sealed class FailingRegistryAccessor : IRegistryAccessor, IRegistryTreeReader, IRegistryKeyCreator
    {
        private readonly FakeRegistryAccessor _inner = new();
        private int _setValueCalls;

        public void Seed(RegistryHive hive, string keyPath, string valueName, object value,
            RegistryValueKind kind = RegistryValueKind.DWord)
        {
            _inner.Seed(hive, keyPath, valueName, value, kind);
        }

        public bool KeyExists(RegistryHive hive, string keyPath) => _inner.KeyExists(hive, keyPath);
        public bool DeleteKey(RegistryHive hive, string keyPath, bool recursive) => _inner.DeleteKey(hive, keyPath, recursive);
        public object? GetValue(RegistryHive hive, string keyPath, string valueName) => _inner.GetValue(hive, keyPath, valueName);
        public void SetValue(RegistryHive hive, string keyPath, string valueName, object value, RegistryValueKind kind)
        {
            _setValueCalls++;
            if (_setValueCalls == 1)
                throw new InvalidOperationException("SetValue falló");
            _inner.SetValue(hive, keyPath, valueName, value, kind);
        }
        public bool DeleteValue(RegistryHive hive, string keyPath, string valueName) => _inner.DeleteValue(hive, keyPath, valueName);
        public IReadOnlyList<string> GetSubKeyNames(RegistryHive hive, string keyPath) => _inner.GetSubKeyNames(hive, keyPath);
        public IReadOnlyList<string> GetValueNames(RegistryHive hive, string keyPath) => _inner.GetValueNames(hive, keyPath);
        public void EnsureKey(RegistryHive hive, string keyPath) => _inner.EnsureKey(hive, keyPath);
    }

    /// <summary>
    /// Decorador de FakeRegistryAccessor que hace fallar EnsureKey en la primera
    /// llamada. Se usa para verificar que el rollback de RegistryDeleteKey
    /// devuelve Failed y conserva la entrada cuando EnsureKey lanza.
    /// FakeRegistryAccessor es sealed, así que se usa composición.
    /// </summary>
    private sealed class FailingEnsureKeyRegistryAccessor : IRegistryAccessor, IRegistryTreeReader, IRegistryKeyCreator
    {
        private readonly FakeRegistryAccessor _inner = new();
        private int _ensureKeyCalls;

        public void Seed(RegistryHive hive, string keyPath, string valueName, object value,
            RegistryValueKind kind = RegistryValueKind.DWord)
        {
            _inner.Seed(hive, keyPath, valueName, value, kind);
        }

        public bool KeyExists(RegistryHive hive, string keyPath) => _inner.KeyExists(hive, keyPath);
        public bool DeleteKey(RegistryHive hive, string keyPath, bool recursive) => _inner.DeleteKey(hive, keyPath, recursive);
        public object? GetValue(RegistryHive hive, string keyPath, string valueName) => _inner.GetValue(hive, keyPath, valueName);
        public void SetValue(RegistryHive hive, string keyPath, string valueName, object value, RegistryValueKind kind) => _inner.SetValue(hive, keyPath, valueName, value, kind);
        public bool DeleteValue(RegistryHive hive, string keyPath, string valueName) => _inner.DeleteValue(hive, keyPath, valueName);
        public IReadOnlyList<string> GetSubKeyNames(RegistryHive hive, string keyPath) => _inner.GetSubKeyNames(hive, keyPath);
        public IReadOnlyList<string> GetValueNames(RegistryHive hive, string keyPath) => _inner.GetValueNames(hive, keyPath);

        public void EnsureKey(RegistryHive hive, string keyPath)
        {
            _ensureKeyCalls++;
            if (_ensureKeyCalls == 1)
                throw new InvalidOperationException("EnsureKey falló");
            _inner.EnsureKey(hive, keyPath);
        }
    }

    /// <summary>
    /// Entrada de diario que siempre falla al restaurarse: usada para verificar
    /// que RollbackAsync continúa tras un error y conserva la entrada fallida.
    /// </summary>
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

    /// <summary>
    /// Implementación en memoria propia de IRegistryAccessor, IRegistryTreeReader,
    /// IRegistryKeyCreator e IRegistryKindReader que cuenta las lecturas de árbol
    /// (GetSubKeyNames / GetValueNames) y permite controlar exactamente cuántas
    /// claves y valores existen por clave, para que los tests de límites de
    /// snapshot (MaxKeys / MaxValues / MaxDepth) sean determinísticos.
    /// </summary>
    private sealed class CountingRegistryAccessor : IRegistryAccessor, IRegistryTreeReader, IRegistryKeyCreator, IRegistryKindReader
    {
        // Clave → diccionario de nombre de valor → (valor, kind)
        private readonly Dictionary<string, Dictionary<string, (object? Value, RegistryValueKind Kind)>> _valuesByKey = new(StringComparer.OrdinalIgnoreCase);
        // Clave → lista de nombres de subclaves
        private readonly Dictionary<string, List<string>> _subKeysByKey = new(StringComparer.OrdinalIgnoreCase);
        // Claves conocidas (para KeyExists / GetValue / etc.)
        private readonly HashSet<(RegistryHive, string)> _knownKeys = new();

        private int _subKeyReads;
        private int _valueReads;

        public int SubKeyReads => _subKeyReads;
        public int ValueReads => _valueReads;

        public void Seed(RegistryHive hive, string keyPath, string valueName, object value,
            RegistryValueKind kind = RegistryValueKind.DWord)
        {
            var parts = keyPath.Split('\\');
            // Registrar cada nivel intermedio como subclave de su padre, para que
            // GetSubKeyNames devuelva el árbol completo y los límites de snapshot
            // (MaxKeys / MaxDepth) se disparen de forma determinística.
            for (int i = 1; i < parts.Length; i++)
            {
                var parent = string.Join("\\", parts, 0, i);
                var child = string.Join("\\", parts, 0, i + 1);
                if (!_valuesByKey.ContainsKey(parent))
                {
                    _valuesByKey[parent] = new(StringComparer.OrdinalIgnoreCase);
                    _subKeysByKey[parent] = new();
                }
                if (!_subKeysByKey[parent].Contains(child))
                    _subKeysByKey[parent].Add(child);
                if (!_valuesByKey.ContainsKey(child))
                {
                    _valuesByKey[child] = new(StringComparer.OrdinalIgnoreCase);
                    _subKeysByKey[child] = new();
                }
                _knownKeys.Add((RegistryHive.LocalMachine, child));
            }
            // Registrar el valor en el nodo final.
            if (!_valuesByKey.ContainsKey(keyPath))
            {
                _valuesByKey[keyPath] = new(StringComparer.OrdinalIgnoreCase);
                _subKeysByKey[keyPath] = new();
            }
            _knownKeys.Add((hive, keyPath));
            _valuesByKey[keyPath][valueName] = (value, kind);
        }

        public void SeedSubKey(string parentKeyPath, string childKeyPath)
        {
            if (!_valuesByKey.ContainsKey(parentKeyPath))
            {
                _valuesByKey[parentKeyPath] = new(StringComparer.OrdinalIgnoreCase);
                _subKeysByKey[parentKeyPath] = new();
            }
            if (!_subKeysByKey[parentKeyPath].Contains(childKeyPath))
                _subKeysByKey[parentKeyPath].Add(childKeyPath);
            if (!_valuesByKey.ContainsKey(childKeyPath))
            {
                _valuesByKey[childKeyPath] = new(StringComparer.OrdinalIgnoreCase);
                _subKeysByKey[childKeyPath] = new();
            }
            _knownKeys.Add((RegistryHive.LocalMachine, childKeyPath));
        }

        public bool KeyExists(RegistryHive hive, string keyPath) => _knownKeys.Contains((hive, keyPath)) || _valuesByKey.ContainsKey(keyPath);
        public bool DeleteKey(RegistryHive hive, string keyPath, bool recursive)
        {
            if (!_valuesByKey.Remove(keyPath)) return false;
            _subKeysByKey.Remove(keyPath);
            return true;
        }
        public object? GetValue(RegistryHive hive, string keyPath, string valueName) =>
            _valuesByKey.TryGetValue(keyPath, out var vals) && vals.TryGetValue(valueName, out var entry)
                ? entry.Value : null;
        public void SetValue(RegistryHive hive, string keyPath, string valueName, object value, RegistryValueKind kind)
        {
            if (!_valuesByKey.ContainsKey(keyPath))
            {
                _valuesByKey[keyPath] = new(StringComparer.OrdinalIgnoreCase);
                _subKeysByKey[keyPath] = new();
            }
            _knownKeys.Add((hive, keyPath));
            _valuesByKey[keyPath][valueName] = (value, kind);
        }
        public bool DeleteValue(RegistryHive hive, string keyPath, string valueName) =>
            _valuesByKey.TryGetValue(keyPath, out var vals) && vals.Remove(valueName);
        public void EnsureKey(RegistryHive hive, string keyPath)
        {
            if (!_valuesByKey.ContainsKey(keyPath))
            {
                _valuesByKey[keyPath] = new(StringComparer.OrdinalIgnoreCase);
                _subKeysByKey[keyPath] = new();
            }
            _knownKeys.Add((hive, keyPath));
        }
        public IReadOnlyList<string> GetSubKeyNames(RegistryHive hive, string keyPath)
        {
            _subKeyReads++;
            return _subKeysByKey.TryGetValue(keyPath, out var list) ? list : Array.Empty<string>();
        }
        public IReadOnlyList<string> GetValueNames(RegistryHive hive, string keyPath)
        {
            _valueReads++;
            return _valuesByKey.TryGetValue(keyPath, out var vals) ? new List<string>(vals.Keys) : Array.Empty<string>();
        }
        public RegistryValueKind GetKind(RegistryHive hive, string keyPath, string valueName) =>
            _valuesByKey.TryGetValue(keyPath, out var vals) && vals.TryGetValue(valueName, out var entry)
                ? entry.Kind : RegistryValueKind.Unknown;
    }
}
