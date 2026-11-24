using System.Diagnostics;
using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Core.System;
using Evo.Engine.Execution;
using Evo.Engine.Executors;
using Evo.Engine.Undo;
using Evo.Detection;

namespace Evo.Engine;

/// <summary>Resultado de la evaluación previa (sin mutar nada).</summary>
public sealed record PreflightResult
{
    public required bool Allowed { get; init; }

    public required string Reason { get; init; }

    public required CompatibilityResult Compatibility { get; init; }

    public required PrivilegeLevel EffectivePrivilege { get; init; }
}

/// <summary>
/// Coordina la ejecución de una capacidad: compatibilidad, privilegios,
/// dependencias, conflictos, dry-run y rollback automático (REQ-001, REQ-004).
/// </summary>
public sealed class EngineCoordinator
{
    private readonly ISystemEnvironment _environment;
    private readonly WindowsDetector _detector;
    private readonly IReadOnlyDictionary<ActionKind, IActionExecutor> _executors;
    private readonly IReadOnlyDictionary<string, CapabilityContract> _catalog;

    public EngineCoordinator(
        ISystemEnvironment environment,
        WindowsDetector detector,
        IEnumerable<IActionExecutor> executors,
        IEnumerable<CapabilityContract>? catalog = null)
    {
        ArgumentNullException.ThrowIfNull(environment);
        ArgumentNullException.ThrowIfNull(detector);
        ArgumentNullException.ThrowIfNull(executors);

        _environment = environment;
        _detector = detector;
        _executors = executors.ToDictionary(e => e.Kind);
        _catalog = (catalog ?? []).ToDictionary(c => c.Id, StringComparer.Ordinal);
    }

    /// <summary>Diario de la última ejecución con cambios aplicados.</summary>
    public UndoJournal Journal { get; } = new();

    /// <summary>Privilegio efectivo del proceso actual.</summary>
    public PrivilegeLevel EffectivePrivilege
    {
        get
        {
            if (!_environment.IsAdmin || !_environment.IsElevated)
            {
                return PrivilegeLevel.User;
            }

            // TrustedInstaller no se puede asumir: se declara solo si el propio
            // entorno lo indica mediante un contrato explícito (no implementado).
            return PrivilegeLevel.Admin;
        }
    }

    /// <summary>
    /// Evalúa si la capacidad puede ejecutarse: compatibilidad de Windows,
    /// privilegios, dependencias y conflictos. No muta nada.
    /// </summary>
    public PreflightResult Preflight(CapabilityContract capability, IEnumerable<string>? appliedCapabilityIds = null)
    {
        ArgumentNullException.ThrowIfNull(capability);

        var compatibility = _detector.Detect();
        var errors = CapabilityRules.Validate(capability).ToList();

        if (!compatibility.IsSupported)
        {
            errors.Add($"Sistema no compatible: {compatibility.Code} — {compatibility.Reason}");
        }

        if (capability.Privilege > EffectivePrivilege)
        {
            errors.Add(
                $"Requiere privilegio {capability.Privilege} y el proceso tiene {EffectivePrivilege}.");
        }

        if (capability.SupportedBuilds.Count > 0 &&
            !capability.SupportedBuilds.Contains(compatibility.Build))
        {
            errors.Add(
                $"Build {compatibility.Build} no está en SupportedBuilds " +
                $"({string.Join(", ", capability.SupportedBuilds)}).");
        }

        var applied = (appliedCapabilityIds ?? []).ToHashSet(StringComparer.Ordinal);

        foreach (var dependency in capability.DependsOn)
        {
            if (_catalog.Count > 0 && !_catalog.ContainsKey(dependency))
            {
                errors.Add($"La dependencia '{dependency}' no existe en el catálogo.");
            }

            if (!applied.Contains(dependency))
            {
                errors.Add($"Falta la dependencia '{dependency}'.");
            }
        }

        foreach (var conflict in capability.ConflictsWith)
        {
            if (applied.Contains(conflict))
            {
                errors.Add($"Conflicto con la capacidad ya aplicada '{conflict}'.");
            }
        }

        return new PreflightResult
        {
            Allowed = errors.Count == 0,
            Reason = string.Join(" | ", errors),
            Compatibility = compatibility,
            EffectivePrivilege = EffectivePrivilege,
        };
    }

