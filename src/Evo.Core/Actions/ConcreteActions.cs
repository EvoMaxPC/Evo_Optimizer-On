using System.Text.Json.Serialization;

namespace Evo.Core.Actions;

/// <summary>Hive del registro admitido por el motor.</summary>
public enum RegistryHiveKind
{
    LocalMachine = 0,
    CurrentUser = 1,
    ClassesRoot = 2,
    Users = 3,
}

/// <summary>Qué hacer con el valor de registro.</summary>
public enum RegistryOperation
{
    Set = 0,
    Delete = 1,
}

/// <summary>Tipos de valor de registro soportados (subconjunto estable).</summary>
public enum RegistryValueType
{
    String = 0,
    DWord = 1,
    QWord = 2,
    Binary = 3,
    MultiString = 4,
    ExpandString = 5,
}

/// <summary>Escritura o borrado de un valor de registro.</summary>
public sealed record RegistryAction : CapabilityAction
{
    public override ActionKind Kind => ActionKind.Registry;

    public required RegistryHiveKind Hive { get; init; }

    public required string KeyPath { get; init; }

    public required string ValueName { get; init; }

    public required RegistryOperation Operation { get; init; }

    public RegistryValueType ValueType { get; init; } = RegistryValueType.DWord;

    /// <summary>Valor serializado como texto (los binarios, en base64).</summary>
    public string? Value { get; init; }

    protected override string Fingerprint =>
        $"{Hive}\\{KeyPath}\\{ValueName}";
}

/// <summary>Tipo de arranque a aplicar a un servicio.</summary>
public enum ServiceOperation
{
    SetStartupType = 0,
    Start = 1,
    Stop = 2,
}

/// <summary>Cambio sobre un servicio de Windows.</summary>
public sealed record ServiceAction : CapabilityAction
{
    public override ActionKind Kind => ActionKind.Service;

    public required string ServiceName { get; init; }

    public required ServiceOperation Operation { get; init; }

    /// <summary>Solo para <see cref="ServiceOperation.SetStartupType"/>.</summary>
    public string? StartupType { get; init; }

    protected override string Fingerprint => ServiceName;
}

/// <summary>Habilitación o deshabilitación de una tarea programada.</summary>
public sealed record TaskAction : CapabilityAction
{
    public override ActionKind Kind => ActionKind.Task;

    public required string TaskPath { get; init; }

    public required string TaskName { get; init; }

    public required bool Enabled { get; init; }

    protected override string Fingerprint => $"{TaskPath}\\{TaskName}";
}

/// <summary>Terminación de un proceso requerido por la operación.</summary>
public sealed record ProcessAction : CapabilityAction
{
    public override ActionKind Kind => ActionKind.Process;

    public required string ProcessName { get; init; }

    /// <summary>Si es false, el proceso debe estar parado antes de seguir.</summary>
    public bool Terminate { get; init; } = true;

    protected override string Fingerprint => ProcessName;
}

/// <summary>Ejecución de un comando externo (sin shell implícita).</summary>
public sealed record CommandAction : CapabilityAction
{
    public override ActionKind Kind => ActionKind.Command;

    public required string FileName { get; init; }

    public IReadOnlyList<string> Arguments { get; init; } = [];

    /// <summary>Si es true, un código de salida distinto de 0 no aborta.</summary>
    public bool IgnoreExitCode { get; init; }

    /// <summary>Códigos de salida aceptados (por defecto solo 0).</summary>
    public IReadOnlyList<int> AllowedExitCodes { get; init; } = [0];

    [JsonIgnore]
    public string CommandLine => Arguments.Count == 0
        ? FileName
        : $"{FileName} {string.Join(' ', Arguments)}";

    protected override string Fingerprint => CommandLine;
}

/// <summary>
/// Borrado de una clave COMPLETA del registro (paso 11, ADR-0005).
/// </summary>
/// <remarks>
/// A diferencia de <see cref="RegistryAction"/> —que borra un valor—, esta
/// acción elimina la clave y su subárbol. Para que sea reversible el ejecutor
/// toma una instantánea completa (valores con tipo y subclaves, recursivamente)
/// ANTES de borrar y la guarda en el diario. Si la instantánea falla o supera el
/// límite declarado en <c>RegistrySnapshotLimits</c> (Evo.Engine.Executors), el
/// motor ABORTA sin borrar (fail-closed). El límite vive en el ejecutor, no aquí:
/// Evo.Core no conoce implementaciones del motor.
/// </remarks>
public sealed record RegistryDeleteKeyAction : CapabilityAction
{
    public override ActionKind Kind => ActionKind.RegistryDeleteKey;

    public required RegistryHiveKind Hive { get; init; }

    /// <summary>Ruta completa de la clave a borrar.</summary>
    public required string KeyPath { get; init; }

    /// <summary>
    /// Si es false (por defecto) sólo se borra la clave; si es true se borra el
    /// subárbol. El pin de Atlas (Toggles) borra la clave tal cual, sin recursión.
    /// </summary>
    public bool Recursive { get; init; }

    protected override string Fingerprint => $"{Hive}\\{KeyPath}";
}

/// <summary>
/// Creación de una tarea programada desde una definición declarativa mínima
/// (paso 11, ADR-0005).
/// </summary>
/// <remarks>
/// La inversa es eliminar la tarea creada. Si la tarea ya existía, el ejecutor
/// captura su estado previo (habilitada/deshabilitada y definición si el accesor
/// sabe leerla) y el diario la restaura en vez de borrarla.
/// </remarks>
public sealed record TaskCreateAction : CapabilityAction
{
    public override ActionKind Kind => ActionKind.TaskCreate;

    public required string TaskPath { get; init; }

    public required string TaskName { get; init; }

    /// <summary>Programa o ejecutable de la acción de la tarea.</summary>
    public required string Execute { get; init; }

    /// <summary>Argumentos de la acción (texto ya compuesto, sin shell).</summary>
    public string Arguments { get; init; } = string.Empty;

    /// <summary>
    /// Desencadenante simple. Sólo se admiten los del pin:
    /// <c>Daily</c> (con <see cref="TriggerAt"/>) y <c>OnLogon</c>.
    /// </summary>
    public required string Trigger { get; init; }

    /// <summary>Hora del desencadenante diario, en formato <c>HH:mm</c>.</summary>
    public string? TriggerAt { get; init; }

    /// <summary>Cuenta con la que se registra la tarea (por ejemplo <c>System</c>).</summary>
    public required string UserId { get; init; }

    /// <summary>Nivel de ejecución: <c>Highest</c> o <c>Limited</c>.</summary>
    public required string RunLevel { get; init; }

    /// <summary>Descripción que se graba en la tarea.</summary>
    public string TaskDescription { get; init; } = string.Empty;

    /// <summary>Si es true, la tarea ya existente se sobrescribe en vez de fallar.</summary>
    public bool Overwrite { get; init; }

    protected override string Fingerprint => $"{TaskPath}\\{TaskName}";
}
