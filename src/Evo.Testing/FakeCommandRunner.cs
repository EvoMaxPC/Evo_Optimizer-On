using Evo.Core.System;

namespace Evo.Testing;

/// <summary>Comando simulado registrado por el fake.</summary>
public sealed record RecordedCommand(string FileName, IReadOnlyList<string> Arguments)
{
    public string CommandLine => Arguments.Count == 0
        ? FileName
        : $"{FileName} {string.Join(' ', Arguments)}";
}

/// <summary>
/// Ejecutor de comandos simulado: registra las llamadas y permite fijar
/// salidas y códigos de retorno por comando o por defecto.
/// </summary>
public sealed class FakeCommandRunner : ICommandRunner
{
    private readonly Dictionary<string, CommandResult> _responses = new(StringComparer.OrdinalIgnoreCase);

    /// <summary>Comandos ejecutados, en orden.</summary>
    public List<RecordedCommand> Executed { get; } = [];

    /// <summary>Resultado por defecto (éxito vacío si no se configura).</summary>
    public CommandResult DefaultResult { get; set; } =
        new() { ExitCode = 0, StandardOutput = string.Empty, StandardError = string.Empty };

    /// <summary>Fija la respuesta de un comando concreto (comparación exacta).</summary>
    public FakeCommandRunner Respond(string commandLine, int exitCode = 0, string stdout = "", string stderr = "")
    {
        _responses[commandLine] = new CommandResult
        {
            ExitCode = exitCode,
            StandardOutput = stdout,
            StandardError = stderr,
        };
        return this;
    }

    /// <summary>Hace que el comando lance una excepción (fallo duro).</summary>
    public FakeCommandRunner Throw(string commandLine, string message = "fallo simulado")
    {
        _throwing[commandLine] = message;
        return this;
    }

    private readonly Dictionary<string, string> _throwing = new(StringComparer.OrdinalIgnoreCase);

    public Task<CommandResult> RunCommandAsync(
        string fileName,
        IReadOnlyList<string> arguments,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();

        var command = new RecordedCommand(fileName, arguments);
        Executed.Add(command);

        if (_throwing.TryGetValue(command.CommandLine, out var message))
        {
            throw new InvalidOperationException(message);
        }

        return Task.FromResult(
            _responses.TryGetValue(command.CommandLine, out var result) ? result : DefaultResult);
    }

    /// <summary>Nombres de los comandos ejecutados, en orden.</summary>
    public IReadOnlyList<string> CommandLines => Executed.Select(c => c.CommandLine).ToList();
}
