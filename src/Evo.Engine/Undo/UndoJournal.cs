using System.Linq;
using Evo.Core.Actions;
using Evo.Core.System;
using Microsoft.Win32;

namespace Evo.Engine.Undo;

/// <summary>Resultado de deshacer una única entrada del diario.</summary>
public sealed record UndoEntryOutcome
{
    /// <summary>Clave de la acción que se deshace.</summary>
    public required string ActionKey { get; init; }

    /// <summary>Descripción legible de la acción.</summary>
    public required string Description { get; init; }

    /// <summary>Resultado del deshacer.</summary>
    public required UndoRestoreResult Result { get; init; }

    /// <summary>Mensaje de error cuando <see cref="Result"/> es <see cref="UndoRestoreResult.Failed"/>.</summary>
    public string? FailureMessage { get; init; }
}

/// <summary>Resultado de restaurar una única entrada del diario.</summary>
public enum UndoRestoreResult
{
    /// <summary>Se restauró el estado previo de verdad.</summary>
    Restored = 0,

    /// <summary>La entrada no tiene reversión real (comando, proceso informativo).</summary>
    NotReversible = 1,

    /// <summary>Se intentó restaurar pero falló; se conserva para reintento.</summary>
    Failed = 2,
}

/// <summary>Informe completo de un rollback.</summary>
public sealed record RollbackReport
{
    /// <summary>Entradas que se restauraron de verdad.</summary>
    public required IReadOnlyList<UndoEntryOutcome> Restored { get; init; }

    /// <summary>Entradas sin reversión real (no cuenta como restaurado).</summary>
    public required IReadOnlyList<UndoEntryOutcome> NotReversible { get; init; }

    /// <summary>
    /// Entradas que fallaron al restaurarse; se conservan para reintento.
    /// </summary>
    public required IReadOnlyList<UndoEntryOutcome> Failed { get; init; }

    /// <summary>True si no hubo excepciones al deshacer.</summary>
    public bool Success => Failed.Count == 0;

    /// <summary>Número de entradas restauradas.</summary>
    public int Count => Restored.Count;

    /// <summary>
    /// Errores de las entradas falladas (compatibilidad con informes previos).
    /// </summary>
    public IReadOnlyList<string> Errors =>
        Failed.Select(f => $"{f.ActionKey}: {f.FailureMessage ?? string.Empty}").ToList();

    /// <summary>True si hay al menos una entrada no reversible.</summary>
    public bool HasUnrestorable => NotReversible.Count > 0;

    /// <summary>True si no hay fallos ni entradas no reversibles.</summary>
    public bool AllReversible => Failed.Count == 0 && NotReversible.Count == 0;
}

/// <summary>Estado global del rollback de una ejecución.</summary>
public enum RollbackOutcome
{
    /// <summary>No se ejecutó ningún rollback.</summary>
    None = 0,

    /// <summary>Todas las entradas se deshicieron (sin fallos ni no reversibles).</summary>
    RolledBack = 1,

    /// <summary>Sin fallos, pero hubo entradas no reversibles.</summary>
    RolledBackWithUnrestorable = 2,

    /// <summary>Hubo fallos (al menos una entrada no se deshizo).</summary>
    PartiallyRolledBack = 3,

    /// <summary>Todas las entradas fallaron al deshacerse.</summary>
    RollbackFailed = 4,
}

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

    /// <summary>
    /// Aplica la operación inversa y devuelve el resultado explícito del
    /// deshacer.
    /// </summary>
    public abstract UndoEntryOutcome Restore(IUndoContext context);
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

    public override UndoEntryOutcome Restore(IUndoContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        if (context.DryRun)
        {
            return new UndoEntryOutcome
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.NotReversible,
            };
        }

        if (ExistedBefore)
        {
            context.Registry.SetValue(Hive, KeyPath, ValueName, PreviousValue!, PreviousKind);
        }
        else
        {
            context.Registry.DeleteValue(Hive, KeyPath, ValueName);
        }

        return new UndoEntryOutcome
        {
            ActionKey = ActionKey,
            Description = Description,
            Result = UndoRestoreResult.Restored,
        };
    }
}

