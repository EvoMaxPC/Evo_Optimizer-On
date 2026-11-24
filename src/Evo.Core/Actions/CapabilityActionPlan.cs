namespace Evo.Core.Actions;

/// <summary>
/// Plan de una capacidad: sus acciones ordenadas por <see cref="CapabilityAction.Order"/>
/// y con validación de dependencias internas.
/// </summary>
public sealed class CapabilityActionPlan
{
    public CapabilityActionPlan(IEnumerable<CapabilityAction> actions)
    {
        ArgumentNullException.ThrowIfNull(actions);
        Actions = actions.OrderBy(a => a.Order).ToList();
    }

    /// <summary>Acciones ordenadas.</summary>
    public IReadOnlyList<CapabilityAction> Actions { get; }

    /// <summary>True si no hay acciones.</summary>
    public bool IsEmpty => Actions.Count == 0;

    /// <summary>
    /// Comprueba que el orden de las acciones es coherente: no admite dos
    /// acciones con el mismo <see cref="CapabilityAction.Order"/>.
    /// Devuelve la lista de violaciones (vacía = válido).
    /// </summary>
    public IReadOnlyList<string> Validate()
    {
        var errors = new List<string>();

        if (Actions.Count == 0)
        {
            errors.Add("El plan no tiene acciones.");
            return errors;
        }

        foreach (var duplicate in Actions.GroupBy(a => a.Order).Where(g => g.Count() > 1))
        {
            errors.Add($"Hay {duplicate.Count()} acciones con Order={duplicate.Key}.");
        }

        foreach (var action in Actions)
        {
            if (action.Order < 0)
            {
                errors.Add($"'{action.Key}': Order negativo.");
            }
        }

        return errors;
    }
}
