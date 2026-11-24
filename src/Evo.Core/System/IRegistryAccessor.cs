using Microsoft.Win32;

namespace Evo.Core.System;

/// <summary>Acceso al registro encapsulado; sin efectos en dry-run.</summary>
public interface IRegistryAccessor
{
    /// <summary>Lee un valor; null si la clave o el valor no existen.</summary>
    object? GetValue(RegistryHive hive, string keyPath, string valueName);

    /// <summary>Escribe un valor (cualquier tipo soportado por el registro).</summary>
    void SetValue(RegistryHive hive, string keyPath, string valueName, object value, RegistryValueKind kind);

    /// <summary>Borra un valor. Devuelve true si existía.</summary>
    bool DeleteValue(RegistryHive hive, string keyPath, string valueName);

    /// <summary>True si la clave existe.</summary>
    bool KeyExists(RegistryHive hive, string keyPath);

    /// <summary>Borra una clave (sin recursión salvo que <paramref name="recursive"/>).</summary>
    bool DeleteKey(RegistryHive hive, string keyPath, bool recursive);
}
