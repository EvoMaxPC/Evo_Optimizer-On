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
