using System.Diagnostics;
using Evo.Core.Actions;
using Evo.Core.Confirmation;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Core.Restore;
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
/// dependencias, conflictos, confirmación, punto de restauración, dry-run y
/// rollback automático (REQ-001, REQ-004).
/// </summary>
/// <remarks>
/// En <see cref="ExecutionMode.Execute"/> y sólo en ese modo, antes de la
/// primera mutación:
/// <list type="number">
///   <item>se pide la confirmación que exige el contrato (nunca en DryRun/Audit);</item>
///   <item>si el contrato pide punto de restauración (<c>Restore &gt;= RestorePoint</c> o
///   confirmación <c>SummaryAndRestorePoint</c>/<c>TypeOperationName</c>) se crea el
///   punto;</item>
///   <item>si el punto no está disponible o falla, se aborta la ejecución sin
///   mutar nada (fail-closed), salvo <c>AcceptNoRestorePoint</c> explícito, que
///   queda registrado en el resumen.</item>
/// </list>
/// </remarks>
public sealed class EngineCoordinator
{
    private readonly ISystemEnvironment _environment;
    private readonly WindowsDetector _detector;
    private readonly IReadOnlyDictionary<ActionKind, IActionExecutor> _executors;
    private readonly IReadOnlyDictionary<string, CapabilityContract> _catalog;
    private readonly IRestorePointService? _restorePoints;
    private readonly IConfirmationProvider? _confirmations;

    public EngineCoordinator(
        ISystemEnvironment environment,
        WindowsDetector detector,
        IEnumerable<IActionExecutor> executors,
        IEnumerable<CapabilityContract>? catalog = null,
        IRestorePointService? restorePoints = null,
        IConfirmationProvider? confirmations = null)
    {
        ArgumentNullException.ThrowIfNull(environment);
        ArgumentNullException.ThrowIfNull(detector);
        ArgumentNullException.ThrowIfNull(executors);

        _environment = environment;
        _detector = detector;
        _executors = executors.ToDictionary(e => e.Kind);
        _catalog = (catalog ?? []).ToDictionary(c => c.Id, StringComparer.Ordinal);
        _restorePoints = restorePoints;
        _confirmations = confirmations;
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

    /// <summary>True si el contrato exige punto de restauración antes de mutar.</summary>
    public static bool RequiresRestorePoint(CapabilityContract capability)
    {
        ArgumentNullException.ThrowIfNull(capability);

        return capability.Restore >= RestoreLevel.RestorePoint
            || ConfirmationLadder.RequiresRestorePoint(capability.Confirmation);
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
        var planned = plan.Steps.Select(s => s.Description).ToList();
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
                PlannedActions = planned,
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
                PlannedActions = planned,
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
                PlannedActions = planned,
            };
        }

        // --- Puerta previa a la primera mutación (sólo Execute) ----------------
        string? restorePointId = null;
        var requiresRestorePoint = RequiresRestorePoint(plan.Capability);
        var restorePointWaived = false;
        var confirmationType = plan.Capability.Confirmation;
        var confirmed = false;
        var canceled = false;

