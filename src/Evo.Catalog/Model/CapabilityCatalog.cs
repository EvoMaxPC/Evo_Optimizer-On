using System.Text.Json.Serialization;

namespace Evo.Catalog.Model;

/// <summary>Metadatos de versión y origen del catálogo.</summary>
public sealed record CatalogMetadata
{
    [JsonPropertyName("version")]
    public string Version { get; init; } = string.Empty;

    [JsonPropertyName("schemaVersion")]
    public int SchemaVersion { get; init; } = 1;

    [JsonPropertyName("provenance")]
    public string Provenance { get; init; } = string.Empty;

    [JsonPropertyName("generatedBy")]
    public string GeneratedBy { get; init; } = string.Empty;
}

/// <summary>Colección de capacidades indexada por Id.</summary>
public sealed class CapabilityCatalog
{
    private readonly Dictionary<string, CapabilityDefinition> _byId;

    public CapabilityCatalog(CatalogMetadata metadata, IEnumerable<CapabilityDefinition> capabilities)
    {
        ArgumentNullException.ThrowIfNull(metadata);
        ArgumentNullException.ThrowIfNull(capabilities);

        Metadata = metadata;
        Definitions = capabilities.ToList();
        _byId = new Dictionary<string, CapabilityDefinition>(StringComparer.Ordinal);
        foreach (var definition in Definitions)
        {
            if (definition.Id is not null)
            {
                _byId[definition.Id] = definition;
            }
        }
    }

    public CatalogMetadata Metadata { get; }

    public IReadOnlyList<CapabilityDefinition> Definitions { get; }

    public int Count => Definitions.Count;

    /// <summary>Busca por Id exacto (case-sensitive).</summary>
    public CapabilityDefinition? Find(string id) =>
        _byId.TryGetValue(id, out var definition) ? definition : null;

    /// <summary>Acceso indexado por Id.</summary>
    public CapabilityDefinition this[string id] => _byId[id];

    /// <summary>Ids presentes (en orden de declaración).</summary>
    public IReadOnlyList<string> Ids => Definitions.Select(d => d.Id).ToList();
}
