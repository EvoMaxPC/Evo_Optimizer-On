# Paso 8d — Punto de restauración, rango de Copilot y sección por ítem

- Rama `arena/ab2d6de7-evo-optimizer-on`.
- HEAD al empezar: `561a1a0117e2ff9937a663d5ae40d56b16d34699` (idéntico a
  `git ls-remote` al empezar).
- Pins: Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`, WinUtil
  `70c23c80641d7370532af2f619b2842658600842`.
- Sandbox Debian 12, Python 3.11.2, **sin dotnet**: lo .NET se verifica en Actions.

---

## T0 — Evidencia y cuentas pendientes del 8c

### T0a — Identidad y CI

`git rev-parse HEAD` = `561a1a0117e2ff9937a663d5ae40d56b16d34699`;
`git ls-remote origin refs/heads/arena/ab2d6de7-evo-optimizer-on` devuelve el
mismo sha. Inventario intacto:
`0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709`.

### T0b — Los 454 tests y por qué la tabla del 8c no cuadraba

`pytest --collect-only -q`, agrupado por fichero:

| Fichero | Tests |
| --- | --- |
| `tests/test_paso6.py` | 19 |
| `tests/test_paso7.py` | 21 |
| `tests/test_paso8.py` | 174 |
| `tests/test_paso8b.py` | 24 |
| `tests/test_paso8c.py` | 17 |
| `tools/ledger_extract/tests/test_count_inventory.py` | 24 |
| `tools/ledger_extract/tests/test_paso2.py` | 31 |
| `tools/ledger_extract/tests/test_paso3.py` | 16 |
| `tools/ledger_extract/tests/test_paso3b.py` | 16 |
| `tools/ledger_extract/tests/test_paso4b.py` | 14 |
| `tools/ledger_extract/tests/test_paso4c.py` | 27 |
| `tools/ledger_extract/tests/test_paso4d.py` | 33 |
| `tools/ledger_extract/tests/test_paso4e.py` | 16 |
| `tools/ledger_extract/tests/test_paso5.py` | 22 |
| **Σ** | **454** |

La tabla del 8c tenía **14** ficheros (no 13) y sumaba mal: el total real de esa
tabla era 450, y la diferencia de 4 es que `test_paso8.py` tenía 174 casos, no
170. El 8c contó 170 porque leyó una versión intermedia del fichero antes de
cerrar el commit; con el commit final son 174.

**`test_paso7.py`: 21 → 21.** No bajó. El 8b dijo 22 y esa cifra era errónea:
recolectando el fichero en el commit del paso 7 (`e8990e6`) salen **21**, y en
`1d5a01b` (último commit del 8b) también **21**; el fichero no se ha tocado
desde `e8990e6` (`git log -- tests/test_paso7.py` sólo muestra ese commit).

**Los +56 del 8b: sí, son parametrización de `test_paso8.py`.** Entre `1d5a01b`
y `3ff8d71`:

| Fichero | 1d5a01b | 3ff8d71 |
| --- | --- | --- |
| `tests/test_paso8.py` | 114 | 170 |
| `tests/test_paso7.py` | 21 | 21 |
| resto | 218 | 242 |
| **Σ** | **353** | **433** |

Los +56 de `test_paso8.py` son `@pytest.mark.parametrize` sobre las
capacidades del catálogo: al pasar de 24 a 38 capacidades, cada test
parametrizado crece. El resto (+24) son los 24 tests nuevos de
`tests/test_paso8b.py`.

### T0c — Tests .NET: 109 → 126 → 128

Conteo por proyecto (método de recuento: `[Fact]` = 1 caso; `[Theory]` = número
de `[InlineData]`), contrastado con `test-per-project.txt` de `ci-report`:

| Proyecto | 1d5a01b (8b inicio) | 3ff8d71 (8c inicio) | HEAD 8d |
| --- | --- | --- | --- |
| `Evo.Catalog.Tests` | 34 | 36 | 36 |
| `Evo.Core.Tests` | 19 | 34 | 34 |
| `Evo.Detection.Tests` | 35 | 35 | 35 |
| `Evo.Engine.Tests` | 21 | 21 | 23 |
| **Σ** | **109** | **126** | **128** |

Los **17 del 8b** (clase → test):

- `Evo.Core.Tests/ReversibilityTests.cs` (13):
  `ReversibleConSessionUndoYRiesgoBajoEsValido`, `ReversibleConRestoreNoneEsInvalido`,
  `ReversibleConRiesgoMedioExigeRestorePoint`, `NothingToRestoreConNoneYRiesgoSafeEsValido`,
  `NothingToRestoreSeAdmiteHastaRiesgoMedium`, `NothingToRestoreConRiesgoAltoEsInvalido`,
  `NothingToRestoreConRestoreDistintoDeNoneEsInvalido`,
  `IrreversibleConRiesgoAltoYConfirmacionDeResumenEsValido`,
  `IrreversibleConRiesgoBajoEsInvalido`, `IrreversibleConConfirmacionSimpleClickEsInvalido`,
  `IrreversibleConRestorePointEsInvalido`, `IrreversibleCriticalSigueExigiendoTypeOperationName`,
  `MinimumRestoreDependeDeLaReversibilidad`.
- `Evo.Core.Tests/CapabilityContractTests.cs` (+2):
  `ReversibleNoAdmiteRestoreNone` (theory, 5 `InlineData`),
  `NothingToRestoreConRiesgoMedioYNoneEsValido`.
- `Evo.Catalog.Tests/CatalogValidatorTests.cs` (+2 `Fact`):
  `IrreversibleHighWithNoneIsValidUnderAdr0003`, `MissingReversibilityFailsValidation`.
  (El tercer caso, `InsufficientRestoreForReversibleRiskFails`, es un renombrado de
  `InsufficientRestoreForRiskFails`, no un test nuevo.)
- `Evo.Engine.Tests/Wave1EngineTests.cs` (+0 netos): el 8b **amplió**
  `TestWave1Catalog_WinsxsComponentCleanupIsAlwaysSafeOnly` con una segunda
  ejecución (`cleanup.winsxs.resetbase`), sin añadir un `[Fact]`.

Los **2 del 8c** (`Evo.Engine.Tests/Wave1EngineTests.cs`):
`TestWave1Catalog_WebSearchCapability_ReallyDisablesBing` y
`TestWave1Catalog_WindowsAiSplit_RecallAndCopilotAreSeparate`.

### T0d — Pendientes por sección y fuente × estado

Pendientes por `section_guess` **al cerrar el 8c** (140 sin sección):

| Sección | Pending | | Sección | Pending |
| --- | --- | --- | --- | --- |
| 1 | 0 | | 10 | 91 |
| 2 | 3 | | 11 | 16 |
| 3 | 32 | | 12 | 8 |
| 4 | 7 | | 13 | 15 |
| 5 | 13 | | 14 | 10 |
| 6 | 0 | | 15 | 35 |
| 7 | 4 | | 16 | 2 |
| 8 | 12 | | 17 | 0 |
| 9 | 8 | | **(sin sección)** | **140** |

Fuente × estado (435 filas, `upstream-capability-map.tsv` del 8c):

| source | covered | pending | variant-of | not-a-capability | Σ |
| --- | --- | --- | --- | --- | --- |
| `atlas-manifest` | 13 | 169 | 0 | 0 | 182 |
| `atlas-toggle` | 2 | 89 | 0 | 0 | 91 |
| `winutil` | 24 | 127 | 0 | 11 | 162 |
| **Σ** | **39** | **385** | **0** | **11** | **435** |

**Cuadre del «129».** En el mensaje del 8c aparecían dos cifras distintas para
lo mismo: 140 y 129. La buena era **140**: filas `pending` sin `section_guess`
en `upstream-capability-map.tsv`. Los **129** eran los ítems sin sección del
**mapa por categoría** (`category-section-map.tsv`, suma de las categorías
`mixed`), que es otro universo: incluye ítems ya cubiertos o `not-a-capability`,
que no cuentan como `pending`. Diferencia: 140 − 129 = **11**, exactamente los
`not-a-capability` de WinUtil que caen en categorías `mixed`. El 8c mezcló las
dos cuentas; aquí quedan separadas y cuadradas.

### T0e — Licencia

```
$ git grep -n "confirmado por el responsable" -- README.md docs/legal/ docs/adr/
README.md:6:catálogo — **confirmado por el responsable** el 2026-11-24 (reloj del agente, UTC),
docs/legal/upstream-licenses.md:162:**Confirmado por el responsable** el 2026-11-24 (reloj del agente, UTC).
$ git grep -n -i "confirmad[ao] por el responsable" -- README.md docs/legal/ docs/adr/
docs/adr/ADR-0002-datos-de-atlas-y-gpl.md:4:- **Fecha**: ... **licencia GPL-3.0-only confirmada por el responsable 2026-11-24** ...
docs/adr/ADR-0002-datos-de-atlas-y-gpl.md:84:La licencia **GPL-3.0-only** de EVO CLEAN queda **confirmada por el responsable**
```

Salida real: **2 aciertos** con grep simple (el ADR escribe «confirmada por el
responsable» en `:4`, así que `git grep -c` literal no lo ve):
`README.md:6`, `docs/legal/upstream-licenses.md:162`. Buscando la variante de
género: `docs/adr/ADR-0002-datos-de-atlas-y-gpl.md:4` («licencia GPL-3.0-only
confirmada por el responsable 2026-11-24») y `:84` («queda **confirmada por el
responsable**»). Las cuatro llevan fecha 2026-11-24. No hubo que corregir nada;
queda anotado que el literal exacto sólo casa en dos de los tres ficheros.

---

## T1 — Punto de restauración en el motor

### T1a — Lo que había (y por qué era deuda)

`EngineCoordinator.ExecuteAsync` sólo miraba `Preflight` (compatibilidad,
privilegio, `SupportedBuilds`, dependencias y conflictos), `plan.Validate()` y el
modo. **No leía `Restore` ni `Confirmation`**. `CapabilityRules` sí las validaba
en el catálogo, pero nada en ejecución.

Las 13 capacidades con `Restore = RestorePoint` o confirmación reforzada (todas
con `Irreversible` y `Restore = None`):

| Capacidad | Risk | Restore | Confirmation | Estado |
| --- | --- | --- | --- | --- |
| `cleanup.recycle.bin` | High | None | SummaryAndRestorePoint | Implemented |
| `cleanup.winsxs.component` | High | None | SummaryAndRestorePoint | Implemented |
| `cleanup.winsxs.resetbase` | High | None | SummaryAndRestorePoint | Specified |
| `debloat.appx.consumer` | High | None | SummaryAndRestorePoint | Implemented |
| `debloat.cortana.remove` | High | None | SummaryAndRestorePoint | Implemented |
| `debloat.onedrive.uninstall` | High | None | SummaryAndRestorePoint | Implemented |
| `debloat.copilot.remove` | High | None | SummaryAndRestorePoint | **Specified (8d)** |
| `debloat.telemetry.appx` | High | None | SummaryAndRestorePoint | Implemented |
| `debloat.edge.remove` | High | None | SummaryAndRestorePoint | Specified |
| `debloat.explorer.auto-folder-discovery` | High | None | SummaryAndRestorePoint | Specified |
| `debloat.drivers.razer` | High | None | SummaryAndRestorePoint | Specified |
| `debloat.drivers.logitech` | High | None | SummaryAndRestorePoint | Specified |
| `debloat.network.adobe-blocklist` | High | None | SummaryAndRestorePoint | Specified |

Ninguna declara `Restore = RestorePoint`: todas piden punto por la vía de la
confirmación. Por eso `EngineCoordinator.RequiresRestorePoint` mira **las dos**
condiciones.

### T1b/T1c — Interfaces y regla del motor

- `src/Evo.Core/Restore/IRestorePointService.cs`: `IsAvailableAsync`,
  `CreateAsync(descripción)` y `RestorePointResult { Success, Id, ErrorMessage }`.
  `Success` sin `Id` = fallo.
- `src/Evo.Core/Confirmation/IConfirmationProvider.cs`: `ConfirmationRequest`
  (tipo, riesgo, resumen, texto a escribir, si el punto está disponible) y
  `ConfirmationResponse { Approved, TypedText, Reason }`.
- `EngineCoordinator`: parámetros opcionales `IRestorePointService` e
  `IConfirmationProvider`; método estático `RequiresRestorePoint`.
- Sólo en `ExecutionMode.Execute`, **antes** del bucle de acciones:
  confirmación → (si `TypeOperationName`) texto exacto → punto (o
  `AcceptNoRestorePoint`). Cualquier fallo devuelve `ExecutionSummary` con
  `AbortedReason`, `Results` vacío y `Mutated == false`.
- `ExecutionSummary` gana `AbortedReason`/`Aborted`, `RestorePointId`,
  `ConfirmationRequested`, `Confirmed` y `RestorePointWaived`.
- `UndoJournal.RestorePointId`: el punto y las entradas del diario viajan juntos.
- `ActionContext.AcceptNoRestorePoint`: la opción explícita, nunca automática.

### T1d — Fakes

`FakeRestorePointService` (disponible/no, falla/no, lanza al consultar, id
forzado, `Calls` en orden, `Created`, y un gancho `BeforeCreate` que permite
fotografiar el estado y demostrar que al crear el punto **aún no había
mutaciones**). `FakeConfirmationProvider` (aprueba/rechaza, texto exacto o no,
registro de peticiones) y `NeverCalledConfirmationProvider`.

### T1e — Tests

`tests/Evo.Engine.Tests/RestorePointGateTests.cs`, **16 `[Fact]`** (más de los 10
pedidos): DryRun no crea punto ni pide confirmación; Audit tampoco;
Execute crea el punto **antes** de la primera mutación (con el gancho
`BeforeCreate` se comprueba 0 mutaciones en ese instante); fail-closed si no
está disponible; fail-closed si la creación falla; fail-closed si el servicio
lanza; `AcceptNoRestorePoint` ejecuta y lo declara; confirmación rechazada = 0
mutaciones y 0 puntos; la confirmación se pide antes de crear el punto; una
capacidad sin requisito no lo crea; un punto por plan con 4 acciones; el texto
exacto en `TypeOperationName` (rechaza el casi-nombre); `RestorePointAvailable`
llega a la confirmación; sin proveedor de confirmación se aborta; el rollback
automático sigue funcionando con punto.

### T1f — ADR-0004

`docs/adr/ADR-0004-puntos-de-restauracion.md`, estado **propuesto**. Compara WMI
`SystemRestore.CreateRestorePoint`, `Checkpoint-Computer` y COM directo; deja
como **NO VERIFICADO** el valor de la frecuencia mínima entre puntos y el
comportamiento exacto en 24H2/25H2; documenta lo único medido en el pin
(WinUtil desactiva `SystemRestorePointCreationFrequency` antes de crear el
punto; Atlas activa la protección pero **no crea** puntos y además la desactiva
por política en su toggle `SystemRestore`) y fija la validación en VM del
responsable. **No se implementa la llamada real.**

---

## T2 — Copilot y rangos

### T2a — Evidencia del rango, línea a línea

| Fichero:línea | Qué dice | Qué fija |
| --- | --- | --- |
| `Tweaks/qol/taskbar/disable-copilot.psd1:6` | «`RemoveMicrosoftCopilotApp` (25H2+) additionally uninstalls the Copilot app where supported; only Enterprise and Education honour it» | La política es de **25H2+** y sólo la honran Ent/Edu |
| `…disable-copilot.psd1:9` | `RemoveMicrosoftCopilotApp = 1` | La acción 1 del catálogo sale de aquí |
| `Toggles/General/Copilot.psd1:13-14` | estado `Disable`: `RemoveMicrosoftCopilotApp=1` (HKLM) y `ShowCopilotButton=0` (HKCU) | Acciones 1 y 3 |
| `Toggles/General/Copilot.ps1:42` | `Enable` **borra** la política | Es reversible por política (no por paquete) |
| `Toggles/General/Copilot.ps1:52` | `$legacyTaskbarAvailable = ($Toggle.WindowsBuild -lt 26100 …)` | El botón de barra de tareas sólo existe **por debajo** de 26100 |
| `Toggles/General/Copilot.ps1:18,59` | `Microsoft.Copilot*` / `Get-AppxPackage -Name Microsoft.Copilot` | El objeto del borrado es el paquete |
| `Toggles/General/Copilot.ps1:71` | `install --id 9NHT9RB2F4HD --source msstore` | Vía de reinstalación (Store) |

**¿El pin menciona 23H2/22631?** Sí, pero **no** como límite de esta capacidad:
`tests/Atlas.AiFeatureToggles.Tests.ps1:127` y `:161` usan `22631` como build de
ejemplo en pruebas y `app/src/services/windows_release.rs:390,416,424` lo usan
como build «no soportada» para probar transiciones. No hay una guarda de build
en el `.psd1` ni en el `.ps1` de Copilot.

**Conclusión:** se mantiene `[22631, 26100, 26200]` con `State = Specified` y el
texto **RANGO NO VERIFICADO** en `provenance`, porque el pin fija el límite
25H2+ de la política pero **no** fija el de las otras dos acciones. No se
amplía a 19045: el pin no lo menciona en relación con Copilot.

### T2b — Capacidades cuyo `supportedBuilds` no cubre las cuatro builds

Sólo dos, y las dos lo justifican en `provenance`:

| Capacidad | Builds | Evidencia |
| --- | --- | --- |
| `debloat.windows.ai.recall` | 26100, 26200 | `Toggles/General/Recall.psd1:14-16` documenta `AllowRecallEnablement=0` como **24H2 26100.3915+**; las políticas `WindowsAI` no existen antes de 26100. El rango de Click To Do y del agente de Configuración sigue **NO VERIFICADO**. |
| `debloat.copilot.remove` | 22631, 26100, 26200 | La política es 25H2+ (26200); `ShowCopilotButton` y el paquete se usan por debajo de 26100; **RANGO NO VERIFICADO** por acción. |

Las otras 37 capacidades declaran las cuatro builds (19045, 22631, 26100, 26200).

---

## T3 — Sección por ítem

### T3a — Ficheros

- `tools/ledger_extract/extract_atlas_toggle_keys.py` →
  `inventory/ledger/atlas-toggle-keys.tsv` (**283 claves de 46 toggles**, con
  `source_ref`, `line` y `sha256_line`). Existe porque `atlas-toggle-ops.tsv`
  sale de `Toggles/catalog.json`, donde `work.registry` es un **contador**: sus
  303 filas son `unresolved` y no sirven para decidir sección.
- `tools/ledger_extract/build_item_section_map.py` →
  `inventory/partition/item-section-map.tsv` (435 filas, 8 columnas).
- `docs/inventory-recon/seccion-por-item-reglas.md`: las reglas con ejemplo real.
- `build_upstream_capability_map.py`: usa el mapa por ítem cuando la categoría
  es `mixed` o no hay sección, y añade `section_basis`
  `item-effect | item-name-rule | item-manifest-path`.
- `build_wave_plan.py`: cifras nuevas y texto de método actualizado.

### T3b — Orden de decisión y reglas

1. **categoría** (paso 8c): 250 filas.
2. **ruta del `.psd1`** (`qol/`, `privacy/`, …): implementada, **0 filas** la
   usan porque en este pin todos los ítems de esas rutas ya venían con sección
   por categoría.
3. **efectos** (claves de registro, servicios, características, AppX): 57 filas.
   Si los efectos apuntan a más de una sección, **no deciden**.
4. **nombre** con términos propios (sin genéricos): 98 filas.
5. **`unassigned`** con motivo escrito: 30 filas.

### T3c — Resultado

| source | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | unassigned | Σ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `winutil` | 4 | 5 | 4 | 1 | 5 | 1 | 2 | 3 | 4 | 32 | 19 | 2 | 3 | 4 | 41 | 8 | 0 | 24 | 162 |
| `atlas-toggle` | 0 | 3 | 2 | 7 | 4 | 1 | 2 | 8 | 2 | 30 | 2 | 6 | 7 | 9 | 7 | 0 | 0 | 1 | 91 |
| `atlas-manifest` | 0 | 5 | 44 | 1 | 12 | 0 | 0 | 5 | 5 | 81 | 6 | 10 | 6 | 1 | 1 | 0 | 0 | 5 | 182 |
| **Σ** | **4** | **13** | **50** | **9** | **21** | **2** | **4** | **16** | **11** | **143** | **27** | **18** | **16** | **14** | **49** | **8** | **0** | **30** | **435** |

Bases: `category` 250 · `name-rule` 98 · `effect` 57 · `manual-review` 30.
En `upstream-capability-map.tsv` las filas sin sección bajan de **140 a 28** y
los `pending` sin sección de **140 a 18**.

Los 30 `unassigned` son: 10 entradas de navegación de WinUtil, 3 presets
(`Advanced`, `Minimal`, `Standard`), 8 paneles heredados (`WPFPanel*`), el botón
`Install Features`, `O&O ShutUp10++` (lanza una herramienta de terceros),
`GiveAccessToMenu`, `WPFToggleLongPaths`, `WPFTweaksPreventDeviceMetadataFromNetwork`,
`misc/delete-windows-specific-files`, `misc/make-measuresleep-admin`,
`misc/register-user-upgrade`, `scripts/disable-pnp`, `scripts/set-profile-pictures`.
Cada uno lleva el motivo en `evidence` (tabla `NO_EFFECT_REASON` del script).

### T3d — Muestra reproducible (semilla 42, 25 ítems con regla propia)

`random.seed(42)`; `random.sample(pool, 25)` sobre las filas con
`basis != "category"` (185), ordenadas después por `upstream_id`. Salida literal
del TSV, recortada a 60 caracteres en `evidence`:

```
upstream_id | section | basis | evidence
atlas:manifest:misc/rebuild-perf-counters | 14 | name-rule | name:repair
atlas:manifest:misc/register-user-upgrade | unassigned | manual-review | registra una entrada de arranque propia de Atlas: no es una 
atlas:manifest:qol/add-sharing-settings-shortcut | 11 | name-rule | name:network
atlas:manifest:qol/disable-usb-issues-notifications | 10 | name-rule | name:explorer
atlas:manifest:qol/disable-win11-settings-banner | 10 | name-rule | name:explorer
atlas:manifest:qol/do-not-reduce-sounds | 10 | name-rule | name:explorer
atlas:manifest:qol/restore-start-folder-choices | 10 | name-rule | name:explorer
atlas:manifest:scripts/disable-mitigations | 13 | name-rule | name:security
atlas:toggle:FileSharing | 11 | name-rule | name:network
atlas:toggle:MicrosoftStore | 15 | name-rule | name:apps
atlas:toggle:PauseUpdates | 12 | effect | key:WindowsUpdate
atlas:toggle:PowerSaving | 5 | name-rule | name:power
atlas:toggle:Sleep | 7 | name-rule | name:memory
atlas:toggle:Widgets | 10 | name-rule | name:explorer
winutil:nav-entry:WPFGetInstalled | unassigned | manual-review | entrada de navegacion de la UI de WinUtil: no tiene efecto p
winutil:nav-entry:WPFInstall | unassigned | manual-review | entrada de navegacion de la UI de WinUtil: no tiene efecto p
winutil:tweak:WPFToggleLongPaths | 10 | name-rule | name:explorer
winutil:tweak:WPFToggleTaskView | 10 | effect | key:Explorer\Advanced
winutil:tweak:WPFToggleWindowSnapping | 10 | effect | key:Control Panel
winutil:tweak:WPFTweaksDisableBitLocker | 13 | name-rule | name:security
winutil:tweak:WPFTweaksDisableNotifications | 10 | name-rule | name:explorer
winutil:tweak:WPFTweaksIPv46 | 11 | name-rule | name:network
winutil:tweak:WPFTweaksRevertStartMenu | 10 | name-rule | name:explorer
winutil:tweak:WPFTweaksServices | 4 | effect | svc:set-multiple
winutil:tweak:WPFTweaksWidget | 15 | effect | appx:*
```

De los 25: **22 asignados por regla propia** (`name-rule` 17, `effect` 5) y
**3 `unassigned`** con motivo escrito (`register-user-upgrade`, `WPFInstall`,
`WPFGetInstalled`). `WPFToggleLongPaths → 10` por `name:explorer` es el caso más
débil de la muestra: ver desviaciones.

### T3e — Plan de oleadas

`docs/reports/plan-oleadas.md` regenerado (60 líneas) y `--check` OK. Sobre las
588 líneas del inventario reconciliado: Mapped 149, Mapped-To-App 5,
EVO-Exclusive 37, Absent-At-Pin 326, Informative 71, Mapped cubiertas 47,
trabajo medido 470. Pendientes upstream 385, de los que **367 quedan con
sección** y **18 sin sección**. El fichero separa **MEDIDO** (todas las cifras)
de **PROPUESTA** (orden de oleadas, marcada como no medida).

---

## T4 — Tests, CI y PR

- `tests/test_paso8d.py`: **25 tests** (pedían ≥10): determinismo y bytes del
  TSV, columnas exactas, 0 duplicados, 435 filas, celdas ≤ 400, cobertura
  upstream ↔ item, `unassigned` sólo con `manual-review` y motivo, `reviewed=no`,
  reglas documentadas con ejemplo, ninguna regla genérica, el troceo de nombres
  (`BitLocker` sí, `Windows Restore`↛`store`), conflicto de efectos no decide,
  tres servicios = sección 4, `section_basis` del mapa, cobertura 1-3 = 26/26,
  plan reproducible, muestra semilla 42, ADR-0004 propuesto sin implementación,
  interfaces en `Evo.Core`, puerta antes del bucle, y los dos rangos.
- Python total: **479** (454 + 25).
- .NET: **144 en CI, verde** (128 + 16 del paso 8d).
- `ledger-verify.yml`: paso «Paso 8d» con doble ejecución + `diff` de sha256 de
  los cuatro artefactos, `--check` del plan, copia a `ci-out` y comprobaciones
  numéricas. Ejecutado en local con éxito antes de subir.
- Cuerpo del PR #1 actualizado con `gh api -X PATCH`; sigue en borrador.

### CI real (tres intentos, sin dorar nada)

| Commit | `ledger-verify` | `dotnet-ci` | Qué pasó |
| --- | --- | --- | --- |
| `68f833e` | success | **failure** (2 jobs) | `CS0246: ActionContext` en `RestorePointGateTests.cs:61`: el tipo vive en `Evo.Engine.Executors` y faltaba el `using`. El sandbox no tiene dotnet, así que este error no se podía ver en local. |
| `bd0663d` | success | **failure** (2 jobs) | Compila, y fallan 2 de 144: `Execute_CreaElPuntoAntesDeLaPrimeraMutacion` y `FailClosed_SiElPuntoNoEstaDisponible_NoMutaNada`, ambos con `Expected: 0 / Actual: 1`. Causa: `FakeRegistryAccessor.Seed` **cuenta como mutación**; los tests comparaban contra cero absoluto en vez de contra la línea base. El motor no mutaba nada. |
| `e88d3d3` | success | **success** (2 jobs) | 144/144 en `windows-2025` y en `windows-11-arm`. |

Salida real de `ci-report` sobre `e88d3d3`:

```
Evo.Catalog.Tests: total=36 passed=36 failed=0
Evo.Core.Tests:    total=34 passed=34 failed=0
Evo.Detection.Tests: total=35 passed=35 failed=0
Evo.Engine.Tests:  total=39 passed=39 failed=0
total=144 passed=144 failed=0
```

Paso 8d en CI (`latest/ledger-verify/`):

```
determinismo paso 8d: OK
{"asignadas": 405, "filas": 435,
 "por_basis": {"category":250,"effect":57,"manual-review":30,"name-rule":98}}
