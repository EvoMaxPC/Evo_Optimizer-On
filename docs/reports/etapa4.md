# Informe ETAPA 6-D — Paso 4: caso del motor real con `WindowsRegistryAccessor` (Evo.Windows.Tests)

## Tabla de Evo.Windows.Tests (run 46082726973, sha `7ef772f49b616a3e309655f021d5778ae459cee0`, ambos runners)

| Test (clase.método) | Línea declarada | Resultado en test-console.txt (windows-2025) | Resultado en test-console.txt (windows-11-arm) | Veredicto |
|---|---|---|---|---|
| Evo.Windows.Tests.WindowsAccessorsTests.Registry_Roundtrip_AllSupportedKinds | 46 | Passed [30 ms] | Passed [53 ms] | PASA |
| Evo.Windows.Tests.WindowsAccessorsTests.Registry_DefaultValue_EmptyName | 69 | Passed [< 1 ms] | Passed [< 1 ms] | PASA |
| Evo.Windows.Tests.WindowsAccessorsTests.Registry_Binary_ZeroAndFF | 78 | Passed [1 ms] | Passed [1 ms] | PASA |
| Evo.Windows.Tests.WindowsAccessorsTests.Registry_ExpandString_NotExpanded | 88 | Passed [< 1 ms] | Passed [< 1 ms] | PASA |
| Evo.Windows.Tests.WindowsAccessorsTests.Registry_MissingKeyAndValue_ReturnNull | 96 | Passed [< 1 ms] | Passed [< 1 ms] | PASA |
| Evo.Windows.Tests.WindowsAccessorsTests.Registry_NestedKey_AncestorsCreated | 105 | Passed [1 ms] | Passed [1 ms] | PASA |
| Evo.Windows.Tests.WindowsAccessorsTests.RegistryDeleteKey_RealExecutor_RollbackRestoresTree | 118 | Passed [15 ms] | Passed [14 ms] | PASA |
| Evo.Windows.Tests.WindowsAccessorsTests.Service_EventLog_ReadOnly | 167 | Passed [708 ms] | Passed [457 ms] | PASA |
| Evo.Windows.Tests.WindowsAccessorsTests.Service_MissingService_NoException | 177 | Passed [7 ms] | Passed [6 ms] | PASA |
| Evo.Windows.Tests.WindowsAccessorsTests.Process_StartAndTerminate_Ping | 188 | Passed [239 ms] | Passed [29 ms] | PASA |
| Evo.Windows.Tests.EngineCoordinatorRealTest.Motor_Real_Escribe_Y_Deshace_En_HKCU | 147 | Passed [50 ms] | Passed [42 ms] | PASA |

Todos los 11 tests de `Evo.Windows.Tests` aparecen como `Passed` en el `test-console.txt` literal de ambos runners → **PASA**. No hay `Failed` ni `Skipped`.

Líneas declaradas obtenidas con `grep -n "\[Fact\]\|public async Task\|public void " tests/Evo.Windows.Tests/*.cs`. Un test cuenta como PASA solo si su nombre completo aparece precedido de `  Passed ` en test-console.txt; de lo contrario es NO VERIFICADO. Todos aparecen.

## Diff de src/Evo.Windows y src/Evo.Engine

Rango comparado: `ed6457e94f2f9b63696dfdb1e43106fc02cb3406` .. `550cfb01e3ba61f5291644eb39e42e517e72cd93`.

```
git diff --stat ... -- src/Evo.Windows/
```
→ (sin salida: **0 archivos**, sin cambios en src/Evo.Windows en ese rango).

```
git diff --stat ... -- src/Evo.Engine/
```
→ 6 archivos, 185 insertions, 70 deletions:
```
 src/Evo.Engine/EngineCoordinator.cs                |   4 +-
 src/Evo.Engine/Execution/ExecutionModels.cs        |   3 +-
 src/Evo.Engine/Executors/ProcessActionExecutor.cs  |  29 ++++--
 src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs | 112 +++++++++++++++------
 src/Evo.Engine/Executors/TaskCreateExecutor.cs     |  46 ++++--
 src/Evo.Engine/Undo/UndoJournal.cs                 |  61 ++++++++---
```

## Código con `nl -ba`

### src/Evo.Windows/WindowsRegistryAccessor.cs (170 líneas)

Leído completo (archivo en workspace). Extractos relevantes:

