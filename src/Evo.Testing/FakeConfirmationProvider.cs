using Evo.Core.Confirmation;
using Evo.Core.Enums;

namespace Evo.Testing;

/// <summary>
/// Confirmación falsa. Aprueba o rechaza según se configure y registra las
/// peticiones para poder comprobar qué se pidió y en qué orden.
/// </summary>
public sealed class FakeConfirmationProvider : IConfirmationProvider
{
    /// <summary>Decisión por defecto de todas las peticiones.</summary>
    public bool Approve { get; set; } = true;

    /// <summary>Texto que escribe el usuario en <c>TypeOperationName</c>.</summary>
    public string TypedText { get; set; } = string.Empty;

    /// <summary>Motivo devuelto al rechazar.</summary>
    public string RejectionReason { get; set; } = "rechazado en el fake";

    /// <summary>Si es true, simula que el usuario escribe el id correcto.</summary>
    public bool TypeExactName { get; set; }

    /// <summary>True si el proveedor no se llegó a usar.</summary>
    public bool Unused => Requests.Count == 0;

    public List<ConfirmationRequest> Requests { get; } = [];

    public ConfirmationRequest? Last => Requests.Count == 0 ? null : Requests[^1];

    public Task<ConfirmationResponse> ConfirmAsync(
        ConfirmationRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);
        cancellationToken.ThrowIfCancellationRequested();
        Requests.Add(request);

        if (!Approve)
        {
            return Task.FromResult(ConfirmationResponse.Reject(RejectionReason));
        }

        var typed = TypeExactName ? request.RequiredText : TypedText;
        return Task.FromResult(new ConfirmationResponse { Approved = true, TypedText = typed });
    }
}

/// <summary>Proveedor de confirmación vacío para contratos que no piden nada.</summary>
public sealed class NeverCalledConfirmationProvider : IConfirmationProvider
{
    public int Calls { get; private set; }

    public Task<ConfirmationResponse> ConfirmAsync(
        ConfirmationRequest request,
        CancellationToken cancellationToken = default)
    {
        Calls++;
        return Task.FromResult(ConfirmationResponse.Reject("no debería haberse pedido confirmación"));
    }
}

/// <summary>
/// Ayuda para construir peticiones en tests sin repetir campos.
/// </summary>
public static class ConfirmationRequestFactory
{
    public static ConfirmationRequest For(
        string capabilityId,
        ConfirmationType type,
        RiskLevel risk = RiskLevel.High,
        IReadOnlyList<string>? summary = null) => new()
        {
            CapabilityId = capabilityId,
            CapabilityName = capabilityId,
            Type = type,
            Risk = risk,
            Summary = summary ?? [],
        };
}
