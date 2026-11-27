using Evo.Core.Actions;
using Evo.Engine.Execution;
using Evo.Engine.Undo;

namespace Evo.Engine.Executors;

/// <summary>
/// Detiene procesos requeridos. No se registra en el diario: los procesos no se
/// pueden "des-terminar", así que el rollback lo informa como no reversible.
/// </summary>
public sealed class ProcessActionExecutor : IActionExecutor
{
    public ActionKind Kind => ActionKind.Process;

    public Task<ActionResult> ExecuteAsync(CapabilityAction action, ActionContext context)
    {
        ArgumentNullException.ThrowIfNull(action);
        ArgumentNullException.ThrowIfNull(context);

        if (action is not ProcessAction processAction)
        {
            return Task.FromResult(ActionResult.Fail(action.Key, "Acción no es de proceso."));
        }

        var running = context.Processes.IsRunning(processAction.ProcessName);
        var previous = running ? "Running" : "Stopped";

        if (!running)
        {
            return Task.FromResult(ActionResult.Skip(
                action.Key,
                $"El proceso '{processAction.ProcessName}' no estaba en ejecución.",
                Describe(processAction)));
        }

        if (!context.Mutates)
        {
            // DryRun / Audit: no muta, solo informa.
            return Task.FromResult(ActionResult.Ok(
                action.Key, previous, "Stopped", false, Describe(processAction)));
        }

        if (!processAction.Terminate)
        {
            // La acción no solicita terminarlo: no muta, no hay journal,
            // se reporta como Skipped (applied=false).
            return Task.FromResult(ActionResult.Skip(
                action.Key,
                $"El proceso '{processAction.ProcessName}' está activo; la acción no solicita terminarlo.",
                Describe(processAction)));
        }

        // Terminate=true: terminar y verificar que realmente se detuvo.
        if (!context.Processes.TerminateProcess(processAction.ProcessName))
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                $"El proceso '{processAction.ProcessName}' no se pudo detener.",
                previous,
                Describe(processAction)));
        }

        if (context.Processes.IsRunning(processAction.ProcessName))
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                $"El proceso '{processAction.ProcessName}' no se pudo detener.",
                previous,
                Describe(processAction)));
        }

        // Se registra en el diario con estado previo "Running" pero el
        // rollback de procesos es informativo (no se reinician solos).
        context.Journal.Add(new ProcessUndoEntry
        {
            CapabilityId = context.CapabilityId,
            ActionKey = action.Key,
            Description = Describe(processAction),
            PreviousState = previous,
            ProcessName = processAction.ProcessName,
        });

        return Task.FromResult(ActionResult.Ok(
            action.Key, previous, "Stopped", true, Describe(processAction)));
    }

    public string? ReadCurrentState(CapabilityAction action, ActionContext context)
    {
        if (action is not ProcessAction processAction)
        {
            return null;
        }

        return context.Processes.IsRunning(processAction.ProcessName) ? "Running" : "Stopped";
    }

    private static string Describe(ProcessAction action) =>
        $"Proceso {action.ProcessName}: {(action.Terminate ? "detener" : "debe estar parado")}";
}

/// <summary>Entrada de diario para procesos: el rollback no reinicia nada.</summary>
public sealed record ProcessUndoEntry : UndoJournalEntry
{
    public required string ProcessName { get; init; }

    public override UndoEntryOutcome Restore(IUndoContext context)
    {
        // Un proceso no se puede "des-terminar": el rollback deja constancia y
        // no muta el sistema. Es no reversible por definición. Documentado como
        // limitación en docs/reports/paso7.md.
        ArgumentNullException.ThrowIfNull(context);

        return new UndoEntryOutcome
        {
            ActionKey = ActionKey,
            Description = Description,
            Result = UndoRestoreResult.NotReversible,
        };
    }
}
