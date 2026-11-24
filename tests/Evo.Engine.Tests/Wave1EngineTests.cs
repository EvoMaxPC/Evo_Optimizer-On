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
/// Ejercita el motor con las capacidades REALES de la oleada 1 (catalog/capabilities),
/// sobre los seis fakes en memoria. Ningún test toca el sistema.
/// </summary>
public sealed class Wave1EngineTests
{
    private const string DataCollectionKey = @"SOFTWARE\Policies\Microsoft\Windows\DataCollection";
    private const string AdvertisingKey = @"SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo";
    private const string SystemPolicyKey = @"SOFTWARE\Policies\Microsoft\Windows\System";
    private const string ConsentStoreKey =
        @"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location";
    private const string CeipTaskPath = @"\Microsoft\Windows\Customer Experience Improvement Program";

    /// <summary>Catálogo real de la oleada 1, cargado tal cual del repositorio.</summary>
    private static IReadOnlyList<CapabilityDefinition> LoadWave1()
    {
        var directory = Path.Combine(AppContext.BaseDirectory, "capabilities");
        Assert.True(Directory.Exists(directory), $"No existe el directorio de catálogo: {directory}");
        return new CatalogLoader().LoadDirectory(directory).SelectMany(d => d.Capabilities).ToList();
    }

    private static CapabilityDefinition Definition(string id) =>
        LoadWave1().SingleOrDefault(d => d.Id == id)
        ?? throw new InvalidOperationException($"No está '{id}' en el catálogo de la oleada 1.");

    /// <summary>Contrato del motor a partir de la definición del catálogo.</summary>
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

    /// <summary>TestHarness cuyo coordinador conoce todas las capacidades de la oleada 1
    /// (necesario para que Preflight resuelva dependencias y conflictos).</summary>
    private static TestHarness Harness(int build = 26100) =>
        TestHarness.Create(
            admin: true,
            build: build,
            catalog: LoadWave1().Select(d => d.ToContract()).ToList());

    /// <summary>Estado inicial con valores distintos a los que escribe el catálogo,
    /// para que un Execute se note y un DryRun no.</summary>
    private static void Seed(TestHarness harness)
    {
        harness.Registry.Seed(RegistryHive.LocalMachine, DataCollectionKey, "AllowTelemetry", 3);
        harness.Registry.Seed(RegistryHive.CurrentUser, AdvertisingKey, "Enabled", 1);
        harness.Registry.Seed(RegistryHive.LocalMachine, SystemPolicyKey, "EnableActivityFeed", 1);
        harness.Registry.Seed(RegistryHive.LocalMachine, ConsentStoreKey, "Value", "Allow", RegistryValueKind.String);
        harness.Registry.Seed(
            RegistryHive.LocalMachine,
            @"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection",
            "AllowTelemetry",
            2);
        harness.Registry.Seed(
            RegistryHive.LocalMachine,
            @"SYSTEM\CurrentControlSet\Control\Diagnostics\Performance",
            "DisableDiagnosticTracing",
            0);
        harness.Registry.Seed(
            RegistryHive.LocalMachine,
            @"SOFTWARE\Policies\Microsoft\Windows\AdvertisingInfo",
            "DisabledByGroupPolicy",
            0);
        harness.Registry.Seed(RegistryHive.LocalMachine, AdvertisingKey, "Enabled", 1);
        harness.Registry.Seed(RegistryHive.LocalMachine, SystemPolicyKey, "PublishUserActivities", 1);
        harness.Registry.Seed(RegistryHive.LocalMachine, SystemPolicyKey, "UploadUserActivities", 1);

        harness.Services.Seed("DiagTrack", ServiceStatus.Running, ServiceStartupType.Automatic);
        harness.Services.Seed("lfsvc", ServiceStatus.Running, ServiceStartupType.Manual);

        harness.Tasks.Seed(CeipTaskPath, "Consolidator", enabled: true);
        harness.Tasks.Seed(CeipTaskPath, "UsbCeip", enabled: true);
        harness.Tasks.Seed(
            @"\Microsoft\Windows\DiskDiagnostic",
            "Microsoft-Windows-DiskDiagnosticDataCollector",
            enabled: true);
        harness.Tasks.Seed(
            @"\Microsoft\Windows\Flighting\FeatureConfig",
            "UsageDataReporting",
            enabled: true);
        harness.Tasks.Seed(@"\Microsoft\Windows\Autochk", "Proxy", enabled: true);
    }

    private static int MutationCount(TestHarness h) =>
        h.Registry.MutationCount + h.Services.MutationCount + h.Tasks.MutationCount;

