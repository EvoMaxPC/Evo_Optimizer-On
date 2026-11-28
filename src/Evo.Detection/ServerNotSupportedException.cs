namespace Evo.Detection;

/// <summary>
/// Se lanza cuando la detección confirma un Windows Server (o cualquier
/// InstallationType distinto de Client). REQ-003: Windows Server no es objetivo.
/// </summary>
public sealed class ServerNotSupportedException : Exception
{
    public ServerNotSupportedException()
        : base("Windows Server no está soportado por EVO CLEAN.")
    {
    }

    public ServerNotSupportedException(string message)
        : base(message)
    {
    }

    public ServerNotSupportedException(string message, Exception innerException)
        : base(message, innerException)
    {
    }

    public ServerNotSupportedException(string message, string installationType, string editionId)
        : base(message)
    {
        InstallationType = installationType;
        EditionId = editionId;
    }

    /// <summary>InstallationType reportado por el sistema, tal cual.</summary>
    public string InstallationType { get; } = string.Empty;

    /// <summary>EditionID reportado por el sistema, tal cual.</summary>
    public string EditionId { get; } = string.Empty;
}
