using Evo.Core.System;
using System.Diagnostics;

namespace Evo.Windows;

/// <summary>
/// Acceso real a procesos de Windows mediante <see cref="System.Diagnostics.Process"/>.
/// Lista y consulta procesos por nombre, y termina verificando que ya no existan.
/// </summary>
public sealed class WindowsProcessAccessor : IProcessAccessor
{
    /// <summary>True si hay al menos un proceso con ese nombre en ejecución.</summary>
    /// <param name="processName">Nombre del proceso (sin extensión, p. ej. "notepad").</param>
    /// <returns>true si al menos uno está corriendo.</returns>
    public bool IsRunning(string processName)
    {
        return Process.GetProcessesByName(processName).Length > 0;
    }

    /// <summary>Termina todos los procesos con ese nombre y verifica que ya no existan.</summary>
    /// <param name="processName">Nombre del proceso.</param>
    /// <returns>true si se encontró y cerró al menos uno.</returns>
    public bool TerminateProcess(string processName)
    {
        var processes = Process.GetProcessesByName(processName);
        if (processes.Length == 0) return false;

        foreach (var process in processes)
        {
            try
            {
                process.Kill();
            }
            catch
            {
                // El proceso puede haber terminado entre el listado y el Kill.
            }
        }

        // Verificar que ya no estén vivos.
        var stillAlive = Process.GetProcessesByName(processName).Length > 0;
        if (stillAlive)
        {
            throw new InvalidOperationException($"El proceso '{processName}' sigue en ejecución tras intentar terminarlo.");
        }

        return true;
    }

    /// <summary>Arranca un proceso y devuelve su id.</summary>
    /// <param name="fileName">Ruta o nombre del ejecutable.</param>
    /// <param name="arguments">Argumentos de línea de comandos.</param>
    /// <returns>Id del proceso, o -1 si no arrancó.</returns>
    public int StartProcess(string fileName, IReadOnlyList<string> arguments)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = string.Join(" ", arguments),
                UseShellExecute = false,
            };
            var process = Process.Start(psi);
            return process?.Id ?? -1;
        }
        catch
        {
            return -1;
        }
    }
}
