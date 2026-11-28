using Evo.Core.Enums;
using Evo.Core.System;
using Evo.Detection.Model;
using Microsoft.Win32;

namespace Evo.Detection;

/// <summary>
/// Detector de versión de Windows. Se apoya solo en
/// <see cref="ISystemEnvironment"/> e <see cref="IRegistryAccessor"/> (REQ-004)
/// y en datos de <c>catalog/windows-releases.json</c> (REQ-003).
/// </summary>
/// <remarks>
/// <c>ProductName</c> no se consulta: reporta «Windows 10» en kernels 26xxx
/// (ERRATA-EVO-003). La identidad se deriva de <c>CurrentBuildNumber</c>,
/// <c>UBR</c>, <c>EditionID</c> e <c>InstallationType</c>.
/// </remarks>
public sealed class WindowsDetector
{
    /// <summary>Clave del registro con la identidad del sistema.</summary>
    public const string CurrentVersionKey = @"SOFTWARE\Microsoft\Windows NT\CurrentVersion";

    private readonly ISystemEnvironment _environment;
    private readonly IRegistryAccessor _registry;
    private readonly WindowsReleaseCatalog _catalog;

    public WindowsDetector(
        ISystemEnvironment environment,
        IRegistryAccessor registry,
        WindowsReleaseCatalog catalog)
    {
        ArgumentNullException.ThrowIfNull(environment);
        ArgumentNullException.ThrowIfNull(registry);
        ArgumentNullException.ThrowIfNull(catalog);

        _environment = environment;
        _registry = registry;
        _catalog = catalog;
    }

    /// <summary>
    /// Detecta y clasifica. Nunca lanza por un sistema no soportado: devuelve
    /// el veredicto. Use <see cref="EnsureSupported"/> si prefiere excepción.
    /// </summary>
    public CompatibilityResult Detect()
    {
        var build = ReadInt("CurrentBuildNumber", _environment.CurrentBuild);
        var ubr = ReadInt("UBR", _environment.UBR);
        var edition = ReadString("EditionID", _environment.EditionID);
        var installationType = ReadString("InstallationType", _environment.InstallationType);
        var architecture = Normalize(_environment.Architecture);

        var baseResult = new CompatibilityResult
        {
            Status = CompatibilityStatus.Indeterminate,
            Build = build,
            Ubr = ubr,
            EditionId = edition,
            InstallationType = installationType,
            Architecture = architecture,
        };

        if (build <= 0)
        {
            return baseResult with
            {
                Reason = "No se pudo leer CurrentBuildNumber.",
            };
        }

        // 1) InstallationType: solo Client es objetivo. Fail-closed: un valor
        //    desconocido o vacío también se rechaza.
        if (!string.Equals(installationType, "Client", StringComparison.OrdinalIgnoreCase))
        {
            var isServer = installationType.StartsWith("Server", StringComparison.OrdinalIgnoreCase);
            return baseResult with
            {
                Status = CompatibilityStatus.ServerRejected,
                Reason = isServer
                    ? $"Windows Server no está soportado (InstallationType='{installationType}', EditionID='{edition}')."
                    : $"InstallationType '{installationType}' no soportado; solo 'Client'.",
            };
        }

        // 2) Build contra el catálogo (dato, no código).
        var release = _catalog.Find(build);
        var overCeiling = _catalog.MaxSupportedBuild > 0 && build > _catalog.MaxSupportedBuild;
        if (release is null || overCeiling)
        {
            return baseResult with
            {
                Status = CompatibilityStatus.UnknownBuildRejected,
                Reason = $"Build {build} desconocido: no casa con ninguna entrada del catálogo.",
            };
        }

        // 3) Arquitectura declarada para esa versión.
        if (!release.SupportsArchitecture(architecture))
        {
            return baseResult with
            {
                Status = CompatibilityStatus.ArchitectureRejected,
                Release = release,
                Reason = $"Arquitectura '{architecture}' no declarada para {release.DisplayName}.",
            };
        }

        // 4) Aviso de fin de soporte / ESU (Windows 10 22H2).
        var warnings = new List<string>();
        if (release.RequiresEsuNotice || release.EsuRequired)
        {
            warnings.Add(
                $"{release.DisplayName} (build {build}) está fuera del soporte general: " +
                "requiere ESU (Extended Security Updates) para seguir recibiendo parches.");
        }

        var status = warnings.Count > 0
            ? CompatibilityStatus.SupportedWithWarning
            : CompatibilityStatus.Supported;

        return baseResult with
        {
            Status = status,
            Release = release,
            Warnings = warnings,
        };
    }

    /// <summary>
    /// Igual que <see cref="Detect"/> pero lanza <see cref="ServerNotSupportedException"/>
    /// si el sistema es Windows Server.
    /// </summary>
    public CompatibilityResult EnsureSupported()
    {
        var result = Detect();
        if (result.Status == CompatibilityStatus.ServerRejected)
        {
            throw new ServerNotSupportedException(
                result.Reason, result.InstallationType, result.EditionId);
        }

        return result;
    }

    private string ReadString(string valueName, string fallback)
    {
        var value = _registry.GetValue(RegistryHive.LocalMachine, CurrentVersionKey, valueName);
        return value switch
        {
            string text when !string.IsNullOrWhiteSpace(text) => text.Trim(),
            int number => number.ToString(System.Globalization.CultureInfo.InvariantCulture),
            _ => fallback ?? string.Empty,
        };
    }

    private int ReadInt(string valueName, int fallback)
    {
        var value = _registry.GetValue(RegistryHive.LocalMachine, CurrentVersionKey, valueName);
        switch (value)
        {
            case int number:
                return number;
            case long number:
                return (int)number;
            case string text when int.TryParse(
                text.Trim(),
                System.Globalization.NumberStyles.Integer,
                System.Globalization.CultureInfo.InvariantCulture,
                out var parsed):
                return parsed;
            default:
                return fallback;
        }
    }

    private static string Normalize(string architecture)
    {
        if (string.IsNullOrWhiteSpace(architecture))
        {
            return string.Empty;
        }

        return architecture.Trim().ToLowerInvariant() switch
        {
            "amd64" or "x86_64" or "x64" => "x64",
            "arm64" or "aarch64" => "arm64",
            "x86" or "i386" => "x86",
            var other => other,
        };
    }
}
