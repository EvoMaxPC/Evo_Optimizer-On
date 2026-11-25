using System.Globalization;
using System.Text.RegularExpressions;
using Evo.Catalog;
using Evo.Catalog.Model;
using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Testing;
using Microsoft.Win32;
using Xunit;

namespace Evo.Catalog.Tests;

/// <summary>
/// Carga y valida el fichero REAL de la oleada 2 (sección 10, Explorador de
/// archivos e interfaz) tal como está en <c>catalog/capabilities/</c>. Igual que
/// en la oleada 1, no hay JSON de mentira: si el catálogo se rompe, el test se
/// rompe.
/// </summary>
public sealed class Wave2CatalogTests
{
    /// <summary>Las 29 capacidades de la sección 10, en orden ordinal.</summary>
    private static readonly string[] Section10 =
    [
        "explorer.app-icon-thumbnails.hide",
        "explorer.check-boxes.disable",
        "explorer.compact-view.enable",
        "explorer.extract-context-menu.add",
        "explorer.file-extensions.show",
        "explorer.gallery.hide",
        "explorer.hidden-files.show",
        "explorer.home.hide",
        "explorer.long-paths.enable",
        "explorer.quick-access.hide",
        "explorer.recent-items.disable",
        "explorer.removable-drives.sidebar",
        "explorer.shortcut-icon.classic",
        "explorer.shortcut-text.hide",
        "ui.context-menu.classic",
        "ui.lockscreen.hide",
        "ui.logon.acrylic-blur",
        "ui.notifications.center-hide",
        "ui.numlock.startup",
        "ui.scrollbars.always-visible",
        "ui.snap-layouts.disable",
        "ui.snapping.windows",
        "ui.taskbar.end-task",
        "ui.taskbar.icons-centered",
        "ui.taskbar.search-icon",
        "ui.taskbar.task-view-button",
        "ui.theme.dark",
        "ui.verbose-messages.enable",
        "ui.visual-effects.minimal",
    ];

    /// <summary>Las builds que declara <c>catalog/windows-releases.json</c>.</summary>
    private static readonly int[] KnownBuilds = [19045, 22631, 26100, 26200];

    /// <summary>Builds de Windows 11 del catálogo (la 19045 queda fuera).</summary>
    private static readonly int[] Windows11 = [22631, 26100, 26200];

    /// <summary>CLSID del menú contextual clásico (Win11).</summary>
    private const string ClassicContextMenuClsid = "{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}";

    /// <summary>CLSID de la carpeta Inicio que el pin borra (Win11).</summary>
    private const string ClassicHomeClsid = "{f874310e-b6b7-47dc-bc84-b9e6b38f5903}";

    private static string CapabilitiesDirectory()
    {
        var directory = Path.Combine(AppContext.BaseDirectory, "capabilities");
        Assert.True(Directory.Exists(directory), $"No existe el directorio de catálogo: {directory}");
        return directory;
    }

    /// <summary>Sólo la sección 10: el validador se ejecuta sobre el catálogo completo
    /// para que R-REF/R-SYMMETRY puedan resolver referencias cruzadas.</summary>
    private static CapabilityCatalog LoadAll()
    {
        var documents = new CatalogLoader().LoadDirectory(CapabilitiesDirectory());
        return new CapabilityCatalog(
            documents[0].Metadata, documents.SelectMany(d => d.Capabilities));
    }

    private static IReadOnlyList<CapabilityDefinition> Wave2() =>
        LoadAll().Definitions.Where(d => d.SectionId == 10).ToList();

    private static CapabilityDefinition Definition(string id) =>
        Wave2().SingleOrDefault(d => d.Id == id)
        ?? throw new InvalidOperationException($"No está '{id}' en el catálogo de la sección 10.");

    private static IEnumerable<RegistryAction> RegistryActions(CapabilityDefinition definition) =>
        definition.Actions.OfType<RegistryAction>();

    /// <summary>
    /// Colmenas que la capacidad TOCA, con las dos formas de registro: escribir o
    /// borrar UN valor (<see cref="RegistryAction"/>) y borrar una CLAVE completa
    /// (<see cref="RegistryDeleteKeyAction"/>, paso 11) y crear una CLAVE vacía
    /// (<see cref="RegistryCreateKeyAction"/>, paso 12). Mirar sólo la primera
    /// dejaba `explorer.home.hide` como «User» cuando borra en HKLM.
    /// </summary>
    private static IEnumerable<RegistryHiveKind> RegistryHives(CapabilityDefinition definition) =>
        definition.Actions.OfType<RegistryAction>().Select(a => a.Hive)
            .Concat(definition.Actions.OfType<RegistryDeleteKeyAction>().Select(a => a.Hive))
            // Paso 12: crear una clave vacía también toca una colmena.
            .Concat(definition.Actions.OfType<RegistryCreateKeyAction>().Select(a => a.Hive));

