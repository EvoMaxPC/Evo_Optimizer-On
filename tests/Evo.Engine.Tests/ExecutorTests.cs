using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.System;
using Evo.Engine.Execution;
using Evo.Engine.Executors;
using Evo.Engine.Undo;
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
