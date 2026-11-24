namespace Evo.Core.System;

/// <summary>Control de tareas programadas (ruta + nombre).</summary>
public interface ITaskAccessor
{
    bool Exists(string taskPath, string taskName);

    bool IsTaskEnabled(string taskPath, string taskName);

    void EnableTask(string taskPath, string taskName);

    void DisableTask(string taskPath, string taskName);
}
