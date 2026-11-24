using Evo.Catalog;
using Evo.Catalog.Model;
using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Core.System;
using Evo.Engine.Execution;
using Evo.Testing;
using Microsoft.Win32;
using Xunit;

namespace Evo.Engine.Tests;

/// <summary>
/// Ejercita el motor con las capacidades REALES de la oleada 2 (sección 10) sobre
/// los fakes en memoria. Ningún test toca el sistema: todo pasa por
/// <see cref="FakeRegistryAccessor"/> y su diario.
/// </summary>
public sealed class Wave2EngineTests
{
    private const string Advanced =
        @"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced";

    private const string ClassicMenuKey =
        @"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32";

    private static IReadOnlyList<CapabilityDefinition> LoadAll()
    {
        var directory = Path.Combine(AppContext.BaseDirectory, "capabilities");
        Assert.True(Directory.Exists(directory), $"No existe el directorio de catálogo: {directory}");
        return new CatalogLoader().LoadDirectory(directory)
            .SelectMany(d => d.Capabilities)
            .Where(d => d.SectionId == 10)
            .ToList();
    }

    private static CapabilityDefinition Definition(string id) =>
        LoadAll().SingleOrDefault(d => d.Id == id)
        ?? throw new InvalidOperationException($"No está '{id}' en el catálogo de la sección 10.");

    private static CapabilityContract Contract(string id) => Definition(id).ToContract();

    private static ExecutionPlan Plan(string id)
    {
        var definition = Definition(id);
        return new ExecutionPlan(definition.ToContract(), definition.Actions
            .OrderBy(a => a.Order)
            .Select(a => new PlannedStep
            {
                Order = a.Order,
                Description = a.Description,
                Action = a,
            }));
    }

    private static TestHarness Harness(int build = 26100) =>
        TestHarness.Create(
            admin: true,
            build: build,
            catalog: LoadAll().Select(d => d.ToContract()).ToList());

    private static int MutationCount(TestHarness h) =>
        h.Registry.MutationCount + h.Services.MutationCount + h.Tasks.MutationCount;

    // -------------------------------------------------------------- T4.2 DryRun
    /// <summary>T4.2: en DryRun el plan se informa entero y los fakes no cambian.</summary>
    [Fact]
    public async Task TestWave2Catalog_DryRun_NoSystemMutation()
    {
        var ids = new[]
        {
            "ui.context-menu.classic",
            "explorer.recent-items.disable",
            "ui.visual-effects.minimal",
            "explorer.extract-context-menu.add",
            "ui.numlock.startup",
        };

        foreach (var id in ids)
        {
            var harness = Harness();
            harness.Registry.Seed(RegistryHive.CurrentUser, Advanced, "HideFileExt", 1);

            var snapshot = harness.Registry.Snapshot();
            var mutationsBefore = MutationCount(harness);

            var summary = await harness.Coordinator.ExecuteAsync(
                Plan(id), ExecutionMode.DryRun, harness.Context(ExecutionMode.DryRun));

            Assert.True(summary.Succeeded > 0, $"{id}: {summary.BlockedReason}");
            Assert.Equal(0, summary.Failed);
            Assert.False(summary.Mutated);
            Assert.Empty(summary.UndoJournalEntry);
            Assert.Equal(Definition(id).Actions.Count, summary.PlannedActions.Count);
            Assert.Equal(Definition(id).Actions.Count, summary.Results.Count);
            Assert.All(summary.Results, r => Assert.False(r.Applied));

            Assert.Equal(mutationsBefore, MutationCount(harness));
            Assert.Equal(
                snapshot.Keys.OrderBy(k => k, StringComparer.OrdinalIgnoreCase),
                harness.Registry.Snapshot().Keys.OrderBy(k => k, StringComparer.OrdinalIgnoreCase));
        }
    }

    // ------------------------------------------------- T4.3 Execute + deshacer
    /// <summary>T4.3: Execute escribe los valores del pin y el rollback del diario
    /// devuelve el registro exactamente al estado anterior (incluido el caso en
    /// que el valor no existía: vuelve a no existir).</summary>
    [Fact]
    public async Task TestWave2Catalog_ExecuteAndRollback_RestoresState()
    {
        var harness = Harness();
        harness.Registry.Seed(RegistryHive.CurrentUser, Advanced, "HideFileExt", 1);
        harness.Registry.Seed(RegistryHive.CurrentUser, Advanced, "TaskbarAl", 0);
        harness.Registry.Seed(
            RegistryHive.CurrentUser, Advanced, "ShowSecondsInSystemClock", 1);

        var before = harness.Registry.Snapshot();

        foreach (var id in new[]
                 {
                     "explorer.file-extensions.show",
                     "ui.taskbar.icons-centered",
                     "ui.taskbar.task-view-button",
                 })
        {
            var summary = await harness.Coordinator.ExecuteAsync(
                Plan(id), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));
            Assert.Equal(0, summary.Failed);
            Assert.True(summary.Mutated);
            Assert.NotEmpty(summary.UndoJournalEntry);
        }

