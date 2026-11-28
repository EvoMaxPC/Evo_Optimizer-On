using Evo.Core.Actions;
using Evo.Core.Confirmation;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Core.Restore;
using Evo.Core.System;
using Evo.Catalog;
using Evo.Catalog.Model;
using Evo.Detection;
using Evo.Detection.Model;
using Evo.Engine;
using Evo.Engine.Execution;
using Evo.Engine.Executors;
using Evo.Engine.Undo;
using Evo.Testing;
using Evo.Windows;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;

namespace Evo.App;

/// <summary>Modelo de vista principal. Lógica sin controles WPF.</summary>
public sealed class MainViewModel
{
    private readonly ISystemEnvironment _environment;
    private readonly WindowsDetector _detector;
    private readonly IConfirmationProvider _confirmations;
    private readonly IRestorePointService _restorePoints;
    private readonly ICommandRunner _commands;
    private readonly IRegistryAccessor? _registry;
    private readonly IReadOnlyDictionary<ActionKind, IActionExecutor> _executors;
    private readonly IReadOnlyDictionary<string, CapabilityContract> _catalog;
    /// <summary>Un diario por capacidad (indexado por Id), para que el deshacer
    /// de una fila revierta SOLO lo aplicado de esa capacidad.</summary>
    private readonly Dictionary<string, UndoJournal> _journals = new(StringComparer.Ordinal);
    private readonly Dictionary<string, CapabilityDefinition> _byCapabilityId = new(StringComparer.Ordinal);

    private MainViewModel(
        ISystemEnvironment environment,
        WindowsDetector detector,
        IConfirmationProvider confirmations,
        IRestorePointService restorePoints,
        ICommandRunner commands,
        IReadOnlyDictionary<ActionKind, IActionExecutor> executors,
        IReadOnlyDictionary<string, CapabilityContract> catalog,
        CompatibilityResult compatibility,
        IReadOnlyList<CapabilityDefinition> capabilities,
        ObservableCollection<SectionViewModel> sections,
        string resultsText,
        bool hasResults,
        bool canApplyAny,
        IRegistryAccessor? registry = null)
    {
        _environment = environment;
        _detector = detector;
        _confirmations = confirmations;
        _restorePoints = restorePoints;
        _commands = commands;
        _executors = executors;
        _catalog = catalog;
        _registry = registry;

        CurrentBuild = compatibility.Build;
        UBR = compatibility.Ubr;
        EditionID = compatibility.EditionId;
        InstallationType = compatibility.InstallationType;
        IsWindowsCompatible = compatibility.IsSupported;
        CompatibilityMessage = compatibility.Reason;
        Sections = sections;
        ResultsText = resultsText;
        HasResults = hasResults;
        CanApplyAny = canApplyAny;

        _byCapabilityId = capabilities.ToDictionary(c => c.Id, StringComparer.Ordinal);
    }

    /// <summary>Build detectado.</summary>
    public int CurrentBuild { get; }

    /// <summary>UBR detectado.</summary>
    public int UBR { get; }

    /// <summary>Edición detectada.</summary>
    public string EditionID { get; } = string.Empty;

    /// <summary>Tipo de instalación (Client / Server).</summary>
    public string InstallationType { get; } = string.Empty;

    /// <summary>True si Windows es compatible (cliente y build conocido).</summary>
    public bool IsWindowsCompatible { get; }

    /// <summary>Mensaje de incompatibilidad (vacío si compatible).</summary>
    public string CompatibilityMessage { get; } = string.Empty;

    /// <summary>Secciones del inventario con sus capacidades.</summary>
    public ObservableCollection<SectionViewModel> Sections { get; } = [];

    /// <summary>Texto del área de resultados.</summary>
    public string ResultsText { get; private set; } = string.Empty;

    /// <summary>True si hay resultados para mostrar.</summary>
    public bool HasResults { get; private set; }

