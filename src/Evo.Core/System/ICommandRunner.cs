namespace Evo.Core.System;

/// <summary>Resultado de un comando externo.</summary>
public sealed record CommandResult
{
    public required int ExitCode { get; init; }

    public string StandardOutput { get; init; } = string.Empty;

    public string StandardError { get; init; } = string.Empty;

    public bool Succeeded => ExitCode == 0;
}

/// <summary>Ejecución de comandos externos (sin shell implícita).</summary>
public interface ICommandRunner
{
    Task<CommandResult> RunCommandAsync(
        string fileName,
        IReadOnlyList<string> arguments,
        CancellationToken cancellationToken = default);
}