        // --- Mutó de verdad, con los valores del pin ---
        Assert.Equal(0, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, Advanced, "HideFileExt")!);
        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, Advanced, "TaskbarAl")!);
        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, Advanced, "ShowTaskViewButton")!);

        // Ninguna de las tres toca la de reloj (no era su clave).
        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, Advanced, "ShowSecondsInSystemClock")!);

        // --- Rollback ---
        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        Assert.Empty(rollback.Errors);

        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, Advanced, "HideFileExt")!);
        Assert.Equal(0, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, Advanced, "TaskbarAl")!);
        // ShowTaskViewButton no existía antes: el deshacer lo deja en null.
        Assert.Null(harness.Registry.GetValue(
            RegistryHive.CurrentUser, Advanced, "ShowTaskViewButton"));

        Assert.Equal(
            before.Keys.OrderBy(k => k, StringComparer.OrdinalIgnoreCase),
            harness.Registry.Snapshot().Keys.OrderBy(k => k, StringComparer.OrdinalIgnoreCase));
    }

    /// <summary>T4.3b: la capacidad de nueve acciones (elementos recientes) se
    /// ejecuta entera y se deshace entera: nueve escrituras, nueve entradas de
    /// diario y ningún valor fuera de sitio al volver.</summary>
    [Fact]
    public async Task TestWave2Catalog_LargestCapability_RoundTrips()
    {
        var definition = Definition("explorer.recent-items.disable");
        Assert.Equal(9, definition.Actions.Count);

        var harness = Harness();
        var before = harness.Registry.Snapshot();

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan(definition.Id), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));
        Assert.Equal(0, summary.Failed);
        Assert.Equal(9, summary.Succeeded);
        Assert.Equal(9, summary.Results.Count(r => r.Applied));

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        Assert.Equal(
            before.Keys.OrderBy(k => k, StringComparer.OrdinalIgnoreCase),
            harness.Registry.Snapshot().Keys.OrderBy(k => k, StringComparer.OrdinalIgnoreCase));
    }

    // ------------------------------------------------------------- T1 por build
    /// <summary>T1: en una build no soportada el motor bloquea ANTES de tocar nada
    /// (el CLSID del menú clásico no existe en 19045).</summary>
    [Fact]
    public async Task TestWave2Catalog_UnsupportedBuildIsBlockedBeforeMutating()
    {
        var harness = Harness(build: 19045);
        var before = harness.Registry.Snapshot();
        var mutationsBefore = MutationCount(harness);

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("ui.context-menu.classic"), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));

        Assert.True(summary.Blocked, "en 19045 el preflight debe rechazarla");
        Assert.Contains("19045", summary.BlockedReason, StringComparison.Ordinal);
        Assert.False(summary.Mutated);
        Assert.Empty(summary.UndoJournalEntry);
        Assert.Equal(mutationsBefore, MutationCount(harness));
        Assert.Equal(
            before.Keys.OrderBy(k => k, StringComparer.OrdinalIgnoreCase),
            harness.Registry.Snapshot().Keys.OrderBy(k => k, StringComparer.OrdinalIgnoreCase));

        // Y en 26100 la misma capacidad sí se aplica.
        var supported = Harness(build: 26100);
        var applied = await supported.Coordinator.ExecuteAsync(
            Plan("ui.context-menu.classic"), ExecutionMode.Execute,
            supported.Context(ExecutionMode.Execute));
        Assert.Equal(0, applied.Failed);
        Assert.True(applied.Mutated);
        // El valor predeterminado de InprocServer32 se deja vacío: es lo que
        // reactiva el menú clásico en Windows 11.
        Assert.Equal(string.Empty, supported.Registry.GetValue(
            RegistryHive.CurrentUser, ClassicMenuKey, string.Empty));
    }

    // ------------------------------------------------------- T1 privilegios HKLM
    /// <summary>T1: las capacidades que escriben HKLM declaran Admin y, sin
    /// elevación, el motor las bloquea sin mutar nada.</summary>
    [Fact]
    public async Task TestWave2Catalog_AdminCapabilityRequiresElevation()
    {
        var admin = Definition("explorer.long-paths.enable");
        Assert.Equal(PrivilegeLevel.Admin, admin.Privilege);
        Assert.Contains(admin.Actions.OfType<RegistryAction>(),
            a => a.Hive == RegistryHiveKind.LocalMachine);

        var harness = TestHarness.Create(
            admin: false,
            build: 26100,
            catalog: LoadAll().Select(d => d.ToContract()).ToList());
        var mutationsBefore = MutationCount(harness);

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("explorer.long-paths.enable"), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));

        Assert.True(summary.Blocked, "sin elevación el preflight debe rechazarla");
        Assert.Contains("privilegio", summary.BlockedReason, StringComparison.OrdinalIgnoreCase);
        Assert.False(summary.Mutated);
        Assert.Empty(summary.UndoJournalEntry);
        Assert.Equal(mutationsBefore, MutationCount(harness));
    }

    /// <summary>T1: el Toggle 8c se aplica con la semántica correcta. El tema oscuro
    /// del pin deja `AppsUseLightTheme=0` y `SystemUsesLightTheme=0` (el estado
    /// ENCENDIDO del toggle es el valor 0).</summary>
    [Fact]
    public async Task TestWave2Catalog_ToggleSemanticsMatchThePin()
    {
        const string personalize =
            @"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize";
        var harness = Harness();
        harness.Registry.Seed(RegistryHive.CurrentUser, personalize, "AppsUseLightTheme", 1);
        harness.Registry.Seed(RegistryHive.CurrentUser, personalize, "SystemUsesLightTheme", 1);

        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("ui.theme.dark"), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));
        Assert.Equal(0, summary.Failed);
        Assert.Equal(0, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, personalize, "AppsUseLightTheme")!);
        Assert.Equal(0, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, personalize, "SystemUsesLightTheme")!);

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, personalize, "AppsUseLightTheme")!);
    }
}
