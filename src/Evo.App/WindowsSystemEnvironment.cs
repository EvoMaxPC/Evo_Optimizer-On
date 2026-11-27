using Microsoft.Win32;
using Evo.Core.System;

namespace Evo.App;

/// <summary>Entorno del sistema real (lectura de registro y versión de Windows).</summary>
public sealed class WindowsSystemEnvironment : ISystemEnvironment
{
    public int CurrentBuild => ReadInt("CurrentBuildNumber", 0);
    public int UBR => ReadInt("UBR", 0);
    public string EditionID => ReadString("EditionID") ?? string.Empty;
    public string InstallationType => ReadString("InstallationType") ?? string.Empty;
    public string Architecture => ReadString("ProcessorArchitecture") ?? string.Empty;

    public bool IsAdmin => IsAdministrator();
    public bool IsElevated => IsElevatedProcess();

    private static int ReadInt(string valueName, int defaultValue)
    {
        try
        {
            using var key = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64)
                .OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion");
            var val = key?.GetValue(valueName);
            return val is not null ? int.Parse(val.ToString()!) : defaultValue;
        }
        catch
        {
            return defaultValue;
        }
    }

    private static string? ReadString(string valueName)
    {
        try
        {
            using var key = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64)
                .OpenSubKey(@"SOFTWARE\Microsoft\Windows NT\CurrentVersion");
            return key?.GetValue(valueName) as string;
        }
        catch
        {
            return null;
        }
    }

    private static bool IsAdministrator()
    {
        try
        {
            using var identity = System.Security.Principal.WindowsIdentity.GetCurrent();
            var principal = new System.Security.Principal.WindowsPrincipal(identity);
            return principal.IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
        }
        catch
        {
            return false;
        }
    }

    private static bool IsElevatedProcess()
    {
        try
        {
            using var identity = System.Security.Principal.WindowsIdentity.GetCurrent();
            var principal = new System.Security.Principal.WindowsPrincipal(identity);
            return principal.IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
        }
        catch
        {
            return false;
        }
    }
}
