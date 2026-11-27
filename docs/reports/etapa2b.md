# Informe ETAPA 2-B — Correcciones del motor (estado tras CI)

**Rama:** `arena/ab2d6de7-evo-optimizer-on` (base `main` `402af190`)
**PR:** #1 (DRAFT, no mergeado)
**Commit:** `fix: etapa 2b - corrige compilacion y cierra informe con resultados reales`

## Alcance

Solo los siguientes paths (sin tocar catálogo ni inventario):

- `src/Evo.Core/System/IProcessAccessor.cs`
- `src/Evo.Core/System/ITaskAccessor.cs`
- `src/Evo.Core/System/IRegistryAccessor.cs` (sin cambios de código, referencia)
- `src/Evo.Engine/Undo/UndoJournal.cs`
- `src/Evo.Engine/Executors/ProcessActionExecutor.cs`
- `src/Evo.Engine/Executors/TaskCreateExecutor.cs`
- `src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs`
- `src/Evo.Engine/EngineCoordinator.cs`
- `src/Evo.Testing/FakeProcessAccessor.cs`
- `src/Evo.Testing/FakeTaskAccessor.cs`
- `src/Evo.Testing/FakeRegistryAccessor.cs` (sin cambios, referencia)
- `tests/Evo.Engine.Tests/ExecutorTests.cs`
- `docs/reports/etapa2b.md` (este informe)

## Cambios aplicados (6 pasos)

### Paso 1 — UndoJournal.RollbackAsync por identidad (índices, no ActionKey)

`RollbackAsync` usa un `HashSet<int>` de índices de entradas fallidas para reconstruir `_entries`, conservando **solo** las entradas que fallaron. Permite tener dos entradas con el mismo `ActionKey`: una que se restaura con éxito y otra que falla; solo la fallida se conserva para reintento.

**Corrección de compilación (ETAPA 2-C):** `_entries` es `readonly`; `RollbackAsync` intentaba reasignarlo (`_entries = _entries.Where(...).ToList()`), causando `CS0191`. Se corrigió usando `_entries.Clear()` + `_entries.AddRange(...)` en lugar de reasignación.

### Paso 2 — Procesos: revertir `StopProcess`, reporte honesto

- `IProcessAccessor`: `StopProcess` eliminado. Quedan `IsRunning`, `TerminateProcess`, `StartProcess`.
- `FakeProcessAccessor`: lista `Stopped` y `StopProcess` eliminados. Mantiene `Terminated`.
- `ProcessActionExecutor`:
  - Proceso no existente → `Skipped`, sin mutar, sin journal.
  - Proceso corriendo + `Terminate=false` → `Skipped`, sin mutar, mensaje "el proceso esta activo; la acción no solicita terminarlo", sin journal.
  - Proceso corriendo + `Terminate=true` → `TerminateProcess`; si `IsRunning` sigue true → `Failed`; si se detuvo → `Ok`, journal entry.
  - `DryRun` → sin mutar.

### Paso 3 — Tareas: guardar definición ORIGINAL + `GetDefinition`

- `ITaskAccessor`: añadido `TaskDefinition? GetDefinition(string taskPath, string taskName)`.
- `FakeTaskAccessor`: `Seed` acepta `TaskDefinition` opcional; `FailGetDefinitionWith`; implementa `GetDefinition`.
- `TaskCreateUndoEntry.Definition` → `PreviousDefinition`.
- `TaskCreateExecutor`: fail-closed al reemplazar — llama a `GetDefinition` **antes** de `CreateTask`; si devuelve null o lanza → `Failed` sin mutar, sin journal entry. Guarda `PreviousDefinition` en la entrada del journal.
- `TaskCreateUndoEntry.Restore`: si `!ExistedBefore` → borra tarea; si `ExistedBefore=true` y `PreviousDefinition is null` → `NotReversible`; si `ExistedBefore=true` y `PreviousDefinition != null` → `CreateTask(PreviousDefinition)` + ajuste `WasEnabled`.

