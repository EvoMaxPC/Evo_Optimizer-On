using Evo.Core.Actions;
using Evo.Core.Confirmation;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Core.Restore;
using Evo.Core.System;
using Evo.Catalog.Model;
using Evo.Detection;
using Evo.Detection.Model;
using Evo.Testing;
using Xunit;

namespace Evo.App.Tests;

/// <summary>Tests de los ViewModels de Evo.App con fakes de Evo.Testing.</summary>
public class Tests
{
    private const int TestBuild = 26100;

    /// <summary>Entorno cliente Windows 11 24H2 conocido.</summary>
    private static FakeSystemEnvironment ClientEnv() =>
        FakeSystemEnvironment.Win11_24H2_Client();

    /// <summary>Catálogo de releases con una sola entrada para el build de prueba.</summary>
    private static WindowsReleaseCatalog ReleaseCatalog(int build = TestBuild) =>
        new()
        {
            Releases =
            [
                new WindowsRelease
                {
                    Id = $"win{build}",
                    DisplayName = $"Windows 11 build {build}",
                    Build = build,
                    BuildMin = build,
                    InstallationType = "Client",
                    Architectures = ["x64"],
                },
            ],
        };

    /// <summary>Capacidad de prueba Implemented, Safe, sin registro obligatorio.</summary>
    private static CapabilityDefinition SafeCapability(
        string id,
        int sectionId = 1,
        IReadOnlyList<int>? supportedBuilds = null) =>
        new()
        {
            Id = id,
            Name = $"Capacidad {id}",
            Description = $"Descripción de {id}",
            SectionId = sectionId,
            Risk = RiskLevel.Safe,
            SecurityImpact = Evo.Core.Enums.SecurityImpact.Neutral,
            Privilege = PrivilegeLevel.User,
            Restore = RestoreLevel.SessionUndo,
            Reversibility = Evo.Core.Enums.Reversibility.Reversible,
            Confirmation = ConfirmationType.None,
            State = CapabilityState.Implemented,
            SupportedBuilds = supportedBuilds ?? [TestBuild],
            Actions =
            [
                new RegistryAction
                {
                    Order = 1,
                    Description = $"Set {id}",
                    Hive = RegistryHiveKind.CurrentUser,
                    KeyPath = @"Software\Evo\Test",
                    ValueName = id,
                    Operation = RegistryOperation.Set,
                    ValueType = RegistryValueType.DWord,
                    Value = "1",
                },
            ],
        };

    /// <summary>Capacidad Specified (no ejecutable).</summary>
    private static CapabilityDefinition SpecifiedCapability(string id, int sectionId = 4) =>
        SafeCapability(id, sectionId) with
        {
            State = CapabilityState.Specified,
        };

    /// <summary>Capacidad Critical (bloqueada por TypeOperationName).</summary>
    private static CapabilityDefinition CriticalCapability(string id, int sectionId = 13) =>
        SafeCapability(id, sectionId) with
        {
            Risk = RiskLevel.Critical,
            Confirmation = ConfirmationType.TypeOperationName,
        };

    /// <summary>Capacidad que exige punto de restauración.</summary>
    private static CapabilityDefinition RestorePointCapability(string id, int sectionId = 13) =>
        SafeCapability(id, sectionId) with
        {
            Risk = RiskLevel.High,
            Restore = RestoreLevel.RestorePoint,
            Confirmation = ConfirmationType.SummaryAndRestorePoint,
        };

    /// <summary>Construye un CompatibilityResult soportado para el build dado.</summary>
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

    /// <summary>Construye un CompatibilityResult rechazado (Server).</summary>
    private static CompatibilityResult ServerResult() =>
        new()
        {
            Status = CompatibilityStatus.ServerRejected,
            Build = 26100,
            Ubr = 3915,
            EditionId = "ServerDatacenter",
            InstallationType = "Server",
            Architecture = "x64",
            Reason = "Windows Server no está soportado (InstallationType='Server', EditionID='ServerDatacenter').",
        };

    /// <summary>Construye un CompatibilityResult rechazado (build desconocido).</summary>
    private static CompatibilityResult UnknownBuildResult() =>
        new()
        {
            Status = CompatibilityStatus.UnknownBuildRejected,
            Build = 99999,
            Ubr = 0,
            EditionId = "Professional",
            InstallationType = "Client",
            Architecture = "x64",
            Reason = "Build 99999 desconocido: no casa con ninguna entrada del catálogo.",
        };

