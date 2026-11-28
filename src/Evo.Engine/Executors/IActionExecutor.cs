using Evo.Core.Actions;
using Evo.Engine.Execution;
using Evo.Engine.Undo;
using Evo.Core.System;

namespace Evo.Engine.Executors;

/// <summary>
/// Entorno de ejecución de una acción: acceso al sistema (interfaces), modo y
/// diario. No conoce la implementación concreta (REQ-004).
/// </summary>
public sealed record ActionContext
{
    public required IRegistryAccessor Registry { get; init; }

    public required IServiceAccessor Services { get; init; }

    public required ITaskAccessor Tasks { get; init; }

    public required IProcessAccessor Processes { get; init; }

    public required ICommandRunner Commands { get; init; }

    public required ExecutionMode Mode { get; init; }

    public required UndoJournal Journal { get; init; }

    public required string CapabilityId { get; init; }

    /// <summary>
    /// Opción explícita del usuario: aceptar ejecutar sin punto de restauración
    /// aunque el contrato lo exija. El motor lo registra en el resumen
    /// (<c>RestorePointWaived</c>). Nunca se activa solo.
    /// </summary>
    public bool AcceptNoRestorePoint { get; init; }

    /// <summary>True solo en <see cref="ExecutionMode.Execute"/>.</summary>
    public bool Mutates => Mode == ExecutionMode.Execute;
}

/// <summary>Ejecutor de un tipo de acción.</summary>
public interface IActionExecutor
{
    /// <summary>Tipo de acción que atiende.</summary>
    ActionKind Kind { get; }

    /// <summary>Aplica (o simula) la acción y registra su inversa.</summary>
    Task<ActionResult> ExecuteAsync(CapabilityAction action, ActionContext context);

    /// <summary>Estado actual de lo que la acción tocaría (para Audit/DryRun).</summary>
    string? ReadCurrentState(CapabilityAction action, ActionContext context);
}