/// <summary>
/// Deshacer un cambio de servicio (arranque y/o estado de ejecución).
/// </summary>
/// <remarks>
/// Desde el paso 11 cada acción declara UNA cosa: <c>SetStartupType</c> sólo el
/// tipo de inicio (<see cref="StartupTypeChanged"/>), y <c>Start</c>/<c>Stop</c>
/// sólo el estado de ejecución (<see cref="StatusChanged"/>). El deshacer aplica
/// la que cambió; el orden importa cuando cambian las dos: primero el tipo de
/// inicio (para que el servicio no quede deshabilitado al arrancarlo) y después
/// el estado.
/// </remarks>
public sealed record ServiceUndoEntry : UndoJournalEntry
{
    public required string ServiceName { get; init; }

    public required bool StartupTypeChanged { get; init; }

    public ServiceStartupType PreviousStartupType { get; init; }

    public required bool StatusChanged { get; init; }

    public ServiceStatus PreviousStatus { get; init; }

    public override UndoEntryOutcome Restore(IUndoContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        if (context.DryRun)
        {
            return new UndoEntryOutcome
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.NotReversible,
            };
        }

        // Tipo de inicio primero: si el servicio quedó deshabilitado, arrancarlo
        // antes de devolverle el arranque fallaría con ERROR_SERVICE_DISABLED.
        if (StartupTypeChanged)
        {
            context.Services.SetStartupType(ServiceName, PreviousStartupType);
        }

        if (StatusChanged && PreviousStatus == ServiceStatus.Running)
        {
            context.Services.StartService(ServiceName);
        }
        else if (StatusChanged && PreviousStatus == ServiceStatus.Stopped)
        {
            context.Services.StopService(ServiceName);
        }

        return new UndoEntryOutcome
        {
            ActionKey = ActionKey,
            Description = Description,
            Result = UndoRestoreResult.Restored,
        };
    }
}

/// <summary>
/// Deshacer el borrado de una clave completa: la recrea con sus valores, sus
/// tipos y sus subclaves tal como estaban (paso 11, ADR-0005).
/// </summary>
/// <remarks>
/// Si la clave no existía cuando se ejecutó la acción, el diario nunca se crea
/// (la acción fue un no-op) y por tanto el deshacer no crea nada. Si el borrado
/// fue un no-op registrado (<see cref="ExistedBefore"/> = false) el deshacer
/// vuelve a ser un no-op.
/// </remarks>
public sealed record RegistryDeleteKeyUndoEntry : UndoJournalEntry
{
    public required RegistryHive Hive { get; init; }

    public required string KeyPath { get; init; }

    public required bool Recursive { get; init; }

    /// <summary>True si la clave existía (la acción sí borró algo).</summary>
    public required bool ExistedBefore { get; init; }

    /// <summary>Instantánea que se recrea al deshacer.</summary>
    public required Executors.RegistryKeySnapshot Snapshot { get; init; }

    public override UndoEntryOutcome Restore(IUndoContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        if (context.DryRun)
        {
            return new UndoEntryOutcome
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.NotReversible,
            };
        }

