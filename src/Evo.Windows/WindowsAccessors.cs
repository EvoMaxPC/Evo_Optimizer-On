using Evo.Core.System;

namespace Evo.Windows;

/// <summary>
/// Punto de entrada para obtener los accesores reales de Windows. La app
/// usará esta clase para crear el conjunto de accesores que el motor consume
/// a través de sus interfaces.
/// </summary>
public static class WindowsAccessors
{
    /// <summary>Crea el conjunto completo de accesores reales de Windows.</summary>
    /// <returns>Tupla con (registro, servicio, proceso, tareas).</returns>
    public static (IRegistryAccessor Registry, IServiceAccessor Services, IProcessAccessor Processes, ITaskAccessor Tasks) CreateReal() =>
        (
            new WindowsRegistryAccessor(),
            new WindowsServiceAccessor(),
            new WindowsProcessAccessor(),
            new UnavailableTaskAccessor()
        );
}
