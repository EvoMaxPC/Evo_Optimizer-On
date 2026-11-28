using Evo.Core.Confirmation;
using Evo.Core.Enums;
using System.Text;

namespace Evo.App;

/// <summary>Proveedor de confirmación para WPF con diálogo real.</summary>
/// <remarks>
/// Muestra un <see cref="System.Windows.MessageBox"/> con el nombre de la
/// capacidad, el riesgo y el resumen de acciones. Devuelve false si el
/// usuario elige "No". Las capacidades <see cref="ConfirmationType.None"/>
/// nunca llegan aquí porque el motor no pide confirmación para ellas.
/// </remarks>
public sealed class WpfConfirmationProvider : IConfirmationProvider
{
    public Task<ConfirmationResponse> ConfirmAsync(
        ConfirmationRequest request,
        System.Threading.CancellationToken cancellationToken = default)
    {
        var mensaje = new StringBuilder();
        mensaje.AppendLine($"¿Desea aplicar '{request.CapabilityName}'?");
        mensaje.AppendLine($"Riesgo: {request.Risk}");
        mensaje.AppendLine($"Tipo de confirmación: {request.Type}");
        if (request.Summary is not null)
        {
            foreach (var linea in request.Summary)
                mensaje.AppendLine($"- {linea}");
        }

        var resultado = System.Windows.MessageBox.Show(
            mensaje.ToString(),
            $"Confirmar: {request.CapabilityName}",
            System.Windows.MessageBoxButton.YesNo,
            System.Windows.MessageBoxImage.Warning);

        return resultado == System.Windows.MessageBoxResult.Yes
            ? Task.FromResult(ConfirmationResponse.Approve())
            : Task.FromResult(ConfirmationResponse.Reject("el usuario rechazó la operación"));
    }
}
