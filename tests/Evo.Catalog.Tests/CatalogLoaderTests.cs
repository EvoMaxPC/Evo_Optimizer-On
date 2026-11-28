using System.Text;
using Evo.Catalog;
using Evo.Core.Actions;
using Evo.Core.Enums;
using Xunit;

namespace Evo.Catalog.Tests;

/// <summary>Carga estricta de ficheros y streams.</summary>
public sealed class CatalogLoaderTests
{
    private const string FullJson = """
    {
      // comentario permitido
      "metadata": { "version": "2.0.0", "schemaVersion": 1, "provenance": "unit-test", "generatedBy": "tests" },
      "capabilities": [
        {
          "id": "privacy.telemetry.diagtrack",
          "name": "Desactivar DiagTrack",
          "description": "Detiene y deshabilita el servicio de telemetría.",
          "sectionId": 3,
          "risk": "Medium",
          "securityImpact": "Improves",
          "privilege": "Admin",
          "restore": "RestorePoint",
          "reversibility": "Reversible",
          "confirmation": "Summary",
          "state": "Implemented",
          "variants": ["Evo", "WinUtil", "Atlas"],
          "conflictsWith": ["privacy.telemetry.diagtrack-policy"],
          "dependsOn": [],
          "supportedBuilds": [19045, 22631, 26100, 26200],
          "provenance": "winutil@70c23c8:config/tweaks.json",
          "actions": [
            { "type": "service", "order": 1, "description": "parar", "serviceName": "DiagTrack", "operation": "Stop" },
            { "type": "service", "order": 2, "description": "deshabilitar", "serviceName": "DiagTrack", "operation": "SetStartupType", "startupType": "Disabled" },
            { "type": "registry", "order": 3, "description": "clave", "hive": "LocalMachine", "keyPath": "SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection", "valueName": "AllowTelemetry", "operation": "Set", "valueType": "DWord", "value": "0" },
            { "type": "task", "order": 4, "description": "tarea", "taskPath": "\\Microsoft\\Windows\\AppID", "taskName": "PolicyConverter", "enabled": false },
            { "type": "command", "order": 5, "description": "winget", "fileName": "winget.exe", "arguments": ["upgrade", "--all"], "ignoreExitCode": true },
            { "type": "process", "order": 6, "description": "search", "processName": "SearchHost", "terminate": true }
          ]
        },
        {
          "id": "privacy.telemetry.diagtrack-policy",
          "name": "Política de telemetría",
          "sectionId": 3,
          "risk": "Low",
          "securityImpact": "Neutral",
          "privilege": "Admin",
          "restore": "SessionUndo",
          "reversibility": "Reversible",
          "confirmation": "SimpleClick",
          "state": "Specified",
          "variants": ["Evo"],
          "conflictsWith": ["privacy.telemetry.diagtrack"],
          "dependsOn": [],
          "supportedBuilds": [],
          "actions": []
        }
      ]
    }
    """;

    [Fact]
    public void LoadsAllActionTypesAndMetadata()
    {
        var document = new CatalogLoader().LoadFromText(FullJson);
        var catalog = document.ToCatalog();
        var definition = catalog["privacy.telemetry.diagtrack"];

        Assert.Equal("2.0.0", document.Metadata.Version);
        Assert.Equal("unit-test", document.Metadata.Provenance);
        Assert.Equal(6, definition.Actions.Count);
        Assert.IsType<ServiceAction>(definition.Actions[0]);
        Assert.IsType<RegistryAction>(definition.Actions[2]);
        Assert.IsType<TaskAction>(definition.Actions[3]);
        Assert.IsType<CommandAction>(definition.Actions[4]);
        Assert.IsType<ProcessAction>(definition.Actions[5]);
        Assert.Equal(RiskLevel.Medium, definition.Risk);
        Assert.Equal(PrivilegeLevel.Admin, definition.Privilege);
        Assert.Equal(RestoreLevel.RestorePoint, definition.Restore);
        Assert.Equal(ConfirmationType.Summary, definition.Confirmation);
        Assert.Equal(CapabilityState.Implemented, definition.State);
        Assert.Equal(3, definition.Variants.Count);
        Assert.Equal("winutil@70c23c8:config/tweaks.json", definition.Provenance);
        Assert.True(new CatalogValidator().Validate(catalog).IsValid);
    }

