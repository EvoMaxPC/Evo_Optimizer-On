namespace Evo.Core.Enums;

/// <summary>
/// Resultado de la detección de compatibilidad. Cualquier valor distinto de
/// <see cref="Supported"/> o <see cref="SupportedWithWarning"/> impide aplicar
/// capacidades (REQ-003: un build desconocido NUNCA es compatible).
/// </summary>
public enum CompatibilityStatus
{
    /// <summary>Build y edición soportados, sin advertencias.</summary>
    Supported = 0,

    /// <summary>Soportado, pero con un aviso obligatorio (p. ej. ESU en Windows 10 22H2).</summary>
    SupportedWithWarning = 1,

    /// <summary>InstallationType distinto de Client (Windows Server u otros).</summary>
    ServerRejected = 2,

    /// <summary>Build que no casa con ninguna entrada del catálogo.</summary>
    UnknownBuildRejected = 3,

    /// <summary>Build conocido, pero no soportado por EVO CLEAN.</summary>
    UnsupportedBuildRejected = 4,

    /// <summary>Arquitectura no soportada por el catálogo.</summary>
    ArchitectureRejected = 5,

    /// <summary>No se pudo leer la información del sistema.</summary>
    Indeterminate = 6,
}
