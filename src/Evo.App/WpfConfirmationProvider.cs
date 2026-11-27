using Evo.Core.Confirmation;
using Evo.Core.Enums;

namespace Evo.App;

/// <summary>Proveedor de confirmación para WPF (placeholder: aprueba automáticamente).</summary>
/// <remarks>
/// En una versión completa mostraría un diálogo WPF. Aquí se aprueba
/// automáticamente para mantener la app mínima; el ViewModel no referencia
/// controles WPF, por lo que esta decisión se aísla en la capa de UI.
/// </remarks>
public sealed class WpfConfirmationProvider : IConfirmationProvider
{
    public Task<ConfirmationResponse> ConfirmAsync(
        ConfirmationRequest request,
        System.Threading.CancellationToken cancellationToken = default)
    {
        // Placeholder: sin interacción de usuario en la versión mínima.
        // Se registra la petición para que sea visible en el área de resultados.
        return Task.FromResult(ConfirmationResponse.Approve());
    }
}