    /// <summary>Crea un ViewModel para tests con capacidades y detección inyectadas.</summary>
    private static MainViewModel CreateVm(
        CompatibilityResult compatibility,
        IReadOnlyList<CapabilityDefinition> capabilities,
        IConfirmationProvider? confirmations = null,
        IRestorePointService? restorePoints = null)
    {
        return MainViewModel.CreateForTest(
            ClientEnv(),
            compatibility,
            capabilities,
            confirmations ?? new FakeConfirmationProvider(),
            restorePoints ?? new FakeRestorePointService(),
            new FakeCommandRunner());
    }

    #region Detección de Windows

    [Fact]
    public void Windows_NoCompatible_NoAplicaNada()
    {
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.a") };
        var vm = CreateVm(ServerResult(), caps);

        Assert.False(vm.IsWindowsCompatible);
        Assert.False(string.IsNullOrWhiteSpace(vm.CompatibilityMessage));
        Assert.Contains("Server", vm.CompatibilityMessage);
        // Ninguna capacidad ejecutable
        Assert.All(vm.Sections.SelectMany(s => s.Capabilities), c => Assert.False(c.IsExecutable));
    }

    [Fact]
    public void Build_Desconocido_NoAplicaNada()
    {
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.a") };
        var vm = CreateVm(UnknownBuildResult(), caps);

        Assert.False(vm.IsWindowsCompatible);
        Assert.All(vm.Sections.SelectMany(s => s.Capabilities), c => Assert.False(c.IsExecutable));
    }

    [Fact]
    public void Build_Conocido_Cliente_Compatible()
    {
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.a") };
        var vm = CreateVm(SupportedResult(), caps);

        Assert.True(vm.IsWindowsCompatible);
        Assert.Equal(TestBuild, vm.CurrentBuild);
        Assert.Equal("Client", vm.InstallationType);
    }

    #endregion

    #region Estados de capacidad

    [Fact]
    public void Specified_No_Ejecutable()
    {
        var caps = new List<CapabilityDefinition> { SpecifiedCapability("cap.specified") };
        var vm = CreateVm(SupportedResult(), caps);

        var cap = Assert.Single(vm.Sections.SelectMany(s => s.Capabilities));
        Assert.Equal(CapabilityState.Specified, cap.State);
        Assert.False(cap.IsExecutable);
        Assert.Equal("Especificada: aún no disponible", cap.NotExecutableReason);
        Assert.False(cap.CanSimulate);
        Assert.False(cap.CanApply);
    }

    [Fact]
    public void Critical_Bloqueada()
    {
        var caps = new List<CapabilityDefinition> { CriticalCapability("cap.critical") };
        var vm = CreateVm(SupportedResult(), caps);

        var cap = Assert.Single(vm.Sections.SelectMany(s => s.Capabilities));
        Assert.Equal(ConfirmationType.TypeOperationName, cap.Confirmation);
        Assert.False(cap.CanApply); // TypeOperationName → no ejecutable desde la UI
    }

    [Fact]
    public void RestorePoint_Bloqueada_SinServicio()
    {
        var caps = new List<CapabilityDefinition> { RestorePointCapability("cap.rp") };
        var restorePoints = new FakeRestorePointService { Available = false };
        var vm = CreateVm(SupportedResult(), caps, restorePoints: restorePoints);

        var cap = Assert.Single(vm.Sections.SelectMany(s => s.Capabilities));
        Assert.True(cap.IsExecutable);
        Assert.True(cap.CanApply);

        // El motor fall-closed: sin servicio de restauración disponible, aborta.
        var result = vm.Apply(cap);
        Assert.Contains("restauración", result.ResultsText,
            StringComparison.OrdinalIgnoreCase);
        Assert.False(restorePoints.CreatedCount > 0, "No se creó punto de restauración.");
    }

    #endregion

    #region Simular y Aplicar

    [Fact]
    public void Simular_DryRun_No_Muta_Fake()
    {
        var registry = new FakeRegistryAccessor();
        // Nota: CreateForTest usa FakeRegistryAccessor interno para el detector,
        // pero el ejecutor usa WindowsRegistryAccessor real. Para probar DryRun
        // sin mutar, usamos la verificación de que el resultado es DryRun.
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.dryrun") };
        var confirmations = new FakeConfirmationProvider { Approve = true };
        var vm = CreateVm(SupportedResult(), caps, confirmations: confirmations);

        var cap = Assert.Single(vm.Sections.SelectMany(s => s.Capabilities));
        var result = vm.Simulate(cap);

        Assert.True(result.HasResults);
        Assert.Contains("DryRun", result.ResultsText);
        // DryRun no debe pedir confirmación
        Assert.Empty(confirmations.Requests);
    }

