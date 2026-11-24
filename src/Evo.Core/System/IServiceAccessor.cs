namespace Evo.Core.System;

/// <summary>Estado de un servicio de Windows.</summary>
public enum ServiceStatus
{
    Unknown = 0,
    Stopped = 1,
    StartPending = 2,
    StopPending = 3,
    Running = 4,
    ContinuePending = 5,
    PausePending = 6,
    Paused = 7,
}

/// <summary>Tipo de arranque de un servicio.</summary>
public enum ServiceStartupType
{
    Unknown = 0,
    Boot = 1,
    System = 2,
    Automatic = 3,
    AutomaticDelayed = 4,
    Manual = 5,
    Disabled = 6,
}

/// <summary>Control de servicios.</summary>
public interface IServiceAccessor
{
    ServiceStatus GetStatus(string serviceName);

    ServiceStartupType GetStartupType(string serviceName);

    void SetStartupType(string serviceName, ServiceStartupType startupType);

    void StartService(string serviceName);

    void StopService(string serviceName);
}
