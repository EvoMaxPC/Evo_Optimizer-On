using System.Collections.Generic;
using System.Linq;
using Evo.App;
using Evo.Core.System;
using Evo.Detection.Model;
using System.Runtime.InteropServices;
using Xunit;

namespace Evo.App.Tests;

/// <summary>Pruebas del mapeo de arquitectura (ETAPA 6-E).</summary>
public class ArchitectureMappingTests
{
    /// <summary>Tabla de mapeo: X64 y Arm64 coinciden con el catálogo; X86 y los
    /// desconocidos devuelven un valor que el detector trata como NO compatible.</summary>
    [Theory]
    [InlineData(Architecture.X64, "x64")]
    [InlineData(Architecture.Arm64, "arm64")]
    [InlineData(Architecture.X86, "x86")]           // no declarado en catalogo -> no compatible
    [InlineData(Architecture.Arm, "desconocido-Arm")]  // no declarado en catalogo -> no compatible
    [InlineData(Architecture.Wasm64, "desconocido-Wasm64")] // no declarado en catalogo -> no compatible
    public void MapArchitecture_DevuelveStringsDelCatalogo_O_NoCompatible(Architecture arch, string esperado)
    {
        Assert.Equal(esperado, WindowsSystemEnvironment.MapArchitecture(arch));
    }

    /// <summary>El entorno real nunca devuelve arquitectura vacía y la arquitectura
    /// detectada está declarada en catalog/windows-releases.json.</summary>
    [Fact]
    public void EntornoReal_Arquitectura_NoVacia_Y_DeclaradaEnCatalogo()
    {
        var entorno = new WindowsSystemEnvironment();
        var arch = entorno.Architecture;

        Assert.False(string.IsNullOrWhiteSpace(arch),
            "La arquitectura del entorno real no puede estar vacía.");

        var catalogo = WindowsReleaseCatalog.LoadFromFile("catalog/windows-releases.json");
        var arquitecturasCatalogo = catalogo.Releases
            .SelectMany(r => r.Architectures)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        Assert.True(arquitecturasCatalogo.Contains(arch),
            $"La arquitectura '{arch}' del entorno real no está declarada en el catálogo ({string.Join(", ", arquitecturasCatalogo)}).");
    }
}
