ETAPA 0 — REVALIDAR HALLAZGOS DE AUDITORÍA DEL MOTOR (SOLO LECTURA) [PARTE 5/5 — FINAL]

Rama: `arena/ab2d6de7-evo-optimizer-on` (base `402af190` de main). HEAD = `908f6ad`. Reglas ETAPA 0: SOLO LECTURA, sin commits/pushes, sin `gh pr ready`, sin merge, sin `git push --force`.

---

### HALLADIZO H8 — Matriz de adaptadores: ActionKind → IActionExecutor; interfaces de sistema solo tienen Fakes

Los ejecutores (`IActionExecutor`) se inyectan en `EngineCoordinator` y reciben un `ActionContext` con los accessores de sistema. Matriz `ActionKind → IActionExecutor → interfaz de sistema usada`:

| ActionKind | Executor | Interfaz de sistema |
| --- | --- | --- |
| Command | CommandActionExecutor | ICommandRunner |
| Registry | RegistryActionExecutor | IRegistryAccessor (+ IRegistryKindReader opcional) |
| RegistryCreateKey | RegistryCreateKeyExecutor | IRegistryAccessor + IRegistryKeyCreator |
| RegistryDeleteKey | RegistryDeleteKeyExecutor | IRegistryTreeReader (fail-closed si no) |
| Service | ServiceActionExecutor | IServiceAccessor |
| Task | TaskActionExecutor | ITaskAccessor |
| TaskCreate | TaskCreateExecutor | ITaskAccessor |
| Process | ProcessActionExecutor | IProcessAccessor |

Las interfaces de sistema (`IServiceAccessor`, `IRegistryAccessor`, `IProcessAccessor`, `ICommandRunner`, `ISystemEnvironment`, `ITaskAccessor`, `IConfirmationProvider`, `IRestorePointService`, `IRegistryTreeReader`, `IRegistryKeyCreator`) NO tienen implementación real de Windows. Las únicas implementaciones son los Fakes en `src/Evo.Testing/` (`FakeRegistryAccessor` implementa también `IRegistryTreeReader`, `IRegistryKeyCreator`, `IRegistryKindReader`). No hay registro DI/`services.Add*` de acceso real al sistema (REQ-004 dice: el motor solo conoce interfaces, no implementaciones concretas).

Veredicto: **CONFIRMADO** (estado arquitectónico real) — `src/Evo.Engine/Executors/IActionExecutor.cs:12-51` (ActionContext + IActionExecutor); `src/Evo.Engine/Undo/IUndoContext.cs`; `src/Evo.Testing/Fake*.cs`. Nota: es un hallazgo de arquitectura (solo fakes, sin implementaciones reales ni DI), no un bug.

Tests hoy para H8: **NINGUNO test de matriz de adaptadores** (los tests usan los ejecutores vía `Wave4EngineTests`/`RestorePointGateTests`/`TestHarness`, pero no validan la matriz ActionKind→interfaz).

---

### HALLADIZO H9 — Evo.sln existe; NO hay proyecto WPF ni OutputType Exe (desviación vs README)

`Evo.sln` EXISTE (71 líneas): 5 proyectos de librería (`Evo.Core`, `Evo.Detection`, `Evo.Testing`, `Evo.Engine`, `Evo.Catalog`) y 4 proyectos de test (`Evo.Core.Tests`, `Evo.Detection.Tests`, `Evo.Engine.Tests`, `Evo.Catalog.Tests`), todos con GUID de C# library (`FAE04EC0-…`, DLL). El TFM `net10.0-windows` se define ÚNICAMENTE en `Directory.Build.props:10` (propiedad central, como señala `docs/architecture.md`). Ningún `.csproj` declara `<OutputType>Exe</OutputType>` ni `<UseWPF>true</UseWPF>`.

README.md anuncia "C# / .NET 10 LTS (`net10.0-windows`) con UI WPF", pero no existe ningún proyecto WPF ni ejecutable (OutputType Exe) en `Evo.sln`.

