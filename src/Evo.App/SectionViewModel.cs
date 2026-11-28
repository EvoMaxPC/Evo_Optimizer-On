using System.Collections.ObjectModel;

namespace Evo.App;

/// <summary>Modelo de vista de una sección del inventario de usuario.</summary>
public sealed class SectionViewModel
{
    /// <summary>Identificador de la sección (número de cadena).</summary>
    public required string SectionId { get; init; }

    /// <summary>Título exacto de la sección (según INVENTARIO_USUARIO.md).</summary>
    public required string Title { get; init; }

    /// <summary>Capacidades de la sección.</summary>
    public required ObservableCollection<CapabilityViewModel> Capabilities { get; init; }

    /// <summary>True si la sección tiene al menos una capacidad.</summary>
    public bool HasCapabilities => Capabilities.Count > 0;
}
