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

/// <summary>
/// Lectura del árbol del registro para poder deshacer un borrado de clave
/// completa (paso 11, ADR-0005). Un accesor que no lo implemente hace que
/// <c>RegistryDeleteKey</c> aborte sin borrar (fail-closed): no se puede
/// prometer un deshacer que no se sabe hacer.
/// </summary>
public interface IRegistryTreeReader
{
    /// <summary>Nombres de las subclaves directas de <paramref name="keyPath"/>.</summary>
    IReadOnlyList<string> GetSubKeyNames(RegistryHive hive, string keyPath);

    /// <summary>Nombres de los valores directos de <paramref name="keyPath"/>.</summary>
    IReadOnlyList<string> GetValueNames(RegistryHive hive, string keyPath);
}

/// <summary>
/// Creación de una clave vacía. Hace falta para deshacer un borrado recursivo
/// que dejó ramas sin valores: recrearlas forma parte del estado previo exacto
/// (paso 11, ADR-0005).
/// </summary>
public interface IRegistryKeyCreator
{
    void EnsureKey(RegistryHive hive, string keyPath);
}
