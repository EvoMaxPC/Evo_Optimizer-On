using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.System;
using Evo.Engine;
using Evo.Engine.Execution;
using Microsoft.Win32;
using Xunit;

namespace Evo.Engine.Tests;

/// <summary>Los cinco escenarios exigidos por el prompt 7 (T4.1).</summary>
public sealed class EngineCoordinatorTests
{
    private const string KeyPath = @"SOFTWARE\Evo\Test";

    private static RegistryAction SetDword(int order, string name, string value) => new()
    {
        Order = order,
        Description = $"set {name}",
        Hive = RegistryHiveKind.LocalMachine,
        KeyPath = KeyPath,
        ValueName = name,
        Operation = RegistryOperation.Set,
        ValueType = RegistryValueType.DWord,
        Value = value,
    };

    private static ServiceAction StopService(int order, string name) => new()
    {
        Order = order,
        Description = $"stop {name}",
        ServiceName = name,
        Operation = ServiceOperation.Stop,
    };

    [Fact]
    public async Task TestDryRun_DoesNotMutateSystem()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "DiagTrack", 1);
        harness.Services.Seed("DiagTrack", ServiceStatus.Running, ServiceStartupType.Automatic);
        var mutationsBefore = harness.Registry.MutationCount + harness.Services.MutationCount;

        var actions = new CapabilityAction[]
        {
            SetDword(1, "DiagTrack", "0"),
            StopService(2, "DiagTrack"),
        };
        var contract = TestHarness.Contract(actions);
        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.DryRun, harness.Context(ExecutionMode.DryRun));

        // Nada mutó
        Assert.Equal(mutationsBefore, harness.Registry.MutationCount + harness.Services.MutationCount);
        Assert.Equal(1, harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "DiagTrack"));
        Assert.Equal(ServiceStatus.Running, harness.Services.GetStatus("DiagTrack"));

        // Pero se informa de lo que habría cambiado
        Assert.False(summary.Mutated);
        Assert.Equal(2, summary.Succeeded);
        Assert.Equal(0, summary.Failed);
        var first = summary.Results[0];
        Assert.Equal("1", first.PreviousState);
        Assert.Equal("0", first.NewState);
        Assert.Empty(summary.UndoJournalEntry);
        Assert.Equal(2, summary.PlannedActions.Count);
    }

    [Fact]
    public async Task TestExecute_MutatesSystemAndCreatesUndo()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "DiagTrack", 1);
        harness.Services.Seed("DiagTrack", ServiceStatus.Running, ServiceStartupType.Automatic);

        var actions = new CapabilityAction[]
        {
            new RegistryAction
            {
                Order = 1,
                Description = "DiagTrack => 0",
                Hive = RegistryHiveKind.LocalMachine,
                KeyPath = KeyPath,
                ValueName = "DiagTrack",
                Operation = RegistryOperation.Set,
                ValueType = RegistryValueType.DWord,
                Value = "0",
            },
            new ServiceAction
            {
                Order = 2,
                Description = "DiagTrack startup Manual",
                ServiceName = "DiagTrack",
                Operation = ServiceOperation.SetStartupType,
                StartupType = "Manual",
            },
        };
        var contract = TestHarness.Contract(actions);
        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));

        Assert.True(summary.Mutated);
        Assert.Equal(2, summary.Succeeded);
        Assert.Equal(0, harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "DiagTrack"));
        Assert.Equal(ServiceStartupType.Manual, harness.Services.GetStartupType("DiagTrack"));

        // El diario guarda el estado previo exacto
        Assert.Equal(2, summary.UndoJournalEntry.Count);
        var registryEntry = Assert.IsType<Undo.RegistryUndoEntry>(summary.UndoJournalEntry[0]);
        Assert.Equal("1", registryEntry.PreviousState);
        Assert.True(registryEntry.ExistedBefore);
        Assert.Equal(1, registryEntry.PreviousValue);
        Assert.Equal(RegistryValueKind.DWord, registryEntry.PreviousKind);

        var serviceEntry = Assert.IsType<Undo.ServiceUndoEntry>(summary.UndoJournalEntry[1]);
        Assert.Equal(ServiceStartupType.Automatic, serviceEntry.PreviousStartupType);
        Assert.Equal(ServiceStatus.Running, serviceEntry.PreviousStatus);
    }

    [Fact]
    public async Task TestRollback_RestoresOriginalStateExactly()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 10);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "B", 20);
        harness.Services.Seed("Svc1", ServiceStatus.Running, ServiceStartupType.Automatic);
        harness.Services.Seed("Svc2", ServiceStatus.Stopped, ServiceStartupType.Manual);

        var registryBefore = harness.Registry.Snapshot();
        var servicesBefore = harness.Services.Snapshot();

        var actions = new CapabilityAction[]
        {
            SetDword(1, "A", "99"),
            SetDword(2, "B", "42"),
            new RegistryAction
            {
                Order = 3,
                Description = "borrar A",
                Hive = RegistryHiveKind.LocalMachine,
                KeyPath = KeyPath,
                ValueName = "C",
                Operation = RegistryOperation.Set,
                ValueType = RegistryValueType.String,
                Value = "nuevo",
            },
            StopService(4, "Svc1"),
            new ServiceAction
            {
                Order = 5,
                Description = "Svc2 arranque Automatic",
                ServiceName = "Svc2",
                Operation = ServiceOperation.SetStartupType,
                StartupType = "Automatic",
            },
        };

        var contract = TestHarness.Contract(actions);
        var context = harness.Context(ExecutionMode.Execute);
        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, context);

        Assert.Equal(5, summary.Succeeded);
        Assert.Equal(5, summary.UndoJournalEntry.Count);

        var rollback = await harness.Coordinator.RollbackAsync(context);

        Assert.True(rollback.Success);
        Assert.Equal(5, rollback.Count);
        // Estado original restaurado exactamente
        Assert.Equal(10, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A"));
        Assert.Equal(20, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "B"));
        Assert.Null(harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "C"));
        Assert.Equal(ServiceStatus.Running, harness.Services.GetStatus("Svc1"));
        Assert.Equal(ServiceStartupType.Manual, harness.Services.GetStartupType("Svc2"));
        Assert.Equal(registryBefore.Count, harness.Registry.Snapshot().Count);
        Assert.Equal(servicesBefore.Count, harness.Services.Snapshot().Count);
        Assert.True(harness.Coordinator.Journal.IsEmpty);
    }

    [Fact]
    public async Task TestPartialFailure_TriggersRollback()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "B", 2);
        harness.Commands.Throw("explode.exe --now");

        var actions = new CapabilityAction[]
        {
            SetDword(1, "A", "111"),
            SetDword(2, "B", "222"),
            new CommandAction
            {
                Order = 3,
                Description = "comando que falla",
                FileName = "explode.exe",
                Arguments = ["--now"],
            },
            SetDword(4, "A", "333"),
        };

        var contract = TestHarness.Contract(actions);
        var context = harness.Context(ExecutionMode.Execute);
        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, context);

        Assert.Equal(1, summary.Failed);
        Assert.Equal(2, summary.Succeeded);
        Assert.Equal(3, summary.Results.Count); // la cuarta ya no se intenta
        Assert.Contains("fallo simulado", summary.Results[2].ErrorMessage, StringComparison.Ordinal);

        // Rollback automático: A y B vuelven a su valor inicial
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A"));
        Assert.Equal(2, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "B"));
        Assert.True(harness.Coordinator.Journal.IsEmpty);
    }

    [Fact]
    public async Task TestPrivilegeEnforcement()
    {
        var harness = TestHarness.Create(admin: false);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);

        var actions = new CapabilityAction[] { SetDword(1, "A", "0") };

        var adminContract = TestHarness.Contract(actions, privilege: PrivilegeLevel.Admin);
        var blocked = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(adminContract, actions), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));

        Assert.True(blocked.Blocked);
        Assert.Contains("Admin", blocked.BlockedReason, StringComparison.Ordinal);
        Assert.Empty(blocked.Results);
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A"));

        var tiContract = TestHarness.Contract(
            actions,
            risk: RiskLevel.Critical,
            privilege: PrivilegeLevel.TrustedInstaller,
            restore: RestoreLevel.FullBackup);
        var tiBlocked = harness.Coordinator.Preflight(tiContract);

        Assert.False(tiBlocked.Allowed);
        Assert.Contains("TrustedInstaller", tiBlocked.Reason, StringComparison.Ordinal);
        Assert.Equal(PrivilegeLevel.User, tiBlocked.EffectivePrivilege);

        // La misma capacidad con privilegios pasa
        var elevated = TestHarness.Create(admin: true);
        elevated.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        var allowed = await elevated.Coordinator.ExecuteAsync(
            TestHarness.Plan(adminContract, actions), ExecutionMode.Execute, elevated.Context(ExecutionMode.Execute));
        Assert.False(allowed.Blocked);
        Assert.Equal(1, allowed.Succeeded);
    }

    [Fact]
    public async Task IncompatibleSystemBlocksExecution()
    {
        var harness = TestHarness.Create(build: 99999);
        var actions = new CapabilityAction[] { SetDword(1, "A", "0") };
        var contract = TestHarness.Contract(actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));

        Assert.True(summary.Blocked);
        Assert.Contains("UNKNOWN_BUILD_REJECTED", summary.BlockedReason, StringComparison.Ordinal);
    }

    [Fact]
    public void PreflightChecksDependenciesAndConflicts()
    {
        var harness = TestHarness.Create();
        var actions = new CapabilityAction[] { SetDword(1, "A", "0") };

        var withDependency = TestHarness.Contract(actions, dependsOn: ["base.capability"]);
        Assert.False(harness.Coordinator.Preflight(withDependency).Allowed);
        Assert.True(harness.Coordinator.Preflight(withDependency, ["base.capability"]).Allowed);

        var withConflict = TestHarness.Contract(actions, conflictsWith: ["other.capability"]);
        Assert.True(harness.Coordinator.Preflight(withConflict).Allowed);
        var conflicted = harness.Coordinator.Preflight(withConflict, ["other.capability"]);
        Assert.False(conflicted.Allowed);
        Assert.Contains("Conflicto", conflicted.Reason, StringComparison.Ordinal);
    }

    [Fact]
    public async Task AuditModeReportsStateWithoutMutating()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 7);
        var actions = new CapabilityAction[] { SetDword(1, "A", "0") };
        var contract = TestHarness.Contract(actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Audit, harness.Context(ExecutionMode.Audit));

        Assert.Equal(ExecutionMode.Audit, summary.Mode);
        Assert.Equal(1, summary.Skipped);
        Assert.Equal("7", summary.Results[0].ErrorMessage);
        Assert.Equal(7, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A"));
    }
}