        if (mode == ExecutionMode.Execute)
        {
            try
            {
                if (confirmationType != ConfirmationType.None)
                {
                    if (_confirmations is null)
                    {
                        return Aborted(
                            plan, mode, stopwatch, planned,
                            "No hay proveedor de confirmación configurado y el contrato exige " +
                            $"{confirmationType}: se aborta sin mutar nada.");
                    }

                    var pointAvailableForPrompt = requiresRestorePoint
                        && _restorePoints is not null
                        && await IsRestorePointAvailableAsync(cancellationToken);

                    var response = await _confirmations.ConfirmAsync(
                        new ConfirmationRequest
                        {
                            CapabilityId = plan.Capability.Id,
                            CapabilityName = plan.Capability.Name,
                            Type = confirmationType,
                            Risk = plan.Capability.Risk,
                            Summary = planned,
                            RestorePointAvailable = pointAvailableForPrompt,
                        },
                        cancellationToken).ConfigureAwait(false);

                    if (!response.Approved)
                    {
                        return Aborted(
                            plan, mode, stopwatch, planned,
                            $"Confirmación rechazada: {response.Reason}".TrimEnd(' ', ':'),
                            confirmationType: confirmationType);
                    }

                    if (confirmationType == ConfirmationType.TypeOperationName &&
                        !string.Equals(response.TypedText, plan.Capability.Id, StringComparison.Ordinal))
                    {
                        return Aborted(
                            plan, mode, stopwatch, planned,
                            $"El texto escrito ('{response.TypedText}') no es el nombre exacto " +
                            $"'{plan.Capability.Id}': se aborta sin mutar nada.",
                            confirmationType: confirmationType);
                    }

                    confirmed = true;
                }

                if (requiresRestorePoint)
                {
                    if (template.AcceptNoRestorePoint)
                    {
                        // Declarado: el usuario asume el riesgo. Se registra en el resumen.
                        restorePointWaived = true;
                    }
                    else if (_restorePoints is null)
                    {
                        return Aborted(
                            plan, mode, stopwatch, planned,
                            "El contrato exige punto de restauración y el motor no tiene " +
                            "servicio de puntos configurado: se aborta sin mutar nada.",
                            confirmed: confirmed, confirmationType: confirmationType);
                    }
                    else if (!await IsRestorePointAvailableAsync(cancellationToken))
                    {
                        return Aborted(
                            plan, mode, stopwatch, planned,
                            "La Protección del sistema no está disponible: no se puede crear el " +
                            "punto de restauración y el contrato lo exige. Se aborta sin mutar nada " +
                            "(fail-closed).",
                            confirmed: confirmed, confirmationType: confirmationType);
                    }
                    else
                    {
                        var created = await _restorePoints.CreateAsync(
                            $"EVO CLEAN — {plan.Capability.Id}", cancellationToken).ConfigureAwait(false);

                        if (!created.Success || string.IsNullOrWhiteSpace(created.Id))
                        {
                            return Aborted(
                                plan, mode, stopwatch, planned,
                                $"No se pudo crear el punto de restauración " +
                                $"({created.ErrorMessage}): se aborta sin mutar nada (fail-closed).",
                                confirmed: confirmed, confirmationType: confirmationType);
                        }

                        restorePointId = created.Id;
                    }
                }
            }
            catch (OperationCanceledException)
            {
                // Cancelación en la puerta previa (confirmación / punto de
                // restauración con token ya cancelado): se trata como cancelación
                // honesta (H1). Nunca se deja escapar una OCE del coordinador.
                canceled = true;
            }
        }

        var results = new List<ActionResult>();
        var journal = new UndoJournal();
        if (restorePointId is not null)
        {
            journal.RestorePointId = restorePointId;
        }

        var context = template with { Mode = mode, Journal = journal, CapabilityId = plan.Capability.Id };
        var failed = false;

        if (!canceled)
        {
            foreach (var step in plan.Steps)
        {
            try
            {
                cancellationToken.ThrowIfCancellationRequested();

                if (!_executors.TryGetValue(step.Action.Kind, out var executor))
                {
                    results.Add(ActionResult.Fail(
                        step.Action.Key, $"No hay ejecutor para {step.Action.Kind}.", description: step.Description));
                    failed = true;
                    break;
                }

                var result = await executor.ExecuteAsync(step.Action, context).ConfigureAwait(false);
                results.Add(result);

                if (result.Status == ActionStatus.Failed)
                {
                    failed = true;
                    break;
                }
            }
            catch (OperationCanceledException)
            {
                // Cancelación antes o durante una acción: se trata como un
                // fallo controlado para que entre por el mismo camino de
                // rollback que cualquier otro fallo (A3).
                canceled = true;
                failed = true;
                break;
            }
            catch (Exception ex) when (ex is not OutOfMemoryException)
            {
                results.Add(ActionResult.Fail(
                    step.Action.Key, ex.Message, description: step.Description));
                failed = true;
                break;
            }
        }
        }

        var rollbackEntries = journal.Entries.ToList();
        RollbackReport? rollbackReport = null;

        // El rollback se ejecuta en Execute cuando hay algo aplicado y la
        // ejecución terminó en fallo o cancelación. Nunca se cancela el
        // rollback (A3/A5): journal.RollbackAsync no recibe el token del
        // llamante, así que una cancelación durante el rollback se ignora y
        // el deshacer se completa.
        bool doRollback = mode == ExecutionMode.Execute &&
                          rollbackEntries.Count > 0 &&
                          (failed || canceled);

