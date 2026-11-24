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
public sealed class FakeRegistryAccessor : IRegistryAccessor, IRegistryKindReader
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
