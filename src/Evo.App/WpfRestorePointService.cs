using Evo.Core.Restore;

namespace Evo.App;

/// <summary>Servicio de puntos de restauración para WPF (placeholder: no disponible).</summary>
/// <remarks>
/// La implementación real (WMI SystemRestore.CreateRestorePoint) queda
/// documentada en ADR-0004 y no está disponible en esta versión. El motor
/// actúa fail-closed: si el contrato exige punto de restauración y el
/// servicio no está disponible, aborta sin mutar nada.
/// </remarks>
public sealed class WpfRestorePointService : IRestorePointService
{
    public Task<bool> IsAvailableAsync(System.Threading.CancellationToken cancellationToken = default)
    {
        return Task.FromResult(false);
    }

    public Task<RestorePointResult> CreateAsync(string description, System.Threading.CancellationToken cancellationToken = default)
    {
        return Task.FromResult(RestorePointResult.Fail("Servicio de puntos de restauración no disponible en esta versión."));
    }
}
