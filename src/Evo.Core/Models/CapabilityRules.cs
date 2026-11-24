using Evo.Core.Enums;

namespace Evo.Core.Models;

/// <summary>
/// Reglas de coherencia entre riesgo, confirmación y restauración.
/// Se aplican tanto en el catálogo como en tiempo de ejecución
/// (REQ-001: confirmación según riesgo y restauración cuando proceda).
/// </summary>
public static class CapabilityRules
{
    /// <summary>Restauración mínima exigible para cada nivel de riesgo.</summary>
    public static RestoreLevel MinimumRestore(RiskLevel risk) => risk switch
    {
        RiskLevel.Safe => RestoreLevel.None,
        RiskLevel.Low => RestoreLevel.SessionUndo,
        RiskLevel.Medium => RestoreLevel.RestorePoint,
        RiskLevel.High => RestoreLevel.RestorePoint,
        RiskLevel.Critical => RestoreLevel.FullBackup,
        _ => RestoreLevel.FullBackup,
    };

    /// <summary>Confirmación mínima exigible para cada nivel de riesgo.</summary>
    public static ConfirmationType MinimumConfirmation(RiskLevel risk) => risk switch
    {
        RiskLevel.Safe => ConfirmationType.None,
        RiskLevel.Low => ConfirmationType.SimpleClick,
        RiskLevel.Medium => ConfirmationType.Summary,
        RiskLevel.High => ConfirmationType.SummaryAndRestorePoint,
        RiskLevel.Critical => ConfirmationType.TypeOperationName,
        _ => ConfirmationType.TypeOperationName,
    };

    /// <summary>
    /// Valida el contrato. Devuelve la lista de violaciones (vacía = válido).
    /// </summary>
    public static IReadOnlyList<string> Validate(CapabilityContract capability)
    {
        ArgumentNullException.ThrowIfNull(capability);

        var errors = new List<string>();

        if (string.IsNullOrWhiteSpace(capability.Id))
        {
            errors.Add("Id vacío.");
        }

        if (string.IsNullOrWhiteSpace(capability.Name))
        {
            errors.Add($"'{capability.Id}': Name vacío.");
        }

        if (capability.SectionId is < 1 or > 17)
        {
            errors.Add($"'{capability.Id}': SectionId {capability.SectionId} fuera de 1-17.");
        }

        if (capability.Variants is null || capability.Variants.Count == 0)
        {
            errors.Add($"'{capability.Id}': Variants no puede estar vacío.");
        }

        var minimumConfirmation = MinimumConfirmation(capability.Risk);
        if (capability.Confirmation < minimumConfirmation)
        {
            errors.Add(
                $"'{capability.Id}': riesgo {capability.Risk} exige confirmación " +
                $"{minimumConfirmation} como mínimo (declarada {capability.Confirmation}).");
        }

        var minimumRestore = MinimumRestore(capability.Risk);
        if (capability.Restore < minimumRestore)
        {
            errors.Add(
                $"'{capability.Id}': riesgo {capability.Risk} exige restauración " +
                $"{minimumRestore} como mínimo (declarada {capability.Restore}).");
        }

        if (capability.Restore == RestoreLevel.None && capability.Risk >= RiskLevel.High)
        {
            errors.Add(
                $"'{capability.Id}': RestoreLevel.None es incompatible con riesgo " +
                $"{capability.Risk} (>= High).");
        }

        if (capability.Risk == RiskLevel.Critical &&
            capability.Confirmation != ConfirmationType.TypeOperationName)
        {
            errors.Add($"'{capability.Id}': Critical exige TypeOperationName.");
        }

        if (capability.SecurityImpact == SecurityImpact.Reduces &&
            capability.Risk < RiskLevel.Medium)
        {
            errors.Add(
                $"'{capability.Id}': reducir seguridad exige riesgo >= Medium " +
                $"(declarado {capability.Risk}).");
        }

        if (capability.Privilege == PrivilegeLevel.TrustedInstaller &&
            capability.Risk < RiskLevel.High)
        {
            errors.Add(
                $"'{capability.Id}': TrustedInstaller exige riesgo >= High " +
                $"(declarado {capability.Risk}).");
        }

        if (capability.ConflictsWith is not null && capability.ConflictsWith.Contains(capability.Id))
        {
            errors.Add($"'{capability.Id}': se declara en conflicto consigo misma.");
        }

        if (capability.DependsOn is not null && capability.DependsOn.Contains(capability.Id))
        {
            errors.Add($"'{capability.Id}': se declara dependiente de sí misma.");
        }

        var overlap = (capability.ConflictsWith ?? [])
            .Intersect(capability.DependsOn ?? [], StringComparer.Ordinal)
            .ToList();
        if (overlap.Count > 0)
        {
            errors.Add($"'{capability.Id}': id en ConflictsWith y DependsOn a la vez: {string.Join(", ", overlap)}.");
        }

        return errors;
    }

    /// <summary>True si el contrato cumple todas las reglas.</summary>
    public static bool IsValid(CapabilityContract capability) =>
        Validate(capability).Count == 0;
}
