using Evo.Core.System;

namespace Evo.Windows;

/// <summary>
/// Acceso a tareas programadas no disponible todavía (pendiente para una etapa
/// posterior). Todos los métodos lanzan <see cref="NotSupportedException"/>.
/// </summary>
public sealed class UnavailableTaskAccessor : ITaskAccessor
{
    private const string Message = "Tareas programadas reales: pendiente (etapa posterior).";

    /// <summary>Siempre lanza <see cref="NotSupportedException"/>.</summary>
    /// <param name="taskPath">Ruta de la tarea.</param>
    /// <param name="taskName">Nombre de la tarea.</param>
    /// <returns>No devuelve; lanza.</returns>
    public bool Exists(string taskPath, string taskName) => throw new NotSupportedException(Message);

    /// <summary>Siempre lanza <see cref="NotSupportedException"/>.</summary>
    /// <param name="taskPath">Ruta de la tarea.</param>
    /// <param name="taskName">Nombre de la tarea.</param>
    /// <returns>No devuelve; lanza.</returns>
    public bool IsTaskEnabled(string taskPath, string taskName) => throw new NotSupportedException(Message);

    /// <summary>Siempre lanza <see cref="NotSupportedException"/>.</summary>
    /// <param name="taskPath">Ruta de la tarea.</param>
    /// <param name="taskName">Nombre de la tarea.</param>
    public void EnableTask(string taskPath, string taskName) => throw new NotSupportedException(Message);

    /// <summary>Siempre lanza <see cref="NotSupportedException"/>.</summary>
    /// <param name="taskPath">Ruta de la tarea.</param>
    /// <param name="taskName">Nombre de la tarea.</param>
    public void DisableTask(string taskPath, string taskName) => throw new NotSupportedException(Message);

    /// <summary>Siempre lanza <see cref="NotSupportedException"/>.</summary>
    /// <param name="definition">Definición de la tarea.</param>
    public void CreateTask(TaskDefinition definition) => throw new NotSupportedException(Message);

    /// <summary>Siempre lanza <see cref="NotSupportedException"/>.</summary>
    /// <param name="taskPath">Ruta de la tarea.</param>
    /// <param name="taskName">Nombre de la tarea.</param>
    /// <returns>No devuelve; lanza.</returns>
    public bool DeleteTask(string taskPath, string taskName) => throw new NotSupportedException(Message);

    /// <summary>Siempre lanza <see cref="NotSupportedException"/>.</summary>
    /// <param name="taskPath">Ruta de la tarea.</param>
    /// <param name="taskName">Nombre de la tarea.</param>
    /// <returns>No devuelve; lanza.</returns>
    public TaskDefinition? GetDefinition(string taskPath, string taskName) => throw new NotSupportedException(Message);
}
