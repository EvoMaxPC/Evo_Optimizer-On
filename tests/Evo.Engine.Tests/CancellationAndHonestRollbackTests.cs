using Evo.Core.Actions;
using Evo.Core.System;
using Evo.Engine.Execution;
using Evo.Engine.Undo;
using Evo.Testing;
using Microsoft.Win32;
using Xunit;

namespace Evo.Engine.Tests;

/// <summary>Etapa 1: cancelación honesta (H1) y rollback honesto (H2).</summary>
public sealed class CancellationAndHonestRollbackTests
{
    private const string KeyPath = @"SOFTWARE\Evo\Etapa1";

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

    // ---------------- H1: cancelación ----------------

    [Fact]
    public async Task CancelacionAntesDeCualquierMutacion_RetornaCanceladoSinRollback()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        harness.Registry.ResetSetValueCounter();

        var actions = new CapabilityAction[] { SetDword(1, "A", "99") };
        var contract = TestHarness.Contract(actions);
        var context = harness.Context(ExecutionMode.Execute);
        var cts = new CancellationTokenSource();
        cts.Cancel();

        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, context, cts.Token);

        Assert.Equal("Cancelado", summary.AbortedReason);
        Assert.True(summary.Aborted);
        Assert.Empty(summary.Results);
        Assert.Null(summary.RollbackReport);
        Assert.Equal(RollbackOutcome.None, summary.RollbackOutcome);
        Assert.Empty(summary.UndoJournalEntry);
        // Nada mutó
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A"));
    }

    [Fact]
    public async Task CancelacionTrasMutacion_RollbackYCanceladoConInforme()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "B", 2);
        harness.Registry.ResetSetValueCounter();
        // La 2ª escritura (acción 2) lanza OperationCanceledException: simula cancelación durante la acción.
        harness.Registry.ThrowOnSetValueCall = 2;

        var actions = new CapabilityAction[]
        {
            SetDword(1, "A", "111"), // se aplica
            SetDword(2, "B", "222"), // SetValue lanza OCE
        };
        var contract = TestHarness.Contract(actions);
        var context = harness.Context(ExecutionMode.Execute);

        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, context, CancellationToken.None);

        Assert.Equal("Cancelado", summary.AbortedReason);
        Assert.True(summary.Aborted);
        // A se deshace (vuelve a 1); B nunca se aplicó
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A"));
        Assert.Null(harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "B"));
        // Informe de rollback: solo A (1 entrada) restaurada, sin fallos
        Assert.NotNull(summary.RollbackReport);
        var report = summary.RollbackReport!;
        Assert.Single(report.Restored);
        Assert.Empty(report.NotReversible);
        Assert.Empty(report.Failed);
        Assert.True(report.Success);
        Assert.Equal(RollbackOutcome.RolledBack, summary.RollbackOutcome);
        Assert.Single(summary.UndoJournalEntry);
    }

    [Fact]
    public async Task CancelacionEntreAcciones_RollbackDeLaPrimera()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        harness.Registry.ResetSetValueCounter();
        // La escritura de la acción 2 se cancela: la acción 1 ya se aplicó y debe deshacerse.
        harness.Registry.ThrowOnSetValueCall = 2;

        var actions = new CapabilityAction[]
        {
            SetDword(1, "A", "111"), // se aplica
            SetDword(2, "B", "222"), // no llega a aplicarse (cancelación observada antes de su efecto)
        };
        var contract = TestHarness.Contract(actions);
        var context = harness.Context(ExecutionMode.Execute);

        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, context, CancellationToken.None);

        Assert.Equal("Cancelado", summary.AbortedReason);
        Assert.True(summary.Aborted);
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A"));
        Assert.Null(harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "B"));
        Assert.NotNull(summary.RollbackReport);
        var report = summary.RollbackReport!;
        Assert.Single(report.Restored);
        Assert.Empty(report.Failed);
        Assert.Equal(RollbackOutcome.RolledBack, summary.RollbackOutcome);
    }

    [Fact]
    public async Task CancelacionEnDryRun_SinCambiosNiRollback()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        var cts = new CancellationTokenSource();
        cts.Cancel();

        var actions = new CapabilityAction[] { SetDword(1, "A", "99") };
        var contract = TestHarness.Contract(actions);
        var context = harness.Context(ExecutionMode.DryRun);

        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.DryRun, context, cts.Token);

        Assert.Equal("Cancelado", summary.AbortedReason);
        Assert.True(summary.Aborted);
        Assert.False(summary.Mutated);
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A"));
        Assert.Null(summary.RollbackReport);
        Assert.Equal(RollbackOutcome.None, summary.RollbackOutcome);
    }

    // ---------------- H2: rollback honesto ----------------

    private static UndoContext BuildContext(
        FakeRegistryAccessor registry,
        FakeServiceAccessor services,
        FakeTaskAccessor tasks,
        FakeProcessAccessor processes,
        FakeCommandRunner commands,
        bool dryRun = false) =>
        new(registry, services, tasks, processes, commands, dryRun);

    [Fact]
    public async Task RollbackTodoRestored_InformeTodosRestauradosYEstadoReal()
    {
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V", 1);
        var services = new FakeServiceAccessor();
        services.Seed("Svc", ServiceStatus.Stopped, ServiceStartupType.Automatic);

        var journal = new UndoJournal();
        journal.Add(new RegistryUndoEntry
        {
            CapabilityId = "c", ActionKey = "reg", Description = "reg", PreviousState = "1",
            Hive = RegistryHive.LocalMachine, KeyPath = @"SOFTWARE\Evo\X", ValueName = "V",
            ExistedBefore = true, PreviousValue = 1, PreviousKind = RegistryValueKind.DWord,
        });
        journal.Add(new ServiceUndoEntry
        {
            CapabilityId = "c", ActionKey = "svc", Description = "svc", PreviousState = "Stopped",
            ServiceName = "Svc", StartupTypeChanged = false, PreviousStartupType = ServiceStartupType.Unknown,
            StatusChanged = true, PreviousStatus = ServiceStatus.Running,
        });

        var report = await journal.RollbackAsync(BuildContext(
            registry, services, new FakeTaskAccessor(), new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.True(report.Success);
        Assert.Equal(2, report.Count);
        Assert.Equal(2, report.Restored.Count);
        Assert.Empty(report.NotReversible);
        Assert.Empty(report.Failed);
        Assert.True(report.AllReversible);
        // Estado real restaurado
        Assert.Equal(1, (int?)registry.GetValue(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V"));
        Assert.Equal(ServiceStatus.Running, services.GetStatus("Svc"));
        // Diario vacío tras rollback exitoso
        Assert.True(journal.IsEmpty);
    }

    [Fact]
    public async Task RollbackConEntradaNoReversible_NoCuentaComoRestaurada()
    {
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V", 1);
        var processes = new FakeProcessAccessor();
        processes.Seed("SearchHost", running: true);

        var journal = new UndoJournal();
        journal.Add(new RegistryUndoEntry
        {
            CapabilityId = "c", ActionKey = "reg", Description = "reg", PreviousState = "1",
            Hive = RegistryHive.LocalMachine, KeyPath = @"SOFTWARE\Evo\X", ValueName = "V",
            ExistedBefore = true, PreviousValue = 1, PreviousKind = RegistryValueKind.DWord,
        });
        journal.Add(new NotReversibleEntry
        {
            CapabilityId = "c", ActionKey = "proc", Description = "proc", PreviousState = "Running",
        });

        var report = await journal.RollbackAsync(BuildContext(
            registry, new FakeServiceAccessor(), new FakeTaskAccessor(), processes, new FakeCommandRunner()));

        Assert.True(report.Success); // no hubo excepciones
        Assert.Equal(1, report.Restored.Count);
        Assert.Single(report.NotReversible);
        Assert.Empty(report.Failed);
        Assert.True(report.HasUnrestorable);
        Assert.False(report.AllReversible);
        // El registro sí se restauró; la entrada no reversible no se restauró
        Assert.Equal(1, (int?)registry.GetValue(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V"));
        Assert.Empty(processes.Started);
        // Diario vacío: todo se procesó y nada falló
        Assert.True(journal.IsEmpty);
    }

    [Fact]
    public async Task RollbackEntradaQueFalla_QuedaFailedYSeContinua()
    {
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V", 1);
        var journal = new UndoJournal();
        journal.Add(new RegistryUndoEntry
        {
            CapabilityId = "c", ActionKey = "ok", Description = "ok", PreviousState = "1",
            Hive = RegistryHive.LocalMachine, KeyPath = @"SOFTWARE\Evo\X", ValueName = "V",
            ExistedBefore = true, PreviousValue = 1, PreviousKind = RegistryValueKind.DWord,
        });
        journal.Add(new FailingEntry { CapabilityId = "c", ActionKey = "fail", Description = "fail", PreviousState = null });

        var report = await journal.RollbackAsync(BuildContext(
            registry, new FakeServiceAccessor(), new FakeTaskAccessor(), new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.False(report.Success);
        Assert.Single(report.Restored);
        Assert.Empty(report.NotReversible);
        Assert.Single(report.Failed);
        Assert.Single(report.Errors);
        Assert.Contains("boom", report.Errors[0]);
        // La que se pudo deshacer, se deshizo
        Assert.Equal(1, (int?)registry.GetValue(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V"));
        // El diario conserva solo la fallida para reintento
        Assert.False(journal.IsEmpty);
        Assert.Single(journal.Entries);
        Assert.Equal("fail", journal.Entries[0].ActionKey);
    }

    [Fact]
    public async Task RollbackMezcla_InformeExactoYOrdenLifo()
    {
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V", 1);
        var processes = new FakeProcessAccessor();
        processes.Seed("SearchHost", running: true);

        var journal = new UndoJournal();
        journal.Add(new RegistryUndoEntry
        {
            CapabilityId = "c", ActionKey = "first", Description = "first", PreviousState = "1",
            Hive = RegistryHive.LocalMachine, KeyPath = @"SOFTWARE\Evo\X", ValueName = "V",
            ExistedBefore = true, PreviousValue = 1, PreviousKind = RegistryValueKind.DWord,
        });
        journal.Add(new NotReversibleEntry
        {
            CapabilityId = "c", ActionKey = "second", Description = "second", PreviousState = "Running",
        });
        journal.Add(new FailingEntry { CapabilityId = "c", ActionKey = "third", Description = "third", PreviousState = null });

        var report = await journal.RollbackAsync(BuildContext(
            registry, new FakeServiceAccessor(), new FakeTaskAccessor(), processes, new FakeCommandRunner()));

        // Se procesan todas las entradas (LIFO): first, second, third
        Assert.Equal(3, report.Restored.Count + report.NotReversible.Count + report.Failed.Count);
        Assert.Single(report.Restored);
        Assert.Single(report.NotReversible);
        Assert.Single(report.Failed);
        Assert.False(report.Success);
        Assert.Equal(RollbackOutcome.PartiallyRolledBack, ComputeOutcome(report));
        // Estado real: registro restaurado, la no reversible no se tocó
        Assert.Equal(1, (int?)registry.GetValue(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V"));
        Assert.Empty(processes.Started);
    }

    [Fact]
    public async Task RollbackSegundoIntento_SoloReprocesaLasConservadas()
    {
        var calls = new int[1];
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V", 99);
        var journal = new UndoJournal();
        journal.Add(new CounterEntry
        {
            CapabilityId = "c", ActionKey = "ok", Description = "ok", PreviousState = "1",
            Calls = calls,
        });
        journal.Add(new FailingEntry { CapabilityId = "c", ActionKey = "fail", Description = "fail", PreviousState = null });

        var ctx = BuildContext(
            registry, new FakeServiceAccessor(), new FakeTaskAccessor(), new FakeProcessAccessor(), new FakeCommandRunner());
        var r1 = await journal.RollbackAsync(ctx);

        Assert.False(r1.Success);
        Assert.Single(r1.Restored);
        Assert.Single(r1.Failed);
        Assert.Equal(1, calls[0]); // "ok" restaurado una vez
        Assert.Single(journal.Entries); // solo "fail" conservada
        Assert.Equal("fail", journal.Entries[0].ActionKey);

        var r2 = await journal.RollbackAsync(ctx);
        Assert.False(r2.Success); // "fail" falla de nuevo
        Assert.Equal(1, calls[0]); // "ok" NO se reprocesó
        Assert.Single(journal.Entries); // "fail" sigue conservada
    }

    [Fact]
    public async Task RollbackEnDryRun_InformeNoReversibleYSinVaciarDiario()
    {
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V", 1);
        var journal = new UndoJournal();
        journal.Add(new RegistryUndoEntry
        {
            CapabilityId = "c", ActionKey = "ok", Description = "ok", PreviousState = "1",
            Hive = RegistryHive.LocalMachine, KeyPath = @"SOFTWARE\Evo\X", ValueName = "V",
            ExistedBefore = true, PreviousValue = 1, PreviousKind = RegistryValueKind.DWord,
        });

        var report = await journal.RollbackAsync(BuildContext(
            registry, new FakeServiceAccessor(), new FakeTaskAccessor(), new FakeProcessAccessor(), new FakeCommandRunner(), dryRun: true));

        Assert.Empty(report.Restored);
        Assert.Single(report.NotReversible); // en DryRun no se restaura de verdad
        Assert.Empty(report.Failed);
        Assert.True(report.Success);
        // En DryRun el diario no se vacía ni se muta
        Assert.False(journal.IsEmpty);
        Assert.Equal(1, (int?)registry.GetValue(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V"));
    }

    // ---------------- Helpers ----------------

    private sealed record FailingEntry : UndoJournalEntry
    {
        public override UndoEntryOutcome Restore(IUndoContext context) =>
            new()
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.Failed,
                FailureMessage = "boom",
            };
    }

    private sealed record CounterEntry : UndoJournalEntry
    {
        public int[] Calls { get; init; } = Array.Empty<int>();

        public override UndoEntryOutcome Restore(IUndoContext context)
        {
            Calls[0]++;
            return new UndoEntryOutcome
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.Restored,
            };
        }
    }

    /// <summary>Entrada de prueba que nunca se puede revertir (devuelve NotReversible).</summary>
    private sealed record NotReversibleEntry : UndoJournalEntry
    {
        public override UndoEntryOutcome Restore(IUndoContext context) =>
            new()
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.NotReversible,
            };
    }

    private static RollbackOutcome ComputeOutcome(RollbackReport report)
    {
        if (report.Failed.Count > 0 && report.Restored.Count == 0)
        {
            return RollbackOutcome.RollbackFailed;
        }

        if (report.Failed.Count > 0)
        {
            return RollbackOutcome.PartiallyRolledBack;
        }

        if (report.NotReversible.Count > 0)
        {
            return RollbackOutcome.RolledBackWithUnrestorable;
        }

        return RollbackOutcome.RolledBack;
    }
}
