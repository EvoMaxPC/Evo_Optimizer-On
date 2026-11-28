using Evo.Core.Actions;
using Evo.Core.System;
using Evo.Engine.Execution;
using Evo.Engine.Undo;
using Microsoft.Win32;

namespace Evo.Engine.Executors;

/// <summary>
/// Crea una clave VACÍA del registro con deshacer exacto (paso 12, ADR-0005).
/// </summary>
/// <remarks>
/// Orden, sólo en <see cref="ExecutionMode.Execute"/> cuando hay algo que crear:
/// <list type="number">
///   <item>si el accesor no implementa <see cref="IRegistryKeyCreator"/> → falla
///   sin tocar nada (fail-closed: no se promete un deshacer que no se sabe hacer);</item>
///   <item>si la clave YA existe → no-op registrado, sin mutar y sin entrada de
///   diario: crear algo que existe no es un cambio y borrarlo al deshacer
///   destruiría estado previo;</item>
///   <item>si no existe → se crea y el diario apunta <c>ExistedBefore=false</c>,
///   de modo que el deshacer la borra (y sólo entonces).</item>
/// </list>
/// En DryRun y Audit no se muta nada: se informa de lo que se crearía.
/// </remarks>
public sealed class RegistryCreateKeyExecutor : IActionExecutor
{
    public ActionKind Kind => ActionKind.RegistryCreateKey;

    public Task<ActionResult> ExecuteAsync(CapabilityAction action, ActionContext context)
    {
        ArgumentNullException.ThrowIfNull(action);
        ArgumentNullException.ThrowIfNull(context);

        if (action is not RegistryCreateKeyAction createAction)
        {
            return Task.FromResult(ActionResult.Fail(action.Key, "Acción no es de creación de clave."));
        }

        var hive = RegistryActionExecutor.Map(createAction.Hive);
        var describir = Describe(createAction);

        if (!context.Mutates)
        {
            var exists = context.Registry.KeyExists(hive, createAction.KeyPath);
            return Task.FromResult(ActionResult.Ok(
                action.Key,
                exists ? "present" : "absent",
                exists ? "would-create: ya existía (no-op)" : "would-create",
                false,
                describir));
        }

        // Se mide ANTES de crear: de eso depende el deshacer.
        if (context.Registry.KeyExists(hive, createAction.KeyPath))
        {
            return Task.FromResult(ActionResult.Ok(
                action.Key, "present", "present", false, describir));
        }

        if (context.Registry is not IRegistryKeyCreator creator)
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                "El accesor de registro no sabe crear claves: no se crea nada " +
                "(fail-closed, el deshacer no podría borrarla).",
                "absent",
                describir));
        }

        creator.EnsureKey(hive, createAction.KeyPath);

        // Sólo se apunta el deshacer si la clave NO existía, que es el único caso
        // en el que borrarla devuelve el sistema a su estado anterior.
        if (!context.Registry.KeyExists(hive, createAction.KeyPath))
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                $"El accesor no creó la clave '{createAction.Hive}\\{createAction.KeyPath}'.",
                "absent",
                describir));
        }

        context.Journal.Add(new RegistryCreateKeyUndoEntry
        {
            CapabilityId = context.CapabilityId,
            ActionKey = action.Key,
            Description = describir,
            PreviousState = "absent",
            Hive = hive,
            KeyPath = createAction.KeyPath,
        });

        return Task.FromResult(ActionResult.Ok(
            action.Key, "absent", "created", true, describir));
    }

    public string? ReadCurrentState(CapabilityAction action, ActionContext context)
    {
        if (action is not RegistryCreateKeyAction createAction)
        {
            return null;
        }

        var hive = RegistryActionExecutor.Map(createAction.Hive);
        return context.Registry.KeyExists(hive, createAction.KeyPath) ? "present" : "absent";
    }

    private static string Describe(RegistryCreateKeyAction action) =>
        $"Crear clave {action.Hive}\\{action.KeyPath}";
}
