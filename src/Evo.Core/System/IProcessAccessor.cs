namespace Evo.Core.System;

/// <summary>Inspección y control de procesos.</summary>
public interface IProcessAccessor
{
    bool IsRunning(string processName);

    /// <summary>Termina el proceso. Devuelve true si lo encontró y lo cerró.</summary>
    bool TerminateProcess(string processName);

    /// <summary>Arranca un proceso y devuelve su id (-1 si no arrancó).</summary>
    int StartProcess(string fileName, IReadOnlyList<string> arguments);
}
