using System.Text.RegularExpressions;
using Evo.Catalog.Model;
using Evo.Core.Enums;
using Evo.Core.Models;

namespace Evo.Catalog;

/// <summary>Severidad de un hallazgo del validador.</summary>
public enum IssueSeverity
{
    Error = 0,
    Warning = 1,
}

/// <summary>Hallazgo del validador de catálogo.</summary>
public sealed record ValidationIssue
{
    public required IssueSeverity Severity { get; init; }

    /// <summary>Regla que lo detectó (R-ID, R-SYMMETRY, R-CYCLE, R-RISK, R-BUILD…).</summary>
    public required string Rule { get; init; }

    public required string CapabilityId { get; init; }

    public required string Message { get; init; }
}

/// <summary>Informe de validación completo.</summary>
public sealed record ValidationReport
{
    public required IReadOnlyList<ValidationIssue> Issues { get; init; }

    public bool IsValid => Issues.All(i => i.Severity != IssueSeverity.Error);

    public IReadOnlyList<ValidationIssue> Errors =>
        Issues.Where(i => i.Severity == IssueSeverity.Error).ToList();

    public IReadOnlyList<ValidationIssue> Warnings =>
        Issues.Where(i => i.Severity == IssueSeverity.Warning).ToList();

    /// <summary>Mensaje único con todos los errores (para excepciones y CI).</summary>
    public string ErrorSummary =>
        string.Join(Environment.NewLine, Errors.Select(e => $"[{e.Rule}] {e.CapabilityId}: {e.Message}"));
}

/// <summary>
/// Validador de integridad del catálogo: IDs, simetría de conflictos, ciclos de
/// dependencia, invariantes de riesgo y compatibilidad de builds.
/// </summary>
public sealed partial class CatalogValidator
{
    /// <summary>Formato canónico de Id: <c>privacy.telemetry.diagtrack</c>.</summary>
    public const string IdPattern = @"^[a-z0-9]+(\.[a-z0-9\-]+)+$";

    private readonly IReadOnlyCollection<int> _knownBuilds;

    public CatalogValidator(IEnumerable<int>? knownBuilds = null)
    {
        _knownBuilds = (knownBuilds ?? []).ToList();
    }

    [GeneratedRegex(IdPattern, RegexOptions.CultureInvariant)]
    private static partial Regex IdRegex();

    /// <summary>Valida un catálogo completo.</summary>
    public ValidationReport Validate(CapabilityCatalog catalog)
    {
        ArgumentNullException.ThrowIfNull(catalog);

        var issues = new List<ValidationIssue>();
        var ids = catalog.Definitions.Select(d => d.Id).ToList();

        foreach (var duplicate in ids.GroupBy(i => i, StringComparer.Ordinal).Where(g => g.Count() > 1))
        {
            issues.Add(Error("R-ID", duplicate.Key, $"Id duplicado ({duplicate.Count()} veces)."));
        }

        foreach (var definition in catalog.Definitions)
        {
            ValidateId(definition, issues);
            ValidateRiskInvariants(definition, issues);
            ValidateBuilds(definition, issues);
            ValidateActions(definition, issues);
            ValidateReferences(definition, catalog, issues);
        }

        ValidateSymmetry(catalog, issues);
        ValidateCycles(catalog, issues);
        ValidateOrphans(catalog, issues);

        return new ValidationReport { Issues = issues };
    }

    private static void ValidateId(CapabilityDefinition definition, List<ValidationIssue> issues)
    {
        if (string.IsNullOrWhiteSpace(definition.Id))
        {
            issues.Add(Error("R-ID", "<sin id>", "Falta el id."));
            return;
        }

        if (!IdRegex().IsMatch(definition.Id))
        {
            issues.Add(Error(
                "R-ID",
                definition.Id,
                $"Id inválido: debe casar con {IdPattern} (minúsculas, dígitos y guiones, " +
                "al menos dos segmentos separados por punto)."));
        }
    }

