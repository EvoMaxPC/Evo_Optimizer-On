using Evo.Core.Actions;
using Evo.Engine.Execution;
using Evo.Engine.Undo;

namespace Evo.Engine.Executors;

/// <summary>
/// Ejecuta comandos externos vía <see cref="Evo.Core.System.ICommandRunner"/>.
/// No es reversible: se anota en el diario como no restaurable.
/// </summary>
public sealed class CommandActionExecutor : IActionExecutor
{
    public ActionKind Kind => ActionKind.Command;

    public async Task<ActionResult> ExecuteAsync(CapabilityAction action, ActionContext context)
    {
        ArgumentNullException.ThrowIfNull(action);
        ArgumentNullException.ThrowIfNull(context);

        if (action is not CommandAction commandAction)
        {
            return ActionResult.Fail(action.Key, "Acción no es de comando.");
        }

        if (!context.Mutates)
        {
            return ActionResult.Ok(
                action.Key, null, $"would-run: {commandAction.CommandLine}", false,
                Describe(commandAction));
        }

        var result = await context.Commands
            .RunCommandAsync(commandAction.FileName, commandAction.Arguments)
            .ConfigureAwait(false);

        var allowed = commandAction.IgnoreExitCode
                      || commandAction.AllowedExitCodes.Count == 0
                      || commandAction.AllowedExitCodes.Contains(result.ExitCode);

        if (!allowed)
        {
            var detail = string.IsNullOrWhiteSpace(result.StandardError)
                ? result.StandardOutput
                : result.StandardError;
            return ActionResult.Fail(
                action.Key,
                $"El comando '{commandAction.CommandLine}' devolvió {result.ExitCode}: {detail}".Trim(),
                description: Describe(commandAction));
        }

        context.Journal.Add(new CommandUndoEntry
        {
            CapabilityId = context.CapabilityId,
            ActionKey = action.Key,
            Description = Describe(commandAction),
            PreviousState = null,
        });

        return ActionResult.Ok(
            action.Key, null, $"exit={result.ExitCode}", true, Describe(commandAction));
    }

    public string? ReadCurrentState(CapabilityAction action, ActionContext context) => null;

    private static string Describe(CommandAction action) => $"Comando: {action.CommandLine}";
}

/// <summary>Entrada de diario para comandos: no hay operación inversa.</summary>
public sealed record CommandUndoEntry : UndoJournalEntry
{
    public override void Restore(IUndoContext context)
    {
        // Un comando arbitrario no tiene inversa declarada; el rollback no
        // inventa una. Documentado como limitación en docs/reports/paso7.md.
        ArgumentNullException.ThrowIfNull(context);
    }
}