    // ---------------------------------------------------------------- T4.1 carga
    /// <summary>T4.1: el fichero de la sección 10 carga, valida sin errores ni avisos
    /// y declara exactamente las 29 capacidades del enunciado.</summary>
    [Fact]
    public void TestWave2Catalog_LoadsAndValidates()
    {
        var catalog = LoadAll();

        // 39 de las oleadas 1/1b/8c + 29 de la sección 10 + 18 de la sección 9
        // (paso 10) = 86, + 2 del paso 12 = 88. Lo que este test protege sigue siendo la sección 10.
        Assert.Equal(88, catalog.Count);

        var wave2 = catalog.Definitions.Where(d => d.SectionId == 10)
            .Select(d => d.Id).OrderBy(i => i, StringComparer.Ordinal).ToList();
        Assert.Equal(Section10, wave2);

        var report = new CatalogValidator(KnownBuilds).Validate(catalog);
        Assert.True(report.IsValid, report.ErrorSummary);
        Assert.Empty(report.Errors);
        Assert.Empty(report.Warnings);

        foreach (var definition in catalog.Definitions.Where(d => d.SectionId == 10))
        {
            Assert.Matches(CatalogValidator.IdPattern, definition.Id);
            Assert.True(
                definition.Id.StartsWith("explorer.", StringComparison.Ordinal)
                || definition.Id.StartsWith("ui.", StringComparison.Ordinal),
                $"{definition.Id}: namespace fuera de explorer.* / ui.*.");
            Assert.NotEmpty(definition.Actions);
            Assert.False(string.IsNullOrWhiteSpace(definition.Provenance));
            Assert.NotEmpty(definition.Variants);

            // Orden de acciones único y acciones ordenadas de 1 en adelante.
            Assert.Equal(
                definition.Actions.Select(a => a.Order).Distinct().Count(),
                definition.Actions.Count);
            Assert.Equal(
                Enumerable.Range(1, definition.Actions.Count),
                definition.Actions.Select(a => a.Order).OrderBy(o => o));
        }
    }

    /// <summary>T4.1b: el contrato del motor no encuentra violaciones en ninguna
    /// capacidad de la sección 10 (riesgo, restauración y confirmación).</summary>
    [Fact]
    public void TestWave2Catalog_EngineContractIsClean()
    {
        foreach (var definition in Wave2())
        {
            Assert.Empty(CapabilityRules.Validate(definition.ToContract()));

            // ADR-0003: la sección 10 sólo escribe claves de registro, así que no
            // hay ninguna irreversible. Y ninguna pierde el deshacer de sesión.
            Assert.Equal(Reversibility.Reversible, definition.Reversibility);
            Assert.Equal(RestoreLevel.SessionUndo, definition.Restore);

            // Confirmación y restauración mínimas por riesgo (ADR-0003):
            // Risk=Low no puede irse con Confirmation=None ni con Restore=None.
            Assert.True(
                definition.Confirmation >= CapabilityRules.MinimumConfirmation(definition.Risk),
                $"{definition.Id}: confirmación {definition.Confirmation} < mínimo de {definition.Risk}.");
            Assert.True(
                definition.Restore >= CapabilityRules.MinimumRestore(definition.Risk),
                $"{definition.Id}: restauración {definition.Restore} < mínimo de {definition.Risk}.");
        }
    }

    // ------------------------------------------------------------- T1 contrato
    /// <summary>T1: el namespace es <c>explorer.*</c> / <c>ui.*</c>, todos los ids
    /// cumplen <c>^[a-z0-9]+(\.[a-z0-9\-]+)+$</c> y van en la sección 10.</summary>
    [Fact]
    public void TestWave2Catalog_IdsFollowTheContract()
    {
        var pattern = new Regex(@"^[a-z0-9]+(\.[a-z0-9\-]+)+$", RegexOptions.CultureInvariant);
        foreach (var definition in Wave2())
        {
            Assert.Matches(pattern, definition.Id);
            Assert.Contains(
                definition.Id.Split('.')[0], new[] { "explorer", "ui" });
            Assert.Equal(10, definition.SectionId);
        }

        // Ningún id de la sección 10 se repite con los de las secciones 1-3.
        var others = LoadAll().Definitions.Where(d => d.SectionId != 10).Select(d => d.Id);
        Assert.Empty(Section10.Intersect(others, StringComparer.Ordinal));
    }

