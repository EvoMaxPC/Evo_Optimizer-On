using Microsoft.Win32;

namespace Evo.Core.System;

/// <summary>
/// Lectura opcional del tipo de un valor de registro. Un accesor que lo
/// implemente permite al motor restaurar el valor con su tipo original exacto;
/// si no, se usa <see cref="RegistryValueKind.Unknown"/>.
/// </summary>
public interface IRegistryKindReader
{
    RegistryValueKind GetKind(RegistryHive hive, string keyPath, string valueName);
}