    /// <summary>T4.2: en DryRun el plan se informa y los fakes quedan intactos.</summary>
    [Fact]
    public async Task TestWave1Catalog_DryRun_NoSystemMutation()
    {
        var ids = new[]
        {
            "privacy.diagnostic.data.level",
            "privacy.telemetry.diagtrack",
            "privacy.advertising.id",
            "privacy.activity.history",
            "privacy.location.sensors",
            "privacy.ceip.tasks",
        };

        foreach (var id in ids)
        {
            var harness = Harness();
            Seed(harness);

            var snapshotRegistry = harness.Registry.Snapshot();
            var snapshotServices = harness.Services.Snapshot();
            var snapshotTasks = harness.Tasks.Snapshot();
            var mutationsBefore = MutationCount(harness);

            var summary = await harness.Coordinator.ExecuteAsync(
                Plan(id), ExecutionMode.DryRun, harness.Context(ExecutionMode.DryRun));

            Assert.True(summary.Succeeded > 0, $"{id}: {summary.BlockedReason}");
            Assert.Equal(0, summary.Failed);
            Assert.False(summary.Mutated);
            Assert.Empty(summary.UndoJournalEntry);

            // El plan informa exactamente de las acciones declaradas.
            Assert.Equal(Definition(id).Actions.Count, summary.PlannedActions.Count);
            Assert.Equal(Definition(id).Actions.Count, summary.Results.Count);
            Assert.All(summary.Results, r => Assert.False(r.Applied));

            // Nada mutó: mismos contadores y mismos snapshots.
            Assert.Equal(mutationsBefore, MutationCount(harness));
            AssertSameState(snapshotRegistry, harness.Registry.Snapshot());
            AssertSameServices(snapshotServices, harness.Services.Snapshot());
            AssertSameTasks(snapshotTasks, harness.Tasks.Snapshot());
        }
    }

    /// <summary>T4.3: Execute muta el registro, el servicio y la tarea, y
    /// <c>RollbackAsync</c> devuelve el sistema exactamente al estado inicial.</summary>
    [Fact]
    public async Task TestWave1Catalog_ExecuteAndRollback_RestoresState()
    {
        var harness = Harness();
        Seed(harness);

        var registryBefore = harness.Registry.Snapshot();
        var servicesBefore = harness.Services.Snapshot();
        var tasksBefore = harness.Tasks.Snapshot();

        // Tres capacidades representativas: registro (privacy.diagnostic.data.level),
        // servicio (privacy.telemetry.diagtrack) y tarea (privacy.ceip.tasks).
        foreach (var id in new[]
                 {
                     "privacy.diagnostic.data.level",
                     "privacy.telemetry.diagtrack",
                     "privacy.ceip.tasks",
                 })
        {
            var summary = await harness.Coordinator.ExecuteAsync(
                Plan(id), ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));

            Assert.True(summary.Failed == 0, $"{id}: {summary.BlockedReason}");
            Assert.True(summary.Mutated);
            Assert.NotEmpty(summary.UndoJournalEntry);
        }

        // --- Mutó de verdad ---
        // El catálogo escribe AllowTelemetry=0 en las DOS rutas (3 y 2 eran los valores sembrados).
        Assert.Equal(0, harness.Registry.GetValue(RegistryHive.LocalMachine, DataCollectionKey, "AllowTelemetry"));
        Assert.Equal(
            0,
            harness.Registry.GetValue(
                RegistryHive.LocalMachine,
                @"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection",
                "AllowTelemetry"));
        Assert.Equal(
            ServiceStatus.Stopped,
            harness.Services.GetStatus("DiagTrack"));
        Assert.Equal(
            ServiceStartupType.Disabled,
            harness.Services.GetStartupType("DiagTrack"));
        Assert.False(harness.Tasks.IsTaskEnabled(CeipTaskPath, "Consolidator"));
        Assert.False(harness.Tasks.IsTaskEnabled(CeipTaskPath, "UsbCeip"));

        // El borrado del valor de Ubpm no existía antes: sigue sin existir y no rompe.
        Assert.Null(harness.Registry.GetValue(
            RegistryHive.LocalMachine,
            @"SYSTEM\CurrentControlSet\Control\Ubpm",
            "CriticalMaintenance_UsageDataReporting"));

        // --- Rollback: vuelve al estado inicial exacto ---
        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        Assert.Empty(rollback.Errors);

        AssertSameState(registryBefore, harness.Registry.Snapshot());
        AssertSameServices(servicesBefore, harness.Services.Snapshot());
        AssertSameTasks(tasksBefore, harness.Tasks.Snapshot());