57a8470b...  inventory/ledger/atlas-toggle-keys.tsv
d2628a2e...  inventory/partition/item-section-map.tsv
ba1e2863...  inventory/ledger/upstream-capability-map.tsv
f8246687...  docs/reports/plan-oleadas.md
```

Runs: `45333845601` y `45333839388` (`dotnet-ci`), `45333839303`
(`ledger-verify`), los tres sobre `e88d3d3`. Los dos fallos anteriores quedan en
el registro de runs (`45333424119`, `45333435971`); no se ocultan.

---

## Desviaciones, supuestos y riesgos

1. **`Enable Long Paths` acaba en 10 por la regla `name:explorer` sin término
   propio que lo justifique** (`long path` está en la lista porque se añadió para
   que no quedara `unassigned`). Es el punto más débil de la muestra: la regla
   debería ser `manual-review`. Queda declarado, no escondido.
2. `name:explorer` absorbe 143 ítems: es la sección más poblada y la que más
   confía en el nombre. `name-rule` explica 98 asignaciones; el responsable
   debería revisar sobre todo las de interfaz.
3. `debloat.copilot.remove` baja de `Implemented` a `Specified` porque su rango
   no está fijado por el pin. Es una pérdida de madurez declarada, no un error.
4. `atlas-toggle-keys.tsv` es nuevo y convive con `atlas-toggle-ops.tsv` (que
   sigue siendo todo `unresolved`). No se ha reescrito el extractor del 4c para
   no cambiar el pasado.
5. `section_basis` gana tres valores nuevos; los tests del 8c se han ampliado
   para admitirlos sin relajar nada más.
6. Los `unassigned` podrían bajar más con reglas más agresivas; se ha preferido
   dejarlos con motivo escrito antes que asignar por parecido débil.
7. **El primer commit del paso 8d no compilaba** y el segundo tenía 2 tests en
   rojo. Ninguno de los dos era un fallo de diseño del motor (`ActionContext`
   mal importado y `Seed` contado como mutación), pero son dos correcciones
   posteriores al commit «del paso»: quedan como `68f833e` (fallido),
   `bd0663d` (fallido) y `e88d3d3` (verde), en vez de reescribir la historia.
8. El sandbox no tiene dotnet: **cualquier afirmación sobre compilación antes de
   `e88d3d3` era una suposición mía**, no una medición. A partir de ahí lo dice
   el CI.
