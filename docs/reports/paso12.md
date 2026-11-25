# Paso 12 — R1/R2/R3, `registryCreateKey` y estados contrarios

- **Fecha**: 2026-11-23
- **Rama**: `arena/ab2d6de7-evo-optimizer-on` (PR #1, **draft**)
- **Punto de partida**: `cb75abe` (paso 11 verde)
- **Estado**: cerrado. `ledger-verify` en verde con el job nuevo y `dotnet-ci`
  con los xUnit en verde —**239/239 en `windows-2025` y en `windows-11-arm`**—
  sobre `0922fb9`. La primera pasada falló con 7 casos y cuatro eran defectos
  reales que se corrigieron (§7.3).

## 1. Qué pedía el paso y qué se ha hecho

| Encargo | Estado | Dónde se ve |
| --- | --- | --- |
| **Aclaración 1** — línea 278 del inventario | Resuelta: sigue `Absent-At-Pin` | `inventory/ledger/inventory-reconciliation.tsv`; test `test_t0_la_linea_278_sigue_absent_at_pin` |
| **Aclaración 2** — fila `differs` con ruta:línea en los dos lados | Resuelta, 0 desviaciones sin excepción | `catalog/exceptions/value-deviations.json`; `inventory/ledger/catalog-value-audit.tsv` |
| **Aclaración 3** — «15 vs 11 huecos» del paso 10 | Declarada **no reproducible**: la medida da 17 cubiertas / 13 libres | `docs/reports/paso11.md` §T0-b.2 |
| **R1** — `Implemented` sólo si se expresa TODO el pin | Aplicada por código en los dos generadores | `measure_capability_completeness.py` |
| **R2** — `Improves` sólo con justificación escrita | Aplicada; **dos capacidades incumplían** y se han arreglado (§4) | `apply_r2_r3()` |
| **R3** — nada persistente con privilegios altos `Safe`/sin confirmación | Aplicada; el único caso afectado es la tarea `AutoRegBackup` | `system.registry-backup.enable` |
| **T2** — `registryCreateKey` en el motor y cerrar los `AddKey` | Hecho: acción, ejecutor, deshacer y dos capacidades | §3 |
| **T3** — medir estados contrarios de los toggles | Hecho: 20 capacidades medidas, 0 contrarios declarados | `inventory/ledger/toggle-state-audit.tsv` |
| **T4** — tests, CI, informe, ADR | Hecho salvo la ejecución de xUnit | §8 |

## 2. Aclaraciones

### 2.1 Línea 278 (`System Tray Configuration.`)

Fila del inventario **sin equivalente en el pin**: se queda `Absent-At-Pin`. No
es una capacidad sin construir, es una línea del documento de origen que no
existe en Atlas ni en WinUtil en el SHA fijado. Queda escrita para que nadie la
cuente como pendiente de catálogo.

### 2.2 La fila `differs` de la auditoría de valores

`catalog-value-audit.tsv` casa por `(hive, clave, nombre)`. La clave
`HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer\SettingsPageVisibility`
la escriben **dos fuentes distintas** con **valores distintos**:

| Lado | Dónde | Valor |
| --- | --- | --- |
| Catálogo (`system.settings-page-visibility.hide`) | Atlas `…/Tweaks/qol/set-hidden-settings-pages.ps1:5` (valor) y `:8` (clave) | `hide:recovery;maps;…;home` |
| Fuente que casó primero | WinUtil `config/tweaks.json:952-961` (`WPFTweaksWindowsAI`) | `hide:aicomponents` |

La excepción declara las dos rutas con línea, el valor de cada lado y por qué el
catálogo copia el de Atlas (el de WinUtil esconde otra página: es un tweak
distinto sobre la misma clave). El literal del catálogo es el `$value` completo
del script de Atlas, copiado byte a byte; el test
`test_el_literal_de_settings_page_visibility_es_el_del_script_de_atlas` lo fija.

Resultado de la auditoría: **197 filas, 2 excepciones, 0 sin excepción,
veredicto OK**. Distribución: 171 `equals-apply`, 19 `equals-on`, 1 `equals-off`,
1 `differs` (con excepción), 5 `no-source`.

### 2.3 «15 vs 11 huecos»

No se reproduce con los datos actuales: el mapa upstream da **17 líneas ya
cubiertas y 13 libres** en la partición del paso 10. La cifra del paso 10 se deja
como histórica y se corrige en el informe del paso 11, que es donde se midió.

## 3. T2 — `registryCreateKey`

### 3.1 La acción

`RegistryCreateKeyAction` con discriminador JSON exactamente `registryCreateKey`
y contrato cerrado: `hive`, `keyPath`, `order`, `description`. **Sin** `line`
(la línea va en la `provenance`), sin patrones y sin recursión. El validador
rechaza `keyPath` vacío o con comodín (`R-ACTION`).

### 3.2 La semántica de deshacer

`RegistryCreateKeyExecutor`, en `ExecutionMode.Execute` y sólo si hay algo que
crear:

1. Si el accesor no implementa `IRegistryKeyCreator` → **falla sin tocar nada**
   (fail-closed: no se promete un deshacer que no se sabe hacer).
2. Si la clave **ya existe** → **no-op registrado**, sin mutación y **sin entrada
   de diario**. Crear algo que existe no es un cambio, y borrarlo al deshacer
   destruiría estado previo.
3. Si **no existe** → se crea, se comprueba que existe y el diario apunta
   `ExistedBefore=false`; el deshacer **borra la clave, no recursivo**.

En `DryRun`/`Audit` se informa `would-create` y no se muta. `ReadCurrentState`
devuelve `present`/`absent` **antes** de crear, que es de lo que depende el
deshacer.

### 3.3 Los tres `AddKey` del paso 11

| `AddKey` | Clave | Destino |
| --- | --- | --- |
| `Interface/Home.psd1:23` (estado `Enable`) | `HKLM\…\Explorer\Desktop\NameSpace\{f874310e-…}` | capacidad nueva `explorer.home.restore` (§10) |
| `qol/shell/disable-network-location-wizard.psd1:5` | `HKLM\SYSTEM\CurrentControlSet\Control\Network\NewNetworkWindowOff` | capacidad nueva `system.network.location-wizard.disable` (§9) |
| `qol/taskbar/config-pins.ps1:11` | `HKCU\…\Explorer\Taskband` | **sigue sin capacidad**: ver §3.4 |

`explorer.home.restore` **no** declara las dos `DeleteKey` del estado `Disable`:
T3 lo habría marcado como `CONTRARIO-DECLARADO`. Declara la creación de la clave
y los dos valores del estado `Enable` (`System.IsPinnedToNameSpaceTree=0`,
`LaunchTo=0`). El lanzador `Enable Home.cmd` sólo reinicia el Explorador; **no es
un hueco de expresividad**, así que la capacidad queda `Implemented` (no
`Specified`): deshacerla es borrar lo que ella creó.

`system.network.location-wizard.disable` sí cierra un hueco real y su línea del
manifiesto pasa de `pending` a `covered` en `upstream-capability-map.tsv`.

### 3.4 El `AddKey` que sigue fuera: `config-pins`

`qol/taskbar/config-pins.ps1:11` no es una sola operación: crea `Taskband`,
escribe `FavoritesVersion=3` y borra `AuxilliaryPins\{MailPin,CopilotPWAPin}`.
La creación de clave ya es expresable, pero la capacidad **entera** no lo es
todavía (combina crear clave + valor + dos borrados en una misma clave que no
existe de fábrica en todas las builds). Se queda **declarado como hueco**, no
como `Implemented`: es exactamente lo que R1 prohíbe publicar.

## 4. R1 / R2 / R3

### 4.1 R1 — completitud

Medido por `tools/ledger_extract/measure_capability_completeness.py`, que
compara las operaciones del pin con las acciones del catálogo:

```
capacidades medidas        : 88
  Implemented              : 71
  Specified                : 17
  con efectos fuera del pin : 13
violaciones de R1          : 0
veredicto por capacidad    : 88 OK
```

Las cuatro `Specified` de la sección 9 son una **lista cerrada** (un test falla
si aparece otra):

| Capacidad | Lo que el pin hace y el motor no |
| --- | --- |
| `system.hibernation.hide` | `powercfg /h off` (apaga la hibernación, no sólo la entrada del menú) |
| `system.location.consent-deny` | política de Find My Device + páginas de configuración |
| `system.mitigations.disable` | CFG y `bcdedit /set nx` |
| `system.registry-backup.enable` | el script se ejecuta con `-RunLevel Highest` y el motor no expresa el nivel de la tarea |

Todas siguen siendo `Reversible` con deshacer de sesión o mejor, y todas lo
declaran por escrito (`FUERA DE ESTA CAPACIDAD (R1)` en la descripción y
`R1 (paso 12)` en la procedencia).

Las otras 13 `Specified` vienen de oleadas anteriores y su motivo no es R1
(comandos sin inversa, `unexpressed` del pin). El medidor las separa y las marca
como informativas, no como violaciones.

### 4.2 R2 — `Improves` con motivo

**Aquí había un incumplimiento real**: `explorer.file-extensions.show` y
`explorer.hidden-files.show` declaraban `SecurityImpact=Improves` y el motivo
sólo aparecía en la `provenance`, no en la descripción —y el generador de la
sección 10 sólo aplicaba R2/R3 a las specs de Atlas, **no** a los tweaks de
WinUtil. Arreglado en el generador: `apply_r2_r3()` se aplica también al bucle de
`WINUTIL_SPECS`, y ahora las 7 capacidades con `Improves` llevan la frase
`Por que mejora la seguridad:` en la descripción y `R2 (paso 12)` en la
procedencia. Si a una spec le falta el motivo, el generador la degrada a
`Neutral` y lo dice en la procedencia (no se inventa una justificación).

### 4.3 R3 — persistente + privilegios altos

Alcance: lo que **instala** algo persistente con privilegios altos — una tarea
programada o un servicio. Hoy son 7 capacidades, todas con `Risk=Low` y
`Confirmation=SimpleClick`; el caso que R3 obligó a cambiar es
`system.registry-backup.enable` (`Safe`/`None` → `Low`/`SimpleClick`, con el
motivo escrito).

Las escrituras de registro con privilegios de Admin **no** entran en el alcance
que declaran los generadores: son reversibles por el diario y ADR-0003 ya las
gobierna con su propio mínimo (`Safe` ⇒ `Restore=None`). Queda escrito aquí para
que no se lea como un hueco silencioso.

## 5. T3 — estados contrarios

`tools/ledger_extract/measure_toggle_states.py` compara, para cada capacidad que
sale de un `.psd1` de toggle, las operaciones del **estado declarado** con las de
los **demás estados** del mismo fichero, normalizando el dato (los binarios del
pin `@(0x90, …)` se comparan en el mismo formato que el catálogo, base64).

```
capacidades que salen de un toggle : 20
  estado declarado sin contrarios   : 3
  con operaciones pendientes del otro estado: 17
contrarios DECLARADOS (fallo)      : 0
```

- **`CONTRARIO-DECLARADO`** es el fallo duro (exit 1): la capacidad aplicaría el
  estado contrario al que promete. **Cero.**
- **`PENDIENTE-DECLARADO`** es informativo: el otro estado tiene operaciones que
  hoy no declara nadie. Son las capacidades *contrarias* que algún día se
  escribirán (el caso `explorer.removable-drives.sidebar`, donde las dos
  `DeleteKey` del pin están en el estado `Disable` y la capacidad enciende).
  Quedan en el TSV para no perderlas.

Los dos casos que motivaron T3 se comportan como se esperaba: `ui.taskbar.end-task`
y `explorer.removable-drives.sidebar` **no** aparecen como contrarios.

## 6. Cifras (medidas, no heredadas)

```
catálogo            88 capacidades · 243 acciones
sección 9           19 capacidades · 47 acciones (era 18/45)
sección 10          30 capacidades · 60 acciones (era 29/57)
estado              71 `Implemented` / 17 `Specified`  (el catálogo medido: 88 capacidades)
cobertura           85/85 líneas Mapped · 0 huecos (0 declarados)
secciones cerradas  1, 2, 3, 9, 10
auditoría valores   197 filas · 0 sin excepción · veredicto OK
R1                  88 medidas · 0 violaciones · 13 con efectos fuera del pin
T3                  20 medidas · 3 OK · 17 pendientes · 0 contrarios
plan de oleadas     89/435 líneas (20.5 %)
rangos de build     79 completos + 9 recortados
pytest              559 passed  (539 al cierre del paso 11 + 20 de este paso)
xUnit               239/239 en windows-2025 y windows-11-arm
                    (runs 45693509207 / 45693528396, sobre 0922fb9)
```

Las cifras del paso 11 (**86** capacidades, 238 acciones, 231, 195 filas de
auditoría, 45/57 acciones por sección) están **obsoletas** y no deben repetirse:
todos los tests y los jobs de CI se han actualizado a las de arriba.

## 7. Tests

### 7.1 Python — `tests/test_paso12.py` (20 casos)

Cubre, reproduciendo la medida y no leyendo el TSV a ciegas: el tipo
`registryCreateKey` y su contrato cerrado; la semántica del ejecutor
(fail-closed, existente ⇒ no-op, diario sólo si no existía); los tres `AddKey` y
cuál sigue fuera; el paso de `pending` a `covered` en el mapa upstream; R1 sin
violaciones y la lista cerrada de `Specified`; R2 con motivo escrito y R3 en su
alcance; T3 sin contrarios y los pendientes como informativos; el **orden**
`Stop` → `SetStartupType` en las acciones de servicio; las listas de ids de los
xUnit contra el catálogo; las cifras del ledger; la auditoría a cero sin
excepción y el literal de `SettingsPageVisibility` con las dos rutas; la línea
278; la **doble ejecución** de los dos generadores (sha256 idénticos); el
informe, el ADR y el job de CI.

**Lectura de la cifra de pytest.** Al cierre del paso 11 el CI contaba **539**
sobre `tools/ledger_extract/tests tests`; este paso añade 20 y quedan **559**.
La cifra de 360 que se dio al cerrar el paso 12 era la de `tests/` **solo**
(sin el directorio de tests de los extractores, que aporta 199 casos: 24 + 31 +
16 + 16 + 14 + 27 + 33 + 16 + 22). No se ha perdido ningún test: el desglose
fichero a fichero está en §7.4 y las 19 filas dan diferencia 0 salvo
`test_paso12.py` (+20).

### 7.4 Conteo por fichero: `cb75abe` (cierre del paso 11) frente a ahora

```
fichero                                            cb75abe   ahora   dif
tests/test_paso10.py                                    16      16    +0
tests/test_paso11.py                                    21      21    +0
tests/test_paso12.py                                     0      20   +20
tests/test_paso6.py                                     19      19    +0
tests/test_paso7.py                                     21      21    +0
tests/test_paso8.py                                    174     174    +0
tests/test_paso8b.py                                    24      24    +0
tests/test_paso8c.py                                    17      17    +0
tests/test_paso8d.py                                    25      25    +0
tests/test_paso9.py                                     23      23    +0
tools/ledger_extract/tests/test_count_inventory.py      24      24    +0
tools/ledger_extract/tests/test_paso2.py                31      31    +0
tools/ledger_extract/tests/test_paso3.py                16      16    +0
tools/ledger_extract/tests/test_paso3b.py               16      16    +0
tools/ledger_extract/tests/test_paso4b.py               14      14    +0
tools/ledger_extract/tests/test_paso4c.py               27      27    +0
tools/ledger_extract/tests/test_paso4d.py               33      33    +0
tools/ledger_extract/tests/test_paso4e.py               16      16    +0
tools/ledger_extract/tests/test_paso5.py                22      22    +0
TOTAL                                                  539     559   +20
```

### 7.2 xUnit — 15 casos nuevos

- `Evo.Engine.Tests` / `Wave4EngineTests.cs` (10):
  `CreateKey_CreatesTheEmptyKeyAndUndoDeletesIt`,
  `CreateKey_ExistingKeyIsANoOpAndUndoDoesNotDeleteIt`,
  `CreateKey_DryRunDoesNotMutate`, `CreateKey_WithoutKeyCreatorFailsClosed`,
  `CreateKey_GoesThroughTheRestorePointGate`,
  `CreateKey_ReadCurrentStateReportsPresence`,
  `CreateKey_UndoAddsNothingToTheExistingParentSubtree`,
  `CreateKey_TwiceInARowIsIdempotent`,
  `CreateKey_AuditModeReportsTheRealStateAndDoesNotMutate`,
  `HomeRestore_RunsThroughTheCoordinatorAndRollsBackTheWholeTree`.
- `Evo.Engine.Tests` / `Wave3EngineTests.cs` (1):
  `SearchIndexing_StopsBeforeDisablingSoUndoCanRestart`.
- `Evo.Catalog.Tests` / `Wave4CatalogTests.cs` (4):
  `ValidatorRejectsMalformedKeyCreations`, `LoaderReadsKeyCreationActions`,
  `HomeRestoreIsTheExactInverseOfHomeHide`,
  `NetworkLocationWizardCoversItsManifestLine`.

Total **15 ≥ 14**. (`TestWave4Catalog_RegistryBackupIsNowComplete` se
**renombró** a `...DeclaresItsTaskAndStaysSpecified`, no cuenta como caso nuevo:
sigue siendo un caso, con otras aserciones.)

### 7.3 Lo que encontró la primera pasada de CI

La primera ejecución de `dotnet-ci` sobre este paso dio **7 fallos de 232**. Se
arreglaron todos y **cuatro eran defectos de verdad**, no del test:

1. **Orden de las acciones de servicio (el peor).** El generador de §9 emitía
   `SetStartupType(Disabled)` y **después** `Stop(WSearch)`, justo el orden que
   ADR-0005 §4-bis prohíbe: con el diario en LIFO, el deshacer restauraba el
   arranque y luego intentaba arrancar un servicio aún deshabilitado → 1058.
   Lo cazó `TestWave3Catalog_SearchIndexingDisablesWSearch`. Corregido en el
   generador (parar primero) y **fijado por dos tests nuevos**, uno de catálogo
   y otro de motor, más un test de Python que recorre las 88 capacidades
   buscando el par `Stop`+`SetStartupType` en el orden equivocado.
2. **`AssertSameRegistry` exigía una clave del árbol de ejemplo** (`EmptyKey`)
   que no existe en el snapshot vacío del test de creación. Se añadió un helper
   `AssertSameTree` que compara clave por clave sin esperar ninguna concreta.
3. Las **listas de ids** de `Wave1`, `Wave2` y `Wave3` (y los recuentos por
   sección 29/18) no incluían las dos capacidades nuevas.
4. `explorer.home.restore` **excluye 19045** (CLSID de Windows 11) y no estaba
   en la lista de «solo Windows 11» del test de builds.

Los otros tres eran consecuencia directa de lo anterior. Para no repetirlo, hay
un test de Python (`test_las_listas_de_ids_de_los_xunit_incluyen_las_dos_capacidades_nuevas`)
que comprueba las listas **desde el catálogo**, sin necesitar dotnet: las cifras
que se congelan en C# ahora se validan en la suite que sí corre aquí.

## 8. CI

Job nuevo **«Paso 12 (R1/R2/R3, registryCreateKey y estados contrarios)»** en
`.github/workflows/ledger-verify.yml`:

- **doble ejecución** de los dos generadores y de los dos medidores, con
  `sha256sum` comparado entre las dos pasadas (determinismo);
- `--check` de los medidores y de los generadores contra los ficheros
  versionados;
- comprobación de cifras por JSON: 88 capacidades, 0 violaciones R1, 0
  contrarios T3, 197 filas de auditoría, 19/47 y 30/60, la lista cerrada de
  `Specified` y el alcance de R3.

Además se han corregido las cifras que los jobs anteriores tenían congeladas
(paso 9: 29/57 → 30/60; paso 10 y 11: 86 → 88; paso 11: 45/57 → 47/60 y
`new9 == []` → lista cerrada; auditoría 195 → 197). Sin eso, el CI habría fallado
por cifras obsoletas, no por el código.

## 9. Riesgos y límites declarados

- **No hay dotnet en el sandbox**: los xUnit se escriben y revisan aquí, pero se
  ejecutan en el CI. La primera pasada trajo 7 fallos y cuatro eran defectos
  reales (ver §7.3): el más grave, el orden `Stop`/`SetStartupType` que rompía
  el deshacer. La lección está aplicada: las cifras y las listas de ids que se
  congelan en C# se validan también desde Python.
- **La instantánea del borrado de clave es en memoria** (paso 11): sigue igual.
  La creación no toma instantánea porque no hay nada que fotografiar.
- **`config-pins` sigue sin capacidad**: es el único `AddKey` que queda fuera y
  está declarado, con su motivo, en §3.4.
- **R3 no cubre las escrituras de registro con Admin**: se declara el alcance en
  §4.3 en vez de dejar que se lea como un hueco.
- Las cifras 86/238/231/195/45/57 **no deben volver a citarse** como actuales.

## 9-bis. Conteos verificados (paso 12b)

- **pytest**: 559 sobre `tools/ledger_extract/tests tests` (539 al cierre del
  paso 11 + 20 de `tests/test_paso12.py`). La cifra de 360 que se dio al
  cerrarse el paso 12 era `tests/` **solo**; el directorio
  `tools/ledger_extract/tests` aporta 199 casos. Cero tests perdidos: el
  desglose por fichero está en §7.4.
- **xUnit**: **15 casos nuevos** (mínimo pedido: 14) y el total pasa de 224 a
  **239** (+15). El `+13` que se había reportado salía de contar el renombrado
  `TestWave4Catalog_RegistryBackupIsNowComplete` →
  `...DeclaresItsTaskAndStaysSpecified` como si fuera un caso nuevo; no lo es.
- **Cambios de esta tanda**: solo tests y este informe. No se toca el motor, ni
  el catálogo, ni los generadores. El único arreglo de test fue
  `CreateKey_AuditModeReportsTheRealStateAndDoesNotMutate`, que afirmaba
  `present`/`absent` donde el ejecutor devuelve el informe `would-create…` (eso
  lo da `ReadCurrentState`): falló en `dotnet-ci` con 1 fallo de 239 y se
  corrigió el test, no el contrato.

## 10. Para reproducir

```bash
python3 tools/ledger_extract/build_section9_catalog.py --check
python3 tools/ledger_extract/build_section10_catalog.py --check
python3 tools/ledger_extract/measure_capability_completeness.py --check
python3 tools/ledger_extract/measure_toggle_states.py --check
python3 tools/ledger_extract/audit_catalog_values.py
python3 tools/ledger_extract/verify_catalog_coverage.py
python3 tools/ledger_extract/build_upstream_capability_map.py
python3 tools/ledger_extract/build_wave_plan.py
python3 tools/ledger_extract/build_build_ranges_report.py
python3 -m pytest tools/ledger_extract/tests tests -q   # 559 passed
```
