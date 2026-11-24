using Evo.Catalog;
using Evo.Catalog.Model;
using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Models;
using Xunit;

namespace Evo.Catalog.Tests;

/// <summary>
/// Carga y valida los tres ficheros reales de la oleada 1 (secciones 1, 2 y 3)
/// tal como están en <c>catalog/capabilities/</c>. No usa JSON de mentira: si el
/// catálogo se rompe, el test se rompe.
/// </summary>
public sealed class Wave1CatalogTests
{
    /// <summary>Ids pedidos por el enunciado del paso 8, por sección.</summary>
    private static readonly string[] Section1 =
    [
        "cleanup.temp.user",
        "cleanup.temp.system",
        "cleanup.delivery.optimization",
        "cleanup.wer.reports",
        "cleanup.recycle.bin",
        "cleanup.winsxs.component",
        "cleanup.memory.dumps",
        "cleanup.winsxs.resetbase",
    ];

    private static readonly string[] Section2 =
    [
        "debloat.appx.consumer",
        "debloat.cortana.remove",
        "debloat.onedrive.uninstall",
        "debloat.edge.policies",
        "debloat.start.websearch",
        "debloat.windows.ai.recall",
        "debloat.copilot.remove",
        "debloat.content.delivery",
        "debloat.telemetry.appx",
        "debloat.edge.remove",
        "debloat.widgets.disable",
        "debloat.explorer.home-gallery",
        "debloat.start.recommendations",
        "debloat.store.search",
        "debloat.explorer.auto-folder-discovery",
        "debloat.devices.companion-apps",
        "debloat.drivers.razer",
        "debloat.drivers.logitech",
        "debloat.network.adobe-blocklist",
        "privacy.browser.brave-debloat",
        "debloat.start.layout",
        "debloat.settings.home",
    ];

    private static readonly string[] Section3 =
    [
        "privacy.telemetry.diagtrack",
        "privacy.telemetry.dmwappush",
        "privacy.advertising.id",
        "privacy.activity.history",
        "privacy.feedback.frequency",
        "privacy.location.sensors",
        "privacy.ceip.tasks",
        "privacy.diagnostic.data.level",
        "privacy.kms.activation.telemetry",
    ];

    private static readonly int[] KnownBuilds = [19045, 22631, 26100, 26200];

    private static string CapabilitiesDirectory()
    {
        var directory = Path.Combine(AppContext.BaseDirectory, "capabilities");
        Assert.True(Directory.Exists(directory), $"No existe el directorio de catálogo: {directory}");
        return directory;
    }

    private static CapabilityCatalog LoadWave1()
    {
        var loader = new CatalogLoader();
        var documents = loader.LoadDirectory(CapabilitiesDirectory());
        return new CapabilityCatalog(
            documents[0].Metadata, documents.SelectMany(d => d.Capabilities));
    }