    /// <summary>True si se puede aplicar al menos una capacidad.</summary>
    public bool CanApplyAny { get; }

    /// <summary>Crea el ViewModel detectando Windows y cargando el catálogo del disco.</summary>
    public static MainViewModel Create(
        ISystemEnvironment environment,
        IRegistryAccessor registry,
        IConfirmationProvider confirmations,
        IRestorePointService restorePoints,
        ICommandRunner commands)
    {
        var catalogPath = Path.Combine(AppContext.BaseDirectory, "catalog", "windows-releases.json");
        var releaseCatalog = WindowsReleaseCatalog.LoadFromFile(catalogPath);
        var detector = new WindowsDetector(environment, registry, releaseCatalog);
        var compatibility = detector.Detect();

        var capabilitiesPath = Path.Combine(AppContext.BaseDirectory, "capabilities");
        var catalogLoader = new CatalogLoader();
        var documents = catalogLoader.LoadDirectory(capabilitiesPath);
        var capabilities = documents
            .SelectMany(d => d.Capabilities)
            .OrderBy(c => c.SectionId)
            .ThenBy(c => c.Id, StringComparer.Ordinal)
            .ToList();

        var contracts = capabilities
            .ToDictionary(c => c.Id, c => c.ToContract(), StringComparer.Ordinal);

        var executors = new IActionExecutor[]
        {
            new RegistryActionExecutor(),
            new RegistryDeleteKeyExecutor(),
            new RegistryCreateKeyExecutor(),
            new ServiceActionExecutor(),
            new TaskActionExecutor(),
            new TaskCreateExecutor(),
            new ProcessActionExecutor(),
            new CommandActionExecutor(),
        }.ToDictionary(e => e.Kind, e => e);

        var sections = BuildSections(capabilities, compatibility.Build,
            compatibility.IsSupported);
        var canApplyAny = sections
            .SelectMany(s => s.Capabilities)
            .Any(c => c.IsExecutable && c.CanApply);

        return new MainViewModel(
            environment, detector, confirmations, restorePoints, commands,
            executors, contracts, compatibility, capabilities,
            sections, string.Empty, false, canApplyAny);
    }

    /// <summary>Crea un ViewModel para tests con datos inyectados.</summary>
    public static MainViewModel CreateForTest(
        ISystemEnvironment environment,
        CompatibilityResult compatibility,
        IReadOnlyList<CapabilityDefinition> capabilities,
        IConfirmationProvider confirmations,
        IRestorePointService restorePoints,
        ICommandRunner commands,
        IRegistryAccessor? registry = null)
    {
        var executors = new IActionExecutor[]
        {
            new RegistryActionExecutor(),
            new RegistryDeleteKeyExecutor(),
            new RegistryCreateKeyExecutor(),
            new ServiceActionExecutor(),
            new TaskActionExecutor(),
            new TaskCreateExecutor(),
            new ProcessActionExecutor(),
            new CommandActionExecutor(),
        }.ToDictionary(e => e.Kind, e => e);

        var contracts = capabilities
            .ToDictionary(c => c.Id, c => c.ToContract(), StringComparer.Ordinal);

        // El detector necesita un catálogo de releases que incluya el build
        // bajo prueba, si no Preflight rechazará todo por build desconocido.
        var releaseCatalog = compatibility.Build > 0
            ? new WindowsReleaseCatalog
            {
                Releases = new List<WindowsRelease>
                {
                    new WindowsRelease
                    {
                        Id = $"win{compatibility.Build}",
                        DisplayName = $"Windows {compatibility.Build}",
                        Build = compatibility.Build,
                        BuildMin = compatibility.Build,
                        InstallationType = compatibility.InstallationType,
                        Architectures = ["x64"],
                    },
                },
            }
            : new WindowsReleaseCatalog();
        var detector = new WindowsDetector(environment, new FakeRegistryAccessor(), releaseCatalog);

        var sections = BuildSections(capabilities, compatibility.Build,
            compatibility.IsSupported);
        var canApplyAny = sections
            .SelectMany(s => s.Capabilities)
            .Any(c => c.IsExecutable && c.CanApply);

        return new MainViewModel(
            environment, detector, confirmations, restorePoints, commands,
            executors, contracts, compatibility, capabilities,
            sections, string.Empty, false, canApplyAny, registry);
    }

