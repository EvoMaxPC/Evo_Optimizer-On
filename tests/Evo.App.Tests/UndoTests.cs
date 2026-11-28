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
using Microsoft.Win32;
using Xunit;

namespace Evo.App.Tests;

/// <summary>Pruebas del flujo completo Aplicar → Deshacer a través del ViewModel
/// real de Evo.App (ETAPA 6-H).</summary>
public class UndoTests
{
    private const int TestBuild = 26100;
    private const string TestKey = @"Software\Evo\Test";

    /// <summary>Entorno cliente Windows 11 24H2 conocido.</summary>
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

    /// <summary>Capacidad Safe con una acción de registro que escribe un DWord.</summary>
    private static CapabilityDefinition SafeCapability(
        string id, string valueName, object value, string? keyPath = null) =>
        new()
        {
            Id = id,
            Name = $"Capacidad {id}",
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
                    KeyPath = keyPath ?? TestKey,
                    ValueName = valueName,
                    Operation = RegistryOperation.Set,
                    ValueType = RegistryValueType.DWord,
                    Value = value.ToString(),
                },
            ],
        };

    /// <summary>ViewModel con registro falso inyectado (no muta el registro real).</summary>
    private static MainViewModel CreateVmConRegistro(
        IReadOnlyList<CapabilityDefinition> capabilities,
        FakeRegistryAccessor registry,
        IConfirmationProvider? confirmations = null,
        IRestorePointService? restorePoints = null) =>
        MainViewModel.CreateForTest(
            ClientEnv(),
            SupportedResult(),
            capabilities,
            confirmations ?? new FakeConfirmationProvider { Approve = true },
            restorePoints ?? new FakeRestorePointService { Available = true },
            new FakeCommandRunner(),
            registry);

    private static CapabilityViewModel CapacidadDe(
        MainViewModel vm, string id) =>
        Assert.Single(vm.Sections.SelectMany(s => s.Capabilities).Where(c => c.Id == id));

    private static int? LeeDWord(FakeRegistryAccessor registry, string valueName) =>
        (int?)registry.GetValue(RegistryHive.CurrentUser, TestKey, valueName);

    #region Casos de Deshacer

    /// <summary>i) Valor ausente antes: aplicar lo crea, deshacer lo elimina.</summary>
    [Fact]
    public void DespuesDeAplicar_Deshacer_EliminaValorCreado()
    {
        var registry = new FakeRegistryAccessor();
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.i", "ValorI", 42) };
        var vm = CreateVmConRegistro(caps, registry);

        var cap = CapacidadDe(vm, "cap.i");

        var applied = vm.Apply(cap);
        Assert.True(applied.HasResults);
        Assert.Equal(42, LeeDWord(registry, "ValorI"));

        var undone = vm.Undo(cap.Id);
        Assert.True(undone.HasResults);
        Assert.Contains("Se deshizo", undone.ResultsText);
        Assert.DoesNotContain("DryRun", undone.ResultsText);
        Assert.Null(LeeDWord(registry, "ValorI"));
    }

    /// <summary>ii) Valor previo distinto: deshacer lo restaura, no lo elimina.</summary>
    [Fact]
    public void DespuesDeAplicar_Deshacer_RestauraValorPrevio()
    {
        var registry = new FakeRegistryAccessor();
        registry.Seed(RegistryHive.CurrentUser, TestKey, "ValorII", 99, RegistryValueKind.DWord);
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.ii", "ValorII", 42) };
        var vm = CreateVmConRegistro(caps, registry);

        var cap = CapacidadDe(vm, "cap.ii");

        var applied = vm.Apply(cap);
        Assert.Equal(42, LeeDWord(registry, "ValorII"));

        var undone = vm.Undo(cap.Id);
        Assert.True(undone.HasResults);
        Assert.Contains("Se deshizo", undone.ResultsText);
        Assert.Equal(99, LeeDWord(registry, "ValorII"));
    }

    /// <summary>iii) Simular antes de Aplicar no muta; Deshacer tras Aplicar revierte.</summary>
    [Fact]
    public void Simular_Despues_Aplicar_Y_Deshacer_Vuelve_Al_Estado_Original()
    {
        var registry = new FakeRegistryAccessor();
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.iii", "ValorIII", 42) };
        var vm = CreateVmConRegistro(caps, registry);

        var cap = CapacidadDe(vm, "cap.iii");

        // Simular no debe mutar.
        var simulated = vm.Simulate(cap);
        Assert.Null(LeeDWord(registry, "ValorIII"));

        // Aplicar sí muta.
        var applied = vm.Apply(cap);
        Assert.Equal(42, LeeDWord(registry, "ValorIII"));

        // Deshacer revierte.
        var undone = vm.Undo(cap.Id);
        Assert.True(undone.HasResults);
        Assert.Contains("Se deshizo", undone.ResultsText);
        Assert.Null(LeeDWord(registry, "ValorIII"));
    }

    /// <summary>iv) Deshacer sin haber aplicado nada: honestamente "no hay nada".</summary>
    [Fact]
    public void DeshacerSinAplicar_Dice_NoHayNada()
    {
        var registry = new FakeRegistryAccessor();
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.iv", "ValorIV", 42) };
        var vm = CreateVmConRegistro(caps, registry);

        var cap = CapacidadDe(vm, "cap.iv");

        var undone = vm.Undo(cap.Id);
        Assert.True(undone.HasResults);
        Assert.Contains("No hay nada para deshacer", undone.ResultsText);
        Assert.DoesNotContain("DryRun", undone.ResultsText);
        Assert.Null(LeeDWord(registry, "ValorIV"));
    }

    /// <summary>v) Dos clics seguidos en Deshacer: el segundo dice que no hay nada.</summary>
    [Fact]
    public void DosClicsEnDeshacer_ElSegundo_DiceNoHayNada()
    {
        var registry = new FakeRegistryAccessor();
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.v", "ValorV", 42) };
        var vm = CreateVmConRegistro(caps, registry);

        var cap = CapacidadDe(vm, "cap.v");

        var applied = vm.Apply(cap);
        Assert.Equal(42, LeeDWord(registry, "ValorV"));

        var primero = vm.Undo(cap.Id);
        Assert.Contains("Se deshizo", primero.ResultsText);
        Assert.Null(LeeDWord(registry, "ValorV"));

        var segundo = vm.Undo(cap.Id);
        Assert.Contains("No hay nada para deshacer", segundo.ResultsText);
        Assert.Null(LeeDWord(registry, "ValorV"));
    }

    /// <summary>(1) Deshacer por capacidad: aplicar A y B (claves distintas),
    /// deshacer A revierte SOLO A; B queda aplicada. Luego deshacer B revierte B.</summary>
    [Fact]
    public void DeshacerPorCapacidad_A_No_Afecta_A_B()
    {
        var registry = new FakeRegistryAccessor();
        var caps = new List<CapabilityDefinition>
        {
            SafeCapability("cap.a", "ValorA", 42, @"Software\Evo\A"),
            SafeCapability("cap.b", "ValorB", 77, @"Software\Evo\B"),
        };
        var vm = CreateVmConRegistro(caps, registry);

        var capA = CapacidadDe(vm, "cap.a");
        var capB = CapacidadDe(vm, "cap.b");

        var appliedA = vm.Apply(capA);
        Assert.True(appliedA.HasResults);
        Assert.Equal(42, (int?)registry.GetValue(RegistryHive.CurrentUser, @"Software\Evo\A", "ValorA"));

        var appliedB = vm.Apply(capB);
        Assert.True(appliedB.HasResults);
        Assert.Equal(77, (int?)registry.GetValue(RegistryHive.CurrentUser, @"Software\Evo\B", "ValorB"));

        // Deshacer A: revierte solo A, B queda aplicada.
        var undoneA = vm.Undo(capA.Id);
        Assert.True(undoneA.HasResults);
        Assert.Contains("Se deshizo: 1 cambio(s) de cap.a", undoneA.ResultsText);
        Assert.DoesNotContain("DryRun", undoneA.ResultsText);
        Assert.Null(registry.GetValue(RegistryHive.CurrentUser, @"Software\Evo\A", "ValorA"));
        Assert.Equal(77, (int?)registry.GetValue(RegistryHive.CurrentUser, @"Software\Evo\B", "ValorB"));

        // Luego deshacer B: revierte B.
        var undoneB = vm.Undo(capB.Id);
        Assert.True(undoneB.HasResults);
        Assert.Contains("Se deshizo: 1 cambio(s) de cap.b", undoneB.ResultsText);
        Assert.Null(registry.GetValue(RegistryHive.CurrentUser, @"Software\Evo\B", "ValorB"));
    }

    /// <summary>(3) Aplicar A dos veces seguidas y deshacer una vez: el journal de
    /// A tiene dos entradas; RollbackAsync las revierte LIFO, dejando el estado
    /// original de antes de la primera aplicación.</summary>
    [Fact]
    public void AplicarADosVeces_DeshacerUnaVez_VuelveAlEstadoOriginal()
    {
        var registry = new FakeRegistryAccessor();
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.aux", "ValorAux", 42, @"Software\Evo\Aux") };
        var vm = CreateVmConRegistro(caps, registry);

        var cap = CapacidadDe(vm, "cap.aux");

        // Primera aplicación.
        vm.Apply(cap);
        Assert.Equal(42, (int?)registry.GetValue(RegistryHive.CurrentUser, @"Software\Evo\Aux", "ValorAux"));

        // Segunda aplicación (mismo valor, nueva entrada del journal).
        vm.Apply(cap);
        Assert.Equal(42, (int?)registry.GetValue(RegistryHive.CurrentUser, @"Software\Evo\Aux", "ValorAux"));

        // Un solo deshacer revierte AMBAS entradas del journal de A.
        var undone = vm.Undo(cap.Id);
        Assert.True(undone.HasResults);
        Assert.Contains("Se deshizo: 2 cambio(s) de cap.aux", undone.ResultsText);
        Assert.Null(registry.GetValue(RegistryHive.CurrentUser, @"Software\Evo\Aux", "ValorAux"));

        // Diario de A vacío tras el deshacer.
        Assert.True(vm.Undo(cap.Id).ResultsText.Contains("No hay nada para deshacer"));
    }

    /// <summary>Paso 2e: Aplicar X con éxito; el segundo Aplicar de X falla a mitad
    /// (SetValue lanza); Deshacer X debe revertir la PRIMERA aplicación (estado
    /// original: valor ausente) y decir "Se deshizo: 1 cambio(s)".
    ///
    /// Forzado con FakeRegistryAccessor.ThrowOnSetValueCall: la 2ª aplicación
    /// lanza OperationCanceledException en SetValue; EngineCoordinator la
    /// captura (no deja escapar), no agrega entrada al journal de esta
    /// ejecución, y como no hubo mutación nueva no hay rollback automático.
    /// El journal de X conserva solo la entrada de la 1ª aplicación.
    /// </summary>
    [Fact]
    public void DespuesDeAplicar_SegundoAplicarFalla_DeshacerReviertePrimera()
    {
        var registry = new FakeRegistryAccessor();
        var caps = new List<CapabilityDefinition> { SafeCapability("cap.x", "ValorX", 42, @"Software\Evo\X") };
        var vm = CreateVmConRegistro(caps, registry);
        var cap = CapacidadDe(vm, "cap.x");

        // 1ª aplicación: éxito.
        var applied1 = vm.Apply(cap);
        Assert.True(applied1.HasResults);
        Assert.Equal(42, (int?)registry.GetValue(RegistryHive.CurrentUser, @"Software\Evo\X", "ValorX"));

        // 2ª aplicación: SetValue falla en la 1ª llamada (ThrowOnSetValueCall = 1).
        registry.ResetSetValueCounter();
        registry.ThrowOnSetValueCall = 1;
        var applied2 = vm.Apply(cap);
        Assert.True(applied2.HasResults);
        // ValorX sigue en 42: la 2ª aplicación no mutó (SetValue lanzó antes).
        Assert.Equal(42, (int?)registry.GetValue(RegistryHive.CurrentUser, @"Software\Evo\X", "ValorX"));

        // Deshacer X revierte la 1ª aplicación: estado original (valor ausente).
        var undone = vm.Undo(cap.Id);
        Assert.True(undone.HasResults);
        Assert.Contains("Se deshizo: 1 cambio(s) de cap.x", undone.ResultsText);
        Assert.DoesNotContain("DryRun", undone.ResultsText);
        Assert.Null(registry.GetValue(RegistryHive.CurrentUser, @"Software\Evo\X", "ValorX"));
    }

    #endregion
}