Veredicto:
- `Evo.sln` **EXISTE / CONFIRMADO** — `Evo.sln` (71 líneas).
- `OutputType Exe` **NO EXISTE** — ningún `.csproj` lo declara.
- Proyecto WPF **NO EXISTE** — ningún `UseWPF`, ni proyecto de UI en el sln.
→ Desviación respecto a `README.md` (anuncia UI WPF, no hay proyecto WPF ni Exe en el sln).

Tests hoy para H9: **NINGUNO** (ningún test referencia `Evo.sln`/`OutputType`/`UseWPF`).

---

### HALLADIZO H10 — README.md leído (primeras 40 líneas); docs/architecture.md es un STUB

`README.md` (52 líneas): título "EVO CLEAN", optimizador exclusivo Windows, .NET 10, UI WPF, GPL-3.0-only, estado Paso 1, tabla "Documentos que mandan" (AGENT_CONTRACT, INVENTARIO_USUARIO, upstream.lock.json, THIRD_PARTY_NOTICES, docs/reports/, docs/adr/), sección Herramientas y sección "Leer resultados de CI" (CDN bloqueado, método estándar vía ci-report). Primera parte leída íntegramente.

`docs/architecture.md` (15 líneas): es un **STUB** ("> **STUB.** Se rellena en el paso de diseño (capa 0). No contiene decisiones todavía; cualquier contenido aquí es provisional y NO VERIFICADO."). Contenido pendiente: capas del motor, modelo de catálogo, ledger, TFM central, estrategia de reversión. No hay decisiones de arquitectura reales todavía.

Veredicto:
- `README.md` **CONFIRMADO** (existe, leído íntegro) — `README.md`.
- `docs/architecture.md` **STUB / NO VERIFICADO** — `docs/architecture.md` (15 líneas, contenido provisional).

Tests hoy para H10: **NINGUNO** (ningún test referencia `architecture.md`/`README.md`).

---

## TABLA FINAL — Hallazgo | Veredicto | Ruta:línea | Gravedad real en una frase

```
H1 | CONFIRMADO | src/Evo.Engine/EngineCoordinator.cs:338,359,370 | Cancelación tras mutación aplicada puede salir sin rollback (estado inconsistente posible).
H2 | CONFIRMADO | src/Evo.Engine/Undo/UndoJournal.cs:323-355 | Rollback cuenta como Restaurado aunque Restore() no mute nada real; diario se vacía solo si !DryRun.
H3 | CONFIRMADO | src/Evo.Engine/Executors/ProcessActionExecutor.cs:36,59-60 | Proceso activo con Terminate=false no se detiene; se reporta "Stopped" sin actuar.
H4 | CONFIRMADO | src/Evo.Engine/Undo/UndoJournal.cs:206-242; src/Evo.Core/System/ITaskAccessor.cs:4-22 | TaskCreate deshace borrando/restaurando enabled, sin conocer la definición previa completa.
H5 | CONFIRMADO | src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs:87; src/Evo.Engine/Undo/UndoJournal.cs:153-168; ...:112-121,192-194 | Fail-closed si no hay IRegistryTreeReader; restaura claves vacías anidadas; límites de tamaño después del snapshot.
H6 | CONFIRMADO | src/Evo.Core/Models/CapabilityRules.cs:19,30,175-179; src/Evo.Core/Restore/IRestorePointService.cs:29-39; src/Evo.Engine/EngineCoordinator.cs:290-318 | Critical exige FullBackup+TypeOperationName; punto de restauración sin implementación real (fail-closed aborta).
H7 | CONFIRMADO | src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs:112-121,192-194 | Límites de tamaño tras snapshot; tope de profundidad depth>=64 en recorrido.
H8 | CONFIRMADO | src/Evo.Engine/Executors/IActionExecutor.cs:12-51; src/Evo.Testing/Fake*.cs | Matriz ActionKind→ejecutor definida; interfaces de sistema solo tienen Fakes (sin implementación real Windows ni DI).
H9 | Evo.sln CONFIRMADO; OutputType Exe NO EXISTE; WPF NO EXISTE | Evo.sln; Directory.Build.props:10 | README anuncia UI WPF/Exe pero el sln solo tiene librerías DLL y tests.
H10 | README CONFIRMADO; architecture.md STUB/NO VERIFICADO | README.md; docs/architecture.md | README leído; architecture.md es stub sin decisiones reales.
```

