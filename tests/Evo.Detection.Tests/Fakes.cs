using Evo.Core.System;
using Microsoft.Win32;

namespace Evo.Detection.Tests;

/// <summary>Entorno simulado: nunca toca la máquina real.</summary>
internal sealed class FakeSystemEnvironment : ISystemEnvironment
{
    public int CurrentBuild { get; init; } = 26100;

    public int UBR { get; init; } = 3915;

    public string EditionID { get; init; } = "Professional";

    public string InstallationType { get; init; } = "Client";

    public string Architecture { get; init; } = "x64";

    public bool IsAdmin { get; init; } = false;

    public bool IsElevated { get; init; } = false;
}

/// <summary>Registro en memoria con los mismos valores que el sistema simulado.</summary>
internal sealed class FakeRegistryAccessor : IRegistryAccessor
{
    private readonly Dictionary<(RegistryHive, string, string), object> _values = [];

    public static FakeRegistryAccessor FromEnvironment(ISystemEnvironment environment)
    {
        var registry = new FakeRegistryAccessor();
        registry._values[(RegistryHive.LocalMachine, "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion", "CurrentBuildNumber")] =
            environment.CurrentBuild.ToString(System.Globalization.CultureInfo.InvariantCulture);
        registry._values[(RegistryHive.LocalMachine, "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion", "UBR")] =
            environment.UBR;
        registry._values[(RegistryHive.LocalMachine, "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion", "EditionID")] =
            environment.EditionID;
        registry._values[(RegistryHive.LocalMachine, "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion", "InstallationType")] =
            environment.InstallationType;
        return registry;
    }

    public FakeRegistryAccessor With(string keyPath, string valueName, object value)
    {
        _values[(RegistryHive.LocalMachine, keyPath, valueName)] = value;
        return this;
    }

    public object? GetValue(RegistryHive hive, string keyPath, string valueName) =>
        _values.TryGetValue((hive, keyPath, valueName), out var value) ? value : null;

    public void SetValue(RegistryHive hive, string keyPath, string valueName, object value, RegistryValueKind kind) =>
        _values[(hive, keyPath, valueName)] = value;

    public bool DeleteValue(RegistryHive hive, string keyPath, string valueName) =>
        _values.Remove((hive, keyPath, valueName));

    public bool KeyExists(RegistryHive hive, string keyPath) =>
        _values.Keys.Any(k => k.Item1 == hive && k.Item2 == keyPath);

    public bool DeleteKey(RegistryHive hive, string keyPath, bool recursive)
    {
        var keys = _values.Keys
            .Where(k => k.Item1 == hive && k.Item2 == keyPath)
            .ToList();

        foreach (var key in keys)
        {
            _values.Remove(key);
        }

        return keys.Count > 0;
    }
}
