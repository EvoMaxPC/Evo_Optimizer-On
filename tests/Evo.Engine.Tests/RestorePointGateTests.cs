using Evo.Core.Actions;
using Evo.Core.Confirmation;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Core.Restore;
using Evo.Engine.Execution;
using Evo.Testing;
using Microsoft.Win32;
using Xunit;

namespace Evo.Engine.Tests;

/// <summary>
/// Puerta previa a la primera mutación: confirmación según riesgo y punto de
/// restauración con fail-closed (REQ-001, REQ-004, ADR-0004).
/// Ningún test toca el sistema: todo pasa por los fakes.
/// </summary>
public sealed class RestorePointGateTests
{
    private const string KeyPath = @"SOFTWARE\Evo\Gate";

    private static RegistryAction SetDword(int order, string name, string value) => new()
    {
        Order = order,
        Description = $"set {name}",
        Hive = RegistryHiveKind.LocalMachine,
        KeyPath = KeyPath,
        ValueName = name,
        Operation = RegistryOperation.Set,
        ValueType = RegistryValueType.DWord,
        Value = value,
    };

    private static CapabilityAction[] Actions() =>
        [SetDword(1, "First", "0"), SetDword(2, "Second", "0")];

    /// <summary>Contrato que exige punto por Restore=RestorePoint.</summary>
    private static CapabilityContract RestorePointContract(params CapabilityAction[] actions) =>
        TestHarness.Contract(actions, risk: RiskLevel.Medium, restore: RestoreLevel.RestorePoint);

    /// <summary>Contrato que no pide punto desde Restore pero sí desde la confirmación.</summary>
    private static CapabilityContract IrreversibleContract(params CapabilityAction[] actions) => new()
    {
        Id = "test.irreversible",
        Name = "test.irreversible",
        Description = "capacidad irreversible de prueba",
        SectionId = 9,
        Risk = RiskLevel.High,
        SecurityImpact = SecurityImpact.Neutral,
        Privilege = PrivilegeLevel.User,
        Restore = RestoreLevel.None,
        Reversibility = Reversibility.Irreversible,
        Confirmation = ConfirmationType.SummaryAndRestorePoint,
        State = CapabilityState.Implemented,
        Variants = [Variant.Evo],
        ConflictsWith = [],
        DependsOn = [],
        SupportedBuilds = [],
    };

    private static ActionContext WithContext(TestHarness harness, ExecutionMode mode, bool acceptNoRestorePoint = false)
    {
        var context = harness.Context(mode);
        return acceptNoRestorePoint ? context with { AcceptNoRestorePoint = true } : context;
    }

    [Fact]
    public void RequiresRestorePoint_CubreLasDosVias()
    {
        Assert.True(EngineCoordinator.RequiresRestorePoint(RestorePointContract(Actions())));
        Assert.True(EngineCoordinator.RequiresRestorePoint(IrreversibleContract(Actions())));

        var sessionUndo = TestHarness.Contract(
            Actions(), risk: RiskLevel.Low, restore: RestoreLevel.SessionUndo);
        Assert.False(EngineCoordinator.RequiresRestorePoint(sessionUndo));

        var critical = TestHarness.Contract(
            Actions(), risk: RiskLevel.Critical, restore: RestoreLevel.SessionUndo,
            confirmation: ConfirmationType.TypeOperationName);
        Assert.True(EngineCoordinator.RequiresRestorePoint(critical));
    }

    [Fact]
    public async Task DryRun_NoCreaPuntoNiPideConfirmacion()
    {
        var harness = TestHarness.Create();
        var actions = Actions();
        var plan = TestHarness.Plan(RestorePointContract(actions), actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.DryRun, WithContext(harness, ExecutionMode.DryRun));

        Assert.False(summary.Aborted);
        Assert.Null(summary.RestorePointId);
        Assert.Empty(harness.RestorePoints.Calls);
        Assert.True(harness.Confirmations.Unused);
        Assert.False(summary.Mutated);
    }

    [Fact]
    public async Task Audit_NoCreaPuntoNiPideConfirmacion()
    {
        var harness = TestHarness.Create();
        var actions = Actions();
        var plan = TestHarness.Plan(RestorePointContract(actions), actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Audit, WithContext(harness, ExecutionMode.Audit));

        Assert.Equal(ExecutionMode.Audit, summary.Mode);
        Assert.Empty(harness.RestorePoints.Calls);
        Assert.True(harness.Confirmations.Unused);
    }