    /// <summary>Ejecuta (o simula) un plan completo con rollback automático.</summary>
    public async Task<ExecutionSummary> ExecuteAsync(
        ExecutionPlan plan,
        ExecutionMode mode,
        ActionContext template,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(plan);
        ArgumentNullException.ThrowIfNull(template);

        var stopwatch = Stopwatch.StartNew();
        var preflight = Preflight(plan.Capability);

        if (!preflight.Allowed)
        {
            return new ExecutionSummary
            {
                CapabilityId = plan.Capability.Id,
                Mode = mode,
                Results = [],
                Duration = stopwatch.Elapsed,
                BlockedReason = preflight.Reason,
                PlannedActions = plan.Steps.Select(s => s.Description).ToList(),
            };
        }

        var planErrors = plan.Validate();
        if (planErrors.Count > 0)
        {
            return new ExecutionSummary
            {
                CapabilityId = plan.Capability.Id,
                Mode = mode,
                Results = [],
                Duration = stopwatch.Elapsed,
                BlockedReason = string.Join(" | ", planErrors),
            };
        }

        if (mode == ExecutionMode.Audit)
        {
            var audit = new List<ActionResult>();
            foreach (var step in plan.Steps)
            {
                var executor = _executors[step.Action.Kind];
                audit.Add(ActionResult.Skip(
                    step.Action.Key,
                    executor.ReadCurrentState(step.Action, template) ?? "sin estado legible",
                    step.Description));
            }

            return new ExecutionSummary
            {
                CapabilityId = plan.Capability.Id,
                Mode = mode,
                Results = audit,
                Duration = stopwatch.Elapsed,
                PlannedActions = plan.Steps.Select(s => s.Description).ToList(),
            };
        }

        var results = new List<ActionResult>();
        var journal = new UndoJournal();
        var context = template with { Mode = mode, Journal = journal, CapabilityId = plan.Capability.Id };
        var failed = false;

        foreach (var step in plan.Steps)
        {
            cancellationToken.ThrowIfCancellationRequested();

            if (!_executors.TryGetValue(step.Action.Kind, out var executor))
            {
                results.Add(ActionResult.Fail(
                    step.Action.Key, $"No hay ejecutor para {step.Action.Kind}.", description: step.Description));
                failed = true;
                break;
            }

            try
            {
                var result = await executor.ExecuteAsync(step.Action, context).ConfigureAwait(false);
                results.Add(result);

                if (result.Status == ActionStatus.Failed)
                {
                    failed = true;
                    break;
                }
            }
            catch (Exception ex) when (ex is not OperationCanceledException and not OutOfMemoryException)
            {
                results.Add(ActionResult.Fail(
                    step.Action.Key, ex.Message, description: step.Description));
                failed = true;
                break;
            }
        }

        var rollbackEntries = journal.Entries.ToList();

        if (failed && mode == ExecutionMode.Execute)
        {
            // Rollback automático LIFO de lo ya aplicado.
            var undoContext = new UndoContext(
                template.Registry, template.Services, template.Tasks,
                template.Processes, template.Commands);
            // Tras un rollback el diario queda vacío: el estado es el inicial.
            await journal.RollbackAsync(undoContext).ConfigureAwait(false);
            stopwatch.Stop();
            return new ExecutionSummary
            {
                CapabilityId = plan.Capability.Id,
                Mode = mode,
                Results = results,
                Duration = stopwatch.Elapsed,
                UndoJournalEntry = rollbackEntries,
                PlannedActions = plan.Steps.Select(s => s.Description).ToList(),
            };
        }

        if (mode == ExecutionMode.Execute)
        {
            // El diario del coordinador acumula las entradas aplicadas para que
            // el llamante pueda deshacer manualmente más tarde.
            foreach (var entry in rollbackEntries)
            {
                Journal.Add(entry);
            }
        }

        stopwatch.Stop();
        return new ExecutionSummary
        {
            CapabilityId = plan.Capability.Id,
            Mode = mode,
            Results = results,
            Duration = stopwatch.Elapsed,
            UndoJournalEntry = rollbackEntries,
            PlannedActions = plan.Steps.Select(s => s.Description).ToList(),
        };
    }

    /// <summary>Deshace el diario acumulado del coordinador.</summary>
    public Task<RollbackResult> RollbackAsync(ActionContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        var undoContext = new UndoContext(
            context.Registry, context.Services, context.Tasks, context.Processes, context.Commands);
        return Journal.RollbackAsync(undoContext);
    }
}
