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
        if (FailStartWith is not null &&
            string.Equals(FailStartWith, serviceName, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException($"No se pudo iniciar el servicio '{serviceName}'.");
        }

        // Windows no arranca un servicio deshabilitado (ERROR_SERVICE_DISABLED,
        // 1058). El fake lo imita para que un deshacer con el orden equivocado
        // falle en los tests y no sólo en producción.
        if (_services.TryGetValue(serviceName, out var disabled) &&
            disabled.StartupType == ServiceStartupType.Disabled)
        {
            throw new InvalidOperationException(
                $"No se pudo iniciar el servicio '{serviceName}': está deshabilitado (1058).");
        }

        var current = _services.TryGetValue(serviceName, out var service)
            ? service
            : new FakeService(serviceName, ServiceStatus.Stopped, ServiceStartupType.Unknown);
        _services[serviceName] = current with { Status = ServiceStatus.Running };
        MutationCount++;
        Log.Add($"start {serviceName}");
    }

    public void StopService(string serviceName)
    {
        if (FailStopWith is not null &&
            string.Equals(FailStopWith, serviceName, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException($"No se pudo detener el servicio '{serviceName}'.");
        }

        var current = _services.TryGetValue(serviceName, out var service)
            ? service
            : new FakeService(serviceName, ServiceStatus.Stopped, ServiceStartupType.Unknown);
        _services[serviceName] = current with { Status = ServiceStatus.Stopped };
        MutationCount++;
        Log.Add($"stop {serviceName}");
    }

    /// <summary>Si no es null, arrancar el servicio con ese nombre lanza.</summary>
    public string? FailStartWith { get; set; }

    /// <summary>Si no es null, detener el servicio con ese nombre lanza.</summary>
    public string? FailStopWith { get; set; }

    /// <summary>Marca un servicio inexistente como existente pero desconocido.</summary>
    public bool Exists(string serviceName) => _services.ContainsKey(serviceName);
}
