using System.Text.Json.Serialization;

namespace Evo.Catalog.Model;

/// <summary>Documento JSON completo del catálogo.</summary>
public sealed record CatalogDocument
{
    [JsonPropertyName("metadata")]
    public CatalogMetadata Metadata { get; init; } = new();

    [JsonPropertyName("capabilities")]
    public IReadOnlyList<CapabilityDefinition> Capabilities { get; init; } = [];

    /// <summary>Proyecta el documento a <see cref="CapabilityCatalog"/>.</summary>
    public CapabilityCatalog ToCatalog() => new(Metadata, Capabilities);
}