- `GetValue` (líneas 37-43): abre lectura, devuelve `key.GetValue(valueName, null, ...)` o `null` si la clave no existe. No traga excepciones explícitamente; `OpenRead` puede lanzar si no hay permisos.
- `SetValue` (líneas 45-55): valida `SupportedKinds`, abre escritura y llama `key.SetValue(...)`. No tiene `try/catch`: deja pasar `SecurityException`/`UnauthorizedAccessException` de permisos.
- `GetKind` (líneas 149-153): **SÍ traga excepciones** (bloqueo `try { return key.GetValueKind(valueName); } catch { return RegistryValueKind.Unknown; }`). Cualquier excepción de permisos se convierte en `Unknown` sin informar.

### src/Evo.Windows/WindowsProcessAccessor.cs (76 líneas)

Leído completo. `TerminateProcess` tiene `try/catch` vacío alrededor de `process.Kill()` (línea ~50). `StartProcess` tiene `try/catch` vacío que devuelve `-1` (línea ~67).

### Método `SetStartupType` de src/Evo.Windows/WindowsServiceAccessor.cs (líneas 73-95)

```
73:     public void SetStartupType(string serviceName, ServiceStartupType startupType)
74:     {
75:         var keyPath = $"{ServicesBase}\\{serviceName}";
76:         switch (startupType)
77:         {
78:             case ServiceStartupType.Automatic:
79:                 _registry.SetValue(RegistryHive.LocalMachine, keyPath, "Start", 2, RegistryValueKind.DWord);
80:                 _registry.SetValue(RegistryHive.LocalMachine, keyPath, "DelayedAutostart", 0, RegistryValueKind.DWord);
81:                 break;
82:             case ServiceStartupType.AutomaticDelayed:
83:                 _registry.SetValue(RegistryHive.LocalMachine, keyPath, "Start", 2, RegistryValueKind.DWord);
84:                 _registry.SetValue(RegistryHive.LocalMachine, keyPath, "DelayedAutostart", 1, RegistryValueKind.DWord);
85:                 break;
86:             case ServiceStartupType.Manual:
87:                 _registry.SetValue(RegistryHive.LocalMachine, keyPath, "Start", 3, RegistryValueKind.DWord);
88:                 break;
89:             case ServiceStartupType.Disabled:
90:                 _registry.SetValue(RegistryHive.LocalMachine, keyPath, "Start", 4, RegistryValueKind.DWord);
91:                 break;
92:             case ServiceStartupType.Boot:
93:             case ServiceStartupType.System:
94:             default:
95:                 throw new NotSupportedException($"Tipo de arranque no soportado para escritura: {startupType}.");
96:         }
97:     }
```

**Confirmación de escritura en HKLM:** Dentro de `WindowsServiceAccessor`, la escritura en `HKLM` (`RegistryHive.LocalMachine` en las rutas `SYSTEM\CurrentControlSet\Services\<nombre>\Start` y `DelayedAutostart`) ocurre **solo dentro de `SetStartupType`** (líneas 79, 80, 83, 84, 87, 90). `GetStartupType` (líneas 55-70) solo lee (`_registry.GetValue`). `GetStatus` (líneas 28-43) usa `ServiceController` y **traga excepciones** (`catch { return ServiceStatus.Unknown; }`, línea 42).

**Nota sobre el accesor de registro:** La afirmación "el accesor de registro no traga excepciones de permisos" es **parcialmente falsa**. `WindowsRegistryAccessor.GetKind` (líneas 149-153) tiene `try/catch` vacío que devuelve `RegistryValueKind.Unknown` ante cualquier excepción, incluidas de permisos. Los métodos de escritura (`SetValue`, `DeleteValue`, `DeleteKey`, `EnsureKey`) no tienen `try/catch` y dejan pasar excepciones de permisos del .NET.

## Assert literal del test de RegistryDeleteKeyExecutor real

Archivo: `tests/Evo.Engine.Tests/ExecutorTests.cs`, test `RegistryDeleteKey_ArbolCompleto_RestoreRecreaTodo` (líneas 695-720).

```
711:        Assert.False(harness.Registry.KeyExists(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test"));
718:        Assert.Single(report.Restored);
719:        Assert.True(harness.Registry.KeyExists(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test"));
720:        Assert.Equal(1, (int?)harness.Registry.GetValue(RegistryHive.LocalMachine, @"SOFTWARE\Evo\Test", "Val1"));
```

Tras el rollback se comparan:
- existencia de la clave (líneas 711 antes de borrar, 719 tras rollback) → **sí**.
- valor restaurado (línea 720: `GetValue(...,"Val1") == 1`) → **sí**.

**NO CUMPLIDO** para "kinds y subclaves": no hay `Assert` que compare `GetValueKind` (kinds) ni la existencia/contenido de subclaves tras el rollback en este test. Solo se verifica existencia de clave y un valor.
