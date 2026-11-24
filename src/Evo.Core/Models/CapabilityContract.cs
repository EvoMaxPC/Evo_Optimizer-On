using Evo.Core.Enums;

namespace Evo.Core.Models;

/// <summary>
/// Contrato de una capacidad atómica del catálogo EVO. Una capacidad es la
/// unidad mínima que el usuario puede aplicar o revertir por separado
/// (REQ-001: incorporar != ejecutar).
/// </summary>
public sealed record CapabilityContract
{
    /// <summary>Identificador estable, p. ej. <c>atlas:toggle:Animation</c>.</summary>
    public required string Id { get; init; }

    /// <summary>Nombre legible para el usuario.</summary>
    public required string Name { get; init; }

    /// <summary>Descripción funcional de lo que hace.</summary>
    public string Description { get; init; } = string.Empty;

    /// <summary>Sección del inventario del responsable (1-17).</summary>
    public required int SectionId { get; init; }

    /// <summary>Riesgo declarado.</summary>
    public required RiskLevel Risk { get; init; }

    /// <summary>Efecto sobre la seguridad.</summary>
    public required SecurityImpact SecurityImpact { get; init; }

    /// <summary>Privilegio mínimo.</summary>
    public required PrivilegeLevel Privilege { get; init; }

    /// <summary>Restauración ofrecida.</summary>
    public required RestoreLevel Restore { get; init; }

    /// <summary>Confirmación exigida al usuario.</summary>
    public required ConfirmationType Confirmation { get; init; }

    /// <summary>Madurez de la capacidad.</summary>
    public required CapabilityState State { get; init; }

    /// <summary>Linajes que aportan esta capacidad. Nunca vacío.</summary>
    public required IReadOnlyList<Variant> Variants { get; init; }

    /// <summary>Ids de capacidades incompatibles con esta.</summary>
    public IReadOnlyList<string> ConflictsWith { get; init; } = [];

    /// <summary>Ids de capacidades que deben aplicarse antes.</summary>
    public IReadOnlyList<string> DependsOn { get; init; } = [];

    /// <summary>Builds de Windows donde la capacidad está verificada.</summary>
    public IReadOnlyList<int> SupportedBuilds { get; init; } = [];
}
