using Evo.Core.System;

namespace Evo.Testing;

/// <summary>Tarea programada simulada.</summary>
public sealed record FakeTask(string Path, string Name, bool Enabled)
{
    /// <summary>Definición con la que se creó (null si sólo se sembró).</summary>
    public TaskDefinition? Definition { get; init; }
}

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

    /// <summary>Tareas creadas por el motor (además de las sembradas).</summary>
    public List<TaskDefinition> Created { get; } = [];

    /// <summary>Si no es null, la siguiente creación lanza este error.</summary>
    public string? FailCreateWith { get; set; }

    public void CreateTask(TaskDefinition definition)
    {
        ArgumentNullException.ThrowIfNull(definition);

        if (FailCreateWith is not null)
        {
            throw new InvalidOperationException(FailCreateWith);
        }

        _tasks[Key(definition.TaskPath, definition.TaskName)] =
            new FakeTask(definition.TaskPath, definition.TaskName, true) { Definition = definition };
        Created.Add(definition);
        MutationCount++;
        Log.Add($"create {definition.TaskPath}\\{definition.TaskName}");
    }

    public bool DeleteTask(string taskPath, string taskName)
    {
        if (!_tasks.Remove(Key(taskPath, taskName)))
        {
            return false;
        }

        MutationCount++;
        Log.Add($"delete {taskPath}\\{taskName}");
        return true;
    }

    public void EnableTask(string taskPath, string taskName) => Set(taskPath, taskName, true);

    public void DisableTask(string taskPath, string taskName) => Set(taskPath, taskName, false);

    private void Set(string taskPath, string taskName, bool enabled)
    {
        var previous = _tasks.GetValueOrDefault(Key(taskPath, taskName));
        _tasks[Key(taskPath, taskName)] =
            new FakeTask(taskPath, taskName, enabled) { Definition = previous?.Definition };
        MutationCount++;
        Log.Add($"{(enabled ? "enable" : "disable")} {taskPath}\\{taskName}");
    }

    private static string Key(string taskPath, string taskName) => $"{taskPath.TrimEnd('\\')}\\{taskName}";
}