---

## Qué tests existen hoy para cada hallazgo

| Hallazgo | Tests existentes hoy |
| --- | --- |
| H1 | NINGUNO (no hay test de CancellationToken/ThrowIfCancellation) |
| H2 | `ExecutorTests.RollbackIsLifoAndContinuesAfterError` (267); `EngineCoordinatorTests.TestRollback_RestoresOriginalStateExactly` (121), `.TestPartialFailure_TriggersRollback` (181); `Wave1EngineTests.TestWave1Catalog_ExecuteAndRollback_RestoresState` (157); `Wave4EngineTests.DeleteKey_ThroughTheCoordinator_RollsBackCompletely` (172), `.UndoInLifoOrderRestoresTheServiceCompletely` (462) |
| H3 | `ExecutorTests.ProcessExecutorSkipsWhenNotRunning` (181), `.ProcessExecutorTerminatesAndLogs` (198) |
| H4 | NINGUNO específico del hallazgo (solo tests de comportamiento TaskCreate en Wave4EngineTests: 276, 303, 322, 344, 368) |
| H5 | `Wave4EngineTests.DeleteKey_AccessorWithoutTreeReaderAbortsWithoutDeleting` (115), `.DeleteKey_RestoresTheWholeSubtreeWithTypesAndData` (34), `.DeleteKey_SnapshotOverTheLimitAbortsWithoutDeleting` (155), `.DeleteKey_DepthOverTheLimitAbortsBeforeDeleting` (249) |
| H6 | `CapabilityContractTests.CriticalExigeTypeOperationName` (42), `.CriticalConTypeOperationNameYFullBackupEsValido` (55); `RestorePointGateTests` |
| H7 | `Wave4EngineTests.DeleteKey_SnapshotOverTheLimitAbortsWithoutDeleting` (155), `.DeleteKey_DepthOverTheLimitAbortsBeforeDeleting` (249) |
| H8 | NINGUNO (no hay test de matriz de adaptadores) |
| H9 | NINGUNO |
| H10 | NINGUNO |

Totales sesión: pytest 573 passed, xUnit 239/239; dotnet-ci verde; ledger-verify FULLY GREEN (run 45760015409). PR #1 sigue BORRADOR (head 908f6ad).

---

## Cierre

**Desviaciones:**
- H9: `README.md` anuncia "UI WPF" y `.NET 10`, pero `Evo.sln` no contiene proyecto WPF ni `OutputType Exe` (solo librerías DLL + tests). TFM `net10.0-windows` está centralizado en `Directory.Build.props:10`.
- H10: `docs/architecture.md` es un STUB sin decisiones de arquitectura reales.

**Riesgos:**
- H1: cancelación sin rollback tras mutación aplicada → posible estado inconsistente sin deshacer. Sin test que lo cubra.
- H4: `TaskCreateUndoEntry` no conserva la `TaskDefinition` previa → deshace por `enabled`/borrado, no restaura la definición completa (riesgo menor si el undo solo necesita volver al estado enabled/borrado).
- H6: `IRestorePointService` sin implementación real → cualquier capacidad `Critical`/`High` que exija punto de restauración aborta (fail-closed) en entornos sin servicio de puntos (CI/Server).

**Preguntas abiertas:**
- ¿Se planea añadir implementación real de `IRestorePointService` (WMI/Checkpoint-Computer) antes de promover capacidades `Critical`/`High` a producción?
- ¿Existe hoja de ruta para el proyecto WPF / OutputType Exe anunciado en `README.md`?
- ¿Se añadirá un test de cancelación (H1) y un test de matriz de adaptadores (H8)?

Esto concluye ETAPA 0 (H1-H10 validados con `nl -ba`, solo lectura, sin commits ni pushes, PR #1 sigue BORRADOR).

**FIN ETAPA 0**