using Evo.Core.System;
using Microsoft.Win32;

namespace Evo.Windows;

/// <summary>
/// Acceso real al registro de Windows mediante <see cref="Microsoft.Win32.Registry"/>,
/// con vista de 64 bits. Implementa todas las interfaces de registro que usa
/// el motor: <see cref="IRegistryAccessor"/>, <see cref="IRegistryTreeReader"/>,
/// <see cref="IRegistryKeyCreator"/> y <see cref="IRegistryKindReader"/>.
/// </summary>
public sealed class WindowsRegistryAccessor : IRegistryAccessor, IRegistryTreeReader, IRegistryKeyCreator, IRegistryKindReader
{
    /// <summary>Tipos de valor soportados explícitamente (igual que el fake).</summary>
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

    /// <summary>Lee un valor; null si la clave o el valor no existen.</summary>
    /// <param name="hive">Colmena del registro (HKLM, HKCU, HKCR, HKU, HKCC).</param>
    /// <param name="keyPath">Ruta de la clave.</param>
    /// <param name="valueName">Nombre del valor; cadena vacía es el valor predeterminado.</param>
    /// <returns>El valor del registro, o null si no existe.</returns>
    public object? GetValue(RegistryHive hive, string keyPath, string valueName)
    {
        using var key = OpenRead(hive, keyPath);
        if (key is null) return null;
        return key.GetValue(valueName, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
    }

    /// <summary>Escribe un valor (cualquier tipo soportado por el registro).</summary>
    /// <param name="hive">Colmena del registro.</param>
    /// <param name="keyPath">Ruta de la clave.</param>
    /// <param name="valueName">Nombre del valor; cadena vacía es el valor predeterminado.</param>
    /// <param name="value">Dato del valor.</param>
    /// <param name="kind">Tipo de registro del valor.</param>
    public void SetValue(RegistryHive hive, string keyPath, string valueName, object value, RegistryValueKind kind)
    {
        if (!SupportedKinds.Contains(kind))
        {
            throw new NotSupportedException($"Tipo de valor de registro no soportado: {kind}.");
        }

        using var key = OpenWrite(hive, keyPath);
        key.SetValue(valueName, value, kind);
    }

    /// <summary>Borra un valor. Devuelve true si existía.</summary>
    /// <param name="hive">Colmena del registro.</param>
    /// <param name="keyPath">Ruta de la clave.</param>
    /// <param name="valueName">Nombre del valor.</param>
    /// <returns>true si el valor existía y se borró.</returns>
    public bool DeleteValue(RegistryHive hive, string keyPath, string valueName)
    {
        using var key = OpenWrite(hive, keyPath);
        if (key is null) return false;
        var names = key.GetValueNames();
        if (!names.Contains(valueName, StringComparer.OrdinalIgnoreCase)) return false;
        key.DeleteValue(valueName);
        return true;
    }

    /// <summary>True si la clave existe.</summary>
    /// <param name="hive">Colmena del registro.</param>
    /// <param name="keyPath">Ruta de la clave.</param>
    /// <returns>true si la clave existe.</returns>
    public bool KeyExists(RegistryHive hive, string keyPath)
    {
        using var key = OpenRead(hive, keyPath);
        return key is not null;
    }

    /// <summary>Borra una clave (sin recursión salvo que <paramref name="recursive"/> sea true).</summary>
    /// <param name="hive">Colmena del registro.</param>
    /// <param name="keyPath">Ruta de la clave.</param>
    /// <param name="recursive">Si true, borra también el subárbol completo.</param>
    /// <returns>true si la clave existía y se borró.</returns>
    public bool DeleteKey(RegistryHive hive, string keyPath, bool recursive)
    {
        var root = RootKey(hive);
        using var key = root.OpenSubKey(keyPath, writable: false);
        if (key is null) return false;

        if (recursive)
        {
            root.DeleteSubKeyTree(keyPath);
        }
        else
        {
            root.DeleteSubKey(keyPath);
        }

        return true;
    }

    /// <summary>Nombres de las subclaves directas de <paramref name="keyPath"/>.</summary>
    /// <param name="hive">Colmena del registro.</param>
    /// <param name="keyPath">Ruta de la clave.</param>
    /// <returns>Lista de nombres de subclaves directas.</returns>
    public IReadOnlyList<string> GetSubKeyNames(RegistryHive hive, string keyPath)
    {
        using var key = OpenRead(hive, keyPath);
        if (key is null) return [];
        return key.GetSubKeyNames();
    }

    /// <summary>Nombres de los valores directos de <paramref name="keyPath"/>.</summary>
    /// <param name="hive">Colmena del registro.</param>
    /// <param name="keyPath">Ruta de la clave.</param>
    /// <returns>Lista de nombres de valores directos.</returns>
    public IReadOnlyList<string> GetValueNames(RegistryHive hive, string keyPath)
    {
        using var key = OpenRead(hive, keyPath);
        if (key is null) return [];
        return key.GetValueNames();
    }

    /// <summary>Crea la clave vacía si no existe (deshacer de un borrado).</summary>
    /// <param name="hive">Colmena del registro.</param>
    /// <param name="keyPath">Ruta de la clave a crear.</param>
    public void EnsureKey(RegistryHive hive, string keyPath)
    {
        RootKey(hive).CreateSubKey(keyPath);
    }

    /// <summary>Tipo del valor (Unknown si no existe).</summary>
    /// <param name="hive">Colmena del registro.</param>
    /// <param name="keyPath">Ruta de la clave.</param>
    /// <param name="valueName">Nombre del valor.</param>
    /// <returns>Tipo del valor, o Unknown si no existe.</returns>
    public RegistryValueKind GetKind(RegistryHive hive, string keyPath, string valueName)
    {
        using var key = OpenRead(hive, keyPath);
        if (key is null) return RegistryValueKind.Unknown;
        try
        {
            return key.GetValueKind(valueName);
        }
        catch
        {
            return RegistryValueKind.Unknown;
        }
    }

    private static RegistryKey? OpenRead(RegistryHive hive, string keyPath) =>
        RootKey(hive).OpenSubKey(keyPath, writable: false);

    private static RegistryKey OpenWrite(RegistryHive hive, string keyPath) =>
        RootKey(hive).OpenSubKey(keyPath, writable: true)
        ?? RootKey(hive).CreateSubKey(keyPath)
        ?? throw new InvalidOperationException($"No se pudo abrir ni crear la clave '{keyPath}' en la colmena {hive}.");

    private static RegistryKey RootKey(RegistryHive hive) => hive switch
    {
        RegistryHive.LocalMachine => RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64),
        RegistryHive.CurrentUser => RegistryKey.OpenBaseKey(RegistryHive.CurrentUser, RegistryView.Registry64),
        RegistryHive.ClassesRoot => RegistryKey.OpenBaseKey(RegistryHive.ClassesRoot, RegistryView.Registry64),
        RegistryHive.Users => RegistryKey.OpenBaseKey(RegistryHive.Users, RegistryView.Registry64),
        RegistryHive.CurrentConfig => RegistryKey.OpenBaseKey(RegistryHive.CurrentConfig, RegistryView.Registry64),
        _ => throw new NotSupportedException($"Colmena de registro no soportada: {hive}."),
    };
}
