ETAPA 0 — REVALIDAR HALLAZGOS DE AUDITORÍA DEL MOTOR (SOLO LECTURA) [PARTE 2/5]

Rama: `arena/ab2d6de7-evo-optimizer-on` (base `402af190` de main). HEAD = `908f6ad`. Reglas ETAPA 0: SOLO LECTURA, sin commits/pushes, sin `gh pr ready`, sin merge, sin `git push --force`.

---

### HALLADIZO H2 — UndoJournal: 7 tipos de entrada, RollbackAsync cuenta como Restaurado aunque no mute

Siete tipos de `UndoJournalEntry`: `RegistryUndoEntry`, `ServiceUndoEntry`, `RegistryDeleteKeyUndoEntry`, `RegistryCreateKeyUndoEntry`, `TaskCreateUndoEntry`, `TaskUndoEntry`, `ProcessUndoEntry`. `RollbackAsync` (líneas 323-355) recorre LIFO, suma a `restored` cualquier entrada que no lance (líneas 335-336) aunque `Restore()` no mute nada real, y vacía el diario solo si `!context.DryRun` (líneas 344-346).

Función completa (`src/Evo.Engine/Undo/UndoJournal.cs`, `nl -ba`):

```
   323    public Task<RollbackResult> RollbackAsync(IUndoContext context)
   324    {
   325        ArgumentNullException.ThrowIfNull(context);
   326

   327        var restored = new List<string>();
   328        var errors = new List<string>();
   329

   330        for (var index = _entries.Count - 1; index >= 0; index--)
   331        {
   332            var entry = _entries[index];
   333            try
   334            {
   335                entry.Restore(context);
   336                restored.Add(entry.ActionKey);
   337            }
   338            catch (Exception ex) when (ex is not OutOfMemoryException)
   339            {
   340                errors.Add($"{entry.ActionKey}: {ex.Message}");
   341            }
   342        }

   344        if (!context.DryRun)
   345        {
   346            _entries.Clear();
   347        }

   349        return Task.FromResult(new RollbackResult
   350        {
   351            Success = errors.Count == 0,
   352            Restored = restored,
   353            Errors = errors,
   354        });
   355    }
```

Veredicto: **CONFIRMADO** — `src/Evo.Engine/Undo/UndoJournal.cs:323-355` (7 tipos de entrada definidas en el mismo archivo).

Tests hoy para H2:
- `ExecutorTests.RollbackIsLifoAndContinuesAfterError` (línea 267)
- `EngineCoordinatorTests.TestRollback_RestoresOriginalStateExactly` (línea 121)
- `EngineCoordinatorTests.TestPartialFailure_TriggersRollback` (línea 181)
- `Wave1EngineTests.TestWave1Catalog_ExecuteAndRollback_RestoresState` (línea 157)
- `Wave4EngineTests.DeleteKey_ThroughTheCoordinator_RollsBackCompletely` (línea 172)
- `Wave4EngineTests.UndoInLifoOrderRestoresTheServiceCompletely` (línea 462)

---

### HALLADIZO H3 — ProcessActionExecutor: proceso activo y Terminate=false no detiene el proceso

Con proceso activo y `Terminate=false`, salta el bloque de terminación (línea 36), no añade entrada al diario y devuelve `ActionResult.Ok(action.Key, "Running", "Stopped", context.Mutates, ...)` (líneas 59-60) sin llamar a `TerminateProcess`.

Función completa (`src/Evo.Engine/Executors/ProcessActionExecutor.cs`, `nl -ba`):

```
   36        if (context.Mutates && processAction.Terminate)
   37        {
   38            if (!context.Processes.TerminateProcess(processAction.ProcessName))
   39            {
   40                return Task.FromResult(ActionResult.Fail(
   41                    action.Key,
   42                    $"No se pudo terminar '{processAction.ProcessName}'.",
   43                    previous,
   44                    Describe(processAction)));
   45            }
   46

   47            // Se registra en el diario con estado previo "Running" pero el
   48            // rollback de procesos es informativo (no se reinician solos).
   49            context.Journal.Add(new ProcessUndoEntry
   50            {
   51                CapabilityId = context.CapabilityId,
   52                ActionKey = action.Key,
   53                Description = Describe(processAction),
   54                PreviousState = previous,
   55                ProcessName = processAction.ProcessName,
   56            });
   57        }

   59        return Task.FromResult(ActionResult.Ok(
   60            action.Key, previous, "Stopped", context.Mutates, Describe(processAction)));
   61

   62    public string? ReadCurrentState(CapabilityAction action, ActionContext context)
   63    {
```

Veredicto: **CONFIRMADO** — `src/Evo.Engine/Executors/ProcessActionExecutor.cs:36,59-60`.

Tests hoy para H3:
- `ExecutorTests.ProcessExecutorSkipsWhenNotRunning` (línea 181)
- `ExecutorTests.ProcessExecutorTerminatesAndLogs` (línea 198)

---

FIN PARTE 2/5. Continúa en PARTE 3/5 (H4-H5).