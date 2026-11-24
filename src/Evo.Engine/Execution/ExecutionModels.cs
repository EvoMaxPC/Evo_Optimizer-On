using Evo.Core.Enums;
using Evo.Core.Models;

namespace Evo.Engine.Execution;

/// <summary>Modo de ejecución del motor.</summary>
public enum ExecutionMode
{
    /// <summary>Simula sin mutar nada (REQ-004).</summary>
    DryRun = 0,

    /// <summary>Aplica de verdad, con diario de deshacer.</summary>
    Execute = 1,

    /// <summary>Solo lee el estado actual y lo informa.</summary>
    Audit = 2,
}

/// <summary>Estado de una acción tras ejecutarse.</summary>
public enum ActionStatus
{
    Success = 0,
    Skipped = 1,
    Failed = 2,
}

/// <summary>Resultado de una acción atómica.</summary>
public sealed record ActionResult
{
    public required string ActionKey { get; init; }

    public required ActionStatus Status { get; init; }

    public bool Success => Status == ActionStatus.Success;

    public string ErrorMessage { get; init; } = string.Empty;

    /// <summary>Estado previo serializado (null si no existía).</summary>
    public string? PreviousState { get; init; }

    /// <summary>Estado posterior serializado (null si se borró).</summary>
    public string? NewState { get; init; }

    /// <summary>True si la acción se aplicó realmente (no en DryRun/Audit).</summary>
    public bool Applied { get; init; }

    /// <summary>Descripción legible de la acción.</summary>
    public string Description { get; init; } = string.Empty;

    /// <summary>Crea un resultado de éxito.</summary>
    public static ActionResult Ok(string key, string? previous, string? next, bool applied, string description = "") =>
        new()
        {
            ActionKey = key,
            Status = ActionStatus.Success,
            PreviousState = previous,
            NewState = next,
            Applied = applied,
            Description = description,
        };

    /// <summary>Crea un resultado omitido.</summary>
    public static ActionResult Skip(string key, string reason, string description = "") =>
        new()
        {
            ActionKey = key,
            Status = ActionStatus.Skipped,
            ErrorMessage = reason,
            Description = description,
        };

    /// <summary>Crea un resultado fallido.</summary>
    public static ActionResult Fail(string key, string error, string? previous = null, string description = "") =>
        new()
        {
            ActionKey = key,
            Status = ActionStatus.Failed,
            ErrorMessage = error,
            PreviousState = previous,
            Description = description,
        };
}

/// <summary>Resumen de una ejecución completa.</summary>
public sealed record ExecutionSummary
{
    public required string CapabilityId { get; init; }

    public required ExecutionMode Mode { get; init; }

    public required IReadOnlyList<ActionResult> Results { get; init; }

    public int TotalActions => Results.Count;

    public int Succeeded => Results.Count(r => r.Status == ActionStatus.Success);

    public int Failed => Results.Count(r => r.Status == ActionStatus.Failed);

    public int Skipped => Results.Count(r => r.Status == ActionStatus.Skipped);

    public TimeSpan Duration { get; init; }

    /// <summary>True si falló alguna acción.</summary>
    public bool HasFailures => Failed > 0;

    /// <summary>True si se aplicó algún cambio real.</summary>
    public bool Mutated => Results.Any(r => r.Applied);

    /// <summary>Entradas del diario generadas por esta ejecución (una por cambio).</summary>
    public IReadOnlyList<Undo.UndoJournalEntry> UndoJournalEntry { get; init; } = [];

    /// <summary>Motivo del rechazo previo (compatibilidad, privilegios…).</summary>
    public string BlockedReason { get; init; } = string.Empty;

    /// <summary>True si el motor rechazó la capacidad antes de actuar.</summary>
    public bool Blocked => !string.IsNullOrEmpty(BlockedReason);

    /// <summary>Plan evaluado (para informes de DryRun/Audit).</summary>
    public IReadOnlyList<string> PlannedActions { get; init; } = [];

    /// <summary>
    /// Motivo por el que el motor abortó ANTES de la primera mutación
    /// (confirmación rechazada, punto de restauración no disponible o fallido).
    /// Es distinto de <see cref="BlockedReason"/>, que es del preflight.
    /// </summary>
    public string AbortedReason { get; init; } = string.Empty;

    /// <summary>True si el motor abortó por la puerta previa a mutar.</summary>
    public bool Aborted => !string.IsNullOrEmpty(AbortedReason);

    /// <summary>Id del punto de restauración creado, si se creó.</summary>
    public string? RestorePointId { get; init; }

    /// <summary>Confirmación que exigía el contrato (None si no pedía ninguna).</summary>
    public ConfirmationType ConfirmationRequested { get; init; } = ConfirmationType.None;

    /// <summary>True si el usuario aprobó la confirmación.</summary>
    public bool Confirmed { get; init; }

    /// <summary>
    /// True si se ejecutó sin punto de restauración por la opción explícita
    /// <c>AcceptNoRestorePoint</c>. Queda visible para el informe.
    /// </summary>
    public bool RestorePointWaived { get; init; }
}

/// <summary>Acción declarada con su contrato de origen.</summary>
public sealed record PlannedStep
{
    public required int Order { get; init; }

    public required string Description { get; init; }

    public required Evo.Core.Actions.CapabilityAction Action { get; init; }
}

/// <summary>Plan de ejecución de una capacidad, con orden y dependencias.</summary>
public sealed class ExecutionPlan
{
    public ExecutionPlan(CapabilityContract capability, IEnumerable<PlannedStep> steps)
    {
        ArgumentNullException.ThrowIfNull(capability);
        ArgumentNullException.ThrowIfNull(steps);

        Capability = capability;
        Steps = steps.OrderBy(s => s.Order).ToList();
    }

    public CapabilityContract Capability { get; }

    public IReadOnlyList<PlannedStep> Steps { get; }

    public bool IsEmpty => Steps.Count == 0;

    /// <summary>Ids de capacidades de las que depende este plan.</summary>
    public IReadOnlyList<string> Dependencies => Capability.DependsOn;

    /// <summary>Ids de capacidades incompatibles con este plan.</summary>
    public IReadOnlyList<string> Conflicts => Capability.ConflictsWith;

    /// <summary>Valida el plan (orden único, sin huecos negativos, no vacío).</summary>
    public IReadOnlyList<string> Validate()
    {
        var errors = new List<string>();

        if (IsEmpty)
        {
            errors.Add($"'{Capability.Id}': el plan no tiene acciones.");
            return errors;
        }

        foreach (var duplicate in Steps.GroupBy(s => s.Order).Where(g => g.Count() > 1))
        {
            errors.Add($"'{Capability.Id}': {duplicate.Count()} acciones con Order={duplicate.Key}.");
        }

        foreach (var step in Steps)
        {
            if (step.Order < 0)
            {
                errors.Add($"'{Capability.Id}': Order negativo en '{step.Description}'.");
            }
        }

        return errors;
    }
}