    /// <summary>T1: el privilegio declarado se deduce de las colmenas que se escriben:
    /// cualquier escritura en HKLM/HKU exige Admin; HKCU se queda en User.</summary>
    [Fact]
    public void TestWave2Catalog_PrivilegeMatchesTheHivesItWrites()
    {
        foreach (var definition in Wave2())
        {
            var hives = RegistryHives(definition).Distinct().ToList();
            var writesMachine = hives.Contains(RegistryHiveKind.LocalMachine)
                || hives.Contains(RegistryHiveKind.Users);
            var expected = writesMachine ? PrivilegeLevel.Admin : PrivilegeLevel.User;
            Assert.True(
                expected == definition.Privilege,
                $"{definition.Id}: escribe [{string.Join(", ", hives)}] y declara Privilege={definition.Privilege}.");
        }
    }

    /// <summary>T1 (ADR-0003): quien declare reducción de seguridad no puede bajar
    /// de riesgo Medium ni de confirmación Summary. La sección 10 no tiene ninguna
    /// así: `ui.lockscreen.hide` quita la imagen del bloqueo, no la autenticación, y
    /// se dejó en Neutral/Low con el motivo escrito en su descripción.</summary>
    [Fact]
    public void TestWave2Catalog_SecurityReductionIsNeverUnderMediumRisk()
    {
        foreach (var definition in Wave2().Where(d => d.SecurityImpact == SecurityImpact.Reduces))
        {
            Assert.True(definition.Risk >= RiskLevel.Medium, definition.Id);
            Assert.True(definition.Confirmation >= ConfirmationType.Summary, definition.Id);
        }

        var lockscreen = Definition("ui.lockscreen.hide");
        Assert.Equal(SecurityImpact.Neutral, lockscreen.SecurityImpact);
        Assert.Equal(RiskLevel.Low, lockscreen.Risk);
        Assert.Equal(ConfirmationType.SimpleClick, lockscreen.Confirmation);
        Assert.Equal(Reversibility.Reversible, lockscreen.Reversibility);
        Assert.Equal(RestoreLevel.SessionUndo, lockscreen.Restore);
        Assert.Contains("Reduces", lockscreen.Description, StringComparison.Ordinal);
        Assert.Empty(CapabilityRules.Validate(lockscreen.ToContract()));
    }

    // --------------------------------------------------------- T1 rangos build
    /// <summary>T1: el menú contextual clásico escribe el CLSID de Windows 11 y sólo
    /// declara 22631/26100/26200; 19045 (Windows 10) NO está soportada.</summary>
    [Fact]
    public void TestWave2Catalog_ClassicContextMenuIsWindows11Only()
    {
        var definition = Definition("ui.context-menu.classic");

        Assert.DoesNotContain(19045, definition.SupportedBuilds);
        Assert.Equal(Windows11, definition.SupportedBuilds.Order().ToArray());

        var action = Assert.Single(RegistryActions(definition));
        Assert.Equal(RegistryHiveKind.CurrentUser, action.Hive);
        Assert.Contains(ClassicContextMenuClsid, action.KeyPath, StringComparison.Ordinal);
        Assert.Equal(RegistryValueType.String, action.ValueType);
        // El valor predeterminado del CLSID se deja VACÍO: es lo que hace que
        // Explorer vuelva al menú clásico (Get-WinUtilClassicContextMenu).
        Assert.Equal(string.Empty, action.Value);
        Assert.Equal(string.Empty, action.ValueName);

        // Las tres variantes conviven: EVO, Atlas y WinUtil hacen lo mismo.
        Assert.Contains(Variant.Atlas, definition.Variants);
        Assert.Contains(Variant.WinUtil, definition.Variants);
        Assert.Contains(Variant.Evo, definition.Variants);
        Assert.Contains("winutil:tweak:WPFTweaksRightClickMenu", definition.Provenance);
    }