    /// <summary>T4.1: carga, 0 errores, regex de Ids, simetría y ausencia de ciclos.</summary>
    [Fact]
    public void TestWave1Catalog_LoadsAndValidates()
    {
        var catalog = LoadWave1();

        // 24 de la oleada 1 + 14 de la oleada 1b (paso 8b)
        // + 1 neta del 8c (debloat.windows.ai se parte en .recall y .remove)
        // + 29 de la oleada 2 (sección 10, paso 9)
        // + 18 de la oleada 3 (sección 9, paso 10) = 86.
        Assert.Equal(86, catalog.Count);

        // Las 39 de las secciones 1-3 siguen ahí, y el resto son de la sección 10.
        var wave1 = Section1.Concat(Section2).Concat(Section3).ToList();
        Assert.Equal(wave1.OrderBy(i => i, StringComparer.Ordinal),
            catalog.Definitions.Where(d => d.SectionId != 10)
                .Select(d => d.Id).OrderBy(i => i, StringComparer.Ordinal));
        Assert.Equal(29, catalog.Definitions.Count(d => d.SectionId == 10));

        var report = new CatalogValidator(KnownBuilds).Validate(catalog);

        // Ningún error: ni de Id, ni de simetría, ni de ciclo, ni de riesgo.
        Assert.True(report.IsValid, report.ErrorSummary);
        Assert.Empty(report.Errors);

        // R-BUILD sólo puede avisar; en este catálogo tampoco debe avisar.
        Assert.Empty(report.Warnings);

        // ADR-0003: toda capacidad declara reversibilidad y cumple su rama.
        Assert.All(catalog.Definitions, d => Assert.NotNull(d.Reversibility));

        foreach (var definition in catalog.Definitions)
        {
            Assert.Matches(CatalogValidator.IdPattern, definition.Id);
            // Implemented = el motor la ejecuta contra fakes con tests;
            // Specified = declarada con acciones pero sin verificar en el pin.
            Assert.Contains(definition.State,
                new[] { CapabilityState.Implemented, CapabilityState.Specified });
            Assert.NotEmpty(definition.Actions);
            Assert.False(string.IsNullOrWhiteSpace(definition.Provenance));
            // Este bucle recorre TODO el catálogo (incluida la sección 10 desde el
            // paso 9), así que la lista de impactos permitidos sale de las reglas:
            // Neutral la mayoría; Improves en las que quitan telemetría o
            // superficie; y Reduces sólo se admite con riesgo >= Medium
            // (CapabilityRules.SecurityImpact), que ninguna de estas cumple.
            Assert.True(
                definition.SecurityImpact is SecurityImpact.Neutral or SecurityImpact.Improves,
                $"{definition.Id}: SecurityImpact={definition.SecurityImpact} no esperado.");

            // Invariantes de riesgo del paso 6, vía el contrato del motor.
            var contract = definition.ToContract();
            Assert.Empty(CapabilityRules.Validate(contract));

            // Orden de acciones único y no negativo.
            Assert.Equal(
                definition.Actions.Select(a => a.Order).Distinct().Count(),
                definition.Actions.Count);
            Assert.All(definition.Actions, a => Assert.True(a.Order >= 0));

            // Simetría explícita, sin depender de que el validador ya la haya visto.
            foreach (var conflict in definition.ConflictsWith)
            {
                var other = catalog.Find(conflict);
                Assert.NotNull(other);
                Assert.Contains(definition.Id, other!.ConflictsWith);
            }

            // Toda dependencia existe (no hay referencias colgando).
            foreach (var dependency in definition.DependsOn)
            {
                Assert.NotNull(catalog.Find(dependency));
            }
        }

        // Sección explícita por capacidad, la que pide el enunciado.
        Assert.All(Section1, id => Assert.Equal(1, catalog[id].SectionId));
        Assert.All(Section2, id => Assert.Equal(2, catalog[id].SectionId));
        Assert.All(Section3, id => Assert.Equal(3, catalog[id].SectionId));

        // Y ningún ciclo de dependencias: el grafo es un DAG (DFS con coloración).
        Assert.Empty(FindCycle(catalog));
    }

    /// <summary>T4.1b: ningún Id se repite entre las tres secciones y
    /// todas las acciones declaran un tipo soportado por el motor.</summary>
    [Fact]
    public void TestWave1Catalog_IdsAreUniqueAndActionsAreSupported()
    {
        var catalog = LoadWave1();
        var all = Section1.Concat(Section2).Concat(Section3).ToList();

        Assert.Equal(all.Count, all.Distinct(StringComparer.Ordinal).Count());
        foreach (var id in all)
        {
            Assert.NotNull(catalog.Find(id));
        }

        var supported = Enum.GetValues<ActionKind>();
        foreach (var action in catalog.Definitions.SelectMany(d => d.Actions))
        {
            Assert.Contains(action.Kind, supported);
            Assert.False(string.IsNullOrWhiteSpace(action.Description));
        }
    }

    /// <summary>DFS con coloración; devuelve la ruta del primer ciclo encontrado.</summary>
    private static IReadOnlyList<string> FindCycle(CapabilityCatalog catalog)
    {
        var state = new Dictionary<string, int>(StringComparer.Ordinal);
        var path = new List<string>();

        IReadOnlyList<string>? Visit(string id)
        {
            state[id] = 1;
            path.Add(id);
            foreach (var dependency in catalog.Find(id)?.DependsOn ?? [])
            {
                if (catalog.Find(dependency) is null)
                {
                    continue;
                }

                var dependencyState = state.GetValueOrDefault(dependency);
                if (dependencyState == 1)
                {
                    return path.Skip(path.IndexOf(dependency)).Append(dependency).ToList();
                }

                if (dependencyState == 0)
                {
                    var found = Visit(dependency);
                    if (found is not null)
                    {
                        return found;
                    }
                }
            }

            path.RemoveAt(path.Count - 1);
            state[id] = 2;
            return null;
        }

        foreach (var definition in catalog.Definitions)
        {
            if (state.GetValueOrDefault(definition.Id) == 0)
            {
                var cycle = Visit(definition.Id);
                if (cycle is not null)
                {
                    return cycle;
                }
            }
        }

        return [];
    }
}