        if (doRollback)
        {
            var undoContext = new UndoContext(
                template.Registry, template.Services, template.Tasks,
                template.Processes, template.Commands);
            // Tras un rollback el diario conserva solo las entradas que
            // fallaron (para reintento); las restauradas y no reversibles se
            // descardan. El estado de los recursos ya se deshizo.
            rollbackReport = await journal.RollbackAsync(undoContext).ConfigureAwait(false);
        }

        if (canceled)
        {
            // A1: cancelación antes de cualquier mutación (journal vacío) → no
            // hay rollback. A2: cancelación tras ≥1 mutación → ya se deshizo
            // arriba y se informa Cancelled con el resultado del rollback.
            stopwatch.Stop();
            return new ExecutionSummary
            {
                CapabilityId = plan.Capability.Id,
                Mode = mode,
                Results = results,
                Duration = stopwatch.Elapsed,
                UndoJournalEntry = rollbackEntries,
                RollbackReport = rollbackReport,
                RollbackOutcome = rollbackReport is null
                    ? RollbackOutcome.None
                    : ComputeRollbackOutcome(rollbackReport),
                PlannedActions = planned,
                RestorePointId = restorePointId,
                ConfirmationRequested = confirmationType,
                Confirmed = confirmed,
                RestorePointWaived = restorePointWaived,
                AbortedReason = "Cancelado",
            };
        }

        if (failed && mode == ExecutionMode.Execute)
        {
            // Rollback automático LIFO de lo ya aplicado (ya ejecutado arriba
            // cuando doRollback es true; rollbackReport lo refleja).
            stopwatch.Stop();
            return new ExecutionSummary
            {
                CapabilityId = plan.Capability.Id,
                Mode = mode,
                Results = results,
                Duration = stopwatch.Elapsed,
                UndoJournalEntry = rollbackEntries,
                RollbackReport = rollbackReport,
                RollbackOutcome = rollbackReport is null
                    ? RollbackOutcome.None
                    : ComputeRollbackOutcome(rollbackReport),
                PlannedActions = planned,
                RestorePointId = restorePointId,
                ConfirmationRequested = confirmationType,
                Confirmed = confirmed,
                RestorePointWaived = restorePointWaived,
            };
        }

        if (mode == ExecutionMode.Execute)
        {
            // El diario del coordinador acumula las entradas aplicadas para que
            // el llamante pueda deshacer manualmente más tarde.
            if (restorePointId is not null)
            {
                Journal.RestorePointId = restorePointId;
            }

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
            RollbackReport = rollbackReport,
            RollbackOutcome = RollbackOutcome.None,
            PlannedActions = planned,
            RestorePointId = restorePointId,
            ConfirmationRequested = confirmationType,
            Confirmed = confirmed,
            RestorePointWaived = restorePointWaived,
        };
    }

    /// <summary>Deshace el diario acumulado del coordinador.</summary>
    public Task<RollbackReport> RollbackAsync(ActionContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        var undoContext = new UndoContext(
            context.Registry, context.Services, context.Tasks, context.Processes, context.Commands);
        return Journal.RollbackAsync(undoContext);
    }

    private static RollbackOutcome ComputeRollbackOutcome(RollbackReport report)
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

    private async Task<bool> IsRestorePointAvailableAsync(CancellationToken cancellationToken)
    {
        if (_restorePoints is null)
        {
            return false;
        }

        try
        {
            return await _restorePoints.IsAvailableAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (Exception ex) when (ex is not OperationCanceledException and not OutOfMemoryException)
        {
            // Fallo al consultar la disponibilidad = no disponible (fail-closed).
            return false;
        }
    }

    private static ExecutionSummary Aborted(
        ExecutionPlan plan,
        ExecutionMode mode,
        Stopwatch stopwatch,
        IReadOnlyList<string> planned,
        string reason,
        bool confirmed = false,
        ConfirmationType confirmationType = ConfirmationType.None)
    {
        stopwatch.Stop();
        return new ExecutionSummary
        {
            CapabilityId = plan.Capability.Id,
            Mode = mode,
            Results = [],
            Duration = stopwatch.Elapsed,
            AbortedReason = reason,
            PlannedActions = planned,
            Confirmed = confirmed,
            ConfirmationRequested = confirmationType,
        };
    }
}
