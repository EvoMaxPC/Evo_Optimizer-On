using Evo.Core.Enums;
using Evo.Detection.Model;

namespace Evo.Detection;

/// <summary>Resultado completo de la detección de compatibilidad.</summary>
public sealed record CompatibilityResult
{
    /// <summary>Veredicto.</summary>
    public required CompatibilityStatus Status { get; init; }

    /// <summary>Build detectado (0 si no se pudo leer).</summary>
    public required int Build { get; init; }

    /// <summary>UBR detectado.</summary>
    public required int Ubr { get; init; }

    /// <summary>EditionID detectado.</summary>
    public required string EditionId { get; init; }

    /// <summary>InstallationType detectado.</summary>
    public required string InstallationType { get; init; }

    /// <summary>Arquitectura detectada.</summary>
    public required string Architecture { get; init; }

    /// <summary>Entrada del catálogo que casó, si alguna.</summary>
    public WindowsRelease? Release { get; init; }

    /// <summary>Nombre legible de la versión (o del rechazo).</summary>
    public string DisplayName => Release?.DisplayName ?? $"Build {Build} ({InstallationType})";

    /// <summary>Advertencias obligatorias que la UI debe mostrar.</summary>
    public IReadOnlyList<string> Warnings { get; init; } = [];

    /// <summary>Motivo del rechazo (vacío si compatible).</summary>
    public string Reason { get; init; } = string.Empty;

    /// <summary>True solo si se puede aplicar (con o sin advertencia).</summary>
    public bool IsSupported =>
        Status is CompatibilityStatus.Supported or CompatibilityStatus.SupportedWithWarning;

    /// <summary>True si exige aviso de fin de soporte / ESU.</summary>
    public bool RequiresEsuNotice => Release?.RequiresEsuNotice == true;

    /// <summary>Identificador estable del veredicto, para logs y tests.</summary>
    public string Code => Status switch
    {
        CompatibilityStatus.Supported => "SUPPORTED",
        CompatibilityStatus.SupportedWithWarning => "SUPPORTED_WITH_WARNING",
        CompatibilityStatus.ServerRejected => "SERVER_REJECTED",
        CompatibilityStatus.UnknownBuildRejected => "UNKNOWN_BUILD_REJECTED",
        CompatibilityStatus.UnsupportedBuildRejected => "UNSUPPORTED_BUILD_REJECTED",
        CompatibilityStatus.ArchitectureRejected => "ARCHITECTURE_REJECTED",
        _ => "INDETERMINATE",
    };
}
