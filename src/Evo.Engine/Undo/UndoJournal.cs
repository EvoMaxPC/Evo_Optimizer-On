using Evo.Core.Actions;
using Evo.Core.System;
using Microsoft.Win32;

namespace Evo.Engine.Undo;

/// <summary>
/// Entrada del diario de deshacer: la operación inversa exacta de un cambio.
/// </summary>
public abstract record UndoJournalEntry
{
    /// <summary>Capacidad que originó el cambio.</summary>
    public required string CapabilityId { get; init; }

    /// <summary>Clave de la acción original.</summary>
    public required string ActionKey { get; init; }

    /// <summary>Descripción legible.</summary>
    public required string Description { get; init; }

    /// <summary>Estado previo serializado (auditoría).</summary>
    public required string? PreviousState { get; init; }

    /// <summary>Aplica la operación inversa.</summary>
    public abstract void Restore(IUndoContext context);
}

/// <summary>Deshacer una escritura o borrado de registro.</summary>
public sealed record RegistryUndoEntry : UndoJournalEntry
{
    public required RegistryHive Hive { get; init; }

    public required string KeyPath { get; init; }

    public required string ValueName { get; init; }

    /// <summary>True si el valor existía antes del cambio.</summary>
    public required bool ExistedBefore { get; init; }

    public object? PreviousValue { get; init; }

    public RegistryValueKind PreviousKind { get; init; } = RegistryValueKind.Unknown;

    public override void Restore(IUndoContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        if (context.DryRun)
        {
            return;
        }

        if (ExistedBefore)
        {
            context.Registry.SetValue(Hive, KeyPath, ValueName, PreviousValue!, PreviousKind);
        }
        else
        {
            context.Registry.DeleteValue(Hive, KeyPath, ValueName);
        }
    }
}

/// <summary>Deshacer un cambio de servicio (arranque o estado).</summary>
public sealed record ServiceUndoEntry : UndoJournalEntry
{
    public required string ServiceName { get; init; }

    public required bool StartupTypeChanged { get; init; }

    public ServiceStartupType PreviousStartupType { get; init; }

    public required bool StatusChanged { get; init; }

    public ServiceStatus PreviousStatus { get; init; }

    public override void Restore(IUndoContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        if (context.DryRun)
        {
            return;
        }

        if (StartupTypeChanged)
        {
            context.Services.SetStartupType(ServiceName, PreviousStartupType);
        }

        if (StatusChanged)
        {
            if (PreviousStatus == ServiceStatus.Running)
            {
                context.Services.StartService(ServiceName);
            }
            else if (PreviousStatus == ServiceStatus.Stopped)
            {
                context.Services.StopService(ServiceName);
            }
        }
    }
}

/// <summary>Deshacer un cambio de tarea programada.</summary>
public sealed record TaskUndoEntry : UndoJournalEntry
{
    public required string TaskPath { get; init; }

    public required string TaskName { get; init; }

    public required bool WasEnabled { get; init; }

    public override void Restore(IUndoContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        if (context.DryRun)
        {
            return;
        }

        if (WasEnabled)
        {
            context.Tasks.EnableTask(TaskPath, TaskName);
        }
        else
        {
            context.Tasks.DisableTask(TaskPath, TaskName);
        }
    }
}

/// <summary>Resultado de un rollback.</summary>
public sealed record RollbackResult
{
    public required bool Success { get; init; }

    public required IReadOnlyList<string> Restored { get; init; }

    public required IReadOnlyList<string> Errors { get; init; }

    public int Count => Restored.Count;
}

/// <summary>
/// Diario de deshacer. Cada entrada es la operación inversa de un cambio que
/// sí se aplicó; <see cref="RollbackAsync"/> las ejecuta en orden LIFO.
/// </summary>
public sealed class UndoJournal
{
    private readonly List<UndoJournalEntry> _entries = [];

    /// <summary>Entradas en orden de aplicación (el rollback las invierte).</summary>
    public IReadOnlyList<UndoJournalEntry> Entries => _entries;

    public int Count => _entries.Count;

    public bool IsEmpty => _entries.Count == 0;

    /// <summary>Añade una entrada (atómico: o se añade entera o no se añade).</summary>
    public void Add(UndoJournalEntry entry)
    {
        ArgumentNullException.ThrowIfNull(entry);
        _entries.Add(entry);
    }

    /// <summary>Vacía el diario (tras un commit definitivo).</summary>
    public void Clear() => _entries.Clear();

    /// <summary>
    /// Deshace todos los cambios en orden LIFO. Si una entrada falla, se anota
    /// el error y se continúa con las anteriores: nunca se deja el sistema a
    /// medias si se puede evitar.
    /// </summary>
    public Task<RollbackResult> RollbackAsync(IUndoContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        var restored = new List<string>();
        var errors = new List<string>();

        for (var index = _entries.Count - 1; index >= 0; index--)
        {
            var entry = _entries[index];
            try
            {
                entry.Restore(context);
                restored.Add(entry.ActionKey);
            }
            catch (Exception ex) when (ex is not OutOfMemoryException)
            {
                errors.Add($"{entry.ActionKey}: {ex.Message}");
            }
        }

        if (!context.DryRun)
        {
            _entries.Clear();
        }

        return Task.FromResult(new RollbackResult
        {
            Success = errors.Count == 0,
            Restored = restored,
            Errors = errors,
        });
    }

    /// <summary>Orden de aplicación de las claves, para aserciones de tests.</summary>
    public IReadOnlyList<string> AppliedOrder() => _entries.Select(e => e.ActionKey).ToList();
}
