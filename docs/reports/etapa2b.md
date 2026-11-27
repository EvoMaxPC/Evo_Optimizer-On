# Informe ETAPA 2-B — Correcciones del motor

**Rama:** `arena/ab2d6de7-evo-optimizer-on` (base `main` `402af190`)
**PR:** #1 (DRAFT, no mergeado)
**Commit:** `fix: etapa 2b - rollback por identidad, tareas con definicion original, registro fail-closed y procesos sin falso Stopped`

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

`RollbackAsync` ahora usa un `HashSet<int>` de índices de entradas fallidas para reconstruir `_entries`, conservando **solo** las entradas que fallaron. Esto permite tener dos entradas con el mismo `ActionKey` en el diario: una que se restaura con éxito y otra que falla; solo la fallida se conserva para reintento.

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

## Tests (ExecutorTests.cs)

### H3 — Procesos honestos
- Proceso no existente + Terminate=true → Skipped, sin journal.
- Proceso corriendo + Terminate=false → Skipped, sin mutar, sin journal.

### H4 — Tareas con definición ORIGINAL
- Tarea nueva → `PreviousDefinition=null`, Restore borra.
- Tarea existente + Overwrite → guarda `PreviousDefinition` original, Restore restaura definición y `WasEnabled`.
- `GetDefinition` null → Fail sin mutar.
- `GetDefinition` lanza → Fail sin mutar.
- `ExistedBefore=true` + `PreviousDefinition=null` → NotReversible.
- `CreateTask` lanza en rollback → Failed, entrada conservada.

### H5 — RegistryDeleteKey fail-closed
- Árbol completo → snapshot → Restore recrea todo.
- Clave inexistente → no-op, sin journal.
- Sin `IRegistryKeyCreator` → Fail sin mutar, clave intacta.
- `!ExistedBefore` + clave ausente → Restored.
- `!ExistedBefore` + clave existente → Failed.
- `SetValue` lanza en restauración → Failed, entrada conservada.

### H7 — Límites de snapshot
- En límite MaxValues → se borra.
- Excede MaxValues → Fail, clave intacta, journal vacío.
- Excede MaxDepth → Fail, clave intacta, journal vacío.

### PASO 1 — Rollback por identidad
- Dos entradas mismo `ActionKey`, una Restored (DeleteTask) y otra Failed (CreateTask falla) → solo la fallida se conserva por índice.

## Reglas git

- `git add` por ruta (no `-A` ni `.`).
- Mensaje de commit exacto: `fix: etapa 2b - rollback por identidad, tareas con definicion original, registro fail-closed y procesos sin falso Stopped`
- Sin force-push, sin commits vacíos, sin `gh pr ready`, sin mergear.
- PR #1 se mantiene DRAFT.
- Máximo 1 push (2do autorizado si CI falla; tercero NO: parar y reportar).

## Estado de CI

Pendiente — no se puede compilar ni ejecutar tests localmente (sandbox sin dotnet). El compilador es CI de GitHub Actions.
