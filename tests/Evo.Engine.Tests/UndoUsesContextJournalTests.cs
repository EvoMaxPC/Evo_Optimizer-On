using Evo.Core.Actions;
using Evo.Core.Enums;
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
}
