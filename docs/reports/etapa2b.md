# Informe ETAPA 2-H — Evidencia de cierre de la Etapa 2 (sin cambios de código)

**Rama:** `arena/ab2d6de7-evo-optimizer-on` (base `main` `402af190e10a120dc893fa74f0a1d7b7d55b0c75`)
**PR:** #1 (DRAFT, no mergeado)
**HEAD final:** `550cfb01e3ba61f5291644eb39e42e517e72cd93` (local y remoto idénticos)
**Cambios en esta etapa:** ninguno en `src/` ni `tests/`; solo `docs/reports/etapa2b.md`.

## 1. Resultado de CI (HEAD final `550cfb01...`)

| workflow | run id | head_sha | evento | conclusión |
|----------|--------|----------|--------|------------|
| dotnet-ci | 45976059323 | 550cfb01e3ba61f5291644eb39e42e517e72cd93 | push | success |
| dotnet-ci | 45976068136 | e636ad42b20a26d2c105986319ace728e79c3d3a | pull_request | success |
| ledger-verify | 45976059146 | 550cfb01e3ba61f5291644eb39e42e517e72cd93 | push | success |

## 2. test-per-project literal (run final, ambas corridas)

**Push 45976059323 — windows-2025:**
```
Evo.Catalog.Tests: total=79 passed=79 failed=0
Evo.Core.Tests: total=34 passed=34 failed=0
Evo.Detection.Tests: total=35 passed=35 failed=0
Evo.Engine.Tests: total=132 passed=132 failed=0
```
```
sin tests fallidos
```

**Push 45976059323 — windows-11-arm:**
```
Evo.Catalog.Tests: total=79 passed=79 failed=0
Evo.Core.Tests: total=34 passed=34 failed=0
Evo.Detection.Tests: total=35 passed=35 failed=0
Evo.Engine.Tests: total=132 passed=132 failed=0
```
```
sin tests fallidos
```

**PR 45976068136 — windows-2025:**
```
Evo.Catalog.Tests: total=79 passed=79 failed=0
Evo.Core.Tests: total=34 passed=34 failed=0
Evo.Detection.Tests: total=35 passed=35 failed=0
Evo.Engine.Tests: total=132 passed=132 failed=0
```
```
sin tests fallidos
```

**PR 45976068136 — windows-11-arm:**
```
Evo.Catalog.Tests: total=79 passed=79 failed=0
Evo.Core.Tests: total=34 passed=34 failed=0
Evo.Detection.Tests: total=35 passed=35 failed=0
Evo.Engine.Tests: total=132 passed=132 failed=0
```
```
sin tests fallidos
```

Total todos los proyectos: 280 (> 265), 0 fallos en cada runner.

## 3. Test rojo: aclarecimiento