### Paso 4 — RegistryDeleteKey fail-closed + `IRegistryKeyCreator`

- `RegistryDeleteKeyExecutor`: exige `IRegistryKeyCreator` en el accesor de registro **antes** de borrar; si no lo implementa → `Failed` sin mutar, sin journal entry.
- `UndoJournal.RegistryDeleteKeyUndoEntry.Restore`: si `!ExistedBefore` verifica `KeyExists` — si la clave sigue ausente → `Restored`; si ya existe → `Failed` con mensaje explícito.
- `RestoreNode`: lanza `InvalidOperationException` si el registro no implementa `IRegistryKeyCreator`.

### Paso 5 — Límites de snapshot: eliminar `Truncated`/tope 1000

- `RegistryKeySnapshot.Truncated` / `TruncationMessage` eliminados.
- Eliminado tope de 1000 por nivel y variable `truncated`.
- `depth >= 64` sigue siendo tope duro (sin flag de truncación).
- Límites reales del snapshot: `MaxDepth=16`, `MaxValues=4096`, `MaxKeys=1024`.

### Paso 6 — Comentario del diario en `EngineCoordinator`

Comentario corregido: "conserva solo las entradas que fallaron".

## Error de compilación (ETAPA 2-C)

| Archivo | Línea | Código CS | Causa | Corrección |
|---------|-------|-----------|-------|------------|
| `src/Evo.Engine/Undo/UndoJournal.cs` | 580 | CS0191 | `_entries` es `readonly`; `RollbackAsync` intentaba reasignarlo con `_entries = _entries.Where(...).ToList()` | `_entries.Clear()` + `_entries.AddRange(...)` |

El error aparecía en ambos entornos de CI (windows-2025 y windows-11-arm) para los commits `bab443e` y `e7c7dd3`.

## Tests (ExecutorTests.cs)

### H3 — Procesos honestos (5 tests)
| Test | Línea | Punto cubierto |
|------|-------|----------------|
| `ProcessNoCorriendo_SkipSinJournal` | ~300 | Proceso no existente → Skipped, sin journal |
| `ProcessCorriendo_TerminateFalse_SkipSinMutar` | ~319 | Corriendo + Terminate=false → Skipped, sin mutar |
| `ProcessCorriendo_TerminateTrue_SeDetiene_OkNotReversible` | ~345 | Corriendo + Terminate=true → Ok, journal NotReversible |
| `ProcessCorriendo_TerminateTrue_NoSeDetiene_FailedSinJournal` | ~371 | Corriendo + Terminate=true, no se detiene → Failed, sin journal |
| `ProcessDryRun_SinMutacion` | ~405 | DryRun → sin mutar, sin journal |

### H4 — Tareas con definición ORIGINAL (6 tests)
| Test | Línea | Punto cubierto |
|------|-------|----------------|
| `TaskCreateNueva_PreviousDefinitionNull_RestoreBorraTarea` | ~429 | Tarea nueva → PreviousDefinition=null, Restore borra |
| `TaskCreateExistente_PreviousDefinitionOriginal_RestoreRestauraOriginal` | ~459 | Tarea existente + Overwrite → guarda PreviousDefinition original |
| `TaskCreateExistente_GetDefinitionNull_FailSinMutar` | ~513 | GetDefinition null → Fail sin mutar |
| `TaskCreateExistente_GetDefinitionLanza_FailSinMutar` | ~533 | GetDefinition lanza → Fail sin mutar |
| `TaskCreateSinPreviousDefinition_RestoreNotReversible` | ~553 | ExistedBefore=true + PreviousDefinition=null → NotReversible |
| `TaskCreateCreateTaskLanzaDuranteRollback_FailedEntradaConservada` | ~572 | CreateTask lanza en rollback → Failed, entrada conservada |

