# Paso 4b — Semántica de Atlas y reconciliación

Fecha: 2026-11-23 · Rama `arena/ab2d6de7-evo-optimizer-on` · base `03e4f4f`.
Atlas `ec3c4058…`, GPL-3.0. Detalle del esquema:
`docs/inventory-recon/atlas-settings-schema.md`.

Licencia: solo rutas, ids, nombres, categorías, enumerados, tipos, conteos y
hashes. Ni descripciones, ni cuerpos de script, ni cadenas de comando, ni
valores de registro.

## T0a — Rust: 1 283 vs 1 252

El CSV del paso 3b decía "1 252 declaraciones públicas **únicas por fichero**";
la suma por clase (916+159+86+74+41+5+2) es de **declaraciones, no de únicas**.
Diferencia: **31**, exactamente el exceso de nombres repetidos **dentro del
mismo fichero** (21 claves repetidas). Ejemplos reales:

| fichero | declaración | veces |
|---|---|---:|
| `app/src/i18n/describe.rs` | `fn title` | 6 |
| `app/src/i18n/describe.rs` | `fn text` | 6 |
| `app/src/model/rebase.rs` | `fn complete` | 3 |
| `app/src/ui/selection.rs` | `fn new` | 3 |
| `app/src/i18n/describe.rs` | `fn message` | 2 |
| `app/src/pages/mod.rs` | `fn new` | 2 |

Cifras correctas: **1 283 declaraciones**; **1 252 pares (fichero, clase,
nombre) distintos**; **1 113 nombres distintos** ignorando el fichero
(`new` aparece 38 veces en total). Las tres son ciertas con su definición; el
informe anterior mezcló dos de ellas. **Corregido.**

## T0b — `kind=cmd` 192 vs 188 `.cmd`

Los 4 extra son **3 `.vbs` y 1 `.sh`**, que clasifiqué como `cmd` por ser
lanzadores de shell:

| fichero | ext |
|---|---|
| `package/Executables/AtlasModules/Scripts/Entry/Invoke-AtlasUserUpgradeHidden.vbs` | `.vbs` |
| `package/Executables/AtlasModules/Scripts/Entry/Invoke-InitializeNewUserHidden.vbs` | `.vbs` |
| `package/Executables/AtlasModules/Scripts/Entry/Invoke-OneDriveCleanupHidden.vbs` | `.vbs` |
| `build.sh` | `.sh` |

`kind` × extensión para `config` (327):

| ext | ficheros |
|---|---:|
| `.psd1` | 295 |
| `.psm1` | 19 |
| `.md` | 5 |
| `.json` | 4 |
| `.toml` | 2 |
| `.xml` | 2 |
| **total** | **327** |

**El 327 de `config` y el 327 de valores `.reg` es coincidencia pura**: son dos
cuentas independientes (ficheros de configuración frente a líneas
`nombre=` dentro de 11 `.reg`). Se comprueba porque sus desgloses no se parecen
(327 = 295+19+5+4+2+2; 327 valores repartidos en 11 ficheros con 0–153 cada
uno) y porque `atlas-reg-entries.tsv` tiene 327 filas generadas desde `.reg`,
mientras `config` son 327 filas de `atlas-files.tsv`.

## T0c — Columna `scope` en `winutil-functions.tsv`

Columnas: `path area scope lines sha256 functions n_functions`.

| scope | ficheros | funciones |
|---|---:|---:|
| `product` (`functions/`, `scripts/`) | 127 | **210** = 42 + 164 + 4 |
| `test` (`pester/`) | 65 | **204** |
| `tooling` (raíz, `lint/`, `tools/`) | 3 | 0 |
| **total** | **195** | **414** |

`coverage_check.py` informa ahora los tres cubos y sigue en **exit 0**
(206 extract, 180 con items, 26 sin items, **0 sin motivo**).

Corregida en `paso3.md` y `paso3b.md` la frase de que `pester/` "da 0 items":
sus 204 funciones son **ayudantes de test**, no capacidades de producto; el
test sí es comportamiento ejecutable y por eso sigue en `extract`.

## T0d — Las 39 filas de la sonda 16/17