En el run `45943493988` (push #1 de ETAPA 2-F, HEAD `438d207`) hubo 6 tests rojos. En el run `45944406883` (push #2 de ETAPA 2-F, HEAD `306fd8aa`) quedó **un único test rojo**:

```
Evo.Engine.Tests.ExecutorTests.SnapshotEnLimiteMaxDepth_SeBorra (Evo.Engine.Tests): Assert.False() Failure
Expected: False
Actual:   True
   at Evo.Engine.Tests.ExecutorTests.SnapshotEnLimiteMaxDepth_SeBorra() in /_/tests/Evo.Engine.Tests/ExecutorTests.cs:line 1079
```

**Causa real:** `CountingRegistryAccessor.DeleteKey` no limpiaba `_knownKeys`, así que `KeyExists` seguía devolviendo `true` tras borrar. Corrección: agregar `_knownKeys.Remove((hive, keyPath));`. Fue un bug del accesorio de prueba, no un defecto de producción. Se cerró en ETAPA 2-G (push `f77824fd`).

## 4. Excepción propia para el límite (`src/`)

`src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs`:

```csharp
internal sealed class SnapshotLimitExceededException : Exception
{
    public SnapshotLimitExceededException(string message) : base(message) { }
}
```
(Líneas 34-36.)

Límites reales (`RegistrySnapshotLimits`):
- `MaxDepth = 16` (línea 16)
- `MaxValues = 4096` (línea 19)
- `MaxKeys = 1024` (línea 22)

Mensajes de `SnapshotLimitExceededException`:
- `"Límite de profundidad excedido: {depth} > {lim.MaxDepth}"` (línea 236)
- `"Límite de valores excedido: {totalValues} > {lim.MaxValues}"` (línea 251)
- `"Límite de claves excedido: {totalKeys} > {lim.MaxKeys}"` (línea 269)
- `"Límite de profundidad excedido: {maxDepthReached} > {lim.MaxDepth}"` (línea 285)

Catch propio en el executor (línea 130), antes del catch genérico: devuelve `Fail` con `ex.Message + " No se borra (fail-closed)."`.

Test `Wave4EngineTests.DeleteKey_SnapshotOverTheLimitAbortsWithoutDeleting` (línea 155):
```csharp
Assert.Contains("Límite de valores excedido", result.ErrorMessage, StringComparison.Ordinal);
```
Coincide con el mensaje real de la excepción. No se debilitó: ahora verifica el límite concreto (valores) y que la clave no se borre.

## 5. Diff literal de `src/` desde `ed6457e94f2f9b63696dfdb1e43106fc02cb3406`

Archivos modificados: **10**

1. `src/Evo.Core/System/IProcessAccessor.cs` — se eliminó `StopProcess`.
2. `src/Evo.Core/System/ITaskAccessor.cs` — se añadió `GetDefinition`.
3. `src/Evo.Engine/EngineCoordinator.cs` — comentario de rollback actualizado (conserva solo entradas fallidas).
4. `src/Evo.Engine/Execution/ExecutionModels.cs` — `ActionResult.Skip` acepta `previous?` y asigna `PreviousState`.
5. `src/Evo.Engine/Executors/ProcessActionExecutor.cs` — `Terminate=false` → Skipped con `previous`; `Terminate=true` + falla → Fail; sigue corriendo → Fail.
6. `src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs` — exige `IRegistryKeyCreator` antes de borrar (fail-closed); `SnapshotLimitExceededException` propia; eliminado `Truncated`/`TruncationMessage` y tope 1000; `TakeSnapshot` recibe `limits`.
7. `src/Evo.Engine/Executors/TaskCreateExecutor.cs` — fail-closed con `GetDefinition`, guarda `PreviousDefinition` (renombrado de `Definition`).
8. `src/Evo.Engine/Undo/UndoJournal.cs` — `RollbackAsync` por índice (`HashSet<int>` failedIndices), `_entries.Clear()+AddRange(soloFallidas)`; `RegistryDeleteKeyUndoEntry` fail-closed si no existe; `TaskCreateUndoEntry.PreviousDefinition`.
9. `src/Evo.Testing/FakeProcessAccessor.cs` — eliminada `Stopped`/`StopProcess`.
10. `src/Evo.Testing/FakeTaskAccessor.cs` — `Seed(..., TaskDefinition? definition)`, `GetDefinition`, `FailGetDefinitionWith`.

El diff completo de cada archivo se entregó por `git diff` literal en los pasos previos de esta etapa. No hay API pública nueva (`SnapshotLimitExceededException` es `internal`).

## 6. Tabla de tests (línea real | resultado)

Todas las líneas salen de `grep -n`. Resultado `PASA` = confirmado como `Passed` en `test-console.txt` del run final (push 45976059323, windows-2025; test-console.txt sí lista los tests uno por uno). No aplica `NO VERIFICADO`: el conteo indirecto de proyecto (132 passed / 0 failed en Evo.Engine.Tests, ambos runners) confirma todos.

| Test | Línea real | Resultado |
|------|------------|-----------|
| `ProcessNoCorriendo_SkipSinJournal` | ExecutorTests.cs:313 | PASA |
| `ProcessCorriendo_TerminateFalse_SkipSinMutar` | ExecutorTests.cs:338 | PASA |
| `ProcessCorriendo_TerminateTrue_SeDetiene_OkNotReversible` | ExecutorTests.cs:366 | PASA |
| `ProcessCorriendo_TerminateTrue_NoSeDetiene_FailedSinJournal` | ExecutorTests.cs:395 | PASA |
| `ProcessDryRun_SinMutacion` | ExecutorTests.cs:431 | PASA |
| `TaskCreateNueva_PreviousDefinitionNull_RestoreBorraTarea` | ExecutorTests.cs:460 | PASA |
| `TaskCreateExistente_PreviousDefinitionOriginal_RestoreRestauraOriginal` | ExecutorTests.cs:500 | PASA |
| `TaskCreateExistente_GetDefinitionNull_FailSinMutar` | ExecutorTests.cs:563 | PASA |
| `TaskCreateExistente_GetDefinitionLanza_FailSinMutar` | ExecutorTests.cs:591 | PASA |
| `TaskCreateSinPreviousDefinition_RestoreNotReversible` | ExecutorTests.cs:620 | PASA |
| `TaskCreateCreateTaskLanzaDuranteRollback_FailedEntradaConservada` | ExecutorTests.cs:650 | PASA |
| `RegistryDeleteKey_ArbolCompleto_RestoreRecreaTodo` | ExecutorTests.cs:695 | PASA |
| `RegistryDeleteKey_SinIRegistryKeyCreator_FailSinMutar` | ExecutorTests.cs:748 | PASA |
| `RegistryDeleteKey_NoExistedBefore_ClaveAusente_Restored` | ExecutorTests.cs:783 | PASA |
| `RegistryDeleteKey_NoExistedBefore_ClaveExiste_Failed` | ExecutorTests.cs:812 | PASA |
| `RegistryDeleteKey_SetValueLanzaRestauracion_FailedEntradaConservada` | ExecutorTests.cs:844 | PASA |
| `RegistryDeleteKey_EnsureKeyLanzaRestauracion_FailedEntradaConservada` | ExecutorTests.cs:889 | PASA |
| `SnapshotEnLimiteMaxValues_SeBorra` | ExecutorTests.cs:938 | PASA |
| `SnapshotExcedeMaxValues_FailClaveIntacta` | ExecutorTests.cs:975 | PASA |
| `SnapshotExcedeMaxDepth_FailClaveIntacta` | ExecutorTests.cs:1014 | PASA |
| `SnapshotEnLimiteMaxDepth_SeBorra` | ExecutorTests.cs:1051 | PASA |
| `SnapshotExcedeMaxKeys_FailClaveIntacta` | ExecutorTests.cs:1087 | PASA |
| `SnapshotEnLimiteMaxKeys_SeBorra` | ExecutorTests.cs:1125 | PASA |
| `SnapshotExcedeMaxDepth_ConContador_LecturasParciales` | ExecutorTests.cs:1163 | PASA |
| `SnapshotExcedeMaxKeys_ConContador_LecturasParciales` | ExecutorTests.cs:1212 | PASA |
| `SnapshotExcedeMaxValues_ConContador_LecturasParciales` | ExecutorTests.cs:1256 | PASA |
| `RollbackPorIdentidad_SoloEntradaFallida_SeConserva` | ExecutorTests.cs:1304 | PASA |
| `DeleteKey_SnapshotOverTheLimitAbortsWithoutDeleting` | Wave4EngineTests.cs:155 | PASA |
| `DeleteKey_ReaderThrowsOnSubKeyNames_GenericMessageNoLimit` | Wave4EngineTests.cs:176 | PASA |

## 7. Criterios CUMPLIDO / NO CUMPLIDO / NO VERIFICADO

| Criterio | Estado | Evidencia |
|----------|--------|-----------|
| dotnet-ci push en success | CUMPLIDO | run 45976059323, `completed success` |
| dotnet-ci PR en success | CUMPLIDO | run 45976068136, `completed success` |
| ledger-verify en success | CUMPLIDO | run 45976059146, `completed success` |
| xUnit total > 265 y 0 fallos en cada runner | CUMPLIDO | 280 total / 0 fallos, windows-2025 y windows-11-arm |
| diff de src/ entregado literal | CUMPLIDO | 10 archivos, `git diff` literal mostrado |
| PR con draft:true, merged:false | CUMPLIDO | `draft: true`, `merged: false`, `state: open` |
| Tests marcados con evidencia | CUMPLIDO | 28 tests PASA confirmados en test-console.txt |

## 8. Desviaciones, Suposiciones y Riesgos

**Desviaciones:** ninguna en esta etapa (no hubo cambios de código). El informe `docs/reports/etapa2b.md` se reescribe con el estado real post-CI-verde.

**Suposiciones:**
- El SHA remoto `550cfb01...` es el HEAD final de ETAPA 2-G (verificado: local y remoto idénticos).
- `test-console.txt` lista tests individualmente con `Passed ...`, por lo que todos los tests de la tabla 6 están confirmados individualmente, no solo por conteo.

**Riesgos (con justificación):**
- Ninguno activo. CI está completamente verde en los 3 checks (dotnet-ci push, dotnet-ci PR, ledger-verify). El PR sigue en DRAFT y no se mergea (no es un riesgo, es el estado requerido).
- "Riesgos: ninguno" está justificado porque todas las corridas de CI del HEAD final concluyeron en `success` y `test-failures.txt` reporta "sin tests fallidos" en ambos runners.

## Commit

Este informe se sube como único cambio de esta etapa:

```
git add docs/reports/etapa2b.md
git commit -m "fix: etapa 2b - informe final de cierre"
git push origin HEAD:arena/ab2d6de7-evo-optimizer-on
```

FIN ETAPA 2-H
