using Evo.Core.Actions;
using Evo.Engine.Execution;
using Evo.Engine.Undo;

namespace Evo.Engine.Executors;

/// <summary>Habilita o deshabilita una tarea programada guardando su estado.</summary>
public sealed class TaskActionExecutor : IActionExecutor
{
    public ActionKind Kind => ActionKind.Task;

    public Task<ActionResult> ExecuteAsync(CapabilityAction action, ActionContext context)
    {
        ArgumentNullException.ThrowIfNull(action);
        ArgumentNullException.ThrowIfNull(context);

        if (action is not TaskAction taskAction)
        {
            return Task.FromResult(ActionResult.Fail(action.Key, "Acción no es de tarea."));
        }

        if (!context.Tasks.Exists(taskAction.TaskPath, taskAction.TaskName))
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                $"La tarea '{taskAction.TaskPath}\\{taskAction.TaskName}' no existe."));
        }

        var wasEnabled = context.Tasks.IsTaskEnabled(taskAction.TaskPath, taskAction.TaskName);
        var previous = wasEnabled ? "Enabled" : "Disabled";

        if (context.Mutates)
        {
            if (taskAction.Enabled)
            {
                context.Tasks.EnableTask(taskAction.TaskPath, taskAction.TaskName);
            }
            else
            {
                context.Tasks.DisableTask(taskAction.TaskPath, taskAction.TaskName);
            }

            context.Journal.Add(new TaskUndoEntry
            {
                CapabilityId = context.CapabilityId,
                ActionKey = action.Key,
                Description = Describe(taskAction),
                PreviousState = previous,
                TaskPath = taskAction.TaskPath,
                TaskName = taskAction.TaskName,
                WasEnabled = wasEnabled,
            });
        }

        return Task.FromResult(ActionResult.Ok(
            action.Key,
            previous,
            taskAction.Enabled ? "Enabled" : "Disabled",
            context.Mutates,
            Describe(taskAction)));
    }

    public string? ReadCurrentState(CapabilityAction action, ActionContext context)
    {
        if (action is not TaskAction taskAction)
        {
            return null;
        }

        if (!context.Tasks.Exists(taskAction.TaskPath, taskAction.TaskName))
        {
            return null;
        }

        return context.Tasks.IsTaskEnabled(taskAction.TaskPath, taskAction.TaskName)
            ? "Enabled"
            : "Disabled";
    }

    private static string Describe(TaskAction action) =>
        $"Tarea {action.TaskPath}\\{action.TaskName}: {(action.Enabled ? "habilitar" : "deshabilitar")}";
}
