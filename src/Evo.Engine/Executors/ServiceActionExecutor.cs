using System.Runtime.InteropServices;
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
        bool omitido;
        string omitidoReason = string.Empty;
        try
        {
            switch (serviceAction.Operation)
            {
                case ServiceOperation.SetStartupType:
                    target = serviceAction.StartupType;
                    startupChanged = true;
                    statusChanged = false;
                    // Idempotencia: si el tipo de inicio ya es el destino, no hay
                    // nada que hacer (Omitido, sin journal).
                    if (previousStartup == ParseStartup(serviceAction.StartupType))
                    {
                        omitido = true;
                        omitidoReason = $"el servicio '{serviceAction.ServiceName}' ya tiene el tipo de inicio '{serviceAction.StartupType}'.";
                        break;
                    }
                    // Servicio inexistente: no se puede cambiar el arranque de algo
                    // que no está en este equipo.
                    if (previousStatus == ServiceStatus.Unknown && previousStartup == ServiceStartupType.Unknown)
                    {
                        omitido = true;
                        omitidoReason = $"el servicio '{serviceAction.ServiceName}' no existe en este equipo.";
                        break;
                    }
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
                    // Idempotencia: si ya está corriendo, no hay nada que hacer.
                    if (previousStatus == ServiceStatus.Running)
                    {
                        omitido = true;
                        omitidoReason = $"el servicio '{serviceAction.ServiceName}' ya está en ejecución.";
                        break;
                    }
                    // Servicio inexistente: no se puede arrancar algo que no está.
                    if (previousStatus == ServiceStatus.Unknown)
                    {
                        omitido = true;
                        omitidoReason = $"el servicio '{serviceAction.ServiceName}' no existe en este equipo.";
                        break;
                    }
                    if (context.Mutates)
                    {
                        context.Services.StartService(serviceAction.ServiceName);
                    }

                    break;

                case ServiceOperation.Stop:
                    target = ServiceStatus.Stopped.ToString();
                    startupChanged = false;
                    statusChanged = true;
                    // Idempotencia: si ya está detenido (o parándose), no hay nada que hacer.
                    if (previousStatus == ServiceStatus.Stopped ||
                        previousStatus == ServiceStatus.StopPending)
                    {
                        omitido = true;
                        omitidoReason = $"el servicio '{serviceAction.ServiceName}' ya estaba detenido.";
                        break;
                    }
                    // Servicio inexistente: no se puede detener algo que no está.
                    if (previousStatus == ServiceStatus.Unknown)
                    {
                        omitido = true;
                        omitidoReason = $"el servicio '{serviceAction.ServiceName}' no existe en este equipo.";
                        break;
                    }
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
            // Incluye la cadena completa de excepciones (InnerException) y el código
            // Win32 si existe (HRESULT).
            var causa = ex.Message;
            var inner = ex.InnerException;
            while (inner is not null)
            {
                causa += $"; causa: {inner.Message}";
                inner = inner.InnerException;
            }
            var win32 = Win32ErrorCode(ex);
            if (!string.IsNullOrEmpty(win32))
                causa += $" (Win32 {win32})";

            return Task.FromResult(ActionResult.Fail(
                action.Key,
                $"No se pudo aplicar '{serviceAction.Operation}' sobre '{serviceAction.ServiceName}': {causa}",
                $"status={previousStatus};startup={previousStartup}",
                Describe(serviceAction)));
        }

        if (omitido)
        {
            return Task.FromResult(ActionResult.Skip(
                action.Key, omitidoReason, Describe(serviceAction),
                $"status={previousStatus};startup={previousStartup}"));
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

    /// <summary>Código Win32 (HRESULT bajo) de la excepción, si existe.</summary>
    private static string? Win32ErrorCode(Exception ex)
    {
        try
        {
            var hr = Marshal.GetHRForException(ex);
            // FACILITY_WIN32 = 7; el código Win32 está en los 16 bits bajos.
            if ((hr & 0xFFFF0000) == (7 << 16))
                return ((hr & 0x0000FFFF)).ToString();
        }
        catch
        {
            // Si no se puede obtener el HR, se ignora.
        }

        return null;
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
