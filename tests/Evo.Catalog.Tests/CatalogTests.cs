using System.Text.Json;
using Evo.Catalog;
using Evo.Catalog.Model;
using Evo.Core.Actions;
using Evo.Core.Enums;

namespace Evo.Catalog.Tests;

/// <summary>Fábrica de JSON de catálogo para los tests.</summary>
internal static class CatalogJson
{
    /// <summary>Capacidad mínima válida (riesgo bajo, sin acciones).</summary>
    public static string Capability(
        string id,
        string risk = "Low",
        string confirmation = "SimpleClick",
        string restore = "SessionUndo",
        string? conflictsWith = null,
        string? dependsOn = null,
        string securityImpact = "Neutral") => $$"""
        {
          "id": "{{id}}",
          "name": "{{id}}",
          "sectionId": 9,
          "risk": "{{risk}}",
          "securityImpact": "{{securityImpact}}",
          "privilege": "User",
          "restore": "{{restore}}",
          "confirmation": "{{confirmation}}",
          "state": "Specified",
          "variants": ["Evo"],
          "conflictsWith": [{{conflictsWith ?? string.Empty}}],
          "dependsOn": [{{dependsOn ?? string.Empty}}],
          "supportedBuilds": []
        }
        """;

    public static string Document(params string[] capabilities) => $$"""
        {
          "metadata": {
            "version": "1.0.0",
            "schemaVersion": 1,
            "provenance": "test",
            "generatedBy": "Evo.Catalog.Tests"
          },
          "capabilities": [{{string.Join(",", capabilities)}}]
        }
        """;

    public static CapabilityCatalog Parse(string json) =>
        new CatalogLoader().LoadFromText(json).ToCatalog();
}
