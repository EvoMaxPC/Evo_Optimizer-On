using Evo.Core.System;

namespace Evo.Testing;

/// <summary>
/// Entorno simulado y mutable: permite preparar cualquier build, UBR,
/// arquitectura, edición, InstallationType y privilegios.
/// </summary>
public sealed class FakeSystemEnvironment : ISystemEnvironment
{
    public int CurrentBuild { get; set; } = 26100;

    public int UBR { get; set; } = 3915;

    public string EditionID { get; set; } = "Professional";

    public string InstallationType { get; set; } = "Client";

    public string Architecture { get; set; } = "x64";

    public bool IsAdmin { get; set; }

    public bool IsElevated { get; set; }

    /// <summary>Entorno de Windows 11 24H2 cliente, sin privilegios.</summary>
    public static FakeSystemEnvironment Win11_24H2_Client() => new();

    /// <summary>Entorno de Windows 10 22H2 cliente (requiere ESU).</summary>
    public static FakeSystemEnvironment Win10_22H2_Client() => new()
    {
        CurrentBuild = 19045,
        UBR = 6093,
        EditionID = "CoreSingleLanguage",
    };

    /// <summary>Entorno de Windows Server 2025 Datacenter (rechazado).</summary>
    public static FakeSystemEnvironment Server2025() => new()
    {
        CurrentBuild = 26100,
        EditionID = "ServerDatacenter",
        InstallationType = "Server",
        Architecture = "x64",
    };

    /// <summary>Entorno cliente con token de administrador elevado.</summary>
    public FakeSystemEnvironment AsAdminElevated()
    {
        IsAdmin = true;
        IsElevated = true;
        return this;
    }

    /// <summary>Entorno ARM64.</summary>
    public FakeSystemEnvironment AsArm64()
    {
        Architecture = "arm64";
        return this;
    }
}
