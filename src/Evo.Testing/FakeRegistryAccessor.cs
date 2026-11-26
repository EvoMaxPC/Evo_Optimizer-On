using Evo.Core.System;
using Microsoft.Win32;

namespace Evo.Testing;

/// <summary>Entrada del registro en memoria: valor + tipo.</summary>
public sealed record RegistryEntry(object? Value, RegistryValueKind Kind, bool Exists)
{
    public static RegistryEntry Missing { get; } = new(null, RegistryValueKind.Unknown, false);
}

/// <summary>
/// Registro en memoria para pruebas deterministas. Soporta HKLM, HKCU, HKCR y
/// HKU; los valores se guardan normalizados (DWord/QWord como long, Binary
/// como byte[], MultiString como string[]).
/// </summary>
public sealed class FakeRegistryAccessor : IRegistryAccessor, IRegistryKindReader,
    IRegistryTreeReader, IRegistryKeyCreator
{
    private readonly Dictionary<string, Dictionary<string, RegistryEntry>> _keys =
        new(StringComparer.OrdinalIgnoreCase);

    /// <summary>
    /// Tipos de valor admitidos explícitamente por el fake: String, DWord,
    /// QWord, Binary, MultiString y ExpandString. Cualquier otro se rechaza
    /// para que un test no pase por accidente con un tipo que el motor no sabe
    /// serializar.
    /// </summary>
    public static IReadOnlySet<RegistryValueKind> SupportedKinds { get; } =
        new HashSet<RegistryValueKind>
        {
            RegistryValueKind.String,
            RegistryValueKind.DWord,
            RegistryValueKind.QWord,
            RegistryValueKind.Binary,
            RegistryValueKind.MultiString,
            RegistryValueKind.ExpandString,
        };

    /// <summary>Número de escrituras y borrados aplicados (auditoría de tests).</summary>
    public int MutationCount { get; private set; }

    /// <summary>Número de llamadas a <see cref="SetValue"/> realizadas (incluye las de <see cref="Seed"/>).</summary>
    public int SetValueCallCount { get; private set; }

    /// <summary>
    /// Número de llamada a <see cref="SetValue"/> en la que lanzar
    /// <see cref="OperationCanceledException"/> (1-based; 0 = nunca). Sirve
    /// para simular una cancelación del token durante una acción (etapa 1,
    /// H1). Se reinicia con <see cref="ResetSetValueCounter"/>.
    /// </summary>
    public int ThrowOnSetValueCall { get; set; }

    /// <summary>Reinicia el contador de llamadas a <see cref="SetValue"/>.</summary>
    public void ResetSetValueCounter() => SetValueCallCount = 0;

    /// <summary>
    /// Hook opcional invocado al inicio de cada <see cref="SetValue"/> con el
    /// número de llamada (1-based). Permite inyectar cancelación en el momento
    /// exacto (etapa 1, H1/H2).
    /// </summary>
    public Action<int>? OnSetValue { get; set; }

    /// <summary>Llamadas registradas, en orden.</summary>
    public List<string> Log { get; } = [];

    /// <summary>Instantánea profunda del estado actual (para comparar antes/después).</summary>
    public IReadOnlyDictionary<string, IReadOnlyDictionary<string, RegistryEntry>> Snapshot() =>
        _keys.ToDictionary(
            k => k.Key,
            v => (IReadOnlyDictionary<string, RegistryEntry>)new Dictionary<string, RegistryEntry>(
                v.Value, StringComparer.OrdinalIgnoreCase),
            StringComparer.OrdinalIgnoreCase);

    /// <summary>Crea la clave si no existe (solo en los fakes).</summary>
    public void EnsureKey(string fullKey)
    {
        var normalized = Normalize(fullKey);
        if (!_keys.ContainsKey(normalized))
        {
            _keys[normalized] = new Dictionary<string, RegistryEntry>(StringComparer.OrdinalIgnoreCase);
        }
    }

    /// <summary>Tipo del valor (Unknown si no existe).</summary>
    public RegistryValueKind GetKind(RegistryHive hive, string keyPath, string valueName)
    {
        var entry = GetEntry(hive, keyPath, valueName);
        return entry.Exists ? entry.Kind : RegistryValueKind.Unknown;
    }

    public object? GetValue(RegistryHive hive, string keyPath, string valueName)
    {
        var entry = GetEntry(hive, keyPath, valueName);
        Log.Add($"get {HiveName(hive)}\\{keyPath}\\{valueName}");
        return entry.Exists ? entry.Value : null;
    }

    /// <summary>Valor + tipo + existencia (usado por el motor y los tests).</summary>
    public RegistryEntry GetEntry(RegistryHive hive, string keyPath, string valueName)
    {
        var full = Normalize($"{HiveName(hive)}\\{keyPath}");
        if (!_keys.TryGetValue(full, out var values))
        {
            return RegistryEntry.Missing;
        }

        return values.TryGetValue(valueName, out var entry) ? entry : RegistryEntry.Missing;
    }

    public void SetValue(RegistryHive hive, string keyPath, string valueName, object value, RegistryValueKind kind)
    {
        SetValueCallCount++;
        OnSetValue?.Invoke(SetValueCallCount);
        if (ThrowOnSetValueCall > 0 && SetValueCallCount == ThrowOnSetValueCall)
        {
            ThrowOnSetValueCall = 0;
            throw new OperationCanceledException();
        }

        if (!SupportedKinds.Contains(kind))
        {
            throw new NotSupportedException(
                $"Tipo de valor de registro no soportado por el fake: {kind}.");
        }

        var full = Normalize($"{HiveName(hive)}\\{keyPath}");
        EnsureKey(full);
        _keys[full][valueName] = new RegistryEntry(value, kind, true);
        MutationCount++;
        Log.Add($"set {full}\\{valueName}");
    }

    public bool DeleteValue(RegistryHive hive, string keyPath, string valueName)
    {
        var full = Normalize($"{HiveName(hive)}\\{keyPath}");
        if (!_keys.TryGetValue(full, out var values) || !values.Remove(valueName))
        {
            return false;
        }

        MutationCount++;
        Log.Add($"delete-value {full}\\{valueName}");
        return true;
    }

    /// <summary>Nombres de las subclaves directas (necesario para DeleteKey).</summary>
    public IReadOnlyList<string> GetSubKeyNames(RegistryHive hive, string keyPath)
    {
        var full = Normalize($"{HiveName(hive)}\\{keyPath}");
        var prefix = full + "\\";
        var names = _keys.Keys
            .Where(k => k.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            .Select(k => k[prefix.Length..])
            .Where(rest => rest.Length > 0 && !rest.Contains('\\'))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(n => n, StringComparer.OrdinalIgnoreCase)
            .ToList();
        Log.Add($"subkeys {full}");
        return names;
    }

    /// <summary>Nombres de los valores directos de la clave.</summary>
    public IReadOnlyList<string> GetValueNames(RegistryHive hive, string keyPath)
    {
        var full = Normalize($"{HiveName(hive)}\\{keyPath}");
        if (!_keys.TryGetValue(full, out var values))
        {
            return [];
        }

        return values.Keys.OrderBy(n => n, StringComparer.OrdinalIgnoreCase).ToList();
    }

    /// <summary>Crea la clave vacía si no existe (deshacer de un borrado).</summary>
    public void EnsureKey(RegistryHive hive, string keyPath) =>
        EnsureKey($"{HiveName(hive)}\\{keyPath}");

    /// <summary>Cuenta como mutación: sembrar estado de prueba no debe hacerlo.</summary>
    void IRegistryKeyCreator.EnsureKey(RegistryHive hive, string keyPath)
    {
        var full = Normalize($"{HiveName(hive)}\\{keyPath}");
        if (!_keys.ContainsKey(full))
        {
            _keys[full] = new Dictionary<string, RegistryEntry>(StringComparer.OrdinalIgnoreCase);
            MutationCount++;
            Log.Add($"ensure-key {full}");
        }
    }

    public bool KeyExists(RegistryHive hive, string keyPath)
    {
        var full = Normalize($"{HiveName(hive)}\\{keyPath}");
        return _keys.ContainsKey(full);
    }

    public bool DeleteKey(RegistryHive hive, string keyPath, bool recursive)
    {
        var full = Normalize($"{HiveName(hive)}\\{keyPath}");
        var removed = _keys.Remove(full);
        if (recursive)
        {
            foreach (var key in _keys.Keys.Where(k => k.StartsWith(full + "\\", StringComparison.OrdinalIgnoreCase)).ToList())
            {
                _keys.Remove(key);
                removed = true;
            }
        }

        if (removed)
        {
            MutationCount++;
            Log.Add($"delete-key {full}");
        }

        return removed;
    }

    /// <summary>Atajo para preparar estado de prueba.</summary>
    public FakeRegistryAccessor Seed(RegistryHive hive, string keyPath, string valueName, object value, RegistryValueKind kind = RegistryValueKind.DWord)
    {
        SetValue(hive, keyPath, valueName, value, kind);
        Log.Clear();
        return this;
    }

    /// <summary>Vacía el log de llamadas (para medir sólo lo que hace el motor).</summary>
    public void ClearLog() => Log.Clear();

    private static string Normalize(string key) => key.Replace('/', '\\').TrimEnd('\\');

    private static string HiveName(RegistryHive hive) => hive switch
    {
        RegistryHive.LocalMachine => "HKLM",
        RegistryHive.CurrentUser => "HKCU",
        RegistryHive.ClassesRoot => "HKCR",
        RegistryHive.Users => "HKU",
        _ => hive.ToString(),
    };
}