    private static void ValidateRiskInvariants(CapabilityDefinition definition, List<ValidationIssue> issues)
    {
        if (definition.SecurityImpact is null)
        {
            issues.Add(Error(
                "R-RISK", definition.Id, "securityImpact no puede ser nulo ni vacío."));
        }
        else if (!Enum.IsDefined(definition.SecurityImpact.Value))
        {
            issues.Add(Error(
                "R-RISK", definition.Id, "securityImpact tiene un valor no definido."));
        }

        if (definition.Risk == RiskLevel.Critical &&
            definition.Confirmation != ConfirmationType.TypeOperationName)
        {
            issues.Add(Error(
                "R-RISK",
                definition.Id,
                $"Riesgo Critical exige Confirmation=TypeOperationName " +
                $"(declarada {definition.Confirmation})."));
        }

        // ADR-0003: la regla depende de la reversibilidad declarada. Si falta,
        // es error: el catálogo debe decir qué se pierde, no deducirlo.
        if (definition.Reversibility is null)
        {
            issues.Add(Error(
                "R-RISK", definition.Id, "falta 'reversibility' (ADR-0003)."));
        }
        else if (!Enum.IsDefined(definition.Reversibility.Value))
        {
            issues.Add(Error(
                "R-RISK", definition.Id, "'reversibility' tiene un valor no definido."));
        }
        else
        {
            foreach (var message in CapabilityRules.ValidateReversibility(definition.ToContract()))
            {
                issues.Add(Error("R-RISK", definition.Id, message));
            }
        }

        if (definition.SectionId is < 0 or > 17)
        {
            issues.Add(Error(
                "R-RISK", definition.Id, $"SectionId {definition.SectionId} fuera de 0-17."));
        }

        if (definition.Variants.Count == 0)
        {
            issues.Add(Error("R-RISK", definition.Id, "variants no puede estar vacío."));
        }
    }

    private void ValidateBuilds(CapabilityDefinition definition, List<ValidationIssue> issues)
    {
        if (definition.SupportedBuilds.Count == 0)
        {
            return;
        }

        foreach (var build in definition.SupportedBuilds)
        {
            if (build < 10240)
            {
                issues.Add(Error(
                    "R-BUILD",
                    definition.Id,
                    $"Build {build} fuera de rango: Windows 10 empieza en 10240."));
            }
            else if (_knownBuilds.Count > 0 && !_knownBuilds.Contains(build))
            {
                issues.Add(new ValidationIssue
                {
                    Severity = IssueSeverity.Warning,
                    Rule = "R-BUILD",
                    CapabilityId = definition.Id,
                    Message = $"Build {build} no coincide con ninguna entrada de windows-releases.json.",
                });
            }
        }

        if (definition.SupportedBuilds.Distinct().Count() != definition.SupportedBuilds.Count)
        {
            issues.Add(Error("R-BUILD", definition.Id, "SupportedBuilds contiene duplicados."));
        }

        if (definition.SupportedBuilds.SequenceEqual(definition.SupportedBuilds.Order()))
        {
            return;
        }

        issues.Add(new ValidationIssue
        {
            Severity = IssueSeverity.Warning,
            Rule = "R-BUILD",
            CapabilityId = definition.Id,
            Message = "SupportedBuilds no está ordenado.",
        });
    }

