using Evo.Core.Actions;
using Evo.Core.System;
using Evo.Engine.Execution;
using Evo.Engine.Undo;
using Microsoft.Win32;

namespace Evo.Engine.Executors;

/// <summary>
/// Aplica escrituras y borrados de registro. Antes de mutar guarda el valor
/// original (o su ausencia) para poder restaurarlo exactamente.
/// </summary>
public sealed class RegistryActionExecutor : IActionExecutor
{
    public ActionKind Kind => ActionKind.Registry;

    public Task<ActionResult> ExecuteAsync(CapabilityAction action, ActionContext context)
    {
        ArgumentNullException.ThrowIfNull(action);
        ArgumentNullException.ThrowIfNull(context);

        if (action is not RegistryAction registryAction)
        {
            return Task.FromResult(ActionResult.Fail(action.Key, "Acción no es de registro."));
        }

        var hive = Map(registryAction.Hive);
        var before = context.Registry.GetValue(hive, registryAction.KeyPath, registryAction.ValueName);
        var beforeKind = context.Registry is IRegistryKindReader reader
            ? reader.GetKind(hive, registryAction.KeyPath, registryAction.ValueName)
            : RegistryValueKind.Unknown;
        var previous = Serialize(before);

        string? next;
        if (registryAction.Operation == RegistryOperation.Delete)
        {
            next = null;
            if (context.Mutates)
            {
                context.Registry.DeleteValue(hive, registryAction.KeyPath, registryAction.ValueName);
            }
        }
        else
        {
            var value = Deserialize(registryAction.Value, registryAction.ValueType);
            next = Serialize(value);
            if (context.Mutates)
            {
                context.Registry.SetValue(
                    hive,
                    registryAction.KeyPath,
                    registryAction.ValueName,
                    value!,
                    ToRegistryKind(registryAction.ValueType));
            }
        }

        if (context.Mutates)
        {
            context.Journal.Add(new RegistryUndoEntry
            {
                CapabilityId = context.CapabilityId,
                ActionKey = action.Key,
                Description = Describe(registryAction),
                PreviousState = previous,
                Hive = hive,
                KeyPath = registryAction.KeyPath,
                ValueName = registryAction.ValueName,
                ExistedBefore = before is not null,
                PreviousValue = before,
                PreviousKind = beforeKind,
            });
        }

        return Task.FromResult(ActionResult.Ok(
            action.Key, previous, next, context.Mutates, Describe(registryAction)));
    }

    public string? ReadCurrentState(CapabilityAction action, ActionContext context)
    {
        if (action is not RegistryAction registryAction)
        {
            return null;
        }

        var before = context.Registry.GetValue(
            Map(registryAction.Hive), registryAction.KeyPath, registryAction.ValueName);
        return Serialize(before);
    }

    public static RegistryHive Map(RegistryHiveKind hive) => hive switch
    {
        RegistryHiveKind.LocalMachine => RegistryHive.LocalMachine,
        RegistryHiveKind.CurrentUser => RegistryHive.CurrentUser,
        RegistryHiveKind.ClassesRoot => RegistryHive.ClassesRoot,
        RegistryHiveKind.Users => RegistryHive.Users,
        _ => RegistryHive.LocalMachine,
    };

    public static RegistryValueKind ToRegistryKind(RegistryValueType type) => type switch
    {
        RegistryValueType.String => RegistryValueKind.String,
        RegistryValueType.DWord => RegistryValueKind.DWord,
        RegistryValueType.QWord => RegistryValueKind.QWord,
        RegistryValueType.Binary => RegistryValueKind.Binary,
        RegistryValueType.MultiString => RegistryValueKind.MultiString,
        RegistryValueType.ExpandString => RegistryValueKind.ExpandString,
        _ => RegistryValueKind.String,
    };

    /// <summary>Serializa un valor de registro a texto estable.</summary>
    public static string? Serialize(object? value) => value switch
    {
        null => null,
        byte[] bytes => Convert.ToBase64String(bytes),
        string[] strings => string.Join('\u001f', strings),
        bool flag => flag ? "1" : "0",
        IFormattable formattable => formattable.ToString(null, System.Globalization.CultureInfo.InvariantCulture),
        _ => value.ToString(),
    };

    /// <summary>Convierte el texto del catálogo al tipo CLR esperado.</summary>
    public static object? Deserialize(string? value, RegistryValueType type)
    {
        if (value is null && type != RegistryValueType.String)
        {
            return null;
        }

        return type switch
        {
            RegistryValueType.String or RegistryValueType.ExpandString => value ?? string.Empty,
            RegistryValueType.DWord => int.Parse(
                value ?? "0", System.Globalization.CultureInfo.InvariantCulture),
            RegistryValueType.QWord => long.Parse(
                value ?? "0", System.Globalization.CultureInfo.InvariantCulture),
            RegistryValueType.Binary => value is null ? [] : Convert.FromBase64String(value),
            RegistryValueType.MultiString => value is null
                ? []
                : value.Split('\u001f', StringSplitOptions.RemoveEmptyEntries),
            _ => value,
        };
    }

    private static string Describe(RegistryAction action) =>
        action.Operation == RegistryOperation.Delete
            ? $"Borrar {action.Hive}\\{action.KeyPath}\\{action.ValueName}"
            : $"Establecer {action.Hive}\\{action.KeyPath}\\{action.ValueName} = {action.Value}";
}
