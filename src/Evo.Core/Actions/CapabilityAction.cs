using System.Text.Json.Serialization;

namespace Evo.Core.Actions;

/// <summary>
/// Tipo de acción atómica de una capacidad. El discriminante vive en el JSON
/// (<c>"type": "registry"</c>) y se llama <c>Kind</c> en C# para no chocar con
/// el tipo <c>System.Type</c>.
/// </summary>
public enum ActionKind
{
    Registry = 0,
    Service = 1,
    Task = 2,
    Process = 3,
    Command = 4,
}

/// <summary>Acción atómica y reversible declarada por una capacidad.</summary>
[JsonPolymorphic(TypeDiscriminatorPropertyName = "type")]
[JsonDerivedType(typeof(RegistryAction), "registry")]
[JsonDerivedType(typeof(ServiceAction), "service")]
[JsonDerivedType(typeof(TaskAction), "task")]
[JsonDerivedType(typeof(ProcessAction), "process")]
[JsonDerivedType(typeof(CommandAction), "command")]
public abstract record CapabilityAction
{
    /// <summary>Orden de aplicación dentro del plan (menor primero).</summary>
    public int Order { get; init; }

    /// <summary>Descripción legible para el usuario y el diario.</summary>
    public string Description { get; init; } = string.Empty;

    /// <summary>Tipo de acción.</summary>
    [JsonIgnore]
    public abstract ActionKind Kind { get; }

    /// <summary>Clave estable para el diario de deshacer.</summary>
    [JsonIgnore]
    public string Key => $"{Kind}:{Order}:{Fingerprint}";

    /// <summary>Identidad específica del tipo, usada en la clave del diario.</summary>
    [JsonIgnore]
    protected abstract string Fingerprint { get; }
}
