using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Restore;
using Evo.Core.System;
using Evo.Engine;
using Evo.Engine.Execution;
using Evo.Engine.Executors;
using Evo.Engine.Undo;
using Microsoft.Win32;
using Xunit;

namespace Evo.Engine.Tests;

/// <summary>Demuestra que <see cref="EngineCoordinator.ExecuteAsync"/> debe usar el
/// diario del contexto (<c>context.Journal</c>) y no uno interno ignorando el del llamante.</summary>
public sealed class UndoUsesContextJournalTests
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

    private static RegistryAction SetDword(
        int order, string name, string value, RegistryHiveKind hive, string keyPath) => new()
    {
        Order = order,
        Description = $"set {name}",
        Hive = hive,
        KeyPath = keyPath,
        ValueName = name,
        Operation = RegistryOperation.Set,
        ValueType = RegistryValueType.DWord,
        Value = value,
    };

    /// <summary>Si se pasa un diario propio en el contexto, ese diario debe recibir las
    /// entradas (no quedar vacío mientras el coordinador llena el suyo).</summary>
    [Fact]
    public async Task ExecuteAsync_Uses_ContextJournal_Not_CoordinatorOwnJournal()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "A", 1);

        // El diario que el llamante (ViewModel) espera que se llene.
        var viewModelJournal = new UndoJournal();
        var context = new ActionContext
        {
            Registry = harness.Registry,
            Services = harness.Services,
            Tasks = harness.Tasks,
            Processes = harness.Processes,
            Commands = harness.Commands,
            Mode = ExecutionMode.Execute,
            Journal = viewModelJournal,
            CapabilityId = "test.capability",
        };

        var actions = new CapabilityAction[] { SetDword(1, "A", "99") };
        var contract = TestHarness.Contract(actions);
        var summary = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contract, actions), ExecutionMode.Execute, context);

        Assert.True(summary.Succeeded == 1);
        // El diario del contexto (ViewModel) recibió la entrada: no está vacío.
        Assert.NotEmpty(viewModelJournal.Entries);
        var entry = Assert.IsType<Undo.RegistryUndoEntry>(viewModelJournal.Entries[0]);
        Assert.Equal("1", entry.PreviousState);
        Assert.Equal(1, entry.PreviousValue);
    }

    /// <summary>Punto B: el rollback automático del motor (cuando una acción
    /// falla) deshace SOLO las entradas del journal de la capacidad que falló.
    /// Con un journal por capacidad (ETAPA 6-I), otra capacidad que ya se
    /// aplicó con éxito sigue intacta.</summary>
    [Fact]
    public async Task RollbackAutomatico_No_Afecta_Otra_Capacidad()
    {
        var harness = TestHarness.Create();
        var keyA = @"SOFTWARE\Evo\A";
        var keyB = @"SOFTWARE\Evo\B";
        harness.Registry.Seed(RegistryHive.LocalMachine, keyA, "ValorA", 1);
        harness.Registry.Seed(RegistryHive.LocalMachine, keyB, "ValorB", 1);

        // Diarios SEPARADOS por capacidad (ETAPA 6-I): cada harness.Context()
        // crea su propio UndoJournal nuevo.
        var ctxA = harness.Context(ExecutionMode.Execute);
        var ctxB = harness.Context(ExecutionMode.Execute);

        // Capacidad A: Set DWord (éxito). Puertas mínimas (Safe/None/None)
        // para que no haya confirmación ni punto de restauración de por medio.
        var accionesA = new CapabilityAction[]
        {
            SetDword(1, "ValorA", "99", RegistryHiveKind.LocalMachine, keyA),
        };
        var contractA = TestHarness.Contract(
            accionesA, id: "cap.a", risk: RiskLevel.Safe,
            restore: RestoreLevel.None, confirmation: ConfirmationType.None);
        var summaryA = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contractA, accionesA), ExecutionMode.Execute, ctxA);
        Assert.True(summaryA.Succeeded >= 1);
        Assert.Equal(99, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, keyA, "ValorA"));
        Assert.NotEmpty(ctxA.Journal.Entries);

        // Capacidad B: Set DWord + comando que falla → rollback automático de B.
        harness.Commands.Throw("explode.exe --now");
        var accionesB = new CapabilityAction[]
        {
            SetDword(1, "ValorB", "42", RegistryHiveKind.LocalMachine, keyB),
            new CommandAction
            {
                Order = 2,
                Description = "comando que falla",
                FileName = "explode.exe",
                Arguments = ["--now"],
            },
        };
        var contractB = TestHarness.Contract(
            accionesB, id: "cap.b", risk: RiskLevel.Safe,
            restore: RestoreLevel.None, confirmation: ConfirmationType.None);
        var summaryB = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contractB, accionesB), ExecutionMode.Execute, ctxB);
        Assert.Equal(1, summaryB.Succeeded); // la primera acción aplicó
        Assert.Equal(1, summaryB.Failed);  // la segunda falló → rollback automático

        // A SIGUE aplicada: su diario (J_A) no fue tocado por el rollback de B.
        Assert.Equal(99, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, keyA, "ValorA"));
        Assert.NotEmpty(ctxA.Journal.Entries); // J_A intacto

        // B fue revertida por el rollback automático (su Set DWord se deshizo).
        Assert.Null(harness.Registry.GetValue(RegistryHive.LocalMachine, keyB, "ValorB"));
    }
}