| item | winutil | atlas | dudoso |
|---|---:|---:|:--:|
| Atlas Playbook | 0 | 19 | n |
| AME Wizard | 0 | 8 | n |
| TrustedInstaller Broker | 0 | 35 | n |
| Install Plan | 0 | 41 | n |
| Install Session | 0 | 19 | n |
| Installation Phases | 3 | 143 | s |
| Pre-Install | 8 | 14 | n |
| Environment Phase | 0 | 3 | n |
| Choices Phase | 4 | 160 | s |
| Features Phase | 0 | 6 | n |
| Services Phase | 0 | 3 | n |
| Tweaks Phase | 0 | 10 | n |
| Components Phase | 0 | 9 | n |
| Software Phase | 0 | 3 | n |
| Shell Refresh Phase | 0 | 28 | n |
| AppX Support Phase | 0 | 18 | n |
| Windows Transition | 0 | 58 | n |
| ISO Creation | 3 | 38 | s |
| ISO Injection | 6 | 0 | s |
| Upgrade System | 0 | 1 | s |
| New User Initialization | 1 | 28 | n |
| Atlas Health | 0 | 21 | n |
| Toggle State Persistence | 5 | 91 | n |
| Package Verification | 0 | 5 | n |
| Component Servicing | 1 | 61 | n |
| PowerShell Module Initialization | 4 | 185 | n |
| Compile.ps1 | 14 | 0 | n |
| inicialización WPF | 33 | 0 | n |
| Runspaces | 48 | 3 | n |
| trabajos en segundo plano | 58 | 153 | s |
| presets | 35 | 7 | n |
| importación/exportación | 13 | 268 | n |
| deshacer ajustes | 61 | 47 | n |
| detección de cambios revertidos | 24 | 9 | n |
| registro de ejecución | 99 | 48 | s |
| creación de USB | 15 | 62 | s |
| instalación de ISO | 54 | 252 | n |
| actualización del programa | 116 | 535 | s |
| informes de entorno | 11 | 0 | n |

## T0e — `.cab`: autoría NO VERIFICADA

Sustituida en `paso3b.md` la frase "son paquetes de Windows Update, no código de
Atlas" por lo medido: 578 miembros = 4 `.mum` + 4 `.cat` + 570 `.manifest`, con
nombres de componente de Windows; los nombres de fichero son
`Z-Atlas-NoDefender-Package…` y `Z-Atlas-NoTelemetry-Package…`. **La autoría
queda NO VERIFICADO** (no se abrió ningún miembro).

## T0f — A REVISAR revisada

| ruta | bytes | decisión |
|---|---:|---|
| `package/atlas.json` | 5 343 | **extract**: claves `schemaVersion, version, minimumManagerVersion, supportedBuilds, updatableFrom, requirements, estimatedMinutes, choices` — configuración del paquete |
| `app/build.rs` | 5 940 | reference, `reason` `[paso 4b]` |
| `app/examples/i18n_spike.rs` | — | reference, `reason` `[paso 4b]` |
| `app/rustfmt.toml`, `lychee.toml` | — | reference, `reason` `[paso 4b]` |
| `app/licenses/` (2) | — | reference, `reason` `[paso 4b]` |
| `.vscode/` (3), `.zed/` (2) | — | reference, `reason` `[paso 4b]` |

Nuevos conteos: **extract=1082 · reference=465 · exclude=3**, 0 sin clasificar,
0 reglas muertas, 0 excludes sobre comportamiento, **`VEREDICTO: OK`** (ambos
repos). `A REVISAR` = **189**, todos `app/vendor/**`.

Nota: al añadir `package/**/*.json` la regla `package/Executables/**/*.json`
quedó **muerta** y el checker lo detectó (`reglas muertas: 1`,
`VEREDICTO: FALLA`); se eliminó y volvió a `OK`. `partition_review.py` ahora
cuenta como revisada una regla con `reason` marcado `[paso 4b]`.

## T1 — Esquema (resumen)

`Toggles/catalog.json`: 2 claves de nivel 1 (`schemaVersion`, `toggles`), **91**
entradas, 9 campos todos presentes (91/91), `name` único 91/91, sin campo `id`
aparte. `group`: 8 valores; `elevation`: Admin 78 / TrustedInstaller 8 / None 5.
173 `states` con `work` de 7 claves; `work.registry` suma 303 operaciones,
`services` 52, `scheduledTasks` 2. Referencias: 8 + 157 launchers a
`AtlasDesktop/`, 11 `toolboxLauncher` a `Toolbox/` — **176/176 resuelven**.
`.psd1`: 183 ficheros, 2 091 líneas; claves `Name` 190, `Description` 182,
`Registry` 154, `Script` 23, `OnUpgrade` 13, `Run` 9.

