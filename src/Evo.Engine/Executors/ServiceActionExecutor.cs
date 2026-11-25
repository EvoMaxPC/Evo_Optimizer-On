using Evo.Core.Actions;
using Evo.Core.System;
using Evo.Engine.Execution;
using Evo.Engine.Undo;

namespace Evo.Engine.Executors;

/// <summary>
/// Cambia el arranque de un servicio o lo arranca/para, guardando el estado
/// previo completo (arranque + estado) para restaurarlo tal cual.
/// </summary>
public sealed class ServiceActionExecutor : IActionExecutor
{
    public ActionKind Kind => ActionKind.Service;

    public Task<ActionResult> ExecuteAsync(CapabilityAction action, ActionContext context)
    {
        ArgumentNullException.ThrowIfNull(action);
        ArgumentNullException.ThrowIfNull(context);

        if (action is not ServiceAction serviceAction)
        {
            return Task.FromResult(ActionResult.Fail(action.Key, "Acción no es de servicio."));
        }

        var previousStatus = context.Services.GetStatus(serviceAction.ServiceName);
        var previousStartup = context.Services.GetStartupType(serviceAction.ServiceName);

        string? target;
        bool startupChanged;
        bool statusChanged;
        try
        {
            switch (serviceAction.Operation)
            {
                case ServiceOperation.SetStartupType:
                    target = serviceAction.StartupType;
                    startupChanged = true;
                    // Cambiar el arranque NO cambia el estado de ejecución: el
                    // diario sólo devuelve el tipo previo.
                    statusChanged = false;
                    if (context.Mutates)
                    {
                        context.Services.SetStartupType(
                            serviceAction.ServiceName, ParseStartup(serviceAction.StartupType));
                    }

                    break;

                case ServiceOperation.Start:
                    target = ServiceStatus.Running.ToString();
                    startupChanged = false;
                    statusChanged = true;
                    if (context.Mutates)
                    {
                        context.Services.StartService(serviceAction.ServiceName);
                    }

                    break;

                case ServiceOperation.Stop:
                    target = ServiceStatus.Stopped.ToString();
                    startupChanged = false;
                    statusChanged = true;
                    if (context.Mutates)
                    {
                        context.Services.StopService(serviceAction.ServiceName);
                    }

                    break;

                default:
                    return Task.FromResult(ActionResult.Fail(
                        action.Key, $"Operación de servicio desconocida: {serviceAction.Operation}."));
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException and not OutOfMemoryException)
        {
            // Iniciar o detener puede fallar (dependencias, permisos, servicio que
            // ya no existe). El motor falla la acción y el coordinador revierte lo
            // ya aplicado de la capacidad: no se deja a medias.
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                $"No se pudo aplicar '{serviceAction.Operation}' sobre '{serviceAction.ServiceName}': " +
                ex.Message,
                $"status={previousStatus};startup={previousStartup}",
                Describe(serviceAction)));
        }

        var previous = $"status={previousStatus};startup={previousStartup}";

        if (context.Mutates)
        {
            context.Journal.Add(new ServiceUndoEntry
            {
                CapabilityId = context.CapabilityId,
                ActionKey = action.Key,
                Description = Describe(serviceAction),
                PreviousState = previous,
                ServiceName = serviceAction.ServiceName,
                StartupTypeChanged = startupChanged,
                PreviousStartupType = previousStartup,
                StatusChanged = statusChanged,
                PreviousStatus = previousStatus,
            });
        }

        return Task.FromResult(ActionResult.Ok(
            action.Key, previous, target, context.Mutates, Describe(serviceAction)));
    }

    public string? ReadCurrentState(CapabilityAction action, ActionContext context)
    {
        if (action is not ServiceAction serviceAction)
        {
            return null;
        }

        return $"status={context.Services.GetStatus(serviceAction.ServiceName)};" +
               $"startup={context.Services.GetStartupType(serviceAction.ServiceName)}";
    }

    /// <summary>Convierte el nombre del catálogo al enum.</summary>
    internal static ServiceStartupType ParseStartup(string? name)
    {
        if (string.IsNullOrWhiteSpace(name))
        {
            return ServiceStartupType.Manual;
        }

        return name switch
        {
            "Automatic" or "auto" or "auto-start" => ServiceStartupType.Automatic,
            "AutomaticDelayed" => ServiceStartupType.AutomaticDelayed,
            "Manual" or "manual" or "demand" => ServiceStartupType.Manual,
            "Disabled" or "disabled" => ServiceStartupType.Disabled,
            "Boot" => ServiceStartupType.Boot,
            "System" => ServiceStartupType.System,
            _ => ServiceStartupType.Unknown,
        };
    }

    private static string Describe(ServiceAction action) => action.Operation switch
    {
        ServiceOperation.SetStartupType => $"Servicio {action.ServiceName}: arranque = {action.StartupType}",
        ServiceOperation.Start => $"Servicio {action.ServiceName}: iniciar",
        ServiceOperation.Stop => $"Servicio {action.ServiceName}: detener",
        _ => $"Servicio {action.ServiceName}: {action.Operation}",
    };
}
