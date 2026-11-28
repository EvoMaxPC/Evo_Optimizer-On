using System.Text.Json;
using System.Text.Json.Serialization;
using Evo.Catalog.Model;

namespace Evo.Catalog;

/// <summary>Error de carga del catálogo (JSON inválido o esquema incumplido).</summary>
public sealed class CatalogLoadException : Exception
{
    public CatalogLoadException(string message)
        : base(message)
    {
    }

    public CatalogLoadException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

/// <summary>
/// Cargador del catálogo JSON con opciones estrictas: comentarios permitidos,
/// propiedades desconocidas ignoradas, nombres case-insensitive y validación
/// de campos requeridos.
/// </summary>
public sealed class CatalogLoader
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = false,
        NumberHandling = JsonNumberHandling.Strict,
        WriteIndented = false,
        Converters = { new JsonStringEnumConverter(allowIntegerValues: false) },
    };

    /// <summary>Lee todos los <c>*.json</c> de un directorio (orden estable).</summary>
    public IReadOnlyList<CatalogDocument> LoadDirectory(string directory)
    {
        if (!Directory.Exists(directory))
        {
            throw new CatalogLoadException($"El directorio '{directory}' no existe.");
        }

        var documents = new List<CatalogDocument>();
        foreach (var file in Directory.GetFiles(directory, "*.json").OrderBy(f => f, StringComparer.Ordinal))
        {
            documents.Add(LoadFile(file));
        }

        return documents;
    }

    /// <summary>Carga un fichero concreto.</summary>
    public CatalogDocument LoadFile(string path)
    {
        if (!File.Exists(path))
        {
            throw new CatalogLoadException($"El fichero '{path}' no existe.");
        }

        using var stream = File.OpenRead(path);
        return Load(stream);
    }

    /// <summary>Carga desde un stream (tests y pipelines).</summary>
    public CatalogDocument Load(Stream stream)
    {
        ArgumentNullException.ThrowIfNull(stream);

        CatalogDocument? document;
        try
        {
            document = JsonSerializer.Deserialize<CatalogDocument>(stream, Options);
        }
        catch (JsonException ex)
        {
            throw new CatalogLoadException("JSON del catálogo inválido: " + ex.Message, ex);
        }

        if (document is null)
        {
            throw new CatalogLoadException("El catálogo está vacío (null).");
        }

        foreach (var definition in document.Capabilities)
        {
            if (string.IsNullOrWhiteSpace(definition.Id))
            {
                throw new CatalogLoadException("Hay una capacidad sin 'id'.");
            }

            if (string.IsNullOrWhiteSpace(definition.Name))
            {
                throw new CatalogLoadException($"'{definition.Id}': falta 'name'.");
            }

            if (definition.SecurityImpact is null)
            {
                throw new CatalogLoadException($"'{definition.Id}': falta 'securityImpact'.");
            }
        }

        return document;
    }

    /// <summary>Carga desde texto JSON (atajo para tests).</summary>
    public CatalogDocument LoadFromText(string json)
    {
        using var stream = new MemoryStream(System.Text.Encoding.UTF8.GetBytes(json));
        return Load(stream);
    }
}
