namespace Evo.Core.Enums;

/// <summary>Riesgo de una capacidad para el sistema del usuario.</summary>
public enum RiskLevel
{
    Safe = 0,
    Low = 1,
    Medium = 2,
    High = 3,
    Critical = 4,
}

/// <summary>Efecto sobre la seguridad del sistema.</summary>
public enum SecurityImpact
{
    Improves = 0,
    Neutral = 1,
    Reduces = 2,
}

/// <summary>Privilegio mínimo necesario para ejecutar la capacidad.</summary>
public enum PrivilegeLevel
{
    User = 0,
    Admin = 1,
    TrustedInstaller = 2,
}

/// <summary>Nivel de restauración ofrecido antes/después de aplicar.</summary>
public enum RestoreLevel
{
    None = 0,
    SessionUndo = 1,
    RestorePoint = 2,
    FullBackup = 3,
}

/// <summary>Confirmación exigida al usuario antes de aplicar.</summary>
public enum ConfirmationType
{
    None = 0,
    SimpleClick = 1,
    Summary = 2,
    SummaryAndRestorePoint = 3,
    TypeOperationName = 4,
}

/// <summary>Grado de madurez de la capacidad en el catálogo EVO.</summary>
public enum CapabilityState
{
    /// <summary>Declarada, sin especificación completa.</summary>
    Stub = 0,

    /// <summary>Especificada (contrato, riesgo y restauración cerrados).</summary>
    Specified = 1,

    /// <summary>Implementada y verificable.</summary>
    Implemented = 2,
}

/// <summary>Linaje de la capacidad: de dónde viene el conocimiento.</summary>
public enum Variant
{
    Default = 0,
    WinUtil = 1,
    Atlas = 2,
    Evo = 3,
}
