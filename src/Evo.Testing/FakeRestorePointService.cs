using Evo.Core.Restore;

namespace Evo.Testing;

/// <summary>
/// Punto de restauración falso, configurable. Registra cada llamada en
/// <see cref="Calls"/> para poder comprobar el ORDEN respecto a las mutaciones
/// (el motor debe crear el punto antes de la primera escritura).
/// </summary>
public sealed class FakeRestorePointService : IRestorePointService
{
    private int _next = 1;

    /// <summary>Si es false, <c>IsAvailableAsync</c> devuelve false.</summary>
    public bool Available { get; set; } = true;

    /// <summary>Si es true, <c>CreateAsync</c> falla con <see cref="FailureMessage"/>.</summary>
    public bool FailOnCreate { get; set; }

    /// <summary>Si es true, <c>IsAvailableAsync</c> lanza en vez de devolver false.</summary>
    public bool ThrowOnAvailability { get; set; }

    public string FailureMessage { get; set; } = "la creación del punto falló (fake)";

    /// <summary>Si se fija, se usa como id en vez de "rp-N".</summary>
    public string? ForcedId { get; set; }

    /// <summary>Llamadas en orden: "available" / "create:&lt;descripción&gt;".</summary>
    public List<string> Calls { get; } = [];

    /// <summary>
    /// Se invoca al principio de <c>CreateAsync</c>, antes de decidir el
    /// resultado: permite fotografiar el estado de los fakes y comprobar que
    /// todavía no ha habido ninguna mutación.
    /// </summary>
    public Action? BeforeCreate { get; set; }

    /// <summary>Descripciones de los puntos creados.</summary>
    public List<string> Created { get; } = [];

    public int CreatedCount => Created.Count;

    public Task<bool> IsAvailableAsync(CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        Calls.Add("available");

        if (ThrowOnAvailability)
        {
            throw new InvalidOperationException("no se pudo consultar la Protección del sistema (fake)");
        }

        return Task.FromResult(Available);
    }

    public Task<RestorePointResult> CreateAsync(string description, CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        BeforeCreate?.Invoke();
        Calls.Add($"create:{description}");

        if (FailOnCreate)
        {
            return Task.FromResult(RestorePointResult.Fail(FailureMessage));
        }

        if (!Available)
        {
            // Un servicio no disponible que "crea" sería un fake incoherente.
            return Task.FromResult(RestorePointResult.Fail("Protección del sistema desactivada (fake)"));
        }

        var id = ForcedId ?? $"rp-{_next++}";
        Created.Add(description);
        return Task.FromResult(RestorePointResult.Ok(id));
    }
}
