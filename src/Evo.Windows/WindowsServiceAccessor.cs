using Evo.Core.System;
using Microsoft.Win32;
using System.ServiceProcess;

namespace Evo.Windows;

/// <summary>
/// Acceso real a servicios de Windows mediante <see cref="ServiceController"/>
/// para estado y arranque/detención, y mediante el registro de Windows para
/// el tipo de inicio (desviación frente a <c>ChangeServiceConfig</c>:
/// se escribe directamente en
/// <c>HKLM\SYSTEM\CurrentControlSet\Services\&lt;nombre&gt;\Start</c> y
/// <c>DelayedAutostart</c>).
/// </summary>
public sealed class WindowsServiceAccessor : IServiceAccessor
{
    private readonly WindowsRegistryAccessor _registry = new();

    private const string ServicesBase = @"SYSTEM\CurrentControlSet\Services";

    /// <summary>Estado de un servicio.</summary>
    /// <param name="serviceName">Nombre del servicio.</param>
    /// <returns>Estado actual, o Unknown si el servicio no existe.</returns>
    public ServiceStatus GetStatus(string serviceName)
    {
        try
        {
            using var controller = new ServiceController(serviceName);
            return controller.Status switch
            {
                ServiceControllerStatus.Running => ServiceStatus.Running,
                ServiceControllerStatus.Stopped => ServiceStatus.Stopped,
                ServiceControllerStatus.StartPending => ServiceStatus.StartPending,
                ServiceControllerStatus.StopPending => ServiceStatus.StopPending,
                ServiceControllerStatus.ContinuePending => ServiceStatus.ContinuePending,
                ServiceControllerStatus.PausePending => ServiceStatus.PausePending,
                ServiceControllerStatus.Paused => ServiceStatus.Paused,
                _ => ServiceStatus.Unknown,
            };
        }
        catch
        {
            return ServiceStatus.Unknown;
        }
    }

    /// <summary>Tipo de arranque de un servicio (leído del registro).</summary>
    /// <param name="serviceName">Nombre del servicio.</param>
    /// <returns>Tipo de arranque, o Unknown si no se puede leer.</returns>
    public ServiceStartupType GetStartupType(string serviceName)
    {
        var start = _registry.GetValue(RegistryHive.LocalMachine, $"{ServicesBase}\\{serviceName}", "Start");
        var delayed = _registry.GetValue(RegistryHive.LocalMachine, $"{ServicesBase}\\{serviceName}", "DelayedAutostart");

        if (start is not int startInt) return ServiceStartupType.Unknown;

        return startInt switch
        {
            2 when delayed is int d && d == 1 => ServiceStartupType.AutomaticDelayed,
            2 => ServiceStartupType.Automatic,
            3 => ServiceStartupType.Manual,
            4 => ServiceStartupType.Disabled,
            _ => ServiceStartupType.Unknown,
        };
    }

    /// <summary>Escribe el tipo de arranque en el registro.</summary>
    /// <param name="serviceName">Nombre del servicio.</param>
    /// <param name="startupType">Tipo de arranque a establecer.</param>
    /// <remarks>
    /// Desviación: no se usa <c>ChangeServiceConfig</c>; se escribe directamente
    /// en <c>HKLM\SYSTEM\CurrentControlSet\Services\&lt;nombre&gt;\Start</c> y
    /// <c>DelayedAutostart</c>.
    /// </remarks>
    public void SetStartupType(string serviceName, ServiceStartupType startupType)
    {
        var keyPath = $"{ServicesBase}\\{serviceName}";
        switch (startupType)
        {
            case ServiceStartupType.Automatic:
                _registry.SetValue(RegistryHive.LocalMachine, keyPath, "Start", 2, RegistryValueKind.DWord);
                _registry.SetValue(RegistryHive.LocalMachine, keyPath, "DelayedAutostart", 0, RegistryValueKind.DWord);
                break;
            case ServiceStartupType.AutomaticDelayed:
                _registry.SetValue(RegistryHive.LocalMachine, keyPath, "Start", 2, RegistryValueKind.DWord);
                _registry.SetValue(RegistryHive.LocalMachine, keyPath, "DelayedAutostart", 1, RegistryValueKind.DWord);
                break;
            case ServiceStartupType.Manual:
                _registry.SetValue(RegistryHive.LocalMachine, keyPath, "Start", 3, RegistryValueKind.DWord);
                break;
            case ServiceStartupType.Disabled:
                _registry.SetValue(RegistryHive.LocalMachine, keyPath, "Start", 4, RegistryValueKind.DWord);
                break;
            case ServiceStartupType.Boot:
            case ServiceStartupType.System:
            default:
                throw new NotSupportedException($"Tipo de arranque no soportado para escritura: {startupType}.");
        }
    }

    /// <summary>Inicia un servicio con espera de hasta 30 segundos.</summary>
    /// <param name="serviceName">Nombre del servicio.</param>
    public void StartService(string serviceName)
    {
        using var controller = new ServiceController(serviceName);
        controller.Start();
        controller.WaitForStatus(ServiceControllerStatus.Running, TimeSpan.FromSeconds(30));
    }

    /// <summary>Detiene un servicio con espera de hasta 30 segundos.</summary>
    /// <param name="serviceName">Nombre del servicio.</param>
    public void StopService(string serviceName)
    {
        using var controller = new ServiceController(serviceName);
        controller.Stop();
        controller.WaitForStatus(ServiceControllerStatus.Stopped, TimeSpan.FromSeconds(30));
    }
}