        if (!ExistedBefore)
        {
            // No-op original: la clave no existía al borrar. Si sigue sin
            // existir, el estado es correcto (Restored). Si alguien la creó
            // entre medio, es un fallo explícito.
            if (!context.Registry.KeyExists(Hive, KeyPath))
            {
                return new UndoEntryOutcome
                {
                    ActionKey = ActionKey,
                    Description = Description,
                    Result = UndoRestoreResult.Restored,
                };
            }

            return new UndoEntryOutcome
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.Failed,
                FailureMessage = $"La clave '{Hive}\\\\{KeyPath}' ya existe y no debería: no se puede deshacer un no-op.",
            };
        }

        RestoreNode(context.Registry, Hive, Snapshot.Root);

        return new UndoEntryOutcome
        {
            ActionKey = ActionKey,
            Description = Description,
            Result = UndoRestoreResult.Restored,
        };
    }

    private static void RestoreNode(
        Evo.Core.System.IRegistryAccessor registry, RegistryHive hive, Executors.RegistryKeyNode node)
    {
        // Las claves vacías también se recrean: un borrado recursivo se deshace
        // con el árbol exacto, incluidas las ramas sin valores.
        if (registry is not Evo.Core.System.IRegistryKeyCreator creator)
        {
            throw new InvalidOperationException(
                $"El accesor de registro no implementa IRegistryKeyCreator: no se puede recrear '{node.Path}'.");
        }

        creator.EnsureKey(hive, node.Path);

        foreach (var value in node.Values)
        {
            registry.SetValue(hive, node.Path, value.Name, value.Value!, value.Kind);
        }

        foreach (var child in node.Children)
        {
            RestoreNode(registry, hive, child);
        }
    }
}

/// <summary>
/// Deshacer la creación de una clave vacía (paso 12, ADR-0005).
/// </summary>
/// <remarks>
/// Sólo se apunta cuando la clave NO existía antes; en ese caso la inversa es
/// borrarla, que devuelve el árbol exactamente a su estado anterior. Si ya
/// existía, el ejecutor no apunta nada y el deshacer no toca la clave.
/// </remarks>
public sealed record RegistryCreateKeyUndoEntry : UndoJournalEntry
{
    public required RegistryHive Hive { get; init; }

    public required string KeyPath { get; init; }

    public override UndoEntryOutcome Restore(IUndoContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        if (context.DryRun)
        {
            return new UndoEntryOutcome
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.NotReversible,
            };
        }

        // Borrado simple (sin recursión): la clave la creó esta acción y estaba
        // vacía, así que no hay nada dentro que perder. Si algo se coló dentro
        // después, el borrado no recursivo no se lo lleva por delante.
        context.Registry.DeleteKey(Hive, KeyPath, recursive: false);

        return new UndoEntryOutcome
        {
            ActionKey = ActionKey,
            Description = Description,
            Result = UndoRestoreResult.Restored,
        };
    }
}

/// <summary>
/// Deshacer la creación de una tarea programada (paso 11): se borra la tarea
/// creada o se restaura el estado previo de la que ya existente, incluida su
/// definición cuando se guardó.
/// </summary>
public sealed record TaskCreateUndoEntry : UndoJournalEntry
{
    public required string TaskPath { get; init; }

    public required string TaskName { get; init; }

    /// <summary>True si la tarea ya existía antes (se restaura, no se borra).</summary>
    public required bool ExistedBefore { get; init; }

    /// <summary>Estado previo de la tarea si ya existía.</summary>
    public required bool WasEnabled { get; init; }

    /// <summary>Definición ORIGINAL guardada al crear la tarea (null si no se pudo leer).</summary>
    public required TaskDefinition? PreviousDefinition { get; init; }

    public override UndoEntryOutcome Restore(IUndoContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        if (context.DryRun)
        {
            return new UndoEntryOutcome
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.NotReversible,
            };
        }

        if (!ExistedBefore)
        {
            context.Tasks.DeleteTask(TaskPath, TaskName);
            return new UndoEntryOutcome
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.Restored,
            };
        }

        // Sin definición guardada no se puede restaurar la tarea completa.
        if (PreviousDefinition is null)
        {
            return new UndoEntryOutcome
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.NotReversible,
                FailureMessage = "TaskDefinition no se guardo: no se puede restaurar",
            };
        }

        // Restaurar definición original (CreateTask la pone habilitada).
        context.Tasks.CreateTask(PreviousDefinition);

        // Ajustar estado de habilitación previo (preserva la definición).
        if (!WasEnabled)
        {
            context.Tasks.DisableTask(TaskPath, TaskName);
        }

        return new UndoEntryOutcome
        {
            ActionKey = ActionKey,
            Description = Description,
            Result = UndoRestoreResult.Restored,
        };
    }
}

