using Evo.Core.Actions;
using Evo.Core.Confirmation;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Core.Restore;
using Evo.Core.System;
using Evo.App;
using Evo.Catalog.Model;
using Evo.Detection;
using Evo.Detection.Model;
using Evo.Testing;
using Evo.Windows;
using Microsoft.Win32;
using Xunit;

namespace Evo.Windows.Tests;

/// <summary>Prueba real de Aplicar → Deshacer sobre el registro de Windows
/// (HKCU) a través del ViewModel real de Evo.App (ETAPA 6-H).</summary>
public sealed class UndoRealRegistryTest : IDisposable
{
    private const int TestBuild = 26100;
    private readonly WindowsRegistryAccessor _registry = new();
    private readonly string _keyPath;
    private bool _disposed;

    public UndoRealRegistryTest()
    {
        _keyPath = $@"Software\EvoClean.Tests\{Guid.NewGuid():N}";
    }

    /// <summary>Entorno cliente compatible (fake): evita depender del SO del runner.</summary>
    private static FakeSystemEnvironment ClientEnv() =>
        FakeSystemEnvironment.Win11_24H2_Client();

    /// <summary>Detección soportada para el build de prueba.</summary>
    private static CompatibilityResult SupportedResult(int build = TestBuild) =>
        new()
        {
            Status = CompatibilityStatus.Supported,
            Build = build,
            Ubr = 3915,
            EditionId = "Professional",
            InstallationType = "Client",
            Architecture = "x64",
        };

    /// <summary>Capacidad Safe con una acción de registro que escribe un DWord en <paramref name="keyPath"/>.</summary>
    private static CapabilityDefinition SafeCapability(string id, string keyPath, string valueName, object value) =>
        new()
        {
            Id = id,
            Name = $"Capacidad real {id}",
            Description = $"Descripción de {id}",
            SectionId = 1,
            Risk = RiskLevel.Safe,
            SecurityImpact = Evo.Core.Enums.SecurityImpact.Neutral,
            Privilege = PrivilegeLevel.User,
            Restore = RestoreLevel.SessionUndo,
            Reversibility = Evo.Core.Enums.Reversibility.Reversible,
            Confirmation = ConfirmationType.None,
            State = CapabilityState.Implemented,
            SupportedBuilds = [TestBuild],
            Actions =
            [
                new RegistryAction
                {
                    Order = 1,
                    Description = $"Set {id}",
                    Hive = RegistryHiveKind.CurrentUser,
                    KeyPath = keyPath,
                    ValueName = valueName,
                    Operation = RegistryOperation.Set,
                    ValueType = RegistryValueType.DWord,
                    Value = value.ToString(),
                },
            ],
        };

    /// <summary>ViewModel con el registro real de Windows inyectado.</summary>
    private static MainViewModel CreateVmConRegistroReal(
        IReadOnlyList<CapabilityDefinition> capabilities,
        WindowsRegistryAccessor registry,
        string keyPath) =>
        MainViewModel.CreateForTest(
            ClientEnv(),
            SupportedResult(),
            capabilities,
            new FakeConfirmationProvider { Approve = true },
            new FakeRestorePointService { Available = true },
            new FakeCommandRunner(),
            registry);

    /// <summary>Aplicar escribe en HKCU real; Deshacer lo revierte.</summary>
    [Fact]
    public void AplicarYDeshacer_RegistroReal_RevierteValor()
    {
        var registry = _registry;
        var caps = new List<CapabilityDefinition>
        {
            SafeCapability("cap.real", _keyPath, "ValorReal", 42)
        };
        var vm = CreateVmConRegistroReal(caps, registry, _keyPath);

        var cap = Assert.Single(vm.Sections.SelectMany(s => s.Capabilities));

        // Antes de aplicar no existe.
        Assert.Null(registry.GetValue(RegistryHive.CurrentUser, _keyPath, "ValorReal"));

        var applied = vm.Apply(cap);
        Assert.True(applied.HasResults);
        Assert.Equal(42, (int?)registry.GetValue(RegistryHive.CurrentUser, _keyPath, "ValorReal"));

        var undone = vm.Undo();
        Assert.True(undone.HasResults);
        Assert.Contains("Se deshizo", undone.ResultsText);
        Assert.DoesNotContain("DryRun", undone.ResultsText);

        // Después del deshacer el valor vuelve a estar ausente.
        Assert.Null(registry.GetValue(RegistryHive.CurrentUser, _keyPath, "ValorReal"));
    }

    public void Dispose()
    {
        if (!_disposed)
        {
            try
            {
                _registry.DeleteKey(RegistryHive.CurrentUser, _keyPath, recursive: true);
            }
            catch
            {
                // La clave puede no existir si el test falló antes de crearla.
            }
            _disposed = true;
        }
        GC.SuppressFinalize(this);
    }
}
