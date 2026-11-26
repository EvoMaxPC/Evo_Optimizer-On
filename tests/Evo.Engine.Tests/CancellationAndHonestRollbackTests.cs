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

    /// <summary>
    /// 1. Cancelación antes de cualquier mutación: Cancelado sin rollback, sin
    /// excepción, estado fake intacto, RollbackReport null, RollbackOutcome None.
    /// </summary>
    [Fact]
    public async Task CancelacionAntes_RetornaCanceladoSinRollback()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        harness.Registry.ResetSetValueCounter();

        var actions = new CapabilityAction[] { SetDword(1, "A", "99") };
        var contract = TestHarness.Contract(actions);
        var context = harness.Context(ExecutionMode.Execute);
        var cts = new CancellationTokenSource();
        cts.Cancel(); // token cancelado ANTES de ExecuteAsync

        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, context, cts.Token);

        Assert.Equal("Cancelado", summary.AbortedReason);
        Assert.True(summary.Aborted);
        Assert.Empty(summary.Results);
        Assert.Null(summary.RollbackReport);
        Assert.Equal(RollbackOutcome.None, summary.RollbackOutcome);
        Assert.Empty(summary.UndoJournalEntry);
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A"));
    }

    /// <summary>
    /// 2. Cancelación tras mutación reversible: la primera acción se deshace y el
    /// FakeRegistry vuelve al valor ORIGINAL; Cancelled + RolledBack.
    /// </summary>
    [Fact]
    public async Task CancelacionTrasMutacionReversible_FakeRegistryVuelveAlOriginal()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "B", 2);
        harness.Registry.ResetSetValueCounter();
        // La 2ª escritura (SetValue #2) lanza OperationCanceledException.
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
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A")); // vuelve al original
        Assert.Null(harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "B")); // nunca se aplicó
        Assert.NotNull(summary.RollbackReport);
        var report = summary.RollbackReport!;
        Assert.Single(report.Restored);
        Assert.Empty(report.NotReversible);
        Assert.Empty(report.Failed);
        Assert.True(report.Success);
        Assert.Equal(RollbackOutcome.RolledBack, summary.RollbackOutcome);
        Assert.Single(summary.UndoJournalEntry);
    }

    /// <summary>
    /// 3. Cancelación entre acciones: el hook cancela el cts al terminar la primera
    /// acción (sin lanzar); el bucle detecta el token antes de la segunda; la
    /// segunda NO se aplica; la primera se deshace.
    /// </summary>
    [Fact]
    public async Task CancelacionEntreAcciones_RollbackDeLaPrimera()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        harness.Registry.ResetSetValueCounter();
        // Tras la 1ª escritura se cancela el token (sin lanzar OCE aún).
        var cts = new CancellationTokenSource();
        harness.Registry.OnSetValue = call => { if (call == 1) cts.Cancel(); };

        var actions = new CapabilityAction[]
        {
            SetDword(1, "A", "111"), // se aplica, luego se cancela
            SetDword(2, "B", "222"), // no se aplica (token cancelado al entrar)
        };
        var contract = TestHarness.Contract(actions);
        var context = harness.Context(ExecutionMode.Execute);

        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, context, cts.Token);

        Assert.Equal("Cancelado", summary.AbortedReason);
        Assert.True(summary.Aborted);
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A")); // deshecho
        Assert.Null(harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "B")); // nunca se aplicó
        Assert.NotNull(summary.RollbackReport);
        var report = summary.RollbackReport!;
        Assert.Single(report.Restored);
        Assert.Empty(report.Failed);
        Assert.Equal(RollbackOutcome.RolledBack, summary.RollbackOutcome);
    }

    /// <summary>
    /// 4. Token cancelado DURANTE la acción: el hook hace cts.Cancel() y luego
    /// ThrowIfCancellationRequested() en la segunda acción; resultado Cancelled;
    /// el rollback se completa aunque el token YA esté cancelado
    /// (RollbackAsync usa CancellationToken.None).
    /// </summary>
    [Fact]
    public async Task TokenCanceladoDuranteLaAccion_RollbackSeCompletaConTokenNone()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "B", 2);
        harness.Registry.ResetSetValueCounter();
        var cts = new CancellationTokenSource();
        // En la 2ª escritura: cancela y lanza OCE dentro de la acción.
        harness.Registry.OnSetValue = call =>
        {
            if (call == 2)
            {
                cts.Cancel();
                cts.Token.ThrowIfCancellationRequested();
            }
        };

        var actions = new CapabilityAction[]
        {
            SetDword(1, "A", "111"), // se aplica
            SetDword(2, "B", "222"), // OCE dentro de la acción
        };
        var contract = TestHarness.Contract(actions);
        var context = harness.Context(ExecutionMode.Execute);

        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, context, cts.Token);

        Assert.Equal("Cancelado", summary.AbortedReason);
        Assert.True(summary.Aborted);
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A")); // deshecho
        Assert.Null(harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "B")); // nunca se aplicó
        Assert.NotNull(summary.RollbackReport);
        var report = summary.RollbackReport!;
        Assert.Single(report.Restored);
        Assert.Equal(RollbackOutcome.RolledBack, summary.RollbackOutcome);
    }

    /// <summary>
    /// 5. Cancelación DURANTE el rollback: 3 acciones aplicadas, la 3ª lanza OCE
    /// (dispara rollback); el hook cancela el cts durante la PRIMERA restauración.
    /// El rollback se completa entero (usa CancellationToken.None) y el resumen es
    /// Cancelled con RolledBack. La cancelación durante el rollback se ignora.
    /// </summary>
    [Fact]
    public async Task CancelacionDuranteElRollback_SeIgnoraYElRollbackSeCompleta()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "B", 2);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "C", 3);
        harness.Registry.ResetSetValueCounter();
        var cts = new CancellationTokenSource();
        // SetValue #3 (la 3ª acción) lanza OCE; #4 (1ª restauración) cancela el cts.
        harness.Registry.OnSetValue = call =>
        {
            if (call == 3) cts.Token.ThrowIfCancellationRequested(); // nunca llega: C se cancela antes
            if (call == 4) cts.Cancel(); // durante la 1ª restauración
        };
        // Forzar que la 3ª acción lance OCE: ThrowOnSetValueCall = 3.
        harness.Registry.ThrowOnSetValueCall = 3;

        var actions = new CapabilityAction[]
        {
            SetDword(1, "A", "111"), // se aplica (SetValue #1)
            SetDword(2, "B", "222"), // se aplica (SetValue #2)
            SetDword(3, "C", "333"), // lanza OCE (SetValue #3) -> dispara rollback
        };
        var contract = TestHarness.Contract(actions);
        var context = harness.Context(ExecutionMode.Execute);

        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, context, cts.Token);

        Assert.Equal("Cancelado", summary.AbortedReason);
        Assert.True(summary.Aborted);
        // Rollback completo a pesar de la cancelación durante el rollback
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A"));
        Assert.Equal(2, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "B"));
        Assert.Equal(3, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "C"));
        Assert.NotNull(summary.RollbackReport);
        var report = summary.RollbackReport!;
        Assert.Equal(2, report.Restored.Count); // B y A (LIFO)
        Assert.Empty(report.Failed);
        Assert.Equal(RollbackOutcome.RolledBack, summary.RollbackOutcome);
        Assert.True(harness.Coordinator.Journal.IsEmpty);
    }

    /// <summary>
    /// 6. DryRun cancelado: Cancelled, Mutated=false, sin journal, sin rollback.
    /// </summary>
    [Fact]
    public async Task DryRunCancelado_CanceladoSinMutar()
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

    // ---------------- H2: rollback honesto (llamada directa a UndoJournal) ----------------

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
        Assert.Equal(1, (int?)registry.GetValue(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V"));
        Assert.Equal(ServiceStatus.Running, services.GetStatus("Svc"));
        Assert.True(journal.IsEmpty);
    }

    [Fact]
    public async Task RollbackConNotReversible_NoCuentaComoRestaurada()
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

        Assert.True(report.Success);
        Assert.Equal(1, report.Restored.Count);
        Assert.Single(report.NotReversible);
        Assert.Empty(report.Failed);
        Assert.True(report.HasUnrestorable);
        Assert.False(report.AllReversible);
        Assert.Equal(1, (int?)registry.GetValue(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V"));
        Assert.Empty(processes.Started);
        Assert.True(journal.IsEmpty);
    }

    [Fact]
    public async Task RollbackExcepcionQuedaFailed_SeConservaYSeContinua()
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
        journal.Add(new ThrowingEntry { CapabilityId = "c", ActionKey = "fail", Description = "fail", PreviousState = null });

        var report = await journal.RollbackAsync(BuildContext(
            registry, new FakeServiceAccessor(), new FakeTaskAccessor(), new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.False(report.Success);
        Assert.Single(report.Restored);
        Assert.Empty(report.NotReversible);
        Assert.Single(report.Failed);
        Assert.Single(report.Errors);
        Assert.Contains("boom", report.Errors[0]);
        Assert.Equal(1, (int?)registry.GetValue(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V"));
        Assert.False(journal.IsEmpty);
        Assert.Single(journal.Entries);
        Assert.Equal("fail", journal.Entries[0].ActionKey);
    }

    [Fact]
    public async Task RollbackMezclaLifo_InformeExactoYOrdenVerificado()
    {
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V", 1);
        var processes = new FakeProcessAccessor();
        processes.Seed("SearchHost", running: true);

        var orden = new List<string>();
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

        // LIFO: se procesan third, second, first -> todas las listas tienen 1
        Assert.Equal(3, report.Restored.Count + report.NotReversible.Count + report.Failed.Count);
        Assert.Single(report.Restored);
        Assert.Equal("first", report.Restored[0].ActionKey);
        Assert.Single(report.NotReversible);
        Assert.Equal("second", report.NotReversible[0].ActionKey);
        Assert.Single(report.Failed);
        Assert.Equal("third", report.Failed[0].ActionKey);
        Assert.False(report.Success);
        Assert.Equal(RollbackOutcome.PartiallyRolledBack, ComputeOutcome(report));
        Assert.Equal(1, (int?)registry.GetValue(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V"));
        Assert.Empty(processes.Started);
    }

    [Fact]
    public async Task RollbackReintento_EntradaFallaYLuegoFunciona_JournalVacio()
    {
        var calls = new int[1];
        var restoreCalls = new int[1];
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.LocalMachine, @"SOFTWARE\Evo\X", "V", 99);
        var journal = new UndoJournal();
        journal.Add(new CounterEntry
        {
            CapabilityId = "c", ActionKey = "ok", Description = "ok", PreviousState = "1",
            Calls = calls,
        });
        // Falla la primera vez que se restaura, funciona la segunda.
        journal.Add(new RetryEntry
        {
            CapabilityId = "c", ActionKey = "fail", Description = "fail", PreviousState = null,
            RestoreCalls = restoreCalls,
        });

        var ctx = BuildContext(
            registry, new FakeServiceAccessor(), new FakeTaskAccessor(), new FakeProcessAccessor(), new FakeCommandRunner());
        var r1 = await journal.RollbackAsync(ctx);

        Assert.False(r1.Success);
        Assert.Single(r1.Restored);
        Assert.Single(r1.Failed);
        Assert.Equal("ok", r1.Restored[0].ActionKey);
        Assert.Equal("fail", r1.Failed[0].ActionKey);
        Assert.Equal(1, calls[0]); // "ok" restaurado una vez
        Assert.Single(journal.Entries); // solo "fail" conservada
        Assert.Equal("fail", journal.Entries[0].ActionKey);

        var r2 = await journal.RollbackAsync(ctx);
        Assert.True(r2.Success); // "fail" ahora funciona
        Assert.Single(r2.Restored);
        Assert.Equal("fail", r2.Restored[0].ActionKey);
        Assert.Empty(r2.Failed);
        Assert.Equal(1, calls[0]); // "ok" NO se reprocesó
        Assert.True(journal.IsEmpty); // journal vacía tras reintento exitoso
    }

    [Fact]
    public async Task DryRunSinJournalNiInforme_ExecuteYRollbackVacían()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);
        var contract = TestHarness.Contract(new CapabilityAction[] { SetDword(1, "A", "99") });
        var context = harness.Context(ExecutionMode.DryRun);

        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, new CapabilityAction[] { SetDword(1, "A", "99") }), ExecutionMode.DryRun, context);

        Assert.False(summary.Mutated);
        Assert.Empty(summary.UndoJournalEntry);
        Assert.Null(summary.RollbackReport);
        Assert.Equal(RollbackOutcome.None, summary.RollbackOutcome);
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "A"));

        // RollbackAsync con contexto DryRun sobre journal (vacío): informe vacío.
        var emptyJournal = new UndoJournal();
        var dryReport = await emptyJournal.RollbackAsync(BuildContext(
            harness.Registry, harness.Services, harness.Tasks, harness.Processes, harness.Commands, dryRun: true));
        Assert.True(dryReport.Success);
        Assert.Equal(0, dryReport.Count);
        Assert.Empty(dryReport.Restored);
        Assert.Empty(dryReport.NotReversible);
        Assert.Empty(dryReport.Failed);
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

    /// <summary>Entra fallida la primera vez, restaurada la segunda.</summary>
    private sealed record RetryEntry : UndoJournalEntry
    {
        public int[] RestoreCalls { get; init; } = Array.Empty<int>();

        public override UndoEntryOutcome Restore(IUndoContext context)
        {
            RestoreCalls[0]++;
            return RestoreCalls[0] == 1
                ? new UndoEntryOutcome
                {
                    ActionKey = ActionKey,
                    Description = Description,
                    Result = UndoRestoreResult.Failed,
                    FailureMessage = "primera vez falla",
                }
                : new UndoEntryOutcome
                {
                    ActionKey = ActionKey,
                    Description = Description,
                    Result = UndoRestoreResult.Restored,
                };
        }
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

    private sealed record ThrowingEntry : UndoJournalEntry
    {
        public override UndoEntryOutcome Restore(IUndoContext context) =>
            throw new InvalidOperationException("boom");
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