    private static ObservableCollection<SectionViewModel> BuildSections(
        IReadOnlyList<CapabilityDefinition> capabilities, int currentBuild,
        bool isWindowsCompatible)
    {
        var bySection = capabilities
            .GroupBy(c => c.SectionId)
            .ToDictionary(g => g.Key, g => g.ToList());

        var sections = new ObservableCollection<SectionViewModel>();

        foreach (var sectionId in SectionTitles.Ids)
        {
            var title = SectionTitles.GetTitle(sectionId);
            var sectionCaps = bySection.TryGetValue(int.Parse(sectionId), out var caps)
                ? caps
                : new List<CapabilityDefinition>();

            var vms = sectionCaps.Select(c =>
            {
                var buildCompatible = c.SupportedBuilds.Contains(currentBuild);
                bool executable = c.State == CapabilityState.Implemented &&
                    buildCompatible && isWindowsCompatible;

                string notExecutableReason;
                if (c.State != CapabilityState.Implemented)
                    notExecutableReason = "Especificada: aún no disponible";
                else if (!buildCompatible)
                    notExecutableReason = "Build no soportado";
                else
                    notExecutableReason = string.Empty;

                return new CapabilityViewModel
                {
                    Id = c.Id,
                    Name = c.Name,
                    Description = c.Description,
                    SectionId = c.SectionId.ToString(),
                    Risk = c.Risk,
                    SecurityImpact = c.SecurityImpact ?? Evo.Core.Enums.SecurityImpact.Neutral,
                    Privilege = c.Privilege,
                    State = c.State,
                    Restore = c.Restore,
                    Confirmation = c.Confirmation,
                    SupportedBuilds = c.SupportedBuilds,
                    IsBuildCompatible = buildCompatible,
                    IsExecutable = executable,
                    NotExecutableReason = notExecutableReason,
                };
            });

            sections.Add(new SectionViewModel
            {
                SectionId = sectionId,
                Title = title,
                Capabilities = new ObservableCollection<CapabilityViewModel>(vms),
            });
        }

        return sections;
    }

    /// <summary>Simula (DryRun) una capacidad.</summary>
    public MainViewModel Simulate(CapabilityViewModel capability)
    {
        if (!IsWindowsCompatible) return this;
        if (!capability.CanSimulate) return this;

        ExecuteCapability(capability, ExecutionMode.DryRun);
        return this;
    }

    /// <summary>Aplica (Execute) una capacidad.</summary>
    public MainViewModel Apply(CapabilityViewModel capability)
    {
        if (!IsWindowsCompatible) return this;
        if (!capability.CanApply) return this;

        // Punto de restauración: fail-closed antes de llamar al motor.
        bool requiereRestauracion = capability.Restore == RestoreLevel.RestorePoint
            || ConfirmationLadder.RequiresRestorePoint(capability.Confirmation);
        if (requiereRestauracion
            && !_restorePoints.IsAvailableAsync().GetAwaiter().GetResult())
        {
            AppendResult($"Requiere punto de restauración: pendiente ({capability.Id}).");
            return this;
        }

        ExecuteCapability(capability, ExecutionMode.Execute);
        return this;
    }

