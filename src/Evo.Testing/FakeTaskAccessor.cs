using Evo.Core.System;

namespace Evo.Testing;

/// <summary>Tarea programada simulada.</summary>
public sealed record FakeTask(string Path, string Name, bool Enabled);

/// <summary>Gestor de tareas programadas en memoria.</summary>
public sealed class FakeTaskAccessor : ITaskAccessor
{
    private readonly Dictionary<string, FakeTask> _tasks = new(StringComparer.OrdinalIgnoreCase);

    public int MutationCount { get; private set; }

    public List<string> Log { get; } = [];

    public IReadOnlyDictionary<string, FakeTask> Snapshot() =>
        new Dictionary<string, FakeTask>(_tasks, StringComparer.OrdinalIgnoreCase);

    public FakeTaskAccessor Seed(string taskPath, string taskName, bool enabled)
    {
        _tasks[Key(taskPath, taskName)] = new FakeTask(taskPath, taskName, enabled);
        Log.Clear();
        return this;
    }

    public bool Exists(string taskPath, string taskName) => _tasks.ContainsKey(Key(taskPath, taskName));

    public bool IsTaskEnabled(string taskPath, string taskName) =>
        _tasks.TryGetValue(Key(taskPath, taskName), out var task) && task.Enabled;

    public void EnableTask(string taskPath, string taskName) => Set(taskPath, taskName, true);

    public void DisableTask(string taskPath, string taskName) => Set(taskPath, taskName, false);

    private void Set(string taskPath, string taskName, bool enabled)
    {
        _tasks[Key(taskPath, taskName)] = new FakeTask(taskPath, taskName, enabled);
        MutationCount++;
        Log.Add($"{(enabled ? "enable" : "disable")} {taskPath}\\{taskName}");
    }

    private static string Key(string taskPath, string taskName) => $"{taskPath.TrimEnd('\\')}\\{taskName}";
}
