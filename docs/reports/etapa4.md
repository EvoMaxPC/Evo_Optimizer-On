# Informe ETAPA 6-C — Paso 4: caso del motor real con `WindowsRegistryAccessor`

## Objetivo

Añadir un test de integración del motor real (`EngineCoordinator`) que ejecute y deshaga acciones reales sobre el registro de Windows (`HKEY_CURRENT_USER`) usando `WindowsRegistryAccessor` (acceso real, no fake), dentro de `tests/Evo.Windows.Tests`.

## Archivos tocados

| Archivo | Cambio | Líneas |
|---|---|---|
| `tests/Evo.Windows.Tests/Evo.Windows.Tests.csproj` | Añadida referencia a `Evo.Testing.csproj` (para `FakeRestorePointService`, `FakeConfirmationProvider`, `FakeCommandRunner` en el test del motor real). | +1 referencia |
| `tests/Evo.Windows.Tests/EngineCoordinatorRealTest.cs` | **Nuevo.** Test `Motor_Real_Escribe_Y_Deshace_En_HKCU` que escribe un `DWord` y un `String` en `HKCU` mediante `RegistryActionExecutor` + `WindowsRegistryAccessor`, verifica la aplicación real y luego hace `RollbackAsync` comprobando que los valores vuelven a su estado original (ausentes). | 203 nuevas |

## Cómo se construye el test

- `FakeSystemEnvironment` (build 26100, Client, x64, admin+elevado) + `WindowsReleaseCatalog` con release build 26100 → `WindowsDetector` que reporta sistema compatible.
- `EngineCoordinator` con los ejecutores reales (`RegistryActionExecutor`, `ServiceActionExecutor`, `TaskActionExecutor`, `ProcessActionExecutor`, `CommandActionExecutor`, `RegistryDeleteKeyExecutor`, `TaskCreateExecutor`, `RegistryCreateKeyExecutor`), `FakeRestorePointService { Available = true }`, `FakeConfirmationProvider { Approve = true }`.
- `ActionContext` con `Registry = WindowsRegistryAccessor` (real sobre HKCU), `Journal = coordinator.Journal`, modo `Execute`.
- Capacidad de prueba: `Risk=Safe`, `Privilege=User`, `Restore=SessionUndo`, `Reversibility=Reversible`, `SectionId=1`, `SupportedBuilds=[26100]`, `Variants=[Evo]` — contrato válido según `CapabilityRules.Validate` (evita que el preflight bloquee).
- Acciones: `RegistryAction` `Set` DWord `ValorDWord=42` y `RegistryAction` `Set` String `ValorTexto=hola`, ambas sobre `HKCU\<clave única por test>`.
- `Dispose()` borra la clave de prueba de HKCU (recursiva) para no dejar basura.

## Afirmaciones

1. `summary.Blocked == false` (el preflight permite la ejecución).
2. `summary.Aborted == false`.
3. `summary.Succeeded == 2` (ambas acciones de registro aplicadas).
4. Tras `ExecuteAsync`: `HKCU\<clave>\ValorDWord == 42` y `ValorTexto == "hola"` (escritura real en Windows).
5. Tras `RollbackAsync`: `ValorDWord` y `ValorTexto` son `null` (deshacer real).

## Resultado CI (HEAD `7ef772f4`, push 5)

- `dotnet-ci` (windows-2025 y windows-11-arm): **success**. `Evo.Windows.Tests`: 11 tests, 10 passed + este nuevo passing (el anterior push falló por `Reversible`+`Restore=None` bloqueado por `ValidateReversibility`; se corrigió a `Restore=SessionUndo`, `SectionId=1`).
- `ledger-verify`: **success**.
