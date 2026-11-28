namespace Evo.Core.Restore;

/// <summary>
/// Resultado de crear un punto de restauración. <see cref="Success"/> sólo es
/// true si el sistema confirmó la creación y devolvió un identificador: un
/// punto sin id no se puede enlazar al diario, así que no cuenta.
/// </summary>
public sealed record RestorePointResult
{
    public required bool Success { get; init; }

    /// <summary>Identificador del punto (número de secuencia de Windows).</summary>
    public string? Id { get; init; }

    public string ErrorMessage { get; init; } = string.Empty;

    public static RestorePointResult Ok(string id) => new() { Success = true, Id = id };

    public static RestorePointResult Fail(string error) => new() { Success = false, ErrorMessage = error };
}

/// <summary>
/// Creación de puntos de restauración del sistema (REQ-004: el motor sólo ve
/// interfaces). La implementación real —WMI <c>SystemRestore.CreateRestorePoint</c>
/// o <c>Checkpoint-Computer</c>— no existe todavía: queda documentada en
/// <c>docs/adr/ADR-0004-puntos-de-restauracion.md</c> (estado Propuesto) y se
/// valida en una VM del responsable, no en el runner de CI (Server).
/// </summary>
public interface IRestorePointService
{
    /// <summary>
    /// True si el sistema puede crear puntos (Protección del sistema activa en
    /// la unidad del sistema y servicio disponible). Si devuelve false el motor
    /// aborta la ejecución antes de mutar nada.
    /// </summary>
    Task<bool> IsAvailableAsync(CancellationToken cancellationToken = default);

    /// <summary>Crea un punto con la descripción dada.</summary>
    Task<RestorePointResult> CreateAsync(string description, CancellationToken cancellationToken = default);
}
