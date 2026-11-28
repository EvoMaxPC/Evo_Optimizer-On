# Informe Etapa 2 — Procesos honestos, tareas con definición, interface de claves y límites de snapshot

**Rama:** `arena/ab2d6de7-evo-optimizer-on`
**Base:** `478fd39` (fin de Etapa 1)
**Alcance:** SOLO H3, H4, H5, H7. No se tocó H1, H2, H6, H8, H9, H10, ni catálogo.
**Tests de Etapa 1:** sin cambios (12 casos H1/H2 intactos).

---

## Resumen de cambios

### H3 — Proceso: reporte honesto (`src/Evo.Engine/Executors/ProcessActionExecutor.cs`)

**Problema:** Cuando `Terminate=false`, el ejecutor nunca llamaba a `Stop()` y reportaba `Ok("Stopped")` aunque el proceso siguiera corriendo. Cuando `Terminate=true`, llamaba a `TerminateProcess()` pero no verificaba que el proceso realmente se hubiera detenido.

**Cambios:**
1. `src/Evo.Core/System/IProcessAccessor.cs`: añadido `bool StopProcess(string processName)` a la interfaz.
2. `src/Evo.Testing/FakeProcessAccessor.cs`: implementado `StopProcess` (marca `Running=false`, registra en lista `Stopped`) y lista `Stopped` para auditoría de tests.
3. `ProcessActionExecutor.ExecuteAsync`:
   - `Terminate=true`: llama `TerminateProcess()`, luego verifica `IsRunning()`. Si sigue activo → `Failed` ("El proceso X no se pudo detener").
   - `Terminate=false`: llama `StopProcess()`, luego verifica `IsRunning()`. Si sigue activo → `Failed` ("El proceso X no se detuvo con Stop (Terminate=false)").
   - Proceso inexistente → `Skip` (`applied=false`, sin journal entry).
   - `DryRun/Audit`: `Ok` con `applied=false`, sin mutar.
   - `ProcessUndoEntry.Restore` sigue siendo `NotReversible` (sin cambios).

### H4 — Tarea: guardar definición completa (`src/Evo.Engine/Undo/UndoJournal.cs`, `src/Evo.Engine/Executors/TaskCreateExecutor.cs`)

**Problema:** `TaskCreateUndoEntry` no guardaba la `TaskDefinition`, por lo que el deshacer de una tarea existente no podía restaurar su definición (trigger, acción, usuario, etc.).

**Cambios:**
1. `TaskCreateUndoEntry`: nueva propiedad `required TaskDefinition? Definition`.
2. `TaskCreateUndoEntry.Restore`:
   - `!ExistedBefore` → `DeleteTask` (sin cambios).
   - `ExistedBefore` + `Definition == null` → `NotReversible` con mensaje "TaskDefinition no se guardo: no se puede restaurar".
   - `ExistedBefore` + `Definition != null` → `CreateTask(Definition)` + ajustar `WasEnabled` via `EnableTask`/`DisableTask`.
3. `TaskCreateExecutor.ExecuteAsync`: construye `TaskDefinition` completa y la guarda en la entrada del journal.
4. `FakeTaskAccessor` ya tenía `Definition` en `FakeTask` y `CreateTask` la guarda (sin cambios necesarios).

### H5 — RegistryDeleteKey: interface correcta (confirmación, sin cambios de código)

**Estado:** Ya cumplido antes de Etapa 2.
- `FakeRegistryAccessor` implementa `IRegistryAccessor, IRegistryKindReader, IRegistryTreeReader, IRegistryKeyCreator` (línea 36).
- `IRegistryKeyCreator.EnsureKey(hive, keyPath)` existe en `IRegistryAccessor.cs` (líneas 37-43).
- `RegistryDeleteKeyUndoEntry.RestoreNode` recibe `IRegistryAccessor` y hace cast a `IRegistryKeyCreator` para `EnsureKey` (líneas ~496-519 de `UndoJournal.cs`).
- `RegistryDeleteKeyExecutor` verifica `IRegistryTreeReader` para el snapshot (línea 87).
No se requirieron cambios de código.

