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
        var contractA = TestHarness.Contract(accionesA, id: "cap.a");
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
        var contractB = TestHarness.Contract(accionesB, id: "cap.b");
        var summaryB = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contractB, accionesB), ExecutionMode.Execute, ctxB);
        Assert.Equal(1, summaryB.Succeeded); // la primera acción aplicó
        Assert.Equal(1, summaryB.Failed);  // la segunda falló → rollback automático

        // A SIGUE aplicada: su diario (J_A) no fue tocado por el rollback de B.
        Assert.Equal(99, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, keyA, "ValorA"));
        Assert.NotEmpty(ctxA.Journal.Entries); // J_A intacto

        // B fue revertida por el rollback automático: su Set DWord se deshizo
        // y el valor volvió al estado anterior (1, no 42).
        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, keyB, "ValorB"));
    }

    /// <summary>Paso 2, defecto del rollback automático: si la capacidad X ya se
    /// aplicó con éxito (su journal J tiene entradas) y se ejecuta de nuevo
    /// fallando en la 2ª acción, el rollback automático NO debe revertir las
    /// entradas de la primera ejecución exitosa, solo las de esta ejecución.
    ///
    /// Traza a mano del código VIEJO (rollbackEntries = journal.Entries.ToList()):
    ///   - Antes de la 2ª ejecución: J = [e1: ValorX 1→99]  (ValorX == 99)
    ///   - 2ª ejecución: e2: ValorX 99→99 (Set DWord, éxito), luego comando falla.
    ///   - rollbackEntries = [e1, e2]; RollbackAsync LIFO → deshace e2 (ValorX queda 99)
    ///     y luego deshace e1 (ValorX vuelve a 1).  <-- BUG: ValorX == 1.
    ///
    /// Con la corrección (Skip(rollbackStartIndex)): solo e2 se revierte, ValorX
    /// se queda en 99 y J conserva exactamente e1.
    /// Contrato real de la app: Safe / SessionUndo / Confirmation.None
    /// (no requiere punto de restauración, FakeRestorePointService no se invoca).
    /// </summary>
    [Fact]
    public async Task RollbackAutomatico_No_Revierte_EjecucionPreviaExitosa()
    {
        var harness = TestHarness.Create();
        var keyX = @"SOFTWARE\Evo\X";
        harness.Registry.Seed(RegistryHive.LocalMachine, keyX, "ValorX", 1);

        // Journal COMPARTIDO por la capacidad X (ETAPA 6-I: journal por capacidad).
        var journalJ = new UndoJournal();
        var ctxX = new ActionContext
        {
            Registry = harness.Registry,
            Services = harness.Services,
            Tasks = harness.Tasks,
            Processes = harness.Processes,
            Commands = harness.Commands,
            Mode = ExecutionMode.Execute,
            Journal = journalJ,
            CapabilityId = "cap.x",
        };

        // 1ª ejecución: Set DWord ValorX 1→99, éxito.
        var accionesX = new CapabilityAction[]
        {
            SetDword(1, "ValorX", "99", RegistryHiveKind.LocalMachine, keyX),
        };
        var contractX = TestHarness.Contract(
            accionesX, id: "cap.x", risk: RiskLevel.Safe,
            restore: RestoreLevel.SessionUndo, confirmation: ConfirmationType.None);
        var summary1 = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contractX, accionesX), ExecutionMode.Execute, ctxX);
        Assert.True(summary1.Succeeded >= 1);
        Assert.Equal(99, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, keyX, "ValorX"));
        Assert.Single(journalJ.Entries); // una entrada de la 1ª ejecución

        // 2ª ejecución con el MISMO journal J: 1ª acción Set DWord (éxito),
        // 2ª acción comando que falla → rollback automático.
        harness.Commands.Throw("explode.exe --now");
        var accionesX2 = new CapabilityAction[]
        {
            SetDword(1, "ValorX", "99", RegistryHiveKind.LocalMachine, keyX),
            new CommandAction
            {
                Order = 2,
                Description = "comando que falla",
                FileName = "explode.exe",
                Arguments = ["--now"],
            },
        };
        var summary2 = await harness.Coordinator.ExecuteAsync(
            TestHarness.Plan(contractX, accionesX2), ExecutionMode.Execute, ctxX);
        Assert.Equal(1, summary2.Succeeded); // la 1ª acción de esta ejecución aplicó
        Assert.Equal(1, summary2.Failed);   // la 2ª falló → rollback automático

        // CON LA CORRECCIÓN: ValorX se queda en 99 (estado tras la 1ª ejecución),
        // NO vuelve a 1 (lo que daría el código viejo al deshacer también e1).
        Assert.Equal(99, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, keyX, "ValorX"));

        // J conserva exactamente las entradas de la 1ª ejecución (e2 se descartó
        // al restaurarse; e1 nunca fue tocada por el rollback automático).
        Assert.Single(journalJ.Entries);
        var entrada = Assert.IsType<Undo.RegistryUndoEntry>(journalJ.Entries[0]);
        Assert.Equal("1", entrada.PreviousState);
        Assert.Equal(1, entrada.PreviousValue);
    }
}
