ETAPA 0 — REVALIDAR HALLAZGOS DE AUDITORÍA DEL MOTOR (SOLO LECTURA) [PARTE 1/5]

Rama: `arena/ab2d6de7-evo-optimizer-on` (base `402af190` de main). HEAD actual = `908f6ad` (coincide con `ls-remote origin`). T0 verificado: HEAD=908f6ad; `git status`: `M docs/reports/paso12i.md`, `?? docs/reports/paso12h.md`, `?? docs/reports/paso12j.md`; PR #1 `{draft:true, merged:false, state:"open", head:"908f6ad..."}`; `git log 4d09ba1..HEAD` = 9 commits. Reglas ETAPA 0: SOLO LECTURA, sin commits, sin pushes, sin `gh pr ready`, sin merge, sin `git push --force`.

Valido H1-H10 con `nl -ba`. Para cada hallazgo: función completa, veredicto con `ruta:línea`, y tests hoy (nombre o `NINGUNO`).

---

### HALLADIZO H1 — Cancelación puede salir sin rollback tras una mutación ya aplicada

`cancellationToken.ThrowIfCancellationRequested()` se llama al inicio de cada iteración (línea 338), pero el `catch` (línea 359) excluye `OperationCanceledException` y `OutOfMemoryException`, y no hay `try/finally` con rollback. El rollback solo ocurre si `failed && mode == Execute` (línea 370). Si se cancela tras una mutación ya aplicada, sale por `OperationCanceledException` sin deshacer lo mutado.

Función completa (`src/Evo.Engine/EngineCoordinator.cs`, `nl -ba`):

```
   336        foreach (var step in plan.Steps)
   337        {
   338            cancellationToken.ThrowIfCancellationRequested();
   339

   348            try
   349            {
   350                var result = await executor.ExecuteAsync(step.Action, context).ConfigureAwait(false);
   351                results.Add(result);
   352

   353                if (result.Status == ActionStatus.Failed)
   354                {
   355                    failed = true;
   356                    break;
   357                }
   358            }
   359            catch (Exception ex) when (ex is not OperationCanceledException and not OutOfMemoryException)
   360            {
   361                results.Add(ActionResult.Fail(step.Action.Key, ex.Message, description: step.Description));
   362                failed = true;
   363                break;
   364            }
   365        }
   366

   368        var rollbackEntries = journal.Entries.ToList();
   369

   370        if (failed && mode == ExecutionMode.Execute)
   371        {
   372            // Rollback automático LIFO de lo ya aplicado.
   373            var undoContext = new UndoContext(
   374                template.Registry, template.Services, template.Tasks,
   375                template.Processes, template.Commands);
   376            await journal.RollbackAsync(undoContext).ConfigureAwait(false);
   377            ...
   378            return new ExecutionSummary { ... };
   379        }
```

Veredicto: **CONFIRMADO** — `src/Evo.Engine/EngineCoordinator.cs:338,359,370`.

Tests hoy para H1: **NINGUNO** (ningún test en `tests/` menciona `CancellationToken`/`ThrowIfCancellation`/`.Cancel(`).

---

FIN PARTE 1/5. Continúa en PARTE 2/5 (H2-H3).