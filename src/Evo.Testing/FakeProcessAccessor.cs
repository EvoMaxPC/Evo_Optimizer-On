using Evo.Core.System;

namespace Evo.Testing;

/// <summary>Proceso simulado.</summary>
public sealed record FakeProcess(int Id, string Name, bool Running);

/// <summary>Gestor de procesos en memoria que registra cada terminación.</summary>
public sealed class FakeProcessAccessor : IProcessAccessor
{
    private readonly List<FakeProcess> _processes = [];
    private int _nextId = 1000;

    /// <summary>Terminaciones pedidas, en orden.</summary>
    public List<string> Terminated { get; } = [];

    /// <summary>Detenciones pedidas, en orden.</summary>
    public List<string> Stopped { get; } = [];

    /// <summary>Arranques pedidos, en orden.</summary>
    public List<string> Started { get; } = [];

    public IReadOnlyList<FakeProcess> Snapshot() => _processes.ToList();

    public FakeProcessAccessor Seed(string name, bool running = true)
    {
        _processes.Add(new FakeProcess(_nextId++, name, running));
        return this;
    }

    public bool IsRunning(string processName) =>
        _processes.Any(p => p.Running &&
                            string.Equals(p.Name, processName, StringComparison.OrdinalIgnoreCase));

    public bool TerminateProcess(string processName)
    {
        var matches = _processes
            .Where(p => p.Running && string.Equals(p.Name, processName, StringComparison.OrdinalIgnoreCase))
            .ToList();

        if (matches.Count == 0)
        {
            return false;
        }

        foreach (var process in matches)
        {
            _processes[_processes.IndexOf(process)] = process with { Running = false };
            Terminated.Add(process.Name);
        }

        return true;
    }

    public bool StopProcess(string processName)
    {
        var matches = _processes
            .Where(p => p.Running && string.Equals(p.Name, processName, StringComparison.OrdinalIgnoreCase))
            .ToList();

        if (matches.Count == 0)
        {
            return false;
        }

        foreach (var process in matches)
        {
            _processes[_processes.IndexOf(process)] = process with { Running = false };
            Stopped.Add(process.Name);
        }

        return true;
    }

    public int StartProcess(string fileName, IReadOnlyList<string> arguments)
    {
        var id = _nextId++;
        _processes.Add(new FakeProcess(id, Path.GetFileNameWithoutExtension(fileName), true));
        Started.Add(arguments.Count == 0 ? fileName : $"{fileName} {string.Join(' ', arguments)}");
        return id;
    }
}