    /// <summary>Deshace lo aplicado de una sola capacidad (su fila). Revierte
    /// SOLO las entradas de su propio diario, no las de otras capacidades.</summary>
    public MainViewModel Undo(string capabilityId)
    {
        if (!IsWindowsCompatible) return this;

        if (!_journals.TryGetValue(capabilityId, out var journal) || journal.IsEmpty)
        {
            AppendResult("No hay nada para deshacer");
            return this;
        }

        var context = new UndoContext(
            _registry ?? new WindowsRegistryAccessor(),
            new WindowsServiceAccessor(),
            new UnavailableTaskAccessor(),
            new WindowsProcessAccessor(),
            _commands,
            dryRun: false);

        var report = journal.RollbackAsync(context).GetAwaiter().GetResult();

        if (report.Restored.Count > 0)
        {
            AppendResult($"Se deshizo: {report.Restored.Count} cambio(s) de {capabilityId}");
        }
        else if (report.Failed.Count > 0)
        {
            AppendResult($"Fallo al deshacer: {string.Join(" | ", report.Errors)}");
        }
        else
        {
            AppendResult("No hay nada para deshacer");
        }

        return this;
    }

    /// <summary>Obtiene (o crea si no existe) el diario de la capacidad dada.</summary>
    private UndoJournal JournalFor(string capabilityId)
    {
        if (!_journals.TryGetValue(capabilityId, out var journal))
        {
            journal = new UndoJournal();
            _journals[capabilityId] = journal;
        }

        return journal;
    }

    private void ExecuteCapability(CapabilityViewModel capability, ExecutionMode mode)
    {
        if (!_byCapabilityId.TryGetValue(capability.Id, out var definition))
            return;

        // Tareas programadas y comandos externos: no disponibles todavía.
        foreach (var accion in definition.Actions)
        {
            if (accion is TaskAction or CommandAction)
            {
                AppendResult($"{capability.Name}: no disponible todavía.");
                return;
            }
        }

        var contract = definition.ToContract();
        var steps = definition.Actions
            .Select((a, i) => new PlannedStep
            {
                Order = a.Order,
                Description = a.Description,
                Action = a,
            })
            .OrderBy(s => s.Order)
            .ToList();

        var plan = new ExecutionPlan(contract, steps);
        var coordinator = new EngineCoordinator(
            _environment, _detector, _executors.Values,
            catalog: _catalog.Values,
            restorePoints: _restorePoints,
            confirmations: _confirmations);

        // Cada capacidad usa su propio diario (ETAPA 6-I: deshacer por fila).
        var journal = JournalFor(capability.Id);

        var context = new ActionContext
        {
            Registry = _registry ?? new WindowsRegistryAccessor(),
            Services = new WindowsServiceAccessor(),
            Tasks = new UnavailableTaskAccessor(),
            Processes = new WindowsProcessAccessor(),
            Commands = _commands,
            Mode = mode,
            Journal = journal,
            CapabilityId = capability.Id,
        };

        var summary = coordinator.ExecuteAsync(plan, mode, context).GetAwaiter().GetResult();

        AppendResult(summary);
    }

    private void AppendResult(ExecutionSummary summary)
    {
        var lines = new List<string>
        {
            $"[{summary.Mode}] {summary.CapabilityId}",
            $"  Acciones: {summary.TotalActions} | Éxito: {summary.Succeeded} | Fallo: {summary.Failed} | Omitido: {summary.Skipped}",
        };

        if (summary.Blocked)
            lines.Add($"  Bloqueado: {summary.BlockedReason}");
        if (summary.Aborted)
            lines.Add($"  Abortado: {summary.AbortedReason}");
        if (!string.IsNullOrEmpty(summary.RestorePointId))
            lines.Add($"  Punto de restauración: {summary.RestorePointId}");

        foreach (var r in summary.Results)
        {
            lines.Add($"  - {r.ActionKey}: {r.Status}");
            if (!string.IsNullOrEmpty(r.ErrorMessage))
                lines.Add($"      Error: {r.ErrorMessage}");
        }

        lines.Add(string.Empty);
        AppendResult(string.Join(Environment.NewLine, lines));
    }

    private void AppendResult(string text)
    {
        ResultsText = ResultsText + text + Environment.NewLine;
        HasResults = true;
    }
}
