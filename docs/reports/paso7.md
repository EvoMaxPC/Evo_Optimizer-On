# Paso 7 — Motor de ejecución, sistema de deshacer, fakes y validador de catálogo

Fecha: 2026-11-23 · Rama `arena/ab2d6de7-evo-optimizer-on` · HEAD de partida `8329e26`.
Atlas `ec3c4058…d455f` · WinUtil `70c23c80…0842` · EVO CLEAN: GPL-3.0-only.

## T0 — Evidencia

```
$ git rev-parse HEAD
8329e26433fce846434f575926e62802a26bceda
$ git ls-remote origin refs/heads/arena/ab2d6de7-evo-optimizer-on
8329e26433fce846434f575926e62802a26bceda	refs/heads/arena/ab2d6de7-evo-optimizer-on
$ sha256sum docs/requirements/INVENTARIO_USUARIO.md
0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709
```

## Proyectos nuevos (5) — total 9 en `Evo.sln`

| Proyecto | Depende de | Contenido |
|---|---|---|
| `src/Evo.Testing` | Evo.Core | 6 fakes en memoria |
| `src/Evo.Engine` | Evo.Core, Evo.Detection | modelos, diario, 5 ejecutores, coordinador |
| `src/Evo.Catalog` | Evo.Core | modelos JSON, cargador, validador |
| `tests/Evo.Engine.Tests` | Evo.Engine, Evo.Testing, Evo.Detection | 18 casos |
| `tests/Evo.Catalog.Tests` | Evo.Catalog, Evo.Testing | 32 casos |

Además `src/Evo.Core/Actions/` (5 acciones declarativas con polimorfismo
`System.Text.Json`) y `IRegistryKindReader` (lectura del tipo original para el
rollback exacto).

## Fakes

`FakeRegistryAccessor` (HKLM/HKCU/HKCR/HKU; String, DWord, QWord, Binary,
MultiString, ExpandString — rechaza cualquier otro tipo; `Snapshot()` y
`MutationCount`), `FakeServiceAccessor`, `FakeTaskAccessor`,
`FakeProcessAccessor` (registra terminaciones), `FakeCommandRunner`
(`Respond`/`Throw`/`DefaultResult`) y `FakeSystemEnvironment` (build, UBR,
edición, InstallationType, arquitectura y privilegios mutables).

## Motor

- `ExecutionMode` (DryRun/Execute/Audit), `ExecutionPlan`, `ActionResult`
  (Success/Skipped/Failed + PreviousState/NewState), `ExecutionSummary`
  (TotalActions/Succeeded/Failed/Skipped/Duration/UndoJournalEntry).
- `UndoJournal.RollbackAsync(IUndoContext)` recorre las entradas en **LIFO**,
  continúa tras un error y vacía el diario solo si no fue dry-run.
- `RegistryActionExecutor` guarda valor + tipo originales y marca
  `ExistedBefore=false` para que el rollback **borre** lo que antes no existía.
- `ServiceActionExecutor`, `TaskActionExecutor`, `ProcessActionExecutor` y
  `CommandActionExecutor` (códigos de salida permitidos, `IgnoreExitCode`).
- `EngineCoordinator`: compatibilidad (`Evo.Detection`), privilegio efectivo,
  dependencias/conflictos, DryRun vs Execute, Audit y **rollback automático**
  LIFO si una acción falla a mitad de plan.

## Catálogo

`CatalogLoader` (System.Text.Json estricto, comentarios, enums como string,
`id`/`name`/`securityImpact` obligatorios) y `CatalogValidator` con reglas
`R-ID` (`^[a-z0-9]+(\.[a-z0-9\-]+)+$`), `R-SYMMETRY`, `R-CYCLE` (DFS con
coloración, informa la ruta del ciclo), `R-RISK`, `R-BUILD`, `R-REF`,
`R-ACTION` y `R-STATE`.

## CI (SHA final)

```
$ gh api "repos/.../actions/runs?head_sha=24ddbda…"
id=45310547680 dotnet-ci      event=pull_request conclusion=success
id=45310542428 dotnet-ci      event=push         conclusion=success
id=45310542412 ledger-verify  event=push         conclusion=success
$ (ci-report) pytest.txt → 239 passed · pytest_exit=0
```

Cuentas xUnit medidas en el código: 19 + 35 + 18 + 32 = **104 casos** (≥60).

## Incidencias reales detectadas por CI

1. `CS1574` (cref `System.Type` sin resolver) con `TreatWarningsAsErrors` →
   comentario reescrito.
2. `TestPartialFailure_TriggersRollback` esperaba 4 resultados y son 3 (el plan
   se corta en la acción que falla) → expectativa corregida.
3. `TestValidCatalog_PassesValidation` declaraba un conflicto asimétrico → el
   validador tenía razón; se corrigió el fixture.
4. El resumen de tests se pisaba entre proyectos (`results.trx` compartido) →
   un directorio y un `.trx` por proyecto + `test-per-project.txt`.

## Desviaciones

1. **`Restore == None => Risk >= High`** (enunciado) contradice
   `MinimumRestore` del paso 6 (`High → RestorePoint`). Juntas harían
   `RestoreLevel.None` inservible. Se aplica la del paso 6 (más restrictiva) y
   se documenta aquí. `Critical → TypeOperationName` sí se aplica literal.
2. **Procesos y comandos no son reversibles**: el diario los registra pero su
   `Restore` no muta nada (no se puede "des-terminar" un proceso). Declarado en
   `ProcessUndoEntry`/`CommandUndoEntry`.
3. El validador Python pasa a exigir **9** proyectos y dependencias permitidas
   entre ellos (sin ciclos); `test_paso6.py` se relaja a "≥4 proyectos" y
   "los 4 del paso 6 siguen en la solución".

## Supuestos

- `TrustedInstaller` nunca se asume: el privilegio efectivo máximo es `Admin`.
- Los comandos declarados en el catálogo se ejecutan sin shell, con lista de
  argumentos y códigos de salida explícitos.

## Riesgos

- El motor no persiste el diario en disco: si el proceso muere, se pierde. El
  punto de restauración sigue siendo la red de seguridad (paso futuro).
- `R-SYMMETRY` es estricta: un catálogo grande con conflictos unidireccionales
  fallará el build hasta corregirlos (deseado).
- Los tests de DryRun/Execute miden estado de fakes, no del sistema real: la
  validación en VM sigue pendiente del responsable.