/// <summary>Deshacer un cambio de tarea programada.</summary>
public sealed record TaskUndoEntry : UndoJournalEntry
{
    public required string TaskPath { get; init; }

    public required string TaskName { get; init; }

    public required bool WasEnabled { get; init; }

    public override UndoEntryOutcome Restore(IUndoContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        if (context.DryRun)
        {
            return new UndoEntryOutcome
            {
                ActionKey = ActionKey,
                Description = Description,
                Result = UndoRestoreResult.NotReversible,
            };
        }

        if (WasEnabled)
        {
            context.Tasks.EnableTask(TaskPath, TaskName);
        }
        else
        {
            context.Tasks.DisableTask(TaskPath, TaskName);
        }

        return new UndoEntryOutcome
        {
            ActionKey = ActionKey,
            Description = Description,
            Result = UndoRestoreResult.Restored,
        };
    }
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

    /// <summary>
    /// Punto de restauración al que queda vinculado este diario. El motor lo
    /// rellena antes de la primera mutación cuando el contrato lo exige
    /// (ADR-0004): el punto y las entradas se guardan juntos, no en dos sitios
    /// que puedan desincronizarse.
    /// </summary>
    public string? RestorePointId { get; set; }

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
    /// medias si se puede evitar. Las entradas que fallan se conservan en el
    /// diario para que un segundo <see cref="RollbackAsync"/> las reintente;
    /// las restauradas y las no reversibles se descardan.
    /// </summary>
    public Task<RollbackReport> RollbackAsync(IUndoContext context)
    {
        ArgumentNullException.ThrowIfNull(context);

        if (context.DryRun)
        {
            // En DryRun no se procesa ni se toca ninguna entrada: informe vacío
            // (Success=true, Count=0), sin NotReversible fabricado.
            return Task.FromResult(new RollbackReport
            {
                Restored = [],
                NotReversible = [],
                Failed = [],
            });
        }

        var restored = new List<UndoEntryOutcome>();
        var notReversible = new List<UndoEntryOutcome>();
        var failed = new List<UndoEntryOutcome>();
        var failedIndices = new HashSet<int>();

        for (var index = _entries.Count - 1; index >= 0; index--)
        {
            var entry = _entries[index];
            UndoEntryOutcome outcome;
            try
            {
                outcome = entry.Restore(context);
            }
            catch (Exception ex) when (ex is not OutOfMemoryException)
            {
                outcome = new UndoEntryOutcome
                {
                    ActionKey = entry.ActionKey,
                    Description = entry.Description,
                    Result = UndoRestoreResult.Failed,
                    FailureMessage = ex.Message,
                };
            }

            switch (outcome.Result)
            {
                case UndoRestoreResult.Restored:
                    restored.Add(outcome);
                    break;
                case UndoRestoreResult.NotReversible:
                    notReversible.Add(outcome);
                    break;
                case UndoRestoreResult.Failed:
                    failed.Add(outcome);
                    failedIndices.Add(index);
                    break;
            }
        }

        if (!context.DryRun)
        {
            // Se conservan SOLO las entradas que fallaron, identificadas por
            // ÍNDICE (no por ActionKey): si dos entradas distintas comparten el
            // mismo ActionKey y una falló mientras otra se restauró, la
            // restaurada se descarta y la fallida permanece en el diario para
            // que un segundo RollbackAsync la reintente.
            var soloFallidas = _entries
                .Where((entry, index) => failedIndices.Contains(index))
                .ToList();
            _entries.Clear();
            _entries.AddRange(soloFallidas);
        }

        return Task.FromResult(new RollbackReport
        {
            Restored = restored,
            NotReversible = notReversible,
            Failed = failed,
        });
    }

    /// <summary>Orden de aplicación de las claves, para aserciones de tests.</summary>
    public IReadOnlyList<string> AppliedOrder() => _entries.Select(e => e.ActionKey).ToList();
}
