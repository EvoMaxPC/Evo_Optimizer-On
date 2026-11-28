using Evo.App;
using Evo.Core.Enums;
using Evo.Detection;
using Evo.Detection.Model;
using Evo.Windows;
using Xunit;

namespace Evo.Windows.Tests;

/// <summary>Pruebas del detector real con el entorno real (ETAPA 6-E).</summary>
public class DetectorRealArchitectureTests
{
    /// <summary>Con WindowsSystemEnvironment real + WindowsRegistryAccessor real +
    /// el catalogo real, el detector nunca rechaza por arquitectura vacia.</summary>
    [Fact]
    public void DetectorReal_NoRechazaPorArquitecturaVacia()
    {
        var entorno = new WindowsSystemEnvironment();
        var registro = new WindowsRegistryAccessor();
        var catalogo = WindowsReleaseCatalog.LoadFromFile("catalog/windows-releases.json");

        var detector = new WindowsDetector(entorno, registro, catalogo);
        var resultado = detector.Detect();

        // La arquitectura nunca debe estar vacia ni rechazarse por estar vacia.
        Assert.False(string.IsNullOrWhiteSpace(resultado.Architecture),
            $"Arquitectura vacia o nula: {resultado.Reason}");
        Assert.DoesNotContain("Arquitectura ''", resultado.Reason);
    }
}