## T2 — Ledger de toggles

`inventory/ledger/atlas-toggles.tsv` = **91** filas (**predicción 91 ✓, sin
ajustar**), `atlas-tweak-files.tsv` = **183** filas.

sha256: toggles `621b17c2f9f4e58c0c2450f52acd2ccac72f62271b3f8876c306117b68e7f626`,
tweaks `d151c356e9b45d7738bf45a30a4a6a2e71ce7dd9b8355c87ef1789fa944c5b66`,
idénticos en dos ejecuciones y en CI (`determinismo toggles: OK`).

Cruces: **0 ids duplicados**, **0 toggles sin etiqueta**, **0 referencias
rotas**, **183 `.psd1` sin mención en `catalog.json`** (lista completa en el
TSV: `Tweaks/{debloat,privacy,qol,…}/*.psd1`). El catálogo no nombra ficheros
`.psd1`: el puente son 74 nombres de función en `work.machineAction`.

## T3 — ADR-0002

`docs/adr/ADR-0002-datos-de-atlas-y-gpl.md`, estado **Propuesto**. Tres
opciones (A ids+hashes, B redacción propia, C GPLv3 con atribución) con riesgo,
coste y qué impide. **La decisión queda pendiente del responsable**; no la tomo.

## T4 — Sonda de coincidencia (solo ruido, no cobertura)

`docs/reports/probe-coincidencia-inventario.tsv`, 510 líneas medidas:

| fuente | total | exacta | contención | ninguna |
|---|---:|---:|---:|---:|
| winutil | 210 | 81 | 51 | 78 |
| atlas | 300 | 80 | 27 | 193 |

Ejemplos de "ninguna" (winutil): `AppX Removal — eliminación de aplicaciones
provisionadas.`, `Limpieza de restos de OneDrive.`, `Limpieza y gestión de
paquetes redundantes.`, `Edge Debloat.`, `DiagTrack.`
Ejemplos de "ninguna" (atlas): `Remove OneDrive Current User Data.`,
`Remove Atlas Legacy Elevation Artifacts.`, `Disable Reserved Storage.`,
`Configure Storage Sense.`, `Disable Store App Archiving.`

**Esto es una sonda de ruido, no cobertura**: no marca nada como `Mapped`.

## T5 — Tests y CI

`test_paso4b.py`: **14 tests nuevos** (ids duplicados, referencias rotas,
toggle sin etiqueta, `.psd1` con claves y menciones, solo-psd1-de-Tweaks,
determinismo, orden estable, sha canónico, orden de claves, normalización,
exacta/contención/ninguna, totales de la sonda). Suite **101 passed**.
Workflow: +2 pasos (toggles con doble ejecución y cruces; sonda).
Run 45295684895 sobre `bc48671` = success; `ci-report` con ese sha, 29 ficheros.

## Desviaciones

1. El informe 3b mezclaba "declaraciones" y "únicas por fichero" (1 283 vs 1 252).
2. `kind=cmd` incluía `.vbs` y `.sh`; ahora está documentado.
3. La primera versión de la sonda recortaba las iniciales de cada línea
   (aplicaba `heading_title` en vez de leer la línea) y contaba las cabeceras
   de modo; corregido antes de informar.
4. `partition_review` no reconocía motivos escritos; ahora sí (`[paso 4b]`).

## Supuestos

- `states[].launcher` y `toolboxLauncher` son rutas relativas a
  `AtlasDesktop/` y `Toolbox/` respectivamente (176/176 resuelven así).
- Los `.psd1` se leen con regex porque PowerShell no está disponible.

## Riesgos

- **R1** La correspondencia toggle↔`.psd1` sigue **NO VERIFICADA**.
- **R2** ADR-0002 sin decidir: el motor no puede aplicar ajustes todavía.
- **R3** La sonda mide texto, no semántica: un "exacta" puede ser homónimo.