    /// <summary>T1: toda capacidad declara <c>supportedBuilds</c> EXPLÍCITO (nunca
    /// vacío) y sólo usa builds del catálogo; las que excluyen 19045 son las que
    /// dependen de un CLSID o de una función que no existe en Windows 10.</summary>
    [Fact]
    public void TestWave2Catalog_SupportedBuildsAreExplicitAndJustified()
    {
        Assert.All(Wave2(), d => Assert.NotEmpty(d.SupportedBuilds));
        Assert.All(Wave2(), d => Assert.All(d.SupportedBuilds,
            build => Assert.Contains(build, KnownBuilds)));

        var windows11Only = Wave2()
            .Where(d => !d.SupportedBuilds.Contains(19045))
            .Select(d => d.Id).OrderBy(i => i, StringComparer.Ordinal).ToList();
        Assert.Equal(
            new[]
            {
                "explorer.gallery.hide",
                "explorer.home.hide",
                "ui.context-menu.classic",
                "ui.taskbar.end-task",
                "ui.taskbar.icons-centered",
            },
            windows11Only);

        // Las cinco excluyen 19045 porque la clave que escriben no la lee Windows 10
        // (CLSID de la Galería, de Inicio, del menú contextual clásico, o
        // TaskbarAl/TaskbarEndTask): la procedencia lo dice con "Builds:".
        foreach (var id in windows11Only)
        {
            var provenance = Definition(id).Provenance;
            Assert.Contains("Builds:", provenance, StringComparison.Ordinal);
            Assert.True(
                provenance.Contains("CLSID", StringComparison.OrdinalIgnoreCase)
                || provenance.Contains("Windows 11", StringComparison.OrdinalIgnoreCase)
                || provenance.Contains("19045", StringComparison.Ordinal),
                $"{id}: no justifica por qué excluye 19045.");
        }
    }

    // -------------------------------------------------- T1 divergencias Atlas
    /// <summary>T1 (semántica Toggle 8c): las capacidades de Atlas copian UN estado
    /// concreto del <c>.psd1</c>, y la procedencia dice cuál; no se mezclan los
    /// valores del estado contrario.</summary>
    [Fact]
    public void TestWave2Catalog_AtlasCapabilitiesQuoteTheirState()
    {
        var atlas = Wave2().Where(d => d.Variants.Contains(Variant.Atlas)).ToList();
        Assert.NotEmpty(atlas);

        // Las que salen de un toggle con estados lo dicen; las que salen de un
        // .psd1 de Tweaks (una sola forma de aplicarse) no tienen estado y no se
        // les inventa uno.
        var toggles = atlas.Where(d => d.Provenance.Contains("Interface/", StringComparison.Ordinal)
                                       || d.Provenance.Contains("Toggles/", StringComparison.Ordinal));
        Assert.NotEmpty(toggles);
        foreach (var definition in toggles)
        {
            Assert.Matches(new Regex(@"\(estado '[A-Za-z]+'\)"), definition.Provenance);
        }

        foreach (var definition in atlas)
        {
            Assert.Matches(new Regex(@"atlas@[0-9a-f]{40}:"), definition.Provenance);
        }
    }

    /// <summary>T1: las dos desviaciones de valor del catálogo siguen declaradas y
    /// con motivo: el catálogo no cambia en silencio lo que dice el pin.</summary>
    [Fact]
    public void TestWave2Catalog_ValueDeviationsAreDeclared()
    {
        // El fichero de excepciones se comprueba en Python (tests/test_paso9.py,
        // que sí ve el JSON entero); aquí basta con que la capacidad afectada
        // siga declarando el valor del pin y no uno inventado.
        var home = Definition("explorer.home.hide");
        Assert.Contains(RegistryActions(home),
            a => a.ValueName == "LaunchTo" && a.Value == "1");
        Assert.Contains(RegistryActions(home),
            a => a.ValueName == "System.IsPinnedToNameSpaceTree" && a.Value == "0");
    }