    private static void ValidateActions(CapabilityDefinition definition, List<ValidationIssue> issues)
    {
        if (definition.Actions.Count == 0 && definition.State == CapabilityState.Implemented)
        {
            issues.Add(Error(
                "R-ACTION", definition.Id,
                "State=Implemented exige al menos una acción declarada."));
        }

        foreach (var duplicate in definition.Actions.GroupBy(a => a.Order).Where(g => g.Count() > 1))
        {
            issues.Add(Error(
                "R-ACTION", definition.Id, $"Dos acciones con Order={duplicate.Key}."));
        }

        foreach (var action in definition.Actions)
        {
            switch (action)
            {
                case Evo.Core.Actions.CommandAction command
                    when string.IsNullOrWhiteSpace(command.FileName):
                    issues.Add(Error("R-ACTION", definition.Id, "CommandAction sin 'fileName'."));
                    break;

                // Paso 11 (ADR-0005): las acciones nuevas tienen contrato cerrado y
                // el validador comprueba sus campos obligatorios aquí, no sólo al
                // deserializar (un JSON con la clave vacía cargaría igual).
                case Evo.Core.Actions.RegistryDeleteKeyAction deleteKey
                    when string.IsNullOrWhiteSpace(deleteKey.KeyPath):
                    issues.Add(Error(
                        "R-ACTION", definition.Id, "RegistryDeleteKeyAction sin 'keyPath'."));
                    break;

                case Evo.Core.Actions.RegistryDeleteKeyAction deleteKey
                    when deleteKey.KeyPath.Contains("\\*", StringComparison.Ordinal)
                         || deleteKey.KeyPath.Contains("*", StringComparison.Ordinal):
                    issues.Add(Error(
                        "R-ACTION", definition.Id,
                        $"RegistryDeleteKeyAction con comodín en 'keyPath' ('{deleteKey.KeyPath}'): " +
                        "el borrado de claves no admite patrones."));
                    break;

                case Evo.Core.Actions.TaskCreateAction create
                    when string.IsNullOrWhiteSpace(create.TaskName)
                         || string.IsNullOrWhiteSpace(create.Execute)
                         || string.IsNullOrWhiteSpace(create.Trigger)
                         || string.IsNullOrWhiteSpace(create.UserId)
                         || string.IsNullOrWhiteSpace(create.RunLevel):
                    issues.Add(Error(
                        "R-ACTION", definition.Id,
                        "TaskCreateAction exige 'taskName', 'execute', 'trigger', 'userId' y " +
                        "'runLevel'."));
                    break;

                case Evo.Core.Actions.TaskCreateAction create
                    when create.Trigger is not ("Daily" or "OnLogon"):
                    issues.Add(Error(
                        "R-ACTION", definition.Id,
                        $"TaskCreateAction con desencadenante '{create.Trigger}': sólo Daily y OnLogon."));
                    break;

                case Evo.Core.Actions.TaskCreateAction create
                    when create.Trigger == "Daily" && string.IsNullOrWhiteSpace(create.TriggerAt):
                    issues.Add(Error(
                        "R-ACTION", definition.Id,
                        "TaskCreateAction con trigger Daily sin 'triggerAt' (HH:mm)."));
                    break;

                case Evo.Core.Actions.TaskCreateAction create
                    when create.TriggerAt is not null
                         && !System.Text.RegularExpressions.Regex.IsMatch(
                             create.TriggerAt, @"^([01]\d|2[0-3]):[0-5]\d$"):
                    issues.Add(Error(
                        "R-ACTION", definition.Id,
                        $"TaskCreateAction con 'triggerAt' inválido ('{create.TriggerAt}'): se espera HH:mm."));
                    break;

                case Evo.Core.Actions.TaskCreateAction create
                    when create.RunLevel is not ("Highest" or "Limited"):
                    issues.Add(Error(
                        "R-ACTION", definition.Id,
                        $"TaskCreateAction con 'runLevel' '{create.RunLevel}': Highest o Limited."));
                    break;
            }
        }
    }

    private static void ValidateReferences(
        CapabilityDefinition definition,
        CapabilityCatalog catalog,
        List<ValidationIssue> issues)
    {
        foreach (var dependency in definition.DependsOn)
        {
            if (catalog.Find(dependency) is null)
            {
                issues.Add(Error("R-REF", definition.Id,
                    $"Depende de '{dependency}', que no existe en el catálogo."));
            }
        }

        foreach (var conflict in definition.ConflictsWith)
        {
            if (catalog.Find(conflict) is null)
            {
                issues.Add(Error("R-REF", definition.Id,
                    $"Declara conflicto con '{conflict}', que no existe en el catálogo."));
            }
        }
    }

