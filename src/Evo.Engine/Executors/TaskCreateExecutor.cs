using Evo.Core.Actions;
using Evo.Core.System;
using Evo.Engine.Execution;
using Evo.Engine.Undo;

namespace Evo.Engine.Executors;

/// <summary>
/// Crea una tarea programada y deja en el diario su inversa exacta (paso 11).
/// </summary>
/// <remarks>
/// <list type="bullet">
///   <item>Si la tarea NO existía: el deshacer la borra.</item>
///   <item>Si existía y <see cref="TaskCreateAction.Overwrite"/> es false: falla
///   sin tocar nada (no se pisa una tarea ajena sin decirlo).</item>
///   <item>Si existía y <c>Overwrite</c> es true: se captura su estado previo
///   (habilitada/deshabilitada) y el deshacer lo restaura.</item>
/// </list>
/// </remarks>
public sealed class TaskCreateExecutor : IActionExecutor
{
    public ActionKind Kind => ActionKind.TaskCreate;

    public Task<ActionResult> ExecuteAsync(CapabilityAction action, ActionContext context)
    {
        ArgumentNullException.ThrowIfNull(action);
        ArgumentNullException.ThrowIfNull(context);

        if (action is not TaskCreateAction createAction)
        {
            return Task.FromResult(ActionResult.Fail(action.Key, "Acción no es de creación de tarea."));
        }

        if (string.IsNullOrWhiteSpace(createAction.Execute))
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key, "La definición de la tarea no declara 'execute'."));
        }

        if (createAction.Trigger is not ("Daily" or "OnLogon"))
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                $"Desencadenante '{createAction.Trigger}' no soportado: sólo Daily y OnLogon."));
        }

        if (createAction.Trigger == "Daily" && string.IsNullOrWhiteSpace(createAction.TriggerAt))
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key, "Un desencadenante Daily exige 'triggerAt' (HH:mm)."));
        }

        var existed = context.Tasks.Exists(createAction.TaskPath, createAction.TaskName);
        var wasEnabled = existed && context.Tasks.IsTaskEnabled(
            createAction.TaskPath, createAction.TaskName);
        var previous = existed ? (wasEnabled ? "Enabled" : "Disabled") : "absent";

        if (existed && !createAction.Overwrite)
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                $"La tarea '{createAction.TaskPath}\\{createAction.TaskName}' ya existe y la " +
                "acción no declara overwrite: no se pisa.",
                previous,
                Describe(createAction)));
        }

        // Si la tarea existe y se va a sobrescribir, leer la definición ORIGINAL
        // ANTES de reemplazar. Si no se puede leer, fail-closed: no mutar.
        TaskDefinition? previousDefinition = null;
        if (existed && createAction.Overwrite)
        {
            try
            {
                previousDefinition = context.Tasks.GetDefinition(
                    createAction.TaskPath, createAction.TaskName);
            }
            catch (Exception ex) when (ex is not OperationCanceledException and not OutOfMemoryException)
            {
                return Task.FromResult(ActionResult.Fail(
                    action.Key,
                    $"No se pudo leer la definición previa de '{createAction.TaskPath}\\\\{createAction.TaskName}': " +
                    ex.Message + ". No se pisa la tarea (fail-closed).",
                    previous,
                    Describe(createAction)));
            }

            if (previousDefinition is null)
            {
                return Task.FromResult(ActionResult.Fail(
                    action.Key,
                    $"La definición previa de '{createAction.TaskPath}\\\\{createAction.TaskName}' no es legible: " +
                    "no se pisa la tarea (fail-closed).",
                    previous,
                    Describe(createAction)));
            }
        }

        if (context.Mutates)
        {
            try
            {
                context.Tasks.CreateTask(new TaskDefinition
                {
                    TaskPath = createAction.TaskPath,
                    TaskName = createAction.TaskName,
                    Execute = createAction.Execute,
                    Arguments = createAction.Arguments,
                    Trigger = createAction.Trigger,
                    TriggerAt = createAction.TriggerAt,
                    UserId = createAction.UserId,
                    RunLevel = createAction.RunLevel,
                    Description = createAction.TaskDescription,
                });
            }
            catch (Exception ex) when (ex is not OperationCanceledException and not OutOfMemoryException)
            {
                // La tarea NO se creó: no se añade una entrada al diario que
                // prometa borrar algo que no existe.
                return Task.FromResult(ActionResult.Fail(
                    action.Key,
                    $"No se pudo crear la tarea '{createAction.TaskPath}\\{createAction.TaskName}': " +
                    ex.Message,
                    previous,
                    Describe(createAction)));
            }

            context.Journal.Add(new TaskCreateUndoEntry
            {
                CapabilityId = context.CapabilityId,
                ActionKey = action.Key,
                Description = Describe(createAction),
                PreviousState = previous,
                TaskPath = createAction.TaskPath,
                TaskName = createAction.TaskName,
                ExistedBefore = existed,
                WasEnabled = wasEnabled,
                PreviousDefinition = previousDefinition,
            });
        }

        return Task.FromResult(ActionResult.Ok(
            action.Key, previous, "Enabled", context.Mutates, Describe(createAction)));
    }

    public string? ReadCurrentState(CapabilityAction action, ActionContext context)
    {
        if (action is not TaskCreateAction createAction)
        {
            return null;
        }

        if (!context.Tasks.Exists(createAction.TaskPath, createAction.TaskName))
        {
            return "absent";
        }

        return context.Tasks.IsTaskEnabled(createAction.TaskPath, createAction.TaskName)
            ? "Enabled"
            : "Disabled";
    }

    private static string Describe(TaskCreateAction action) =>
        $"Crear tarea {action.TaskPath}\\{action.TaskName}: {action.Execute} {action.Arguments}".Trim();
}
