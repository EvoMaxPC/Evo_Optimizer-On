using Evo.Core.Enums;

namespace Evo.Core.Confirmation;

/// <summary>Petición de confirmación al usuario.</summary>
public sealed record ConfirmationRequest
{
    /// <summary>Capacidad que se va a aplicar.</summary>
    public required string CapabilityId { get; init; }

    /// <summary>Nombre legible para el diálogo.</summary>
    public required string CapabilityName { get; init; }

    /// <summary>Nivel de confirmación exigido por el contrato.</summary>
    public required ConfirmationType Type { get; init; }

    /// <summary>Riesgo declarado (para el texto y la severidad del diálogo).</summary>
    public required RiskLevel Risk { get; init; }

    /// <summary>
    /// Texto exacto que el usuario debe escribir cuando
    /// <see cref="ConfirmationType.TypeOperationName"/>: el id de la capacidad.
    /// </summary>
    public string RequiredText => CapabilityId;

    /// <summary>Resumen de lo que se va a hacer (una línea por acción).</summary>
    public IReadOnlyList<string> Summary { get; init; } = [];

    /// <summary>Si el punto de restauración está disponible en este momento.</summary>
    public bool RestorePointAvailable { get; init; }
}

/// <summary>Respuesta del usuario.</summary>
public sealed record ConfirmationResponse
{
    public required bool Approved { get; init; }

    /// <summary>Texto escrito por el usuario (sólo relevante en TypeOperationName).</summary>
    public string TypedText { get; init; } = string.Empty;

    public string Reason { get; init; } = string.Empty;

    public static ConfirmationResponse Approve() => new() { Approved = true };

    public static ConfirmationResponse Reject(string reason) =>
        new() { Approved = false, Reason = reason };
}

/// <summary>
/// Confirmación del usuario. El motor la pide ANTES de crear el punto de
/// restauración: no se gasta un punto en algo que el usuario va a rechazar.
/// </summary>
public interface IConfirmationProvider
{
    Task<ConfirmationResponse> ConfirmAsync(
        ConfirmationRequest request,
        CancellationToken cancellationToken = default);
}

/// <summary>
/// Mapeo riesgo → confirmación, sin estado. Es el mismo criterio que
/// <c>CapabilityRules.MinimumConfirmation</c>, aquí en forma de valor para que
/// el motor no dependa de constantes duplicadas.
/// </summary>
public static class ConfirmationLadder
{
    public static ConfirmationType ForRisk(RiskLevel risk) => risk switch
    {
        RiskLevel.Safe => ConfirmationType.None,
        RiskLevel.Low => ConfirmationType.SimpleClick,
        RiskLevel.Medium => ConfirmationType.Summary,
        RiskLevel.High => ConfirmationType.SummaryAndRestorePoint,
        RiskLevel.Critical => ConfirmationType.TypeOperationName,
        _ => ConfirmationType.TypeOperationName,
    };

    /// <summary>
    /// Una confirmación implica pedir punto de restauración cuando su propio
    /// nombre lo dice (resumen + punto) o cuando exige escribir el nombre.
    /// </summary>
    public static bool RequiresRestorePoint(ConfirmationType type) =>
        type is ConfirmationType.SummaryAndRestorePoint or ConfirmationType.TypeOperationName;
}
