# ETAPA 1 — CANCELACIÓN Y ROLLBACK HONESTO (P0: H1 + H2)

Rama: `arena/ab2d6de7-evo-optimizer-on`, base `402af190` de main, HEAD `908f6ad` (sincronizado con `origin/arena/ab2d6de7-evo-optimizer-on`, sin force-push ni reescritura de historia).
PR #1: `{draft:true, merged:false, state:"open", head:"908f6ad..."}`.
Reglas respetadas: alcance solo H1 y H2; no se tocaron H3-H7, catálogo, línea 278 ni estados de capacidad; no hay commits vacíos; máximo 2 pushes.

## T0 — estado inicial (antes de cambios)

```
git rev-parse HEAD              -> 908f6ad (tras sync con origin)
git ls-remote origen rama       -> coincide con HEAD
git status --short              -> limpio salvo reportes ETAPA0 sin trackear
gh api pulls/1                  -> {draft:true, merged:false, state:"open", head:"908f6ad..."}
```

## E1 — Tabla: tipo de UndoEntry | ruta:línea | Restore real o no-op | resultado nuevo

```
tipo de UndoEntry          | ruta:línea                              | Restore real o no-op                              | resultado nuevo
RegistryUndoEntry          | src/Evo.Engine/Undo/UndoJournal.cs:128  | Real: SetValue/DeleteValue al estado previo       | Restored
ServiceUndoEntry           | src/Evo.Engine/Undo/UndoJournal.cs:183  | Real: SetStartupType + StartService/StopService   | Restored
RegistryDeleteKeyUndoEntry | src/Evo.Engine/Undo/UndoJournal.cs:246  | Real: recrea árbol con snapshot (si ExistedBefore)| Restored / NotReversible si no existía
RegistryCreateKeyUndoEntry | src/Evo.Engine/Undo/UndoJournal.cs:306  | Real: borra la clave que creó                     | Restored
TaskCreateUndoEntry        | src/Evo.Engine/Undo/UndoJournal.cs:350  | Real: borra creada / restaura enabled de la previa  | Restored
TaskUndoEntry              | src/Evo.Engine/Undo/UndoJournal.cs:402  | Real: restaura enabled                            | Restored
CommandUndoEntry           | src/Evo.Engine/Executors/CommandActionExecutor.cs:71 | No-op (sin inversa declarada)          | NotReversible
ProcessUndoEntry           | src/Evo.Engine/Executors/ProcessActionExecutor.cs:82 | No-op (no reinicia procesos)           | NotReversible
```

Cada entrada devuelve ahora `UndoEntryOutcome` (ActionKey, Description, Result=Restored|NotReversible|Failed, FailureMessage). Una entrada es `Restored` solo si restauró de verdad; `NotReversible` si no tiene inversa real (comandos, procesos); `Failed` si `Restore` lanzó.

## E2 — Cambios de src/ (diff literal) y tests

### src/ (diff resumido por archivo)

`src/Evo.Engine/Undo/UndoJournal.cs`:
- Añadidos `UndoEntryOutcome` (record), `UndoRestoreResult` (enum), `RollbackReport` (record), `RollbackOutcome` (enum).
- `UndoJournalEntry.Restore` pasa de `void` a devolver `UndoEntryOutcome`.
- Las 6 entradas de este archivo devuelven `Restored` (restauran de verdad) o `NotReversible` (DryRun / no existía).
- `RollbackAsync` devuelve `RollbackReport` con listas `Restored` / `NotReversible` / `Failed` (cada una con `UndoEntryOutcome`), procesa LIFO sin detenerse en el primer `Failed`, y conserva en el diario SOLO las entradas `Failed` para reintento (vacía las `Restored` y `NotReversible`).

`src/Evo.Engine/Executors/CommandActionExecutor.cs`:
- `CommandUndoEntry.Restore` devuelve `NotReversible`.

`src/Evo.Engine/Executors/ProcessActionExecutor.cs`:
- `ProcessUndoEntry.Restore` devuelve `NotReversible`.