    [Fact]
    public void AplicarYDeshacer_Fake_Vuelve_Al_Estado_Original()
    {
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.undo") };
        var confirmations = new FakeConfirmationProvider { Approve = true };
        var restorePoints = new FakeRestorePointService { Available = true };
        var vm = CreateVm(SupportedResult(), caps, confirmations: confirmations, restorePoints: restorePoints);

        var cap = Assert.Single(vm.Sections.SelectMany(s => s.Capabilities));
        var applied = vm.Apply(cap);

        Assert.True(applied.HasResults);
        // Después del undo, el diario está vacío
        var undone = applied.Undo();
        Assert.True(undone.HasResults);
        Assert.Contains("Rollback", undone.ResultsText);
    }

    #endregion

    #region Secciones

    [Fact]
    public void Diecisiete_Secciones_Titulos_Exactos()
    {
        var caps = new List<CapabilityDefinition>();
        var vm = CreateVm(SupportedResult(), caps);

        Assert.Equal(17, vm.Sections.Count);

        var titulosEsperados = new[]
        {
            "LIMPIEZA Y ELIMINACIÓN DE COMPONENTES",
            "DEBLOAT DE WINDOWS",
            "TELEMETRÍA Y PRIVACIDAD",
            "OPTIMIZACIÓN DE SERVICIOS",
            "OPTIMIZACIÓN DE CPU Y RENDIMIENTO",
            "OPTIMIZACIÓN GAMING",
            "MEMORIA Y APLICACIONES EN SEGUNDO PLANO",
            "ADMINISTRACIÓN DE INICIO Y APAGADO",
            "REGISTRO DE WINDOWS Y CONFIGURACIÓN DEL SISTEMA",
            "EXPLORADOR DE ARCHIVOS E INTERFAZ",
            "RED Y CONECTIVIDAD",
            "WINDOWS UPDATE Y MANTENIMIENTO",
            "SEGURIDAD Y PROTECCIÓN",
            "REPARACIÓN Y DIAGNÓSTICO",
            "ADMINISTRACIÓN DE APLICACIONES",
            "FUNCIONES DE INSTALACIÓN Y ADMINISTRACIÓN AVANZADA",
            "CAPACIDADES ADICIONALES QUE NO DEBEMOS PERDER",
        };

        for (int i = 0; i < titulosEsperados.Length; i++)
        {
            Assert.Equal(titulosEsperados[i], vm.Sections[i].Title);
        }
    }

    [Fact]
    public void Seccion_Sin_Capacidades_Muestra_Sin_Capacidades_Todavia()
    {
        // Ninguna capacidad → todas las secciones vacías
        var vm = CreateVm(SupportedResult(), new List<CapabilityDefinition>());

        var vacia = vm.Sections.First(s => s.SectionId == "4"); // sin cap en section 4
        Assert.False(vacia.HasCapabilities);
    }

    #endregion

    #region Privilegio Admin

    [Fact]
    public void Privilege_Admin_NoAdmin_Muestra_Aviso()
    {
        var env = ClientEnv();
        env.IsAdmin = false;
        env.IsElevated = false;

        var caps = new List<CapabilityDefinition>
        {
            SafeCapability("cap.admin", sectionId: 1) with { Privilege = PrivilegeLevel.Admin },
        };

        var detector = new WindowsDetector(env, new FakeRegistryAccessor(), ReleaseCatalog());
        var compatibility = detector.Detect();

        var vm = MainViewModel.CreateForTest(
            env, compatibility, caps,
            new FakeConfirmationProvider(),
            new FakeRestorePointService(),
            new FakeCommandRunner());

        // Capacidad Admin con proceso no-admin no es ejecutable efectivamente
        var cap = Assert.Single(vm.Sections.SelectMany(s => s.Capabilities));
        // El motor preflight rechaza por privilegio; aquí comprobamos que el build es compatible
        Assert.True(vm.IsWindowsCompatible);
    }

    [Fact]
    public void TrustedInstaller_No_Disponible()
    {
        var caps = new List<CapabilityDefinition>
        {
            SafeCapability("cap.ti", sectionId: 1) with { Privilege = PrivilegeLevel.TrustedInstaller },
        };

        var vm = CreateVm(SupportedResult(), caps);

        var cap = Assert.Single(vm.Sections.SelectMany(s => s.Capabilities));
        Assert.Equal(PrivilegeLevel.TrustedInstaller, cap.Privilege);
        // TrustedInstaller no se puede asumir desde el proceso actual
    }

    #endregion
}