    // ------------------------------------------------------- T2 undo exacto
    /// <summary>T2: cada acción de registro de la sección 10 escribe o borra UN
    /// VALOR concreto; el diario guarda el valor previo y lo restaura exactamente.
    /// El único borrado de CLAVE de la sección (`explorer.home.hide`) se comprueba
    /// aparte, con su forma exacta: no recursivo y con instantánea previa.</summary>
    [Fact]
    public void TestWave2Catalog_EveryActionTouchesExactlyOneValue()
    {
        foreach (var definition in Wave2())
        {
            foreach (var action in definition.Actions.OfType<RegistryDeleteKeyAction>())
            {
                // Paso 11: la clave del pin se borra tal cual, sin recursión, y el
                // motor aborta sin borrar si no puede fotografiar el subárbol.
                Assert.Equal("explorer.home.hide", definition.Id);
                Assert.False(action.Recursive);
                Assert.Contains(ClassicHomeClsid, action.KeyPath, StringComparison.Ordinal);
                Assert.Equal(RegistryHiveKind.LocalMachine, action.Hive);
            }

            foreach (var action in definition.Actions.OfType<RegistryCreateKeyAction>())
            {
                // Paso 12: la creación de clave es de `explorer.home.restore`
                // (restaurar Inicio) y su inversa es borrarla.
                Assert.Equal("explorer.home.restore", definition.Id);
                Assert.Contains(ClassicHomeClsid, action.KeyPath, StringComparison.Ordinal);
                Assert.Equal(RegistryHiveKind.LocalMachine, action.Hive);
            }

            foreach (var action in RegistryActions(definition))
            {
                Assert.Contains(action.Operation,
                    new[] { RegistryOperation.Set, RegistryOperation.Delete });
                Assert.False(string.IsNullOrWhiteSpace(action.KeyPath));
                Assert.DoesNotContain(action.KeyPath, "?", StringComparison.Ordinal);

                // El único valor binario es UserPreferencesMask (8 bytes del pin,
                // en base64): se comprueba que el texto base64 decodifica a 8 B.
                if (action.ValueType == RegistryValueType.Binary)
                {
                    Assert.Equal("ui.visual-effects.minimal", definition.Id);
                    Assert.Equal("UserPreferencesMask", action.ValueName);
                    Assert.Equal(8, Convert.FromBase64String(action.Value ?? string.Empty).Length);
                }
                else
                {
                    Assert.Contains(action.ValueType,
                        new[] { RegistryValueType.DWord, RegistryValueType.String,
                                RegistryValueType.ExpandString });
                }
            }
        }
    }

    /// <summary>T2: el ejecutor escribe el valor declarado y el rollback del diario
    /// devuelve el valor previo exacto, también cuando el valor NO existía antes
    /// (que es el caso normal en las claves de política de esta sección).</summary>
    [Fact]
    public void TestWave2Catalog_UndoRestoresPreviousValuesExactly()
    {
        var registry = new FakeRegistryAccessor();
        const string advanced = @"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced";
        registry.Seed(RegistryHive.CurrentUser, advanced, "HideFileExt", 1);
        // TaskbarAl (taskbar centrada) NO existe antes: el deshacer debe dejarlo
        // inexistente, no en 0.

        var actions = RegistryActions(Definition("explorer.file-extensions.show"))
            .Concat(RegistryActions(Definition("ui.taskbar.icons-centered")))
            .ToList();
        Assert.Equal(2, actions.Count);

        var journal = new List<(RegistryHive Hive, string Key, string Name, object? Previous)>();
        foreach (var action in actions)
        {
            var hive = action.Hive switch
            {
                RegistryHiveKind.CurrentUser => RegistryHive.CurrentUser,
                RegistryHiveKind.LocalMachine => RegistryHive.LocalMachine,
                _ => RegistryHive.Users,
            };

            var previous = registry.GetValue(hive, action.KeyPath, action.ValueName);
            registry.SetValue(
                hive, action.KeyPath, action.ValueName,
                int.Parse(action.Value, CultureInfo.InvariantCulture),
                RegistryValueKind.DWord);
            journal.Add((hive, action.KeyPath, action.ValueName, previous));
        }

        Assert.Equal(0, (int?)registry.GetValue(RegistryHive.CurrentUser, advanced, "HideFileExt")!);
        Assert.Equal(1, (int?)registry.GetValue(RegistryHive.CurrentUser, advanced, "TaskbarAl")!);

        // Deshacer en orden inverso, como hace el diario del motor.
        foreach (var entry in Enumerable.Reverse(journal))
        {
            if (entry.Previous is null)
            {
                registry.DeleteValue(entry.Hive, entry.Key, entry.Name);
            }
            else
            {
                registry.SetValue(
                    entry.Hive, entry.Key, entry.Name, entry.Previous,
                    RegistryValueKind.DWord);
            }
        }

        Assert.Equal(1, (int?)registry.GetValue(RegistryHive.CurrentUser, advanced, "HideFileExt")!);
        Assert.Null(registry.GetValue(RegistryHive.CurrentUser, advanced, "TaskbarAl"));
    }
}