    [Fact]
    public void ContractProjectionKeepsEveryField()
    {
        var definition = new CatalogLoader().LoadFromText(FullJson).ToCatalog()["privacy.telemetry.diagtrack"];

        var contract = definition.ToContract();

        Assert.Equal(definition.Id, contract.Id);
        Assert.Equal(definition.SectionId, contract.SectionId);
        Assert.Equal(definition.Risk, contract.Risk);
        Assert.Equal(definition.SecurityImpact, contract.SecurityImpact);
        Assert.Equal(definition.Privilege, contract.Privilege);
        Assert.Equal(definition.Restore, contract.Restore);
        Assert.Equal(definition.Confirmation, contract.Confirmation);
        Assert.Equal(definition.State, contract.State);
        Assert.Equal(definition.Variants, contract.Variants);
        Assert.Equal(definition.SupportedBuilds, contract.SupportedBuilds);
    }

    [Fact]
    public void MissingNameThrows()
    {
        const string json = """
        { "capabilities": [ { "id": "a.b" } ] }
        """;

        var exception = Assert.Throws<CatalogLoadException>(
            () => new CatalogLoader().LoadFromText(json));

        Assert.Contains("name", exception.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void MissingSecurityImpactThrows()
    {
        const string json = """
        { "capabilities": [ { "id": "a.b", "name": "A" } ] }
        """;

        Assert.Throws<CatalogLoadException>(() => new CatalogLoader().LoadFromText(json));
    }

    [Fact]
    public void MissingIdThrows()
    {
        const string json = """
        { "capabilities": [ { "name": "A", "securityImpact": "Neutral" } ] }
        """;

        Assert.Throws<CatalogLoadException>(() => new CatalogLoader().LoadFromText(json));
    }

    [Fact]
    public void InvalidJsonThrows()
    {
        Assert.Throws<CatalogLoadException>(() => new CatalogLoader().LoadFromText("{ no json"));
    }

    [Fact]
    public void UnknownEnumValueThrows()
    {
        const string json = """
        { "capabilities": [ { "id": "a.b", "name": "A", "securityImpact": "Neutral", "risk": "Extreme" } ] }
        """;

        Assert.Throws<CatalogLoadException>(() => new CatalogLoader().LoadFromText(json));
    }

    [Fact]
    public void LoadsFromStreamAndFile()
    {
        var loader = new CatalogLoader();
        using var stream = new MemoryStream(Encoding.UTF8.GetBytes(FullJson));
        var fromStream = loader.Load(stream);

        var directory = Path.Combine(Path.GetTempPath(), "evo-catalog-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try
        {
            File.WriteAllText(Path.Combine(directory, "catalog.json"), FullJson);
            var fromDirectory = loader.LoadDirectory(directory);

            Assert.Single(fromDirectory);
            Assert.Equal(fromStream.Capabilities.Count, fromDirectory[0].Capabilities.Count);
            Assert.Equal("2.0.0", fromDirectory[0].Metadata.Version);
        }
        finally
        {
            Directory.Delete(directory, recursive: true);
        }
    }

    [Fact]
    public void MissingDirectoryThrows()
    {
        var exception = Assert.Throws<CatalogLoadException>(
            () => new CatalogLoader().LoadDirectory(Path.Combine(Path.GetTempPath(), "no-existe-" + Guid.NewGuid())));

        Assert.Contains("no existe", exception.Message, StringComparison.Ordinal);
    }
}
