using Evo.Core.Enums;
using Evo.Core.Models;
using Xunit;

namespace Evo.Core.Tests;

/// <summary>
/// ADR-0003: reglas de reversibilidad. Positivos y negativos por cada rama
/// (Reversible, NothingToRestore, Irreversible) y la interacción con el riesgo.
/// </summary>
public sealed class ReversibilityTests
{
    private static CapabilityContract Contract(
        Reversibility reversibility,
        RiskLevel risk,
        RestoreLevel restore,
        ConfirmationType confirmation) => new()
        {
            Id = "evo:test:reversibility",
            Name = "Reversibilidad",
            Description = "Caso de prueba de la ADR-0003.",
            SectionId = 1,
            Risk = risk,
            SecurityImpact = SecurityImpact.Neutral,
            Privilege = PrivilegeLevel.Admin,
            Restore = restore,
            Reversibility = reversibility,
            Confirmation = confirmation,
            State = CapabilityState.Specified,
            Variants = [Variant.Evo],
        };

    // ------------------------------------------------------------ Reversible

    [Fact]
    public void ReversibleConSessionUndoYRiesgoBajoEsValido()
    {
        var contract = Contract(
            Reversibility.Reversible, RiskLevel.Low,
            RestoreLevel.SessionUndo, ConfirmationType.SimpleClick);

        Assert.Empty(CapabilityRules.Validate(contract));
    }

    [Fact]
    public void ReversibleConRestoreNoneEsInvalido()
    {
        var contract = Contract(
            Reversibility.Reversible, RiskLevel.Safe,
            RestoreLevel.None, ConfirmationType.None);

        var errors = CapabilityRules.Validate(contract);

        Assert.Contains(errors, e => e.Contains("SessionUndo", StringComparison.Ordinal));
    }

    [Fact]
    public void ReversibleConRiesgoMedioExigeRestorePoint()
    {
        var contract = Contract(
            Reversibility.Reversible, RiskLevel.Medium,
            RestoreLevel.SessionUndo, ConfirmationType.Summary);

        var errors = CapabilityRules.Validate(contract);

        Assert.Contains(errors, e => e.Contains("RestorePoint", StringComparison.Ordinal));
    }

    // ------------------------------------------------------- NothingToRestore

    [Fact]
    public void NothingToRestoreConNoneYRiesgoSafeEsValido()
    {
        var contract = Contract(
            Reversibility.NothingToRestore, RiskLevel.Safe,
            RestoreLevel.None, ConfirmationType.None);

        Assert.Empty(CapabilityRules.Validate(contract));
    }

    [Fact]
    public void NothingToRestoreSeAdmiteHastaRiesgoMedium()
    {
        var contract = Contract(
            Reversibility.NothingToRestore, RiskLevel.Medium,
            RestoreLevel.None, ConfirmationType.Summary);

        Assert.Empty(CapabilityRules.Validate(contract));
    }

    [Fact]
    public void NothingToRestoreConRiesgoAltoEsInvalido()
    {
        var contract = Contract(
            Reversibility.NothingToRestore, RiskLevel.High,
            RestoreLevel.None, ConfirmationType.SummaryAndRestorePoint);

        var errors = CapabilityRules.Validate(contract);

        Assert.Contains(errors, e => e.Contains("Medium", StringComparison.Ordinal));
    }

    [Fact]
    public void NothingToRestoreConRestoreDistintoDeNoneEsInvalido()
    {
        var contract = Contract(
            Reversibility.NothingToRestore, RiskLevel.Low,
            RestoreLevel.SessionUndo, ConfirmationType.SimpleClick);

        var errors = CapabilityRules.Validate(contract);

        Assert.Contains(errors, e => e.Contains("Restore=None", StringComparison.Ordinal));
    }

    // ----------------------------------------------------------- Irreversible

    [Fact]
    public void IrreversibleConRiesgoAltoYConfirmacionDeResumenEsValido()
    {
        var contract = Contract(
            Reversibility.Irreversible, RiskLevel.High,
            RestoreLevel.None, ConfirmationType.SummaryAndRestorePoint);

        Assert.Empty(CapabilityRules.Validate(contract));
    }

    [Fact]
    public void IrreversibleConRiesgoBajoEsInvalido()
    {
        var contract = Contract(
            Reversibility.Irreversible, RiskLevel.Low,
            RestoreLevel.None, ConfirmationType.Summary);

        var errors = CapabilityRules.Validate(contract);

        Assert.Contains(errors, e => e.Contains("High", StringComparison.Ordinal));
    }

    [Fact]
    public void IrreversibleConConfirmacionSimpleClickEsInvalido()
    {
        var contract = Contract(
            Reversibility.Irreversible, RiskLevel.High,
            RestoreLevel.None, ConfirmationType.SimpleClick);

        var errors = CapabilityRules.Validate(contract);

        Assert.Contains(errors, e => e.Contains("Summary", StringComparison.Ordinal));
    }

    [Fact]
    public void IrreversibleConRestorePointEsInvalido()
    {
        var contract = Contract(
            Reversibility.Irreversible, RiskLevel.High,
            RestoreLevel.RestorePoint, ConfirmationType.SummaryAndRestorePoint);

        var errors = CapabilityRules.Validate(contract);

        Assert.Contains(errors, e => e.Contains("Restore=None", StringComparison.Ordinal));
    }

    [Fact]
    public void IrreversibleCriticalSigueExigiendoTypeOperationName()
    {
        var contract = Contract(
            Reversibility.Irreversible, RiskLevel.Critical,
            RestoreLevel.None, ConfirmationType.SummaryAndRestorePoint);

        var errors = CapabilityRules.Validate(contract);

        Assert.Contains(errors, e => e.Contains("TypeOperationName", StringComparison.Ordinal));
    }

    // ------------------------------------------------- mínimo de restauración

    [Fact]
    public void MinimumRestoreDependeDeLaReversibilidad()
    {
        Assert.Equal(RestoreLevel.None,
            CapabilityRules.MinimumRestore(Reversibility.NothingToRestore, RiskLevel.Medium));
        Assert.Equal(RestoreLevel.SessionUndo,
            CapabilityRules.MinimumRestore(Reversibility.Reversible, RiskLevel.Low));
        Assert.Equal(RestoreLevel.RestorePoint,
            CapabilityRules.MinimumRestore(Reversibility.Reversible, RiskLevel.High));
        Assert.Equal(RestoreLevel.None,
            CapabilityRules.MinimumRestore(Reversibility.Irreversible, RiskLevel.High));
    }
}
