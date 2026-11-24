using Evo.Core.Enums;
using Evo.Detection;
using Evo.Detection.Model;
using Xunit;

namespace Evo.Detection.Tests;

/// <summary>
/// Detección con entornos simulados. Cubre los cinco casos exigidos:
/// 24H2 client, 22H2 client con ESU, Server 2025, build desconocida y ARM64.
/// </summary>
public sealed class WindowsDetectorTests
{
    private static WindowsReleaseCatalog LoadCatalog()
    {
        var path = Path.Combine(AppContext.BaseDirectory, "catalog", "windows-releases.json");
        return WindowsReleaseCatalog.LoadFromFile(path);
    }

    private static CompatibilityResult Detect(
        int build,
        string installationType = "Client",
        string edition = "Professional",
        string architecture = "x64",
        int ubr = 3915)
    {
        var environment = new FakeSystemEnvironment
        {
            CurrentBuild = build,
            UBR = ubr,
            EditionID = edition,
            InstallationType = installationType,
            Architecture = architecture,
        };

        var detector = new WindowsDetector(
            environment,
            FakeRegistryAccessor.FromEnvironment(environment),
            LoadCatalog());

        return detector.Detect();
    }

    [Fact]
    public void Win11_24H2_Client_EsSoportado()
    {
        var result = Detect(26100);

        Assert.Equal(CompatibilityStatus.Supported, result.Status);
        Assert.Equal("SUPPORTED", result.Code);
        Assert.True(result.IsSupported);
        Assert.False(result.RequiresEsuNotice);
        Assert.Empty(result.Warnings);
        Assert.Equal("win11-24h2", result.Release!.Id);
        Assert.Equal(26100, result.Build);
        Assert.Equal(3915, result.Ubr);
        Assert.Equal("Professional", result.EditionId);
    }

    [Fact]
    public void Win10_22H2_Client_EsSoportadoConAvisoEsu()
    {
        var result = Detect(19045, edition: "CoreSingleLanguage", architecture: "x64");

        Assert.Equal(CompatibilityStatus.SupportedWithWarning, result.Status);
        Assert.Equal("SUPPORTED_WITH_WARNING", result.Code);
        Assert.True(result.IsSupported);
        Assert.True(result.RequiresEsuNotice);
        Assert.Single(result.Warnings);
        Assert.Contains("ESU", result.Warnings[0], StringComparison.Ordinal);
        Assert.Equal("win10-22h2", result.Release!.Id);
    }

    [Fact]
    public void WindowsServer2025_Datacenter_EsRechazado()
    {
        var result = Detect(26100, installationType: "Server", edition: "ServerDatacenter");

        Assert.Equal(CompatibilityStatus.ServerRejected, result.Status);
        Assert.Equal("SERVER_REJECTED", result.Code);
        Assert.False(result.IsSupported);
        Assert.Null(result.Release);
        Assert.Contains("Server", result.Reason, StringComparison.Ordinal);
    }

    [Fact]
    public void ServerLanzaExcepcionConEnsureSupported()
    {
        var environment = new FakeSystemEnvironment
        {
            CurrentBuild = 26100,
            InstallationType = "Server",
            EditionID = "ServerDatacenter",
        };

        var detector = new WindowsDetector(
            environment,
            FakeRegistryAccessor.FromEnvironment(environment),
            LoadCatalog());

        var exception = Assert.Throws<ServerNotSupportedException>(() => detector.EnsureSupported());

        Assert.Equal("Server", exception.InstallationType);
        Assert.Equal("ServerDatacenter", exception.EditionId);
    }

    [Fact]
    public void BuildDesconocida99999_EsRechazada()
    {
        var result = Detect(99999);

        Assert.Equal(CompatibilityStatus.UnknownBuildRejected, result.Status);
        Assert.Equal("UNKNOWN_BUILD_REJECTED", result.Code);
        Assert.False(result.IsSupported);
        Assert.Null(result.Release);
        Assert.Contains("99999", result.Reason, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData(19044)]
    [InlineData(22000)]
    [InlineData(22621)]
    [InlineData(26120)]
    [InlineData(30000)]
    public void BuildsFueraDeRangoSonRechazadas(int build)
    {
        var result = Detect(build);

        Assert.Equal(CompatibilityStatus.UnknownBuildRejected, result.Status);
        Assert.False(result.IsSupported);
    }

    [Fact]
    public void InstallationTypeVacioSeRechaza()
    {
        var result = Detect(26100, installationType: string.Empty);

        Assert.Equal(CompatibilityStatus.ServerRejected, result.Status);
        Assert.False(result.IsSupported);
    }

    [Theory]
    [InlineData(26100, "arm64", CompatibilityStatus.Supported)]
    [InlineData(26200, "ARM64", CompatibilityStatus.Supported)]
    [InlineData(19045, "arm64", CompatibilityStatus.SupportedWithWarning)]
    public void Arm64Yx64SeNormalizan(int build, string architecture, CompatibilityStatus expected)
    {
        var result = Detect(build, architecture: architecture);

        Assert.Equal(expected, result.Status);
        Assert.Equal("arm64", result.Architecture);
    }

    [Fact]
    public void ArquitecturaNoDeclaradaSeRechaza()
    {
        var result = Detect(26100, architecture: "x86");

        Assert.Equal(CompatibilityStatus.ArchitectureRejected, result.Status);
        Assert.Equal("ARCHITECTURE_REJECTED", result.Code);
        Assert.False(result.IsSupported);
    }

    [Fact]
    public void BuildSeLeeDelRegistroAunqueElEntornoDigaOtraCosa()
    {
        var environment = new FakeSystemEnvironment { CurrentBuild = 26100, InstallationType = "Client" };
        var registry = FakeRegistryAccessor.FromEnvironment(environment)
            .With(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "CurrentBuildNumber", "26200");

        var detector = new WindowsDetector(environment, registry, LoadCatalog());
        var result = detector.Detect();

        Assert.Equal(26200, result.Build);
        Assert.Equal("win11-25h2", result.Release!.Id);
        Assert.Equal("SUPPORTED", result.Code);
    }

    [Fact]
    public void SinBuildLegibleElResultadoEsIndeterminado()
    {
        var environment = new FakeSystemEnvironment
        {
            CurrentBuild = 0,
            InstallationType = "Client",
        };

        var detector = new WindowsDetector(
            environment,
            FakeRegistryAccessor.FromEnvironment(environment),
            LoadCatalog());

        var result = detector.Detect();

        Assert.Equal(CompatibilityStatus.Indeterminate, result.Status);
        Assert.Equal("INDETERMINATE", result.Code);
        Assert.False(result.IsSupported);
    }
}
