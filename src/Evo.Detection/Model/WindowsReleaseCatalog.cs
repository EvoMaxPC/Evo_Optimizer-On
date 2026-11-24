using System.Text.Json;
using System.Text.Json.Serialization;

namespace Evo.Detection.Model;

/// <summary>
/// Catálogo de versiones soportadas. Carga estricta: cualquier campo
/// obligatorio ausente o incoherente lanza <see cref="InvalidDataException"/>.
/// </summary>
public sealed class WindowsReleaseCatalog
{
    private static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true,
        ReadCommentHandling = JsonCommentHandling.Skip,
        AllowTrailingCommas = false,
    };

    public int SchemaVersion { get; init; }

    public string Catalog { get; init; } = string.Empty;

    public string Description { get; init; } = string.Empty;

    public WindowsReleasePolicy Policy { get; init; } = new();

    public IReadOnlyList<string> SupportedInstallationTypes { get; init; } = [];

    public IReadOnlyList<WindowsRelease> Releases { get; init; } = [];

    /// <summary>Carga desde disco. Lanza si el fichero no existe o no valida.</summary>
    public static WindowsReleaseCatalog LoadFromFile(string path)
    {
        if (!File.Exists(path))
        {
            throw new FileNotFoundException(
                "No se encontró catalog/windows-releases.json.", path);
        }

        return Parse(File.ReadAllText(path));
    }

    /// <summary>Parsea y valida el JSON del catálogo.</summary>
    public static WindowsReleaseCatalog Parse(string json)
    {
        WindowsReleaseCatalog? catalog;
        try
        {
            catalog = JsonSerializer.Deserialize<WindowsReleaseCatalog>(json, Options);
        }
        catch (JsonException ex)
        {
            throw new InvalidDataException("JSON del catálogo inválido: " + ex.Message, ex);
        }

        if (catalog is null)
        {
            throw new InvalidDataException("El catálogo está vacío.");
        }

        var errors = catalog.Validate();
        if (errors.Count > 0)
        {
            throw new InvalidDataException(
                "Catálogo inválido: " + string.Join(" | ", errors));
        }

        return catalog;
    }

    /// <summary>Violaciones del esquema estricto (vacía = válido).</summary>
    public IReadOnlyList<string> Validate()
    {
        var errors = new List<string>();

        if (SchemaVersion != 1)
        {
            errors.Add($"schemaVersion debe ser 1 (es {SchemaVersion}).");
        }

        if (!string.Equals(Catalog, "windows-releases", StringComparison.Ordinal))
        {
            errors.Add($"catalog debe ser 'windows-releases' (es '{Catalog}').");
        }

        if (SupportedInstallationTypes.Count == 0)
        {
            errors.Add("supportedInstallationTypes no puede estar vacío.");
        }

        if (!SupportedInstallationTypes.Contains("Client", StringComparer.Ordinal))
        {
            errors.Add("supportedInstallationTypes debe incluir 'Client'.");
        }

        if (Releases.Count == 0)
        {
            errors.Add("releases no puede estar vacío.");
        }

        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var release in Releases)
        {
            var tag = string.IsNullOrWhiteSpace(release.Id) ? "<sin id>" : release.Id;

            if (string.IsNullOrWhiteSpace(release.Id))
            {
                errors.Add("Hay una entrada sin id.");
            }
            else if (!seen.Add(release.Id))
            {
                errors.Add($"{tag}: id duplicado.");
            }

            if (string.IsNullOrWhiteSpace(release.DisplayName))
            {
                errors.Add($"{tag}: displayName vacío.");
            }

            if (!string.Equals(release.InstallationType, "Client", StringComparison.Ordinal))
            {
                errors.Add($"{tag}: installationType debe ser 'Client' (es '{release.InstallationType}').");
            }

            if (release.BuildMin <= 0 || release.Build <= 0)
            {
                errors.Add($"{tag}: build/buildMin deben ser positivos.");
            }

            if (release.Build < release.BuildMin)
            {
                errors.Add($"{tag}: build {release.Build} menor que buildMin {release.BuildMin}.");
            }

            if (release.BuildMax is int max)
            {
                if (max < release.BuildMin)
                {
                    errors.Add($"{tag}: buildMax {max} menor que buildMin {release.BuildMin}.");
                }

                if (release.OpenEnded)
                {
                    errors.Add($"{tag}: openEnded=true exige buildMax=null.");
                }
            }
            else if (!release.OpenEnded)
            {
                errors.Add($"{tag}: buildMax=null exige openEnded=true.");
            }

            if (release.Architectures.Count == 0)
            {
                errors.Add($"{tag}: architectures no puede estar vacío.");
            }

            foreach (var architecture in release.Architectures)
            {
                if (architecture is not ("x64" or "arm64" or "x86"))
                {
                    errors.Add($"{tag}: arquitectura no soportada '{architecture}'.");
                }
            }

            var policyMax = Policy.MaxSupportedBuild;
            if (ReleaseRangeExceeds(release, policyMax))
            {
                errors.Add($"{tag}: el rango excede policy.maxSupportedBuild ({policyMax}).");
            }
        }

        foreach (var ordered in Releases.OrderBy(r => r.BuildMin).ToList())
        {
            var overlapping = Releases
                .Where(other => !ReferenceEquals(other, ordered))
                .Where(other => other.BuildMin <= (ordered.BuildMax ?? int.MaxValue)
                                && ordered.BuildMin <= (other.BuildMax ?? int.MaxValue))
                .Select(other => other.Id)
                .ToList();

            if (overlapping.Count > 0)
            {
                errors.Add($"{ordered.Id}: rango de build solapado con {string.Join(", ", overlapping)}.");
            }
        }

        return errors;
    }

    // Un rango abierto NO excede: su tope efectivo ES policy.maxSupportedBuild
    // (por encima de ese valor el build se considera desconocido).
    private static bool ReleaseRangeExceeds(WindowsRelease release, int policyMax)
    {
        if (policyMax <= 0)
        {
            return false;
        }

        if (release.BuildMin > policyMax)
        {
            return true;
        }

        return release.BuildMax is int max && max > policyMax;
    }

    /// <summary>Entrada cuyo rango contiene el build, o null.</summary>
    public WindowsRelease? Find(int build) =>
        Releases.FirstOrDefault(r => r.MatchesBuild(build));

    /// <summary>Tope de builds aceptados; 0 = sin tope.</summary>
    public int MaxSupportedBuild => Policy.MaxSupportedBuild;
}

/// <summary>Política global del catálogo.</summary>
public sealed record WindowsReleasePolicy
{
    [JsonPropertyName("unknownBuild")]
    public string UnknownBuild { get; init; } = "reject";

    [JsonPropertyName("nonClientInstallationType")]
    public string NonClientInstallationType { get; init; } = "reject";

    [JsonPropertyName("maxSupportedBuild")]
    public int MaxSupportedBuild { get; init; }
}