    [Fact]
    public async Task Execute_CreaElPuntoAntesDeLaPrimeraMutacion()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "First", 1);
        var actions = Actions();
        var plan = TestHarness.Plan(RestorePointContract(actions), actions);

        // Fotografía en el instante de crear el punto: 0 mutaciones.
        var mutationsWhenPointCreated = -1;
        harness.RestorePoints.BeforeCreate = () =>
            mutationsWhenPointCreated = harness.Registry.MutationCount + harness.Services.MutationCount;

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, WithContext(harness, ExecutionMode.Execute));

        Assert.False(summary.Aborted, summary.AbortedReason);
        Assert.False(string.IsNullOrEmpty(summary.RestorePointId));
        Assert.Equal(0, mutationsWhenPointCreated);
        Assert.Equal(1, harness.RestorePoints.CreatedCount);

        // Orden: primero la disponibilidad, luego la creación del punto y sólo
        // después las mutaciones del registro falso.
        Assert.Equal(
            new[] { "available", "create:EVO CLEAN — test.capability" },
            harness.RestorePoints.Calls);

        Assert.Equal(2, harness.Registry.MutationCount);

        // El id del punto queda vinculado al diario de deshacer.
        Assert.Equal(summary.RestorePointId, harness.Coordinator.Journal.RestorePointId);
        Assert.Equal(2, summary.UndoJournalEntry.Count);
        Assert.Equal(0, summary.Failed);
    }

    [Fact]
    public async Task FailClosed_SiElPuntoNoEstaDisponible_NoMutaNada()
    {
        var harness = TestHarness.Create(restorePointAvailable: false);
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "First", 7);
        var actions = Actions();
        var plan = TestHarness.Plan(RestorePointContract(actions), actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, WithContext(harness, ExecutionMode.Execute));

        Assert.True(summary.Aborted);
        Assert.Contains("Protección del sistema", summary.AbortedReason);
        Assert.Null(summary.RestorePointId);
        Assert.Empty(harness.RestorePoints.Created);
        Assert.Empty(summary.UndoJournalEntry);

        // Nada se escribió: el valor sembrado sigue igual y el fake no registró mutaciones.
        Assert.Equal(7, harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "First"));
        Assert.Equal(0, harness.Registry.MutationCount);
        Assert.Empty(summary.Results);
    }

    [Fact]
    public async Task FailClosed_SiLaCreacionFalla_NoMutaNada()
    {
        var harness = TestHarness.Create(restorePointFails: true);
        var actions = Actions();
        var plan = TestHarness.Plan(RestorePointContract(actions), actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, WithContext(harness, ExecutionMode.Execute));

        Assert.True(summary.Aborted);
        Assert.Contains("punto de restauración", summary.AbortedReason);
        Assert.Equal(0, harness.Registry.MutationCount);
        Assert.Empty(summary.Results);
        Assert.Empty(summary.UndoJournalEntry);
    }

    [Fact]
    public async Task FailClosed_SiElServicioLanzaAlConsultar_SeTrataComoNoDisponible()
    {
        var harness = TestHarness.Create();
        harness.RestorePoints.ThrowOnAvailability = true;
        var actions = Actions();
        var plan = TestHarness.Plan(RestorePointContract(actions), actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, WithContext(harness, ExecutionMode.Execute));

        Assert.True(summary.Aborted);
        Assert.Equal(0, harness.Registry.MutationCount);
        Assert.Empty(harness.RestorePoints.Created);
    }

    [Fact]
    public async Task AcceptNoRestorePoint_EjecutaYLoDeclaraEnElResumen()
    {
        var harness = TestHarness.Create(restorePointAvailable: false);
        var actions = Actions();
        var plan = TestHarness.Plan(RestorePointContract(actions), actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute,
            WithContext(harness, ExecutionMode.Execute, acceptNoRestorePoint: true));

        Assert.False(summary.Aborted, summary.AbortedReason);
        Assert.True(summary.RestorePointWaived);
        Assert.Null(summary.RestorePointId);
        Assert.Equal(2, summary.UndoJournalEntry.Count);
        Assert.True(summary.Mutated);
        // No se creó nada: se aceptó explícitamente no tener punto.
        Assert.Empty(harness.RestorePoints.Created);
    }

    [Fact]
    public async Task ConfirmacionRechazada_CeroMutacionesYCeroPuntos()
    {
        var harness = TestHarness.Create(confirmationApproves: false);
        var actions = Actions();
        var plan = TestHarness.Plan(RestorePointContract(actions), actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, WithContext(harness, ExecutionMode.Execute));

        Assert.True(summary.Aborted);
        Assert.Contains("Confirmación rechazada", summary.AbortedReason);
        Assert.Equal(0, harness.Registry.MutationCount);
        Assert.Empty(harness.RestorePoints.Created);
        Assert.False(summary.Confirmed);
    }

    [Fact]
    public async Task ConfirmacionSePideAntesDeCrearElPunto()
    {
        var harness = TestHarness.Create();
        var actions = Actions();
        var plan = TestHarness.Plan(RestorePointContract(actions), actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, WithContext(harness, ExecutionMode.Execute));

        Assert.False(summary.Aborted, summary.AbortedReason);
        // La disponibilidad se consulta para poder informar al usuario en la
        // petición de confirmación; la CREACIÓN va después de aprobar.
        Assert.Single(harness.Confirmations.Requests);
        Assert.Equal(ConfirmationType.Summary, harness.Confirmations.Last!.Type);
        Assert.Equal(RiskLevel.Medium, harness.Confirmations.Last!.Risk);
        Assert.Equal(1, harness.RestorePoints.CreatedCount);
        Assert.True(summary.Confirmed);
    }

    [Fact]
    public async Task CapacidadSinRequisitoDePunto_NoLoCrea()
    {
        var harness = TestHarness.Create();
        var actions = Actions();
        // Safe + SessionUndo + sin confirmación: contrato válido que NO pide punto.
        var contract = TestHarness.Contract(
            actions, risk: RiskLevel.Safe, restore: RestoreLevel.SessionUndo,
            confirmation: ConfirmationType.None);
        var plan = TestHarness.Plan(contract, actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, WithContext(harness, ExecutionMode.Execute));

        Assert.False(summary.Aborted, summary.AbortedReason);
        Assert.Null(summary.RestorePointId);
        Assert.Empty(harness.RestorePoints.Calls);
        Assert.True(harness.Confirmations.Unused);
        Assert.Equal(2, summary.UndoJournalEntry.Count);
    }

    [Fact]
    public async Task UnPuntoPorPlan_NoUnoPorAccion()
    {
        var harness = TestHarness.Create();
        var actions = new CapabilityAction[]
        {
            SetDword(1, "A", "0"),
            SetDword(2, "B", "0"),
            SetDword(3, "C", "0"),
            SetDword(4, "D", "0"),
        };
        var plan = TestHarness.Plan(IrreversibleContract(actions), actions);

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, WithContext(harness, ExecutionMode.Execute));

        Assert.False(summary.Aborted, summary.AbortedReason);
        Assert.Equal(1, harness.RestorePoints.CreatedCount);
        Assert.Equal(4, summary.Succeeded);
        Assert.Equal(4, summary.UndoJournalEntry.Count);
    }

    [Fact]
    public async Task TypeOperationName_ExigeElNombreExacto()
    {
        var contract = IrreversibleCritical();
        var actions = Actions();

        var wrong = TestHarness.Create();
        wrong.Confirmations.TypeExactName = false;
        wrong.Confirmations.TypedText = "test.irreversib";  // casi
        var planWrong = TestHarness.Plan(contract, actions);
        var rejected = await wrong.Coordinator.ExecuteAsync(
            planWrong, ExecutionMode.Execute, WithContext(wrong, ExecutionMode.Execute));

        Assert.True(rejected.Aborted);
        Assert.Contains("no es el nombre exacto", rejected.AbortedReason);
        Assert.Equal(0, wrong.Registry.MutationCount);
        Assert.Empty(wrong.RestorePoints.Created);

        var right = TestHarness.Create(typeExactName: true);
        var planRight = TestHarness.Plan(contract, actions);
        var accepted = await right.Coordinator.ExecuteAsync(
            planRight, ExecutionMode.Execute, WithContext(right, ExecutionMode.Execute));

        Assert.False(accepted.Aborted, accepted.AbortedReason);
        Assert.Equal(ConfirmationType.TypeOperationName, right.Confirmations.Last!.Type);
        Assert.Equal(1, right.RestorePoints.CreatedCount);
        Assert.Equal(2, accepted.UndoJournalEntry.Count);
    }

    private static CapabilityContract IrreversibleCritical() => new()
    {
        Id = "test.irreversible",
        Name = "test.irreversible",
        Description = "capacidad crítica de prueba",
        SectionId = 9,
        Risk = RiskLevel.Critical,
        SecurityImpact = SecurityImpact.Neutral,
        Privilege = PrivilegeLevel.User,
        Restore = RestoreLevel.None,
        Reversibility = Reversibility.Irreversible,
        Confirmation = ConfirmationType.TypeOperationName,
        State = CapabilityState.Implemented,
        Variants = [Variant.Evo],
        ConflictsWith = [],
        DependsOn = [],
        SupportedBuilds = [],
    };

    [Fact]
    public async Task RestorePointAvailable_LlegaALaConfirmacion()
    {
        var conPunto = TestHarness.Create();
        var sinPunto = TestHarness.Create(restorePointAvailable: false);
        var actions = Actions();

        var a = await conPunto.Coordinator.ExecuteAsync(
            TestHarness.Plan(RestorePointContract(actions), actions),
            ExecutionMode.Execute, WithContext(conPunto, ExecutionMode.Execute));
        var b = await sinPunto.Coordinator.ExecuteAsync(
            TestHarness.Plan(RestorePointContract(actions), actions),
            ExecutionMode.Execute, WithContext(sinPunto, ExecutionMode.Execute));

        Assert.True(conPunto.Confirmations.Last!.RestorePointAvailable);
        Assert.False(sinPunto.Confirmations.Last!.RestorePointAvailable);
        Assert.False(a.Aborted);
        // Sin punto disponible, el usuario aprobó y aun así se aborta (fail-closed).
        Assert.True(b.Aborted);
    }

    [Fact]
    public async Task SinProveedorDeConfirmacion_SeAbortaSinMutar()
    {
        var harness = TestHarness.Create();
        var actions = Actions();
        var contract = RestorePointContract(actions);
        var plan = TestHarness.Plan(contract, actions);

        // Coordinador sin proveedor de confirmación ni de puntos.
        var coordinator = new EngineCoordinator(
            harness.Environment,
            new Evo.Detection.WindowsDetector(
                harness.Environment,
                new DetectionRegistryStub(),
                Evo.Detection.Model.WindowsReleaseCatalog.LoadFromFile(
                    Path.Combine(AppContext.BaseDirectory, "catalog", "windows-releases.json"))),
            new Evo.Engine.Executors.IActionExecutor[]
            {
                new Evo.Engine.Executors.RegistryActionExecutor(),
                new Evo.Engine.Executors.ServiceActionExecutor(),
                new Evo.Engine.Executors.TaskActionExecutor(),
                new Evo.Engine.Executors.ProcessActionExecutor(),
                new Evo.Engine.Executors.CommandActionExecutor(),
            });

        var summary = await coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, harness.Context(ExecutionMode.Execute));

        Assert.True(summary.Aborted);
        Assert.Contains("No hay proveedor de confirmación", summary.AbortedReason);
        Assert.Equal(0, harness.Registry.MutationCount);
    }

    [Fact]
    public async Task RollbackAutomaticoSigueFuncionandoConPunto()
    {
        var harness = TestHarness.Create();
        harness.Registry.Seed(RegistryHive.LocalMachine, KeyPath, "First", 5);

        var failing = new CapabilityAction[]
        {
            SetDword(1, "First", "0"),
            new CommandAction
            {
                Order = 2,
                Description = "comando que falla",
                FileName = "powershell.exe",
                Arguments = ["-Command", "exit 1"],
                AllowedExitCodes = [0],
            },
        };
        var plan = TestHarness.Plan(RestorePointContract(failing), failing);
        // El fake devuelve 1: la acción falla y dispara el rollback automático.
        harness.Commands.DefaultResult = new Evo.Core.System.CommandResult
        {
            ExitCode = 1,
            StandardOutput = string.Empty,
            StandardError = "fallo simulado",
        };

        var summary = await harness.Coordinator.ExecuteAsync(
            plan, ExecutionMode.Execute, WithContext(harness, ExecutionMode.Execute));

        // Se creó el punto (antes de mutar), falló la acción 2 y el rollback
        // devolvió el registro al valor inicial.
        Assert.Equal(1, harness.RestorePoints.CreatedCount);
        Assert.Equal(1, summary.Failed);
        Assert.Equal(5, harness.Registry.GetValue(RegistryHive.LocalMachine, KeyPath, "First"));
        Assert.Empty(harness.Coordinator.Journal.Entries);
    }
}