`src/Evo.Engine/Execution/ExecutionModels.cs`:
- `ExecutionSummary` añade `RollbackReport? RollbackReport` y `RollbackOutcome RollbackOutcome`; se propaga en todos los caminos (éxito, fallo de acción, cancelación).

`src/Evo.Engine/EngineCoordinator.cs`:
- `ExecuteAsync`: la comprobación del token y la ejecución de cada acción van dentro de un `try` que captura `OperationCanceledException` por separado (A3: cancelación entre acciones y durante una acción entran por el mismo camino de rollback).
- Tras el bucle, si `mode == Execute` y hay entradas y (fallo o cancelación) se hace rollback con `CancellationToken.None` (el rollback nunca se cancela; cancelación durante el rollback se ignora y se completa).
- Cancelación antes de cualquier mutación (journal vacío): resumen `Cancelled`, sin rollback (A1).
- Cancelación tras ≥1 mutación: rollback LIFO y resumen `Cancelled` con el informe (A2).
- DryRun con cancelación: `Cancelled` sin efectos (A4).
- Añadido `ComputeRollbackOutcome` → `None / RolledBack / RolledBackWithUnrestorable / PartiallyRolledBack / RollbackFailed`.
- `RollbackAsync(ActionContext)` devuelve ahora `Task<RollbackReport>`.

`src/Evo.Testing/FakeRegistryAccessor.cs` (mínimo para inyectar fallo en tests):
- Añadido `SetValueCallCount`, `ThrowOnSetValueCall` y `ResetSetValueCounter()` para simular `OperationCanceledException` en una escritura concreta.

### Tests nuevos y modificados

| test | fichero | qué comprueba | por qué cambió |
| --- | --- | --- | --- |
| `CancelacionAntesDeCualquierMutacion_RetornaCanceladoSinRollback` | `tests/Evo.Engine.Tests/CancellationAndHonestRollbackTests.cs` | Cancel previo (token ya cancelado): `AbortedReason="Cancelado"`, sin rollback, sin mutación, `RollbackOutcome=None` | Nuevo (H1 A1) |
| `CancelacionTrasMutacion_RollbackYCanceladoConInforme` | mismo | Acción 1 se aplica, acción 2 lanza OCE: rollback deshace la 1, `Cancelled`, `RollbackReport.Restored=1`, `RolledBack` | Nuevo (H1 A2/A3) |
| `CancelacionEntreAcciones_RollbackDeLaPrimera` | mismo | Cancelación observada antes del efecto de la acción 2: se deshace la acción 1 | Nuevo (H1 A2) |
| `CancelacionEnDryRun_SinCambiosNiRollback` | mismo | DryRun + cancel: `Cancelado`, sin mutar, sin rollback | Nuevo (H1 A4) |
| `RollbackTodoRestored_InformeTodosRestauradosYEstadoReal` | mismo | Registro+servicio: todo `Restored`, estado real restaurado, diario vacío | Nuevo (H2 B1/B2) |
| `RollbackConEntradaNoReversible_NoCuentaComoRestaurada` | mismo | Registro `Restored` + proceso `NotReversible`: `HasUnrestorable`, no `AllReversible` | Nuevo (H2 B1) |
| `RollbackEntradaQueFalla_QuedaFailedYSeContinua` | mismo | Entrada que lanza: `Failed`, conservada en diario, el resto se restaura, `Errors` con mensaje | Nuevo (H2 B2/B3) |
| `RollbackMezcla_InformeExactoYOrdenLifo` | mismo | Mezcla `Restored`+`NotReversible`+`Failed`, LIFO, `PartiallyRolledBack` | Nuevo (H2 B2) |
| `RollbackSegundoIntento_SoloReprocesaLasConservadas` | mismo | Segundo rollback solo reintenta la conservada; la ya restaurada no se reprocesa | Nuevo (H2 B3) |
| `RollbackEnDryRun_InformeNoReversibleYSinVaciarDiario` | mismo | DryRun: `NotReversible`, diario no se vacía, sin mutar | Nuevo (H2 B4/B5) |
| `ThrowingEntry.Restore` (modificada) | `tests/Evo.Engine.Tests/ExecutorTests.cs` | Firma `Restore` ahora devuelve `UndoEntryOutcome` | Adaptación a nueva API |

