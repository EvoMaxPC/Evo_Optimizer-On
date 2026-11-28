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
    /// Restauración mínima exigible según la reversibilidad declarada (ADR-0003).
    /// Sustituye a la regla "Restore=None exige Risk >= High" del paso 3, que
    /// dejaba RestoreLevel.None inutilizable: ahora la red de seguridad que se
    /// exige depende de qué se pierde, no solo del riesgo nominal.
    /// </summary>
    public static RestoreLevel MinimumRestore(Reversibility reversibility, RiskLevel risk) =>
        reversibility switch
        {
            // Reversible: se exige poder deshacer, y además el mínimo por riesgo.
            Reversibility.Reversible => MinimumRestore(risk),
            // NothingToRestore: no hay nada que restaurar; None es legítimo hasta Medium.
            Reversibility.NothingToRestore => RestoreLevel.None,
            // Irreversible: None sólo con riesgo alto y confirmación reforzada.
            Reversibility.Irreversible => RestoreLevel.None,
            _ => MinimumRestore(risk),
        };

    /// <summary>
    /// Reglas de la ADR-0003 sobre (reversibilidad, riesgo, restauración,
    /// confirmación). Devuelve las violaciones (vacía = válido).
    /// </summary>
    public static IReadOnlyList<string> ValidateReversibility(CapabilityContract capability)
    {
        ArgumentNullException.ThrowIfNull(capability);

        var errors = new List<string>();
        var risk = capability.Risk;
        var minimumConfirmation = MinimumConfirmation(risk);

        switch (capability.Reversibility)
        {
            case Reversibility.Reversible:
                if (capability.Restore < RestoreLevel.SessionUndo)
                {
                    errors.Add(
                        $"'{capability.Id}': Reversibility=Reversible exige restauración >= " +
                        $"SessionUndo (declarada {capability.Restore}).");
                }

                if (capability.Restore < MinimumRestore(risk))
                {
                    errors.Add(
                        $"'{capability.Id}': Reversibility=Reversible con riesgo {risk} exige " +
                        $"restauración >= {MinimumRestore(risk)} (declarada {capability.Restore}).");
                }

                break;

            case Reversibility.NothingToRestore:
                if (capability.Restore != RestoreLevel.None)
                {
                    errors.Add(
                        $"'{capability.Id}': Reversibility=NothingToRestore exige Restore=None " +
                        $"(declarada {capability.Restore}): si hay algo que restaurar, la " +
                        "clasificación correcta es Reversible.");
                }

                if (risk > RiskLevel.Medium)
                {
                    errors.Add(
                        $"'{capability.Id}': Reversibility=NothingToRestore sólo se admite con " +
                        $"riesgo <= Medium (declarado {risk}).");
                }

                break;

            case Reversibility.Irreversible:
                if (capability.Restore != RestoreLevel.None)
                {
                    errors.Add(
                        $"'{capability.Id}': Reversibility=Irreversible exige Restore=None " +
                        $"(declarada {capability.Restore}): no se puede prometer restauración de " +
                        "algo que no se puede deshacer.");
                }

                if (risk < RiskLevel.High)
                {
                    errors.Add(
                        $"'{capability.Id}': Reversibility=Irreversible exige riesgo >= High " +
                        $"(declarado {risk}).");
                }

                if (capability.Confirmation < ConfirmationType.Summary)
                {
                    errors.Add(
                        $"'{capability.Id}': Reversibility=Irreversible exige confirmación >= " +
                        $"Summary (declarada {capability.Confirmation}).");
                }

                break;

            default:
                errors.Add($"'{capability.Id}': reversibilidad no definida.");
                break;
        }

        // La confirmación nunca baja del mínimo por riesgo, sea cual sea la rama.
        if (capability.Confirmation < minimumConfirmation)
        {
            errors.Add(
                $"'{capability.Id}': riesgo {risk} exige confirmación {minimumConfirmation} " +
                $"como mínimo (declarada {capability.Confirmation}).");
        }

        return errors;
    }

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

        // ADR-0003: la coherencia de restauración y confirmación depende de la
        // reversibilidad declarada, no sólo del riesgo nominal.
        errors.AddRange(ValidateReversibility(capability));

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
