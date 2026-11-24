namespace Evo.Detection.Model;

/// <summary>
/// Una entrada de <c>catalog/windows-releases.json</c>. Es dato, no código
/// (REQ-003): añadir una versión no debe requerir recompilar el detector.
/// </summary>
public sealed record WindowsRelease
{
    public required string Id { get; init; }

    public required string DisplayName { get; init; }

    public string Product { get; init; } = string.Empty;

    public string Version { get; init; } = string.Empty;

    /// <summary>Build nominal declarado (el mínimo del rango).</summary>
    public required int Build { get; init; }

    public required int BuildMin { get; init; }

    /// <summary>Build máximo; null si el rango es abierto.</summary>
    public int? BuildMax { get; init; }

    public bool OpenEnded { get; init; }

    public required string InstallationType { get; init; }

    public IReadOnlyList<string> Architectures { get; init; } = [];

    public bool EsuRequired { get; init; }

    public string SupportStatus { get; init; } = string.Empty;

    public bool RequiresEsuNotice { get; init; }

    public string Notes { get; init; } = string.Empty;

    /// <summary>True si el build cae dentro del rango declarado.</summary>
    public bool MatchesBuild(int build) =>
        build >= BuildMin && (BuildMax is null || build <= BuildMax);

    /// <summary>True si la arquitectura está declarada para esta versión.</summary>
    public bool SupportsArchitecture(string architecture) =>
        Architectures.Count == 0 ||
        Architectures.Contains(architecture, StringComparer.OrdinalIgnoreCase);
}