    private static void ValidateSymmetry(CapabilityCatalog catalog, List<ValidationIssue> issues)
    {
        foreach (var definition in catalog.Definitions)
        {
            foreach (var conflict in definition.ConflictsWith)
            {
                var other = catalog.Find(conflict);
                if (other is null)
                {
                    continue; // ya reportado por R-REF
                }

                if (!other.ConflictsWith.Contains(definition.Id, StringComparer.Ordinal))
                {
                    issues.Add(Error(
                        "R-SYMMETRY",
                        definition.Id,
                        $"Declara conflicto con '{conflict}' pero '{conflict}' no lo declara con " +
                        $"'{definition.Id}': el conflicto debe ser simétrico."));
                }
            }
        }
    }

    /// <summary>
    /// Detecta ciclos de dependencia con DFS y coloración (blanco/gris/negro),
    /// informando la ruta completa del ciclo.
    /// </summary>
    private static void ValidateCycles(CapabilityCatalog catalog, List<ValidationIssue> issues)
    {
        var state = new Dictionary<string, int>(StringComparer.Ordinal); // 0=blanco 1=gris 2=negro
        var path = new List<string>();

        foreach (var definition in catalog.Definitions)
        {
            if (state.GetValueOrDefault(definition.Id) == 0)
            {
                Visit(definition.Id, catalog, state, path, issues);
            }
        }
    }

    private static void Visit(
        string id,
        CapabilityCatalog catalog,
        Dictionary<string, int> state,
        List<string> path,
        List<ValidationIssue> issues)
    {
        state[id] = 1;
        path.Add(id);

        var definition = catalog.Find(id);
        foreach (var dependency in definition?.DependsOn ?? [])
        {
            if (catalog.Find(dependency) is null)
            {
                continue; // ya reportado por R-REF
            }

            var dependencyState = state.GetValueOrDefault(dependency);
            if (dependencyState == 1)
            {
                var start = path.IndexOf(dependency);
                var cycle = string.Join(" -> ", path.Skip(start).Append(dependency));
                issues.Add(Error(
                    "R-CYCLE", dependency, $"Ciclo de dependencia: {cycle}"));
            }
            else if (dependencyState == 0)
            {
                Visit(dependency, catalog, state, path, issues);
            }
        }

        path.RemoveAt(path.Count - 1);
        state[id] = 2;
    }

    private static void ValidateOrphans(CapabilityCatalog catalog, List<ValidationIssue> issues)
    {
        foreach (var definition in catalog.Definitions)
        {
            if (definition.State == CapabilityState.Implemented && definition.Actions.Count == 0)
            {
                continue; // ya reportado por R-ACTION
            }

            if (definition.State == CapabilityState.Stub && definition.Actions.Count > 0)
            {
                issues.Add(new ValidationIssue
                {
                    Severity = IssueSeverity.Warning,
                    Rule = "R-STATE",
                    CapabilityId = definition.Id,
                    Message = "State=Stub con acciones declaradas: revisar la madurez declarada.",
                });
            }
        }
    }

    private static ValidationIssue Error(string rule, string capabilityId, string message) =>
        new()
        {
            Severity = IssueSeverity.Error,
            Rule = rule,
            CapabilityId = capabilityId,
            Message = message,
        };

    /// <summary>Lanza si el catálogo es inválido.</summary>
    public void ThrowIfInvalid(CapabilityCatalog catalog)
    {
        var report = Validate(catalog);
        if (!report.IsValid)
        {
            throw new InvalidOperationException(
                "Catálogo inválido:" + Environment.NewLine + report.ErrorSummary);
        }
    }
}
