using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Core.System;

namespace Evo.App;

/// <summary>Modelo de vista de una capacidad del catálogo.</summary>
/// <remarks>
/// Sin referencias a controles WPF: se puede instanciar y probar en tests
/// unitarios con fakes de <see cref="Evo.Testing"/>.
/// </remarks>
public sealed class CapabilityViewModel
{
    /// <summary>Identificador de la capacidad.</summary>
    public required string Id { get; init; }

    /// <summary>Nombre legible.</summary>
    public required string Name { get; init; }

    /// <summary>Descripción.</summary>
    public required string Description { get; init; }

    /// <summary>Identificador de la sección a la que pertenece.</summary>
    public required string SectionId { get; init; }

    /// <summary>Nivel de riesgo.</summary>
    public required RiskLevel Risk { get; init; }

    /// <summary>Impacto en seguridad.</summary>
    public required SecurityImpact SecurityImpact { get; init; }

    /// <summary>Privilegio requerido.</summary>
    public required PrivilegeLevel Privilege { get; init; }

    /// <summary>Estado (Implemented / Specified / Stub).</summary>
    public required CapabilityState State { get; init; }

    /// <summary>Nivel de restauración.</summary>
    public required RestoreLevel Restore { get; init; }

    /// <summary>Tipo de confirmación requerida.</summary>
    public required ConfirmationType Confirmation { get; init; }

    /// <summary>Builds de Windows soportados.</summary>
    public required IReadOnlyList<int> SupportedBuilds { get; init; }

    /// <summary>True si la capacidad se puede ejecutar en el build detectado.</summary>
    public required bool IsBuildCompatible { get; init; }

    /// <summary>True si la capacidad es ejecutable (Implemented y compatible).</summary>
    public required bool IsExecutable { get; init; }

    /// <summary>Razón por la que no se puede ejecutar (si aplica).</summary>
    public required string NotExecutableReason { get; init; }

    /// <summary>True si se puede simular (DryRun).</summary>
    public bool CanSimulate => IsExecutable;

    /// <summary>True si se puede aplicar (Execute).</summary>
    public bool CanApply => IsExecutable && Confirmation != ConfirmationType.TypeOperationName;

    /// <summary>True si se puede deshacer.</summary>
    public bool CanUndo => true;
}