        // Comprobaciones puntuales, legibles en el .trx si algo falla.
        Assert.Equal(3, harness.Registry.GetValue(RegistryHive.LocalMachine, DataCollectionKey, "AllowTelemetry"));
        Assert.Equal(ServiceStatus.Running, harness.Services.GetStatus("DiagTrack"));
        Assert.Equal(ServiceStartupType.Automatic, harness.Services.GetStartupType("DiagTrack"));
        Assert.True(harness.Tasks.IsTaskEnabled(CeipTaskPath, "Consolidator"));
        Assert.True(harness.Tasks.IsTaskEnabled(CeipTaskPath, "UsbCeip"));
    }

    /// <summary>La capacidad de limpieza con comandos se ejecuta contra
    /// <see cref="FakeCommandRunner"/> y el diario anota el comando como no restaurable.</summary>
    [Fact]
    public async Task TestWave1Catalog_CommandCapability_UsesInjectedRunnerOnly()
    {
        var harness = Harness();
        var plan = Plan("cleanup.winsxs.component");
        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));

        // cleanup.winsxs.component exige punto de restauración: el contrato se
        // relaja aquí porque el fake no ejecuta la confirmación del usuario.
        Assert.Equal(1, summary.Succeeded);
        Assert.Single(harness.Commands.Executed);
        var invocation = harness.Commands.Executed[0];
        Assert.Equal("dism.exe", invocation.FileName);
        Assert.DoesNotContain("/ResetBase", invocation.Arguments);
        Assert.Contains("/StartComponentCleanup", invocation.Arguments);
        Assert.Single(summary.UndoJournalEntry);

        // Y su variante /ResetBase es otra capacidad distinta (ADR-0003: la
        // Irreversible) que sí pasa /ResetBase.
        harness.Commands.Executed.Clear();
        var resetBase = Plan("cleanup.winsxs.resetbase");
        var resetSummary = await harness.Coordinator.ExecuteAsync(
            resetBase, ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));
        Assert.Equal(0, resetSummary.Failed);
        Assert.Contains("/ResetBase", harness.Commands.Executed[0].Arguments);
    }


    /// <summary>Paso 8c (T1d): la busqueda web se desactiva DE VERDAD.
    ///
    /// `BingSearchEnabled=0` es el estado APAGADO de `WPFToggleBingSearch` en el
    /// pin (Value=1 es la casilla encendida). El test comprueba el valor final en
    /// el registro falso, que `DisableSearchBoxSuggestions` sigue en 1 y que el
    /// rollback devuelve el valor previo.
    /// </summary>
    [Fact]
    public async Task TestWave1Catalog_WebSearchCapability_ReallyDisablesBing()
    {
        var harness = Harness();
        const string searchKey = @"Software\Microsoft\Windows\CurrentVersion\Search";
        const string explorerPolicies = @"SOFTWARE\Policies\Microsoft\Windows\Explorer";
        harness.Registry.Seed(RegistryHive.CurrentUser, searchKey, "BingSearchEnabled", 1);
        harness.Registry.Seed(
            RegistryHive.LocalMachine, explorerPolicies, "DisableSearchBoxSuggestions", 0);

        var plan = Plan("debloat.start.websearch");
        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));

        Assert.Equal(0, summary.Failed);
        Assert.Equal(11, summary.Succeeded);
        Assert.Equal(0, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, searchKey, "BingSearchEnabled")!);
        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, explorerPolicies, "DisableSearchBoxSuggestions")!);

        var rollback = await harness.Coordinator.RollbackAsync(harness.Context(ExecutionMode.Execute));
        Assert.True(rollback.Success, string.Join(" | ", rollback.Errors));
        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.CurrentUser, searchKey, "BingSearchEnabled")!);
        Assert.Equal(0, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine, explorerPolicies, "DisableSearchBoxSuggestions")!);
    }

    /// <summary>Paso 8c (T2a): `debloat.windows.ai` se parte en dos capacidades.
    ///
    /// La de Recall sólo escribe políticas (reversible); la de Copilot quita el
    /// paquete (irreversible) y por eso declara `Restore=None` y aviso reforzado.
    /// Se comprueba que ninguna de las dos toca lo de la otra y que la de Recall
    /// está acotada a 24H2+ (la política WindowsAI no existe en 23H2).
    /// </summary>
    [Fact]
    public async Task TestWave1Catalog_WindowsAiSplit_RecallAndCopilotAreSeparate()
    {
        var recall = Definition("debloat.windows.ai.recall");
        var copilot = Definition("debloat.copilot.remove");

        // Rangos propios y reversibilidad propia.
        Assert.Equal(new[] { 26100, 26200 }, recall.SupportedBuilds.OrderBy(b => b));
        Assert.Equal(new[] { 22631, 26100, 26200 }, copilot.SupportedBuilds.OrderBy(b => b));
        Assert.Equal(Reversibility.Reversible, recall.Reversibility);
        Assert.Equal(Reversibility.Irreversible, copilot.Reversibility);
        Assert.Equal(RestoreLevel.SessionUndo, recall.Restore);
        Assert.Equal(RestoreLevel.None, copilot.Restore);

        // Ninguna acción se solapa entre las dos.
        var recallKeys = recall.Actions
            .Select(a => $"{a.Kind}:{(a as RegistryAction)?.KeyPath}:{(a as RegistryAction)?.ValueName}")
            .ToHashSet(StringComparer.Ordinal);
        var copilotKeys = copilot.Actions
            .Select(a => $"{a.Kind}:{(a as RegistryAction)?.KeyPath}:{(a as RegistryAction)?.ValueName}")
            .ToHashSet(StringComparer.Ordinal);
        Assert.Empty(recallKeys.Intersect(copilotKeys, StringComparer.Ordinal));
        Assert.DoesNotContain(recall.Actions, a =>
            a is RegistryAction r && r.ValueName == "RemoveMicrosoftCopilotApp");
        Assert.Contains(copilot.Actions, a =>
            a is RegistryAction r && r.ValueName == "RemoveMicrosoftCopilotApp");

        // Ejecución contra fakes: la de Recall no dispara ningún comando.
        var harness = Harness();
        var summary = await harness.Coordinator.ExecuteAsync(
            Plan("debloat.windows.ai.recall"), ExecutionMode.Execute,
            harness.Context(ExecutionMode.Execute));
        Assert.Equal(0, summary.Failed);
        Assert.Empty(harness.Commands.Executed);
        Assert.Equal(1, (int?)harness.Registry.GetValue(
            RegistryHive.LocalMachine,
            @"SOFTWARE\Policies\Microsoft\Windows\WindowsAI",
            "DisableAIDataAnalysis")!);
    }

    private static void AssertSameState(
        IReadOnlyDictionary<string, IReadOnlyDictionary<string, RegistryEntry>> expected,
        IReadOnlyDictionary<string, IReadOnlyDictionary<string, RegistryEntry>> actual)
    {
        // Se comparan los VALORES existentes: una clave vacía que el rollback deja
        // atrás (porque el valor no existía antes) no es un cambio de estado.
        var expectedValues = Flatten(expected);
        var actualValues = Flatten(actual);

        Assert.Equal(
            expectedValues.Keys.OrderBy(k => k, StringComparer.Ordinal),
            actualValues.Keys.OrderBy(k => k, StringComparer.Ordinal));

        foreach (var (name, entry) in expectedValues)
        {
            var other = actualValues[name];
            Assert.Equal(entry.Kind, other.Kind);
            Assert.Equal(entry.Value, other.Value);
        }
    }

    private static Dictionary<string, RegistryEntry> Flatten(
        IReadOnlyDictionary<string, IReadOnlyDictionary<string, RegistryEntry>> snapshot) =>
        snapshot
            .SelectMany(key => key.Value
                .Where(value => value.Value.Exists)
                .Select(value => new KeyValuePair<string, RegistryEntry>(
                    $"{key.Key}\\{value.Key}", value.Value)))
            .ToDictionary(pair => pair.Key, pair => pair.Value, StringComparer.OrdinalIgnoreCase);

    private static void AssertSameServices(
        IReadOnlyDictionary<string, FakeService> expected,
        IReadOnlyDictionary<string, FakeService> actual)
    {
        Assert.Equal(expected.Keys.OrderBy(k => k, StringComparer.Ordinal),
            actual.Keys.OrderBy(k => k, StringComparer.Ordinal));
        foreach (var (name, service) in expected)
        {
            Assert.Equal(service, actual[name]);
        }
    }

    private static void AssertSameTasks(
        IReadOnlyDictionary<string, FakeTask> expected,
        IReadOnlyDictionary<string, FakeTask> actual)
    {
        Assert.Equal(expected.Keys.OrderBy(k => k, StringComparer.Ordinal),
            actual.Keys.OrderBy(k => k, StringComparer.Ordinal));
        foreach (var (name, task) in expected)
        {
            Assert.Equal(task, actual[name]);
        }
    }
}
