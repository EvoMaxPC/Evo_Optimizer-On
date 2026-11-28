using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Core.Restore;
using Evo.Core.System;
using Evo.Engine;
using Evo.Engine.Execution;
using Evo.Engine.Executors;
using Evo.Engine.Undo;
using Evo.Detection;
using Evo.Detection.Model;
using Evo.Testing;
using Evo.Windows;
using Microsoft.Win32;
using System;
using System.Collections.Generic;
using System.Linq;
using Xunit;

namespace Evo.Windows.Tests;

/// <summary>Caso del motor real con <see cref="WindowsRegistryAccessor"/> sobre HKCU.</summary>
public sealed class EngineCoordinatorRealTest : IDisposable
{
    private readonly WindowsRegistryAccessor _registry = new();
    private readonly string _keyPath;
    private bool _disposed;

    public EngineCoordinatorRealTest()
    {
        _keyPath = $@"Software\EvoClean.Tests\{Guid.NewGuid():N}";
    }

    private static WindowsDetector CrearDetector()
    {
        var environment = new FakeSystemEnvironment
        {
            CurrentBuild = 26100,
            UBR = 3915,
            InstallationType = "Client",
            EditionID = "Professional",
            Architecture = "x64",
            IsAdmin = true,
            IsElevated = true,
        };
        var catalog = new WindowsReleaseCatalog
        {
            Releases =
            [
                new WindowsRelease
                {
                    Id = "win26100",
                    DisplayName = "Windows 11 build 26100",
                    Build = 26100,
                    BuildMin = 26100,
                    InstallationType = "Client",
                    Architectures = ["x64"],
                },
            ],
        };
        // Detector construido con fakes (no lee el registro real de la máquina).
        return new WindowsDetector(environment, new FakeRegistryAccessor(), catalog);
    }

    private static EngineCoordinator CrearCoordinador(WindowsDetector detector, ISystemEnvironment environment)
    {
        var executors = new IActionExecutor[]
        {
            new RegistryActionExecutor(),
            new ServiceActionExecutor(),
            new TaskActionExecutor(),
            new ProcessActionExecutor(),
            new CommandActionExecutor(),
            new RegistryDeleteKeyExecutor(),
            new TaskCreateExecutor(),
            new RegistryCreateKeyExecutor(),
        };
        var restorePoints = new FakeRestorePointService { Available = true };
        var confirmations = new FakeConfirmationProvider { Approve = true };
        return new EngineCoordinator(
            environment, detector, executors,
            catalog: null, restorePoints: restorePoints, confirmations: confirmations);
    }

    private static (CapabilityContract Capability, CapabilityAction[] Acciones) CapacidadDePrueba(string keyPath)
    {
        var acciones = new CapabilityAction[]
        {
            new RegistryAction
            {
                Order = 1,
                Description = "Escribe DWord",
                Hive = RegistryHiveKind.CurrentUser,
                KeyPath = keyPath,
                ValueName = "ValorDWord",
                Operation = RegistryOperation.Set,
                ValueType = RegistryValueType.DWord,
                Value = "42",
            },
            new RegistryAction
            {
                Order = 2,
                Description = "Escribe String",
                Hive = RegistryHiveKind.CurrentUser,
                KeyPath = keyPath,
                ValueName = "ValorTexto",
                Operation = RegistryOperation.Set,
                ValueType = RegistryValueType.String,
                Value = "hola",
            },
        };
        var capability = new CapabilityContract
        {
            Id = $"evo.clean.test.real.{Guid.NewGuid():N}",
            Name = "Capacidad de prueba real (rollback)",
            Description = "Escribe DWord y String en HKCU para validar el deshacer del motor.",
            SectionId = 1,
            Risk = RiskLevel.Safe,
            SecurityImpact = SecurityImpact.Neutral,
            Privilege = PrivilegeLevel.User,
            Restore = RestoreLevel.SessionUndo,
            Reversibility = Reversibility.Reversible,
            Confirmation = ConfirmationType.None,
            State = CapabilityState.Implemented,
            SupportedBuilds = [26100],
            Variants = [Variant.Evo],
            TechnicalNote = string.Empty,
        };
        return (capability, acciones);
    }

    private static ActionContext ContextoDeEjecucion(EngineCoordinator coordinator, IRegistryAccessor registry)
    {
        return new ActionContext
        {
            Registry = registry,
            Services = new WindowsServiceAccessor(),
            Tasks = new UnavailableTaskAccessor(),
            Processes = new WindowsProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = coordinator.Journal,
            CapabilityId = "evo.clean.test.real",
        };
    }

    [Fact]
    public async Task Motor_Real_Escribe_Y_Deshace_En_HKCU()
    {
        var detector = CrearDetector();
        var environment = new FakeSystemEnvironment
        {
            CurrentBuild = 26100,
            UBR = 3915,
            InstallationType = "Client",
            EditionID = "Professional",
            Architecture = "x64",
            IsAdmin = true,
            IsElevated = true,
        };
        var coordinator = CrearCoordinador(detector, environment);
        var (capability, acciones) = CapacidadDePrueba(_keyPath);
        var plan = new ExecutionPlan(capability, acciones
            .Select((a, i) => new PlannedStep
            {
                Order = a.Order,
                Description = a.Description,
                Action = a,
            }));

        var contexto = ContextoDeEjecucion(coordinator, _registry);
        var summary = await coordinator.ExecuteAsync(plan, ExecutionMode.Execute, contexto);

        // Se aplicó realmente en el registro de Windows (HKCU).
        Assert.False(summary.Blocked);
        Assert.False(summary.Aborted);
        Assert.Equal(2, summary.Succeeded);
        Assert.Equal(42, _registry.GetValue(RegistryHive.CurrentUser, _keyPath, "ValorDWord"));
        Assert.Equal("hola", _registry.GetValue(RegistryHive.CurrentUser, _keyPath, "ValorTexto"));

        // Deshace y verifica que volvió al estado original.
        var rollback = await coordinator.RollbackAsync(ContextoDeEjecucion(coordinator, _registry));
        Assert.Null(_registry.GetValue(RegistryHive.CurrentUser, _keyPath, "ValorDWord"));
        Assert.Null(_registry.GetValue(RegistryHive.CurrentUser, _keyPath, "ValorTexto"));
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
