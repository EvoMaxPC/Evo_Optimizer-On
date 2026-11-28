using Evo.Catalog;
using Evo.Catalog.Model;
using Evo.Core.Enums;
using Xunit;

namespace Evo.Catalog.Tests;

/// <summary>Los cinco escenarios exigidos por el prompt 7 (T4.2).</summary>
public sealed class CatalogValidatorTests
{
    private static ValidationReport Validate(string json, IEnumerable<int>? builds = null) =>
        new CatalogValidator(builds).Validate(CatalogJson.Parse(json));

    [Fact]
    public void TestValidCatalog_PassesValidation()
    {
        var json = CatalogJson.Document(
            CatalogJson.Capability(
                "privacy.telemetry.diagtrack",
                conflictsWith: "\"network.dns.encrypted\""),
            CatalogJson.Capability("privacy.telemetry.diagtrack-policy"),
            CatalogJson.Capability(
                "network.dns.encrypted",
                conflictsWith: "\"privacy.telemetry.diagtrack\""));

        var report = Validate(json);

        Assert.Empty(report.Errors);
        Assert.True(report.IsValid, report.ErrorSummary);
    }

    [Fact]
    public void TestValidCatalog_LoadsAndIndexes()
    {
        var json = CatalogJson.Document(
            CatalogJson.Capability("privacy.telemetry.diagtrack"),
            CatalogJson.Capability("privacy.telemetry.diagtrack-policy"));

        var catalog = CatalogJson.Parse(json);

        Assert.Equal(2, catalog.Count);
        Assert.Equal("1.0.0", catalog.Metadata.Version);
        Assert.Equal("test", catalog.Metadata.Provenance);
        Assert.NotNull(catalog.Find("privacy.telemetry.diagtrack"));
        Assert.Null(catalog.Find("Privacy.Telemetry.DiagTrack"));
        Assert.Equal(2, catalog.Ids.Count);
    }

    [Theory]
    [InlineData("Privacy.Telemetry.DiagTrack")]
    [InlineData("privacy telemetry")]
    [InlineData("privacy")]
    [InlineData("privacy..telemetry")]
    [InlineData("privacy.telemetry.")]
    [InlineData(".privacy.telemetry")]
    [InlineData("privacy.telemetry_diagtrack")]
    [InlineData("privacy.telemetry/DiagTrack")]
    public void TestInvalidId_FailsValidation(string id)
    {
        var report = Validate(CatalogJson.Document(CatalogJson.Capability(id)));

        Assert.False(report.IsValid);
        Assert.Contains(report.Errors, e => e.Rule == "R-ID");
        Assert.Contains("Id inválido", report.ErrorSummary, StringComparison.Ordinal);
    }

    [Fact]
    public void ValidIdWithDashesPassesThePattern()
    {
        var report = Validate(CatalogJson.Document(
            CatalogJson.Capability("privacy.telemetry.diagtrack-policy")));

        Assert.True(report.IsValid, report.ErrorSummary);
    }

