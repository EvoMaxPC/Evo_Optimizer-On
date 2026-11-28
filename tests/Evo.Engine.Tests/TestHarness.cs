using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Models;
using Evo.Detection;
using Evo.Detection.Model;
using Evo.Engine;
using Evo.Engine.Execution;
using Evo.Engine.Executors;
using Evo.Engine.Undo;
using Evo.Testing;

namespace Evo.Engine.Tests;

/// <summary>Banco de pruebas común: fakes + coordinador con los 5 ejecutores.</summary>
internal sealed class TestHarness
{
    private TestHarness(
        FakeSystemEnvironment environment,
        FakeRegistryAccessor registry,
        FakeServiceAccessor services,
        FakeTaskAccessor tasks,
        FakeProcessAccessor processes,
        FakeCommandRunner commands,
        EngineCoordinator coordinator,
        FakeRestorePointService restorePoints,
        FakeConfirmationProvider confirmations)
    {
        Environment = environment;
        Registry = registry;
        Services = services;
        Tasks = tasks;
        Processes = processes;
        Commands = commands;
        Coordinator = coordinator;
        RestorePoints = restorePoints;
        Confirmations = confirmations;
    }

    public FakeSystemEnvironment Environment { get; }

    public FakeRegistryAccessor Registry { get; }

    public FakeServiceAccessor Services { get; }

    public FakeTaskAccessor Tasks { get; }

    public FakeProcessAccessor Processes { get; }

    public FakeCommandRunner Commands { get; }

    public EngineCoordinator Coordinator { get; }

    /// <summary>Punto de restauración falso (disponible y con éxito por defecto).</summary>
    public FakeRestorePointService RestorePoints { get; }

    /// <summary>Confirmación falsa (aprueba por defecto).</summary>
    public FakeConfirmationProvider Confirmations { get; }

    public static TestHarness Create(
        bool admin = true,
        int build = 26100,
        IEnumerable<CapabilityContract>? catalog = null,
        bool restorePointAvailable = true,
        bool restorePointFails = false,
        bool confirmationApproves = true,
        bool typeExactName = true)
    {
        var environment = new FakeSystemEnvironment
        {
            CurrentBuild = build,
            UBR = 3915,
            InstallationType = "Client",
            EditionID = "Professional",
            Architecture = "x64",
            IsAdmin = admin,
            IsElevated = admin,
        };

        var catalogPath = Path.Combine(AppContext.BaseDirectory, "catalog", "windows-releases.json");
        var detector = new WindowsDetector(
            environment,
            new DetectionRegistryStub(),
            WindowsReleaseCatalog.LoadFromFile(catalogPath));

        var registry = new FakeRegistryAccessor();
        var services = new FakeServiceAccessor();
        var tasks = new FakeTaskAccessor();
        var processes = new FakeProcessAccessor();
        var commands = new FakeCommandRunner();
        var restorePoints = new FakeRestorePointService
        {
            Available = restorePointAvailable,
            FailOnCreate = restorePointFails,
        };
        var confirmations = new FakeConfirmationProvider
        {
            Approve = confirmationApproves,
            TypeExactName = typeExactName,
        };

        var coordinator = new EngineCoordinator(
            environment,
            detector,
            new IActionExecutor[]
            {
                new RegistryActionExecutor(),
                new ServiceActionExecutor(),
                new TaskActionExecutor(),
                new ProcessActionExecutor(),
                new CommandActionExecutor(),
                new RegistryDeleteKeyExecutor(),
                new TaskCreateExecutor(),
                new RegistryCreateKeyExecutor(),
            },
            catalog,
            restorePoints,
            confirmations);

        return new TestHarness(
            environment, registry, services, tasks, processes, commands, coordinator,
            restorePoints, confirmations);
    }

    /// <summary>Contexto que el motor usa para leer el entorno real (los fakes).</summary>
    public ActionContext Context(ExecutionMode mode) => new()
    {
        Registry = Registry,
        Services = Services,
        Tasks = Tasks,
        Processes = Processes,
        Commands = Commands,
        Mode = mode,
        Journal = new UndoJournal(),
        CapabilityId = "test",
    };

    /// <summary>Contrato de prueba con las acciones dadas.</summary>
    public static CapabilityContract Contract(
        IEnumerable<CapabilityAction> actions,
        string id = "test.capability",
        RiskLevel risk = RiskLevel.Medium,
        PrivilegeLevel privilege = PrivilegeLevel.User,
        RestoreLevel restore = RestoreLevel.RestorePoint,
        ConfirmationType? confirmation = null,
        IReadOnlyList<string>? dependsOn = null,
        IReadOnlyList<string>? conflictsWith = null,
        IReadOnlyList<int>? supportedBuilds = null) => new()
        {
            Id = id,
            Name = id,
            Description = "capacidad de prueba",
            SectionId = 9,
            Risk = risk,
            SecurityImpact = SecurityImpact.Neutral,
            Privilege = privilege,
            Restore = restore,
            Reversibility = Reversibility.Reversible,
            Confirmation = confirmation ?? CapabilityRules.MinimumConfirmation(risk),
            State = CapabilityState.Implemented,
            Variants = [Variant.Evo],
            ConflictsWith = conflictsWith ?? [],
            DependsOn = dependsOn ?? [],
            SupportedBuilds = supportedBuilds ?? [],
        };

    /// <summary>Plan a partir del contrato y las acciones.</summary>
    public static ExecutionPlan Plan(CapabilityContract contract, IEnumerable<CapabilityAction> actions) =>
        new(contract, actions.Select(a => new PlannedStep
        {
            Order = a.Order,
            Description = a.Description,
            Action = a,
        }));
}

/// <summary>Accesor de registro mínimo para el detector (sin valores).</summary>
internal sealed class DetectionRegistryStub : Evo.Core.System.IRegistryAccessor
{
    public object? GetValue(Microsoft.Win32.RegistryHive hive, string keyPath, string valueName) => null;

    public void SetValue(Microsoft.Win32.RegistryHive hive, string keyPath, string valueName, object value,
        Microsoft.Win32.RegistryValueKind kind)
    {
    }

    public bool DeleteValue(Microsoft.Win32.RegistryHive hive, string keyPath, string valueName) => false;

    public bool KeyExists(Microsoft.Win32.RegistryHive hive, string keyPath) => false;

    public bool DeleteKey(Microsoft.Win32.RegistryHive hive, string keyPath, bool recursive) => false;
}
