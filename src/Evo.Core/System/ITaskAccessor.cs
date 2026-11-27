namespace Evo.Core.System;

/// <summary>Control de tareas programadas (ruta + nombre).</summary>
public interface ITaskAccessor
{
    bool Exists(string taskPath, string taskName);

    bool IsTaskEnabled(string taskPath, string taskName);

    void EnableTask(string taskPath, string taskName);

    void DisableTask(string taskPath, string taskName);

    /// <summary>
    /// Crea (o sobrescribe, si <paramref name="definition"/> ya existe y el
    /// accesor lo admite) una tarea programada (paso 11, ADR-0005).
    /// </summary>
    void CreateTask(TaskDefinition definition);

    /// <summary>Borra la tarea; devuelve true si existía.</summary>
    bool DeleteTask(string taskPath, string taskName);

    /// <summary>
    /// Devuelve la definición guardada de la tarea, o null si no existe o si
    /// el accesor no puede leerla.
    /// </summary>
    TaskDefinition? GetDefinition(string taskPath, string taskName);
}

/// <summary>
/// Definición declarativa mínima de una tarea programada. Sólo los
/// desencadenantes simples que usa el pin: diario a una hora o al iniciar
/// sesión (paso 11).
/// </summary>
public sealed record TaskDefinition
{
    public required string TaskPath { get; init; }

    public required string TaskName { get; init; }

    public required string Execute { get; init; }

    public string Arguments { get; init; } = string.Empty;

    /// <summary><c>Daily</c> u <c>OnLogon</c>.</summary>
    public required string Trigger { get; init; }

    /// <summary>Hora <c>HH:mm</c> cuando <see cref="Trigger"/> es <c>Daily</c>.</summary>
    public string? TriggerAt { get; init; }

    public required string UserId { get; init; }

    /// <summary><c>Highest</c> o <c>Limited</c>.</summary>
    public required string RunLevel { get; init; }

    public string Description { get; init; } = string.Empty;
}