    [Fact]
    public void TestAsymmetricConflict_FailsValidation()
    {
        var json = CatalogJson.Document(
            CatalogJson.Capability("privacy.telemetry.diagtrack"),
            CatalogJson.Capability(
                "network.dns.encrypted",
                conflictsWith: "\"privacy.telemetry.diagtrack\""));

        var report = Validate(json);

        Assert.False(report.IsValid);
        var issue = Assert.Single(report.Errors.Where(e => e.Rule == "R-SYMMETRY"));
        Assert.Contains("simétrico", issue.Message, StringComparison.Ordinal);
        Assert.Contains("privacy.telemetry.diagtrack", issue.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void SymmetricConflictPassesValidation()
    {
        var json = CatalogJson.Document(
            CatalogJson.Capability(
                "privacy.telemetry.diagtrack",
                conflictsWith: "\"network.dns.encrypted\""),
            CatalogJson.Capability(
                "network.dns.encrypted",
                conflictsWith: "\"privacy.telemetry.diagtrack\""));

        var report = Validate(json);

        Assert.True(report.IsValid, report.ErrorSummary);
    }

    [Fact]
    public void TestCyclicDependency_FailsValidation()
    {
        var json = CatalogJson.Document(
            CatalogJson.Capability("alpha.one.cap", dependsOn: "\"beta.two.cap\""),
            CatalogJson.Capability("beta.two.cap", dependsOn: "\"gamma.three.cap\""),
            CatalogJson.Capability("gamma.three.cap", dependsOn: "\"alpha.one.cap\""));

        var report = Validate(json);

        Assert.False(report.IsValid);
        var issue = Assert.Single(report.Errors.Where(e => e.Rule == "R-CYCLE"));
        Assert.Contains("Ciclo de dependencia", issue.Message, StringComparison.Ordinal);
        Assert.Contains("alpha.one.cap", issue.Message, StringComparison.Ordinal);
        Assert.Contains("beta.two.cap", issue.Message, StringComparison.Ordinal);
        Assert.Contains("gamma.three.cap", issue.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void AcyclicDependencyChainPassesValidation()
    {
        var json = CatalogJson.Document(
            CatalogJson.Capability("alpha.one.cap"),
            CatalogJson.Capability("beta.two.cap", dependsOn: "\"alpha.one.cap\""),
            CatalogJson.Capability("gamma.three.cap", dependsOn: "\"beta.two.cap\""));

        var report = Validate(json);

        Assert.True(report.IsValid, report.ErrorSummary);
    }

    [Fact]
    public void SelfDependencyIsACycle()
    {
        var report = Validate(CatalogJson.Document(
            CatalogJson.Capability("alpha.one.cap", dependsOn: "\"alpha.one.cap\"")));

        Assert.False(report.IsValid);
        Assert.Contains(report.Errors, e => e.Rule == "R-CYCLE");
    }

    [Fact]
    public void TestCriticalRiskWithoutTypeConfirmation_FailsValidation()
    {
        var json = CatalogJson.Document(CatalogJson.Capability(
            "privacy.telemetry.diagtrack",
            risk: "Critical",
            confirmation: "SimpleClick",
            restore: "FullBackup"));

        var report = Validate(json);

        Assert.False(report.IsValid);
        Assert.Contains(report.Errors, e =>
            e.Rule == "R-RISK" && e.Message.Contains("TypeOperationName", StringComparison.Ordinal));
    }

    [Fact]
    public void CriticalRiskWithTypeOperationNamePasses()
    {
        var report = Validate(CatalogJson.Document(CatalogJson.Capability(
            "privacy.telemetry.diagtrack",
            risk: "Critical",
            confirmation: "TypeOperationName",
            restore: "FullBackup")));

        Assert.True(report.IsValid, report.ErrorSummary);
    }

    [Fact]
    public void InsufficientRestoreForReversibleRiskFails()
    {
        // ADR-0003: Reversible nunca acepta Restore=None, sea cual sea el riesgo.
        var report = Validate(CatalogJson.Document(CatalogJson.Capability(
            "services.diagtrack.disable",
            risk: "Low",
            confirmation: "SimpleClick",
            restore: "None")));

        Assert.False(report.IsValid);
        Assert.Contains(report.Errors, e => e.Rule == "R-RISK" && e.Message.Contains("SessionUndo"));
    }

    [Fact]
    public void IrreversibleHighWithNoneIsValidUnderAdr0003()
    {
        var json = CatalogJson.Document(CatalogJson.Capability(
                "cleanup.example.irreversible",
                risk: "High",
                confirmation: "SummaryAndRestorePoint",
                restore: "None"))
            .Replace("\"reversibility\": \"Reversible\"", "\"reversibility\": \"Irreversible\"");

        var report = Validate(json);

        Assert.True(report.IsValid, report.ErrorSummary);
    }

    [Fact]
    public void MissingReversibilityFailsValidation()
    {
        var json = CatalogJson.Document(CatalogJson.Capability("privacy.telemetry.diagtrack"))
            .Replace("\"reversibility\": \"Reversible\",", "");

        var report = Validate(json);

        Assert.False(report.IsValid);
        Assert.Contains(report.Errors, e =>
            e.Rule == "R-RISK" && e.Message.Contains("reversibility", StringComparison.Ordinal));
    }

    [Fact]
    public void DanglingDependencyFailsValidation()
    {
        var report = Validate(CatalogJson.Document(
            CatalogJson.Capability("alpha.one.cap", dependsOn: "\"no.existe.cap\"")));

        Assert.False(report.IsValid);
        Assert.Contains(report.Errors, e => e.Rule == "R-REF");
    }

    [Fact]
    public void UnknownBuildIsAWarningNotAnError()
    {
        var json = CatalogJson.Document(CatalogJson.Capability("privacy.telemetry.diagtrack"))
            .Replace("\"supportedBuilds\": []", "\"supportedBuilds\": [26100, 27000]");

        var report = Validate(json, builds: [19045, 22631, 26100, 26200]);

        Assert.True(report.IsValid, report.ErrorSummary);
        Assert.Single(report.Warnings);
        Assert.Contains("27000", report.Warnings[0].Message, StringComparison.Ordinal);
    }

    [Fact]
    public void DuplicateIdsFailValidation()
    {
        var json = CatalogJson.Document(
            CatalogJson.Capability("privacy.telemetry.diagtrack"),
            CatalogJson.Capability("privacy.telemetry.diagtrack"));

        var report = Validate(json);

        Assert.False(report.IsValid);
        Assert.Contains(report.Errors, e => e.Rule == "R-ID" && e.Message.Contains("duplicado"));
    }

    [Fact]
    public void ThrowIfInvalidLanzaConDetalle()
    {
        var catalog = CatalogJson.Parse(CatalogJson.Document(CatalogJson.Capability("MAL_ID")));

        var exception = Assert.Throws<InvalidOperationException>(
            () => new CatalogValidator().ThrowIfInvalid(catalog));

        Assert.Contains("R-ID", exception.Message, StringComparison.Ordinal);
    }
}
