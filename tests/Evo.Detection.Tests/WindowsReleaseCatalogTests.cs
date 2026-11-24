using Evo.Detection.Model;
using Xunit;

namespace Evo.Detection.Tests;

/// <summary>El catálogo es dato y su esquema es estricto (REQ-003).</summary>
public sealed class WindowsReleaseCatalogTests
{
    private static string CatalogPath =>
        Path.Combine(AppContext.BaseDirectory, "catalog", "windows-releases.json");

    [Fact]
    public void CatalogoDelRepoEsValido()
    {
        var catalog = WindowsReleaseCatalog.LoadFromFile(CatalogPath);

        Assert.Equal(1, catalog.SchemaVersion);
        Assert.Equal("windows-releases", catalog.Catalog);
        Assert.Equal(5, catalog.Releases.Count);
        Assert.Empty(catalog.Validate());
        Assert.Contains("Client", catalog.SupportedInstallationTypes);
    }

    [Theory]
    [InlineData(19045, "win10-22h2", true)]
    [InlineData(22631, "win11-23h2", false)]
    [InlineData(26100, "win11-24h2", false)]
    [InlineData(26200, "win11-25h2", false)]
    [InlineData(27600, "win11-26h2", false)]
    [InlineData(27999, "win11-26h2", false)]
    public void BuildsDelCatalogoCasanConSuEntrada(int build, string id, bool esu)
    {
        var catalog = WindowsReleaseCatalog.LoadFromFile(CatalogPath);
        var release = catalog.Find(build);

        Assert.NotNull(release);
        Assert.Equal(id, release!.Id);
        Assert.Equal("Client", release.InstallationType);
        Assert.Equal(esu, release.EsuRequired);
    }

    [Theory]
    [InlineData(19044)]
    [InlineData(28000)]
    [InlineData(99999)]
    public void BuildsFueraDelCatalogoNoCasan(int build)
    {
        var catalog = WindowsReleaseCatalog.LoadFromFile(CatalogPath);

        Assert.Null(catalog.Find(build));
    }

    [Fact]
    public void InstallationTypeServerNoEsValidoEnElCatalogo()
    {
        var json = File.ReadAllText(CatalogPath)
            .Replace("\"installationType\": \"Client\"", "\"installationType\": \"Server\"", StringComparison.Ordinal);

        var exception = Assert.Throws<InvalidDataException>(() => WindowsReleaseCatalog.Parse(json));

        Assert.Contains("Client", exception.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void RangoSolapadoSeRechaza()
    {
        const string json = """
        {
          "schemaVersion": 1,
          "catalog": "windows-releases",
          "supportedInstallationTypes": ["Client"],
          "policy": { "maxSupportedBuild": 27999 },
          "releases": [
            { "id": "a", "displayName": "A", "build": 26100, "buildMin": 26100,
              "buildMax": 26100, "installationType": "Client", "architectures": ["x64"] },
            { "id": "b", "displayName": "B", "build": 26100, "buildMin": 26100,
              "buildMax": 26200, "installationType": "Client", "architectures": ["x64"] }
          ]
        }
        """;

        var exception = Assert.Throws<InvalidDataException>(() => WindowsReleaseCatalog.Parse(json));

        Assert.Contains("solapado", exception.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void JsonInvalidoLanzaInvalidData()
    {
        Assert.Throws<InvalidDataException>(() => WindowsReleaseCatalog.Parse("{ no es json"));
    }

    [Fact]
    public void SchemaVersionDistintaSeRechaza()
    {
        var json = File.ReadAllText(CatalogPath)
            .Replace("\"schemaVersion\": 1", "\"schemaVersion\": 2", StringComparison.Ordinal);

        Assert.Throws<InvalidDataException>(() => WindowsReleaseCatalog.Parse(json));
    }

    [Fact]
    public void OpenEndedYBuildMaxDebenSerCoherentes()
    {
        const string json = """
        {
          "schemaVersion": 1,
          "catalog": "windows-releases",
          "supportedInstallationTypes": ["Client"],
          "policy": { "maxSupportedBuild": 27999 },
          "releases": [
            { "id": "a", "displayName": "A", "build": 27600, "buildMin": 27600,
              "buildMax": null, "openEnded": false, "installationType": "Client",
              "architectures": ["x64"] }
          ]
        }
        """;

        var exception = Assert.Throws<InvalidDataException>(() => WindowsReleaseCatalog.Parse(json));

        Assert.Contains("openEnded", exception.Message, StringComparison.Ordinal);
    }
}
