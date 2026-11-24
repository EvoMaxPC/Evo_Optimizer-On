namespace Evo.Core.System;

/// <summary>
/// Lectura del entorno Windows. Es la única fuente de verdad sobre la máquina:
/// el resto del motor no toca el registro ni WMI directamente (REQ-004).
/// </summary>
public interface ISystemEnvironment
{
    /// <summary>Build del kernel, p. ej. 26100. Nunca se asume válido.</summary>
    int CurrentBuild { get; }

    /// <summary>Update Build Revision (<c>UBR</c>), p. ej. 3915.</summary>
    int UBR { get; }

    /// <summary>Edición, p. ej. <c>Professional</c> o <c>ServerDatacenter</c>.</summary>
    string EditionID { get; }

    /// <summary><c>Client</c> o <c>Server</c> (tal cual lo reporta Windows).</summary>
    string InstallationType { get; }

    /// <summary><c>x64</c>, <c>arm64</c> o <c>x86</c>.</summary>
    string Architecture { get; }

    /// <summary>True si el proceso corre con token de administrador.</summary>
    bool IsAdmin { get; }

    /// <summary>True si el token está elevado (UAC) en este proceso.</summary>
    bool IsElevated { get; }
}
