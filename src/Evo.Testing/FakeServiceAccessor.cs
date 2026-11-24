using Evo.Core.System;

namespace Evo.Testing;

/// <summary>Servicio simulado.</summary>
public sealed record FakeService(string Name, ServiceStatus Status, ServiceStartupType StartupType);

/// <summary>Gestor de servicios en memoria.</summary>
public sealed class FakeServiceAccessor : IServiceAccessor
{
    private readonly Dictionary<string, FakeService> _services = new(StringComparer.OrdinalIgnoreCase);

    public int MutationCount { get; private set; }

    public List<string> Log { get; } = [];

    /// <summary>Estado actual (copia).</summary>
    public IReadOnlyDictionary<string, FakeService> Snapshot() =>
        new Dictionary<string, FakeService>(_services, StringComparer.OrdinalIgnoreCase);

    public FakeServiceAccessor Seed(string name, ServiceStatus status, ServiceStartupType startupType)
    {
        _services[name] = new FakeService(name, status, startupType);
        Log.Clear();
        return this;
    }

    public ServiceStatus GetStatus(string serviceName) =>
        _services.TryGetValue(serviceName, out var service) ? service.Status : ServiceStatus.Unknown;

    public ServiceStartupType GetStartupType(string serviceName) =>
        _services.TryGetValue(serviceName, out var service) ? service.StartupType : ServiceStartupType.Unknown;

    public void SetStartupType(string serviceName, ServiceStartupType startupType)
    {
        var current = _services.TryGetValue(serviceName, out var service)
            ? service
            : new FakeService(serviceName, ServiceStatus.Stopped, ServiceStartupType.Unknown);
        _services[serviceName] = current with { StartupType = startupType };
        MutationCount++;
        Log.Add($"startup {serviceName}={startupType}");
    }

    public void StartService(string serviceName)
    {
        var current = _services.TryGetValue(serviceName, out var service)
            ? service
            : new FakeService(serviceName, ServiceStatus.Stopped, ServiceStartupType.Unknown);
        _services[serviceName] = current with { Status = ServiceStatus.Running };
        MutationCount++;
        Log.Add($"start {serviceName}");
    }

    public void StopService(string serviceName)
    {
        var current = _services.TryGetValue(serviceName, out var service)
            ? service
            : new FakeService(serviceName, ServiceStatus.Stopped, ServiceStartupType.Unknown);
        _services[serviceName] = current with { Status = ServiceStatus.Stopped };
        MutationCount++;
        Log.Add($"stop {serviceName}");
    }

    /// <summary>Marca un servicio inexistente como existente pero desconocido.</summary>
    public bool Exists(string serviceName) => _services.ContainsKey(serviceName);
}