### H5 — RegistryDeleteKey fail-closed (6 tests)
| Test | Línea | Punto cubierto |
|------|-------|----------------|
| `RegistryDeleteKey_ArbolCompleto_RestoreRecreaTodo` | ~600 | Árbol con subclaves vacías → snapshot → Restore recrea todo |
| `RegistryDeleteKey_ClaveInexistente_NoOpSinJournal` | ~627 | Clave inexistente → no-op, sin journal |
| `RegistryDeleteKey_SinIRegistryKeyCreator_FailSinMutar` | ~641 | Sin IRegistryKeyCreator → Fail sin mutar, clave intacta |
| `RegistryDeleteKey_NoExistedBefore_ClaveAusente_Restored` | ~669 | !ExistedBefore + clave ausente → Restored |
| `RegistryDeleteKey_NoExistedBefore_ClaveExiste_Failed` | ~690 | !ExistedBefore + clave existente → Failed |
| `RegistryDeleteKey_SetValueLanzaRestauracion_FailedEntradaConservada` | ~711 | SetValue lanza en restauración → Failed, entrada conservada |

### H7 — Límites del snapshot (3 tests)
| Test | Línea | Punto cubierto |
|------|-------|----------------|
| `SnapshotEnLimiteMaxValues_SeBorra` | ~739 | En límite MaxValues → se borra |
| `SnapshotExcedeMaxValues_FailClaveIntacta` | ~763 | Excede MaxValues → Fail, clave intacta |
| `SnapshotExcedeMaxDepth_FailClaveIntacta` | ~787 | Excede MaxDepth → Fail, clave intacta |

### PASO 1 — Rollback por identidad (1 test)
| Test | Línea | Punto cubierto |
|------|-------|----------------|
| `RollbackPorIdentidad_SoloEntradaFallida_SeConserva` | ~811 | Dos entradas mismo ActionKey, una Restored otra Failed → solo la fallida se conserva |

## Tabla resumen: punto | cambio | test | resultado

| Punto | Cambio | Test | Resultado |
|-------|--------|------|-----------|
| 1 (identidad) | RollbackAsync por índice, conserva solo fallidas | `RollbackPorIdentidad_SoloEntradaFallida_SeConserva` | Implementado |
| 2 (procesos) | StopProcess eliminado, reporte honesto | 5 tests H3 | Implementado |
| 3 (tareas) | GetDefinition, PreviousDefinition, fail-closed | 6 tests H4 | Implementado |
| 4 (registro) | IRegistryKeyCreator exigido, fail-closed | 6 tests H5 | Implementado |
| 5 (límites) | Truncated eliminado, tope 64 duro | 3 tests H7 | Implementado |
| 6 (comentario) | Comentario EngineCoordinator corregido | N/A | Implementado |

## Límites reales del snapshot

Confirmados: `MaxDepth=16`, `MaxValues=4096`, `MaxKeys=1024`.

## Grep de símbolos clave

| Símbolo | Resultado |
|---------|-----------|
| `StopProcess` | Eliminado de `IProcessAccessor` y `FakeProcessAccessor` |
| `Stopped` | Eliminado de `FakeProcessAccessor` |
| `Truncated` / `TruncationMessage` | Eliminados de `RegistryKeySnapshot` |
| `PreviousDefinition` | Usado en `TaskCreateUndoEntry` (renombrado de `Definition`) |
| `GetDefinition` | Añadido a `ITaskAccessor`, implementado en `FakeTaskAccessor` |
| `RestoreNode` | Lanza `InvalidOperationException` si no `IRegistryKeyCreator` |

## Grep catálogo (terminate:false)

Sin acciones de proceso con `terminate:false` en el catálogo (confirmado en ETAPA 2-B, paso 0).

## Reglas git

- `git add` por ruta (no `-A` ni `.`).
- Mensaje de commit exacto: `fix: etapa 2b - corrige compilacion y cierra informe con resultados reales`
- Sin force-push, sin commits vacíos, sin `gh pr ready`, sin mergear.
- PR #1 se mantiene DRAFT.
- Pushes autorizados: 1 + 1 de reserva si CI falla.

## Estado de CI

Pendiente — se hizo push tras corregir CS0191 en `UndoJournal.cs`. Esperando resultados de dotnet-ci (push y PR) y ledger-verify.