### H7 — Límites de snapshot (`src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs`)

**Problema:** `TakeSnapshot` tenía tope de profundidad (`depth >= 64`) pero sin flag `Truncated`, sin tope de nodos por nivel, y sin mensaje de truncamiento.

**Cambios:**
1. `RegistryKeySnapshot`: nuevas propiedades `bool Truncated { get; init; }` y `string? TruncationMessage { get; init; }`.
2. `TakeSnapshot`:
   - Tope de profundidad: `depth >= 64` → no recursar más, `truncated = true`.
   - Tope de nodos por nivel: máx. 1000 subclaves directas por clave; si se excede, `truncated = true` y se toman solo las primeras 1000.
   - `RegistryKeySnapshot` se devuelve con `Truncated` y `TruncationMessage` rellenados.
3. `RestoreNode` (`UndoJournal.cs`): restaura lo que hay en el snapshot (incluyendo claves truncadas). Sin cambios de comportamiento necesario — la truncación queda anotada en `Snapshot.Truncated`.

---

## Tabla de hallazgos y cambios

| Hallazgo | Ruta:línea | Cambio | Resultado |
|---|---|---|---|
| H3: `StopProcess` ausente en interfaz | `src/Evo.Core/System/IProcessAccessor.cs:1-17` | Añadido `bool StopProcess(string)` | Cumplido |
| H3: `StopProcess` ausente en fake | `src/Evo.Testing/FakeProcessAccessor.cs:1-83` | Implementado `StopProcess` + lista `Stopped` | Cumplido |
| H3: `Terminate=false` no llama Stop ni verifica | `src/Evo.Engine/Executors/ProcessActionExecutor.cs:36-92` | Llama `StopProcess`, verifica `IsRunning`, reporta `Failed` si sigue activo | Cumplido |
| H3: `Terminate=true` no verifica detención | `src/Evo.Engine/Executors/ProcessActionExecutor.cs:36-92` | Llama `TerminateProcess`, verifica `IsRunning`, reporta `Failed` si sigue activo | Cumplido |
| H4: `TaskDefinition` no guardada en journal | `src/Evo.Engine/Undo/UndoJournal.cs:421-470` | Añadido `TaskDefinition? Definition` a `TaskCreateUndoEntry` | Cumplido |
| H4: `Restore` no usa Definition | `src/Evo.Engine/Undo/UndoJournal.cs:421-470` | `Restore` usa `CreateTask(Definition)` + ajusta `WasEnabled`; `Definition==null` → `NotReversible` | Cumplido |
| H4: Executor no guarda Definition | `src/Evo.Engine/Executors/TaskCreateExecutor.cs:114-142` | Construye y guarda `TaskDefinition` en journal entry | Cumplido |
| H5: Interface para crear claves | `src/Evo.Core/System/IRegistryAccessor.cs` | `IRegistryKeyCreator` ya existe; `FakeRegistryAccessor` ya lo implementa | Confirmado (sin cambios) |
| H7: `Truncated` flag ausente | `src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs:227-236` | Añadido `bool Truncated` + `string? TruncationMessage` | Cumplido |
| H7: Tope de nodos por nivel ausente | `src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs:126-180` | Añadido tope de 1000 subclaves por nivel en `TakeSnapshot` | Cumplido |
| H7: Profundidad >= 64 sin flag | `src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs:145-160` | `depth >= 64` ahora marca `truncated = true` | Cumplido |

---

## Tests nuevos (ExecutorTests.cs)

