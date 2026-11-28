using Evo.Core.System;

namespace Evo.App;

/// <summary>Ejecutor de comandos externos para WPF (placeholder: no disponible).</summary>
/// <remarks>
/// Las tareas programadas y comandos externos se indican como "no disponible
/// todavía" en la UI. Este placeholder devuelve error para cualquier comando.
/// </remarks>
public sealed class WpfCommandRunner : ICommandRunner
{
    public Task<CommandResult> RunCommandAsync(
        string fileName,
        IReadOnlyList<string> arguments,
        System.Threading.CancellationToken cancellationToken = default)
    {
        return Task.FromResult(new CommandResult
        {
            ExitCode = -1,
            StandardOutput = string.Empty,
            StandardError = "Comandos externos no disponibles en esta versión.",
        });
    }
}
