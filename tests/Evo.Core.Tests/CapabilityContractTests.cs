using Evo.Core.Enums;
using Evo.Core.Models;
using Xunit;

namespace Evo.Core.Tests;

/// <summary>Reglas de riesgo vs confirmación y restauración.</summary>
public sealed class CapabilityContractTests
{
    private static CapabilityContract Sample(
        RiskLevel risk = RiskLevel.Low,
        ConfirmationType confirmation = ConfirmationType.SimpleClick,
        RestoreLevel restore = RestoreLevel.SessionUndo,
        SecurityImpact impact = SecurityImpact.Neutral,
        PrivilegeLevel privilege = PrivilegeLevel.User) => new()
        {
            Id = "evo:test:sample",
            Name = "Sample",
            Description = "Capacidad de prueba.",
            SectionId = 9,
            Risk = risk,
            SecurityImpact = impact,
            Privilege = privilege,
            Restore = restore,
            Confirmation = confirmation,
            State = CapabilityState.Specified,
            Variants = [Variant.Evo],
            ConflictsWith = [],
            DependsOn = [],
            SupportedBuilds = [19045, 22631, 26100, 26200],
        };

    [Fact]
    public void ContratoValidoNoTieneErrores()
    {
        Assert.Empty(CapabilityRules.Validate(Sample()));
        Assert.True(CapabilityRules.IsValid(Sample()));
    }

    [Fact]
    public void CriticalExigeTypeOperationName()
    {
        var contract = Sample(
            risk: RiskLevel.Critical,
            confirmation: ConfirmationType.Summary,
            restore: RestoreLevel.FullBackup);

        var errors = CapabilityRules.Validate(contract);

        Assert.Contains(errors, e => e.Contains("TypeOperationName", StringComparison.Ordinal));
    }

    [Fact]
    public void CriticalConTypeOperationNameYFullBackupEsValido()
    {
        var contract = Sample(
            risk: RiskLevel.Critical,
            confirmation: ConfirmationType.TypeOperationName,
            restore: RestoreLevel.FullBackup);

        Assert.Empty(CapabilityRules.Validate(contract));
    }

    [Theory]
    [InlineData(RiskLevel.High)]
    [InlineData(RiskLevel.Critical)]
    public void RestoreNoneEsIncompatibleConRiesgoAlto(RiskLevel risk)
    {
        var contract = Sample(
            risk: risk,
            confirmation: ConfirmationType.TypeOperationName,
            restore: RestoreLevel.None);

        var errors = CapabilityRules.Validate(contract);

        Assert.Contains(errors, e => e.Contains("RestoreLevel.None", StringComparison.Ordinal));
    }

    [Fact]
    public void RestoreNoneConRiesgoMedioEsValido()
    {
        var contract = Sample(
            risk: RiskLevel.Medium,
            confirmation: ConfirmationType.Summary,
            restore: RestoreLevel.None);

        Assert.DoesNotContain(
            CapabilityRules.Validate(contract),
            e => e.Contains("RestoreLevel.None", StringComparison.Ordinal));
    }

    [Theory]
    [InlineData(RiskLevel.Safe, ConfirmationType.None, RestoreLevel.None)]
    [InlineData(RiskLevel.Low, ConfirmationType.SimpleClick, RestoreLevel.SessionUndo)]
    [InlineData(RiskLevel.Medium, ConfirmationType.Summary, RestoreLevel.RestorePoint)]
    [InlineData(RiskLevel.High, ConfirmationType.SummaryAndRestorePoint, RestoreLevel.RestorePoint)]
    [InlineData(RiskLevel.Critical, ConfirmationType.TypeOperationName, RestoreLevel.FullBackup)]
    public void MinimosPorRiesgoSonLosEsperados(
        RiskLevel risk,
        ConfirmationType confirmation,
        RestoreLevel restore)
    {
        Assert.Equal(confirmation, CapabilityRules.MinimumConfirmation(risk));
        Assert.Equal(restore, CapabilityRules.MinimumRestore(risk));
    }

    [Fact]
    public void ConfirmacionPorDebajoDelMinimoFalla()
    {
        var contract = Sample(risk: RiskLevel.High, confirmation: ConfirmationType.SimpleClick,
            restore: RestoreLevel.RestorePoint);

        Assert.Contains(
            CapabilityRules.Validate(contract),
            e => e.Contains("confirmación", StringComparison.Ordinal));
    }

    [Fact]
    public void ReducirSeguridadConRiesgoBajoFalla()
    {
        var contract = Sample(impact: SecurityImpact.Reduces);

        Assert.Contains(
            CapabilityRules.Validate(contract),
            e => e.Contains("reducir seguridad", StringComparison.Ordinal));
    }

    [Fact]
    public void TrustedInstallerExigeRiesgoAlto()
    {
        var contract = Sample(privilege: PrivilegeLevel.TrustedInstaller);

        Assert.Contains(
            CapabilityRules.Validate(contract),
            e => e.Contains("TrustedInstaller", StringComparison.Ordinal));
    }

    [Fact]
    public void SectionIdFueraDeRangoFalla()
    {
        var contract = Sample() with { SectionId = 18 };

        Assert.Contains(
            CapabilityRules.Validate(contract),
            e => e.Contains("SectionId", StringComparison.Ordinal));
    }

    [Fact]
    public void VariantsVacioFalla()
    {
        var contract = Sample() with { Variants = [] };

        Assert.Contains(
            CapabilityRules.Validate(contract),
            e => e.Contains("Variants", StringComparison.Ordinal));
    }

    [Fact]
    public void AutoConflictoYAutoDependenciaFAllan()
    {
        var contract = Sample() with
        {
            ConflictsWith = ["evo:test:sample"],
            DependsOn = ["evo:test:sample"],
        };

        var errors = CapabilityRules.Validate(contract);

        Assert.Contains(errors, e => e.Contains("conflicto consigo", StringComparison.Ordinal));
        Assert.Contains(errors, e => e.Contains("dependiente de sí", StringComparison.Ordinal));
    }

    [Fact]
    public void IdEnConflictoYDependenciaFalla()
    {
        var contract = Sample() with
        {
            ConflictsWith = ["evo:test:other"],
            DependsOn = ["evo:test:other"],
        };

        Assert.Contains(
            CapabilityRules.Validate(contract),
            e => e.Contains("ConflictsWith y DependsOn", StringComparison.Ordinal));
    }

    [Fact]
    public void EnumsTienenLosValoresExigidos()
    {
        Assert.Equal(
            new[] { "Safe", "Low", "Medium", "High", "Critical" },
            Enum.GetNames<RiskLevel>());
        Assert.Equal(
            new[] { "Improves", "Neutral", "Reduces" },
            Enum.GetNames<SecurityImpact>());
        Assert.Equal(
            new[] { "User", "Admin", "TrustedInstaller" },
            Enum.GetNames<PrivilegeLevel>());
        Assert.Equal(
            new[] { "None", "SessionUndo", "RestorePoint", "FullBackup" },
            Enum.GetNames<RestoreLevel>());
        Assert.Equal(
            new[] { "None", "SimpleClick", "Summary", "SummaryAndRestorePoint", "TypeOperationName" },
            Enum.GetNames<ConfirmationType>());
        Assert.Equal(
            new[] { "Stub", "Specified", "Implemented" },
            Enum.GetNames<CapabilityState>());
        Assert.Equal(
            new[] { "Default", "WinUtil", "Atlas", "Evo" },
            Enum.GetNames<Variant>());
    }
}
