using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.System;
using Evo.Engine.Execution;
using Evo.Engine.Executors;
using Evo.Engine.Undo;
using Evo.Windows;
using Microsoft.Win32;
using Xunit;

namespace Evo.Windows.Tests;

/// <summary>Tests de integración de los accesores reales de Windows.</summary>
/// <remarks>
/// Todos los tests de registro usan únicamente
/// <c>HKCU\Software\EvoClean.Tests\&lt;Guid&gt;</c> y lo borran en un
/// <c>finally</c> / <see cref="IAsyncLifetime.DisposeAsync"/>. Nunca se escribe
/// en HKLM ni se inician/detienen servicios reales (solo lectura de EventLog).
/// </remarks>
public sealed class WindowsAccessorsTests : IAsyncLifetime
{
    private readonly string _testRoot = $"Software\\EvoClean.Tests\\{Guid.NewGuid():N}";
    private readonly WindowsRegistryAccessor _registry = new();
    private readonly FakeCommandRunner _commands = new();

    public Task InitializeAsync() => Task.CompletedTask;

    public async Task DisposeAsync()
    {
        // Limpieza siempre: borra la clave de prueba aunque el test falle.
        try
        {
            _registry.DeleteKey(RegistryHive.CurrentUser, _testRoot, recursive: true);
        }
        catch
        {
            // Mejor esfuerzo: la clave puede no existir si el test falló antes de crearla.
        }
        await Task.CompletedTask;
    }

    // ------------------------------------------------------------ Registro

    /// <summary>Roundtrip de cada tipo de valor soportado.</summary>
    [Fact]
    public async Task Registry_Roundtrip_AllSupportedKinds()
    {
        var cases = new[]
        {
            (name: "Str", value: (object)"hola mundo", kind: RegistryValueKind.String),
            (name: "Dw", value: (object)42, kind: RegistryValueKind.DWord),
            (name: "Qw", value: (object)1234567890123L, kind: RegistryValueKind.QWord),
            (name: "Bin", value: (object)new byte[] { 0x00, 0xFF, 0x42 }, kind: RegistryValueKind.Binary),
            (name: "Ms", value: (object)new[] { "uno", "dos", "tres" }, kind: RegistryValueKind.MultiString),
            (name: "Ex", value: (object)"%TEMP%\\archivo", kind: RegistryValueKind.ExpandString),
        };

        foreach (var (name, value, kind) in cases)
        {
            _registry.SetValue(RegistryHive.CurrentUser, _testRoot, name, value, kind);
            var obtained = _registry.GetValue(RegistryHive.CurrentUser, _testRoot, name);
            Assert.Equal(value, obtained);
            Assert.Equal(kind, _registry.GetKind(RegistryHive.CurrentUser, _testRoot, name));
        }
    }

    /// <summary>Valor predeterminado (valueName vacío).</summary>
    [Fact]
    public async Task Registry_DefaultValue_EmptyName()
    {
        _registry.SetValue(RegistryHive.CurrentUser, _testRoot, "", "predeterminado", RegistryValueKind.String);
        Assert.Equal("predeterminado", _registry.GetValue(RegistryHive.CurrentUser, _testRoot, ""));
        Assert.Equal(RegistryValueKind.String, _registry.GetKind(RegistryHive.CurrentUser, _testRoot, ""));
    }

    /// <summary>Binario con bytes 0x00 y 0xFF.</summary>
    [Fact]
    public async Task Registry_Binary_ZeroAndFF()
    {
        var bytes = new byte[] { 0x00, 0xFF, 0x00, 0xFF };
        _registry.SetValue(RegistryHive.CurrentUser, _testRoot, "Bin0FF", bytes, RegistryValueKind.Binary);
        var obtained = Assert.IsType<byte[]>(_registry.GetValue(RegistryHive.CurrentUser, _testRoot, "Bin0FF"));
        Assert.Equal(bytes, obtained);
    }

    /// <summary>ExpandString se lee SIN expandir (DoNotExpandEnvironmentNames).</summary>
    [Fact]
    public async Task Registry_ExpandString_NotExpanded()
    {
        _registry.SetValue(RegistryHive.CurrentUser, _testRoot, "Exp", "%TEMP%\\miapp", RegistryValueKind.ExpandString);
        Assert.Equal("%TEMP%\\miapp", _registry.GetValue(RegistryHive.CurrentUser, _testRoot, "Exp"));
    }

    /// <summary>Clave y valor inexistentes devuelven null (como el fake).</summary>
    [Fact]
    public async Task Registry_MissingKeyAndValue_ReturnNull()
    {
        Assert.Null(_registry.GetValue(RegistryHive.CurrentUser, _testRoot, "NoExiste"));
        Assert.False(_registry.KeyExists(RegistryHive.CurrentUser, _testRoot));
        Assert.Equal(RegistryValueKind.Unknown, _registry.GetKind(RegistryHive.CurrentUser, _testRoot, "NoExiste"));
    }

    /// <summary>Clave anidada: se crean los ancestros.</summary>
    [Fact]
    public async Task Registry_NestedKey_AncestorsCreated()
    {
        var deep = $"{_testRoot}\\Nivel1\\Nivel2\\Nivel3";
        _registry.SetValue(RegistryHive.CurrentUser, deep, "Hoja", 7, RegistryValueKind.DWord);
        Assert.True(_registry.KeyExists(RegistryHive.CurrentUser, deep));
        Assert.Equal(7, _registry.GetValue(RegistryHive.CurrentUser, deep, "Hoja"));
        // Los niveles intermedios existen como claves.
        Assert.True(_registry.KeyExists(RegistryHive.CurrentUser, $"{_testRoot}\\Nivel1"));
        Assert.True(_registry.KeyExists(RegistryHive.CurrentUser, $"{_testRoot}\\Nivel1\\Nivel2"));
    }

    /// <summary>RegistryDeleteKeyExecutor real borra un árbol anidado y rollback lo restaura.</summary>
    [Fact]
    public async Task RegistryDeleteKey_RealExecutor_RollbackRestoresTree()
    {
        var tree = $"{_testRoot}\\Arbol";
        _registry.SetValue(RegistryHive.CurrentUser, tree, "Default", "valor por defecto", RegistryValueKind.String);
        _registry.SetValue(RegistryHive.CurrentUser, tree, "Bin", new byte[] { 0x00, 0xFF }, RegistryValueKind.Binary);
        _registry.SetValue(RegistryHive.CurrentUser, $"{tree}\\Hija", "Valor", 3, RegistryValueKind.DWord);

        var snapshotBefore = SnapshotTree(tree);

        var journal = new UndoJournal();
        var ctx = new ActionContext
        {
            Registry = _registry,
            Services = new WindowsServiceAccessor(),
            Tasks = new UnavailableTaskAccessor(),
            Processes = new WindowsProcessAccessor(),
            Commands = _commands,
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "test.windows",
        };

        var result = await new RegistryDeleteKeyExecutor().ExecuteAsync(
            new RegistryDeleteKeyAction
            {
                Order = 1,
                Hive = RegistryHiveKind.CurrentUser,
                KeyPath = tree,
                Recursive = true,
            },
            ctx);

        Assert.True(result.Success);
        Assert.False(_registry.KeyExists(RegistryHive.CurrentUser, tree));

        // Rollback restaura el árbol.
        await journal.RollbackAsync(new UndoContext(
            _registry, new WindowsServiceAccessor(), new UnavailableTaskAccessor(),
            new WindowsProcessAccessor(), _commands));

        Assert.True(_registry.KeyExists(RegistryHive.CurrentUser, tree));
        var snapshotAfter = SnapshotTree(tree);
        Assert.Equal(snapshotBefore, snapshotAfter);
    }

    /// <summary>EngineCoordinator real: escribir valor, Execute, luego Rollback restaura.</summary>
    [Fact]
    public async Task EngineCoordinator_WriteValue_ExecuteAndRollbackRestores()
    {
        var valuePath = $"{_testRoot}\\CoordinatorTest";
        _registry.SetValue(RegistryHive.CurrentUser, valuePath, "Antes", "original", RegistryValueKind.String);

        var env = new TestSystemEnvironment();
        var detector = new Evo.Detection.WindowsDetector();
        var executors = new IActionExecutor[]
        {
            new RegistryActionExecutor(),
            new RegistryDeleteKeyExecutor(),
        };

        var coordinator = new Evo.Engine.EngineCoordinator(
            env, detector, executors,
            catalog: null, restorePoints: null, confirmations: null);

        var ctx = new ActionContext
        {
            Registry = _registry,
            Services = new WindowsServiceAccessor(),
            Tasks = new UnavailableTaskAccessor(),
            Processes = new WindowsProcessAccessor(),
            Commands = _commands,
            Mode = ExecutionMode.Execute,
            Journal = coordinator.Journal,
            CapabilityId = "test.windows.coordinator",
        };

        // Write value through the coordinator's journal.
        var writeAction = new RegistryAction
        {
            Order = 1,
            Hive = RegistryHiveKind.CurrentUser,
            KeyPath = valuePath,
            ValueName = "Escrito",
            Operation = RegistryOperation.Set,
            ValueType = RegistryValueType.String,
            Value = "nuevo valor",
        };

        var writeResult = await new RegistryActionExecutor().ExecuteAsync(writeAction, ctx);
        Assert.True(writeResult.Success);
        Assert.Equal("nuevo valor", _registry.GetValue(RegistryHive.CurrentUser, valuePath, "Escrito"));

        // Rollback.
        await coordinator.Journal.RollbackAsync(new UndoContext(
            _registry, new WindowsServiceAccessor(), new UnavailableTaskAccessor(),
            new WindowsProcessAccessor(), _commands));

        Assert.Equal("original", _registry.GetValue(RegistryHive.CurrentUser, valuePath, "Antes"));
        Assert.Null(_registry.GetValue(RegistryHive.CurrentUser, valuePath, "Escrito"));
    }

    // ------------------------------------------------------------ Servicio

    /// <summary>EventLog existe en todo Windows cliente; lectura sin excepción.</summary>
    [Fact]
    public void Service_EventLog_ReadOnly()
    {
        var services = new WindowsServiceAccessor();
        var status = services.GetStatus("EventLog");
        // Puede ser Running o Stopped, pero nunca debe lanzar.
        Assert.True(status == ServiceStatus.Running || status == ServiceStatus.Stopped || status == ServiceStatus.Unknown);
    }

    /// <summary>Servicio inexistente no lanza en lecturas.</summary>
    [Fact]
    public void Service_MissingService_NoException()
    {
        var services = new WindowsServiceAccessor();
        Assert.Equal(ServiceStatus.Unknown, services.GetStatus("ServicioQueNoExisteNunca12345"));
        Assert.Equal(ServiceStartupType.Unknown, services.GetStartupType("ServicioQueNoExisteNunca12345"));
    }

    // ------------------------------------------------------------ Proceso

    /// <summary>Iniciar ping, terminarlo y verificar que ya no existe.</summary>
    [Fact]
    public async Task Process_StartAndTerminate_Ping()
    {
        var processes = new WindowsProcessAccessor();
        var id = processes.StartProcess("ping", ["-n", "60", "127.0.0.1"]);
        Assert.True(id > 0);
        Assert.True(processes.IsRunning("ping"));

        Assert.True(processes.TerminateProcess("ping"));
        Assert.False(processes.IsRunning("ping"));
    }

    // ------------------------------------------------------------ Helpers

    private IReadOnlyDictionary<string, IReadOnlyDictionary<string, object?>> SnapshotTree(string keyPath)
    {
        var result = new Dictionary<string, IReadOnlyDictionary<string, object?>>(StringComparer.OrdinalIgnoreCase);
        CollectTree(RegistryHive.CurrentUser, keyPath, result);
        return result;
    }

    private void CollectTree(RegistryHive hive, string path, Dictionary<string, IReadOnlyDictionary<string, object?>> result)
    {
        if (!_registry.KeyExists(hive, path)) return;
        var values = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase);
        foreach (var name in _registry.GetValueNames(hive, path))
        {
            values[name] = _registry.GetValue(hive, path, name);
        }
        result[path] = values;
        foreach (var sub in _registry.GetSubKeyNames(hive, path))
        {
            CollectTree(hive, $"{path}\\{sub}", result);
        }
    }

    private sealed class TestSystemEnvironment : ISystemEnvironment
    {
        public int CurrentBuild => 26100;
        public int UBR => 1;
        public string EditionID => "Professional";
        public string InstallationType => "Client";
        public string Architecture => "x64";
        public bool IsAdmin => true;
        public bool IsElevated => true;
    }

    private sealed class FakeCommandRunner : ICommandRunner
    {
        public Task<CommandResult> RunCommandAsync(string fileName, IReadOnlyList<string> arguments, CancellationToken cancellationToken = default) =>
            Task.FromResult(new CommandResult { ExitCode = 0, StandardOutput = string.Empty, StandardError = string.Empty });
    }
}