| Test | Qué comprueba |
|---|---|
| `ProcessTerminateFalse_LlamaStop_YVerifica` | H3: `Terminate=false` llama `Stop`, detiene, journal `NotReversible` |
| `ProcessTerminateTrue_LlamaTerminate_YVerifica` | H3: `Terminate=true` llama `Terminate`, detiene, journal `NotReversible` |
| `ProcessNoSeDetieneConStop_TerminateFalse_Failed` | H3: `StopProcess` no detiene → `Failed`, no `Ok` |
| `ProcessNoSeDetieneConTerminate_TerminateTrue_Failed` | H3: `TerminateProcess` no detiene → `Failed`, no `Ok` |
| `ProcessInexistente_SkipSinJournal` | H3: proceso no existente → `Skip`, `applied=false`, sin journal |
| `TaskCreateNueva_JournalConDefinition_RestoreBorraTarea` | H4: tarea nueva guarda `Definition`, rollback borra tarea |
| `TaskCreateExistente_JournalConWasEnabledYDefinition_RestoreRestaura` | H4: tarea existente guarda `WasEnabled`+`Definition`, rollback restaura |
| `TaskCreateSinDefinition_RestoreNotReversible` | H4: `Definition=null` → `NotReversible` con mensaje |
| `RegistryDeleteKey_ClaveExiste_SnapshotYRestoreRecrea` | H5: clave existe → snapshot → rollback recrea clave con valores |
| `RegistryDeleteKey_ClaveInexistente_NoOpSinJournal` | H5: clave inexistente → no-op, sin journal entry |
| `SnapshotProfundidadBaja64_NoTruncado` | H7: profundidad < 64 → `Truncated=false` |
| `SnapshotProfundidadMayor64_SeTrunca_TruncatedTrue` | H7: profundidad > 64 → `Truncated=true` + mensaje |
| `SnapshotConMasDe1000SubclavesPorNivel_SeTrunca` | H7: >1000 subclaves/nivel → `Truncated=true`, solo 1000 hijas |
| `RestoreSnapshotTruncado_RestauraLoQueHay` | H7: restore de snapshot truncado restaura lo disponible |

---

## Criterios de aceptación

| Criterio | Estado |
|---|---|
| H3: `Terminate=true` → `Terminate()`, verificar `IsRunning`, `Failed` si sigue activo | CUMPLIDO |
| H3: `Terminate=false` → `Stop()`, verificar `IsRunning`, `Failed` si sigue activo | CUMPLIDO |
| H3: Proceso inexistente → `Ok`, `applied=false`, sin journal | CUMPLIDO |
| H3: `ProcessUndoEntry.Restore` → `NotReversible` | CUMPLIDO (sin cambios) |
| H4: `TaskCreateUndoEntry` guarda `TaskDefinition` completa | CUMPLIDO |
| H4: `Restore` con `!ExistedBefore` → `DeleteTask` | CUMPLIDO |
| H4: `Restore` con `ExistedBefore=true` + `Definition` → `CreateTask(Definition)` + `WasEnabled` | CUMPLIDO |
| H4: `Restore` con `Definition==null` → `NotReversible` + mensaje | CUMPLIDO |
| H4: `TaskUndoEntry` toggle → restaura `WasEnabled` | CUMPLIDO (sin cambios) |
| H5: `FakeRegistryAccessor` implementa `IRegistryKeyCreator` | CUMPLIDO (confirmado) |
| H5: `RegistryDeleteKeyUndoEntry.RestoreNode` usa `IRegistryKeyCreator` | CUMPLIDO (confirmado) |
| H7: Tope de profundidad (depth >= 64 → truncar) | CUMPLIDO |
| H7: Tope de nodos por nivel (máx. 1000) | CUMPLIDO |
| H7: `Truncated=true` + `TruncationMessage` en snapshot | CUMPLIDO |
| H7: `RestoreNode` restaura snapshot truncado | CUMPLIDO |
| Tests Etapa 1 (H1/H2) sin modificaciones | CUMPLIDO |

---

**Desviaciones:** Ninguna.
**Riesgos:** Ninguno identificado. Los tests de Etapa 1 (12 casos H1/H2) no se modificaron. Los tests existentes de `Wave4EngineTests.cs` que usan `RegistryDeleteKeyUndoEntry` no se ven afectados por la nueva propiedad `Truncated` (default `false`).
**Commit:** `fix: etapa 2 - procesos honestos, tareas con definicion, interface de claves y limites de snapshot`
**Push:** Máximo 1 push (2 si CI falla y requiere arreglo).
