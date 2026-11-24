using System.Text.Json.Serialization;
using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Models;

namespace Evo.Catalog.Model;

/// <summary>
/// Definición de una capacidad tal cual vive en el JSON del catálogo. Mapea a
/// <see cref="CapabilityContract"/> y añade las acciones declarativas.
/// </summary>
public sealed record CapabilityDefinition
{
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    [JsonPropertyName("name")]
    public required string Name { get; init; }

    [JsonPropertyName("description")]
    public string Description { get; init; } = string.Empty;

    [JsonPropertyName("sectionId")]
    public int SectionId { get; init; }

    [JsonPropertyName("risk")]
    public RiskLevel Risk { get; init; } = RiskLevel.Safe;

    /// <summary>Efecto sobre la seguridad. Nullable a propósito: el validador
    /// debe poder rechazar una definición que no lo declare.</summary>
    [JsonPropertyName("securityImpact")]
    public SecurityImpact? SecurityImpact { get; init; }

    [JsonPropertyName("privilege")]
    public PrivilegeLevel Privilege { get; init; } = PrivilegeLevel.User;

    [JsonPropertyName("restore")]
    public RestoreLevel Restore { get; init; } = RestoreLevel.None;

    /// <summary>Reversibilidad real (ADR-0003). Nullable a propósito: el
    /// validador debe poder rechazar una definición que no la declare.</summary>
    [JsonPropertyName("reversibility")]
    public Reversibility? Reversibility { get; init; }

    [JsonPropertyName("confirmation")]
    public ConfirmationType Confirmation { get; init; } = ConfirmationType.None;

    [JsonPropertyName("state")]
    public CapabilityState State { get; init; } = CapabilityState.Stub;

    [JsonPropertyName("variants")]
    public IReadOnlyList<Variant> Variants { get; init; } = [Variant.Evo];

    [JsonPropertyName("conflictsWith")]
    public IReadOnlyList<string> ConflictsWith { get; init; } = [];

    [JsonPropertyName("dependsOn")]
    public IReadOnlyList<string> DependsOn { get; init; } = [];

    [JsonPropertyName("supportedBuilds")]
    public IReadOnlyList<int> SupportedBuilds { get; init; } = [];

    [JsonPropertyName("actions")]
    public IReadOnlyList<CapabilityAction> Actions { get; init; } = [];

    [JsonPropertyName("provenance")]
    public string Provenance { get; init; } = string.Empty;

    /// <summary>Proyecta la definición al contrato del motor.</summary>
    public CapabilityContract ToContract() => new()
    {
        Id = Id,
        Name = Name,
        Description = Description,
        SectionId = SectionId,
        Risk = Risk,
        SecurityImpact = SecurityImpact ?? Evo.Core.Enums.SecurityImpact.Neutral,
        Privilege = Privilege,
        Restore = Restore,
        Reversibility = Reversibility ?? Evo.Core.Enums.Reversibility.Reversible,
        Confirmation = Confirmation,
        State = State,
        Variants = Variants,
        ConflictsWith = ConflictsWith,
        DependsOn = DependsOn,
        SupportedBuilds = SupportedBuilds,
    };
}
