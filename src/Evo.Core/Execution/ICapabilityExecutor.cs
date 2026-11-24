using Evo.Core.Models;

namespace Evo.Core.Execution;

/// <summary>Resultado de una ejecución o simulación.</summary>
public sealed record ExecutionResult
{
    public required bool Success { get; init; }

    public required bool DryRun { get; init; }

    public string Message { get; init; } = string.Empty;

    /// <summary>Id del punto de restauración creado, si procede.</summary>
    public string? RestorePointId { get; init; }

    /// <summary>Detalle legible de lo que se hizo (o se habría hecho).</summary>
    public IReadOnlyList<string> Steps { get; init; } = [];
}

/// <summary>
/// Ejecutor de capacidades. Toda mutación del sistema pasa por aquí
/// (REQ-004): dry-run obligatorio y reversión verificable.
/// </summary>
public interface ICapabilityExecutor
{
    Task<ExecutionResult> ExecuteAsync(CapabilityContract capability, CancellationToken cancellationToken = default);

    Task<ExecutionResult> UndoAsync(CapabilityContract capability, CancellationToken cancellationToken = default);

    Task<ExecutionResult> DryRunAsync(CapabilityContract capability, CancellationToken cancellationToken = default);
}