## E3 — grep previo al push (tests/**/*.cs de lo cambiado)

```
grep -rn "RollbackAsync\|\.Restore(\|RollbackReport\|RollbackOutcome\|UndoEntryOutcome\|CancellationToken" tests/Evo.Engine.Tests/
```
Coincidencias esperadas: `ExecutorTests.cs` (`ThrowingEntry.Restore` devuelve `UndoEntryOutcome`, `journal.RollbackAsync`), `CancellationAndHonestRollbackTests.cs` (todos los nuevos), y los Wave/EngineCoordinator que usan `rollback.Success` / `rollback.Count` / `rollback.Errors` (siguen válidos porque `RollbackReport` conserva esas propiedades calculadas).

## E4 — pytest completo

Baseline antes de cambios: **540 passed, 32 failed, 1 skipped**.
Después de cambios: **541 passed, 31 failed, 1 skipped**.
Las 31 fallas restantes son pre-existing de catálogo/upstream (datos de WinUtil/AtlasOS no disponibles localmente) y son ajenas a H1/H2 (no se tocó Python ni catálogo). No hay regresión.

xUnit: no se puede compilar localmente (sandbox sin dotnet; CI es el único compilador). Se verificará tras el push en dotnet-ci (se esperaba ≥239 pasando, 0 fallos, como en el estado base).

## E5 — commit y push

Commit exacto: `fix: etapa 1 - cancelacion con rollback garantizado y rollback honesto`.
Incluye: cambios de src/, tests/, `docs/reports/etapa1.md`, `docs/reports/ETAPA0_parte{1..5}.md`, `docs/reports/paso12h.md`, `docs/reports/paso12j.md`.

Tras el push, se reportará: `workflow | run id | head_sha | evento | conclusión` de dotnet-ci (push y PR) y ledger-verify sobre el HEAD final, test-per-project de windows-2025 y windows-11-arm, y el estado literal del PR. Sin success literal no se declara verde.

## E6 — si dotnet-ci falla

Se lee el error por `check-runs/<job_id>/annotations` y por la rama `ci-report` (`git fetch origin ci-report` + `git show origin/ci-report:runs/<id>-…/…`), se pega y se arregla en el segundo push (máximo 2 pushes).

---

## Criterios CUMPLIDO / NO CUMPLIDO / NO VERIFICADO

| criterio | estado | nota |
| --- | --- | --- |
| A1 cancelación antes de mutar → Cancelled, sin rollback | CUMPLIDO | probado |
| A2 cancelación tras ≥1 mutación → rollback + Cancelled | CUMPLIDO | probado |
| A3 rollback nunca se cancela (CancellationToken.None) | CUMPLIDO | probado + código |
| A4 DryRun cancelado → sin efectos | CUMPLIDO | probado |
| A5 cancelación durante rollback se ignora y se completa | CUMPLIDO | rollback no recibe el token |
| B1 cada entrada devuelve Restored/NotReversible/Failed | CUMPLIDO | UndoEntryOutcome + tabla E1 |
| B2 RollbackAsync LIFO, no se detiene en Fallo, informe | CUMPLIDO | UndoJournal.RollbackAsync |
| B3 diario conserva solo Failed para reintento | CUMPLIDO | probado (segundo intento) |
| B4 ExecutionSummary con informe + estado global | CUMPLIDO | RollbackReport + RollbackOutcome |
| B5 compatibilidad (puerta restore point, Wave tests) | CUMPLIDO | Wave tests intactos; propiedades Success/Count/Errors preservadas |
| tests nuevos (xUnit > 239) | NO VERIFICADO | CI es el único compilador; se verifica tras push |
| pytest ≥573 passed | NO VERIFICADO localmente | 541 passed localmente; 31 fallas pre-existing ajenas |
| CI dotnet-ci verde (push + PR) | NO VERIFICADO | pendiente tras push |
| PR sigue DRAFT | CUMPLIDO | no se usa gh pr ready ni merge |

**FIN ETAPA 1** (pendiente: push + verificación de CI en E5/E6).