using Evo.Core.Actions;
using Evo.Core.Enums;
using Evo.Core.Restore;
using Evo.Core.System;
using Evo.Engine.Executors;
using Evo.Engine.Undo;
using Evo.Testing;
using Evo.Windows;
using Microsoft.Win32;
using System;
using System.Linq;
using Xunit;

namespace Evo.Windows.Tests;

/// <summary>Rollback real de RegistryDeleteKeyExecutor con WindowsRegistryAccessor sobre HKCU.</summary>
public sealed class RegistryDeleteKeyRealRollbackTest : IDisposable
{
    private readonly WindowsRegistryAccessor _registry = new();
    private readonly UndoJournal _journal = new();
    private readonly string _keyPath;
    private bool _disposed;

    public RegistryDeleteKeyRealRollbackTest()
    {
        _keyPath = $@"Software\EvoClean.Tests\{Guid.NewGuid():N}";
    }

    private static ActionContext ContextoDeEjecucion(UndoJournal journal)
    {
        return new ActionContext
        {
            Registry = new WindowsRegistryAccessor(),
            Services = new FakeServiceAccessor(),
            Tasks = new FakeTaskAccessor(),
            Processes = new FakeProcessAccessor(),
            Commands = new FakeCommandRunner(),
            Mode = ExecutionMode.Execute,
            Journal = journal,
            CapabilityId = "evo.clean.test.rollback.real",
        };
    }

    [Fact]
    public async Task BorradoReal_RestauraValores_Kinds_Y_Subclave()
    {
        var hive = RegistryHive.CurrentUser;
        var clavePadre = _keyPath;
        var claveSub = $"{clavePadre}\\Sub";

        // Siembra: clave con DWord, String, Binary y una subclave con un valor.
        _registry.SetValue(hive, clavePadre, "ValDWord", 42, RegistryValueKind.DWord);
        _registry.SetValue(hive, clavePadre, "ValStr", "hola", RegistryValueKind.String);
        _registry.SetValue(hive, clavePadre, "ValBin", new byte[] { 1, 2, 3 }, RegistryValueKind.Binary);
        _registry.EnsureKey(hive, claveSub);
        _registry.SetValue(hive, claveSub, "SubVal", 99, RegistryValueKind.DWord);

        Assert.True(_registry.KeyExists(hive, clavePadre));
        Assert.Contains("Sub", _registry.GetSubKeyNames(hive, clavePadre));

        // Ejecuta el borrado real (recursivo) sobre la clave.
        var resultado = await new RegistryDeleteKeyExecutor().ExecuteAsync(new RegistryDeleteKeyAction
        {
            Order = 1,
            Hive = RegistryHiveKind.CurrentUser,
            KeyPath = clavePadre,
            Recursive = true,
        }, ContextoDeEjecucion(_journal));

        Assert.True(resultado.Success);
        Assert.False(_registry.KeyExists(hive, clavePadre), "La clave debió desaparecer tras el borrado.");
        Assert.Single(_journal.Entries);

        // Rollback real: el deshacer recrea el árbol con valores, kinds y subclaves.
        var reporte = await _journal.RollbackAsync(new UndoContext(
            _registry, new FakeServiceAccessor(), new FakeTaskAccessor(),
            new FakeProcessAccessor(), new FakeCommandRunner()));

        Assert.True(reporte.Success);
        Assert.True(_registry.KeyExists(hive, clavePadre), "La clave debió recrearse tras el rollback.");

        // Valores restaurados.
        Assert.Equal(42, (int?)_registry.GetValue(hive, clavePadre, "ValDWord"));
        Assert.Equal("hola", _registry.GetValue(hive, clavePadre, "ValStr"));
        Assert.Equal(new byte[] { 1, 2, 3 }, (byte[])_registry.GetValue(hive, clavePadre, "ValBin"));

        // Kinds restaurados (esta es la deuda de la 6-D: antes no se comprobaban).
        Assert.Equal(RegistryValueKind.DWord, _registry.GetKind(hive, clavePadre, "ValDWord"));
        Assert.Equal(RegistryValueKind.String, _registry.GetKind(hive, clavePadre, "ValStr"));
        Assert.Equal(RegistryValueKind.Binary, _registry.GetKind(hive, clavePadre, "ValBin"));

        // Subclave restaurada con su valor.
        Assert.Contains("Sub", _registry.GetSubKeyNames(hive, clavePadre));
        Assert.Equal(99, (int?)_registry.GetValue(hive, claveSub, "SubVal"));
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
