using Evo.Core.System;

namespace Evo.Engine.Undo;

/// <summary>
/// Acceso al sistema durante un rollback. Solo expone las interfaces de
/// <c>Evo.Core</c>: el diario no conoce implementaciones concretas (REQ-004).
/// </summary>
public interface IUndoContext
{
    IRegistryAccessor Registry { get; }

    IServiceAccessor Services { get; }

    ITaskAccessor Tasks { get; }

    IProcessAccessor Processes { get; }

    ICommandRunner Commands { get; }

    /// <summary>Si es true, el rollback no muta: solo informa.</summary>
    bool DryRun { get; }
}

/// <summary>Implementación simple de <see cref="IUndoContext"/>.</summary>
public sealed class UndoContext : IUndoContext
{
    public UndoContext(
        IRegistryAccessor registry,
        IServiceAccessor services,
        ITaskAccessor tasks,
        IProcessAccessor processes,
        ICommandRunner commands,
        bool dryRun = false)
    {
        Registry = registry ?? throw new ArgumentNullException(nameof(registry));
        Services = services ?? throw new ArgumentNullException(nameof(services));
        Tasks = tasks ?? throw new ArgumentNullException(nameof(tasks));
        Processes = processes ?? throw new ArgumentNullException(nameof(processes));
        Commands = commands ?? throw new ArgumentNullException(nameof(commands));
        DryRun = dryRun;
    }

    public IRegistryAccessor Registry { get; }

    public IServiceAccessor Services { get; }

    public ITaskAccessor Tasks { get; }

    public IProcessAccessor Processes { get; }

    public ICommandRunner Commands { get; }

    public bool DryRun { get; }
}
