# Paso 4c — Hechos estructurales de Atlas

Fecha: 2026-11-24 · Rama `arena/ab2d6de7-evo-optimizer-on` · base `38d13eb`.
Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`, GPL-3.0-only.
WinUtil `70c23c80641d7370532af2f619b2842658600842`.

Licencia: se extraen **rutas, nombres, hives, claves, nombres de valor, tipos,
conteos y hashes**. **Nunca** datos literales (`Data`), descripciones ni cuerpos
de script. La atribución por dato es `atlas@ec3c4058:<ruta>` (ADR-0002, opción C).

Reproducción: `python3 tools/ledger_extract/extract_atlas_*.py` tras
`fetch_upstream.py`. Todas las cifras de este informe salen de un comando
ejecutado en el sandbox y repetido en CI (doble ejecución + `diff`).

---

## T0a — Reconciliación del "11"

`docs/reports/paso2b.md` cita 11 items con `[patron dudoso]`; el recuento real
de `docs/inventory-recon/seccion16-17-probe.tsv` es **9**. Comando:

```
awk -F'\t' 'NR>1 && $0 ~ /patron dudoso/ {n++; print NR": "$1} END{print "total="n}' \
  docs/inventory-recon/seccion16-17-probe.tsv
```

| # | item |
|---:|---:|
| 6 | 6 |
| 9 | 9 |
| 18 | 18 |
| 19 | 19 |
| 20 | 20 |
| 30 | 30 |
| 35 | 35 |
| 36 | 36 |
| 38 | 38 |

`keyword_patterns.SECTION_PROBES` confirma **39** items y **9** con
`True`. `grep -ri dudoso docs/reports/` no devuelve ninguna mención: el "11" no
procede de ningún fichero del repositorio. **Conclusión: 9 es la cifra
correcta; el "11" del paso 2b es una errata sin artefacto de origen.**

Detalle por item (coincidencias inventario/usuario):

| item | tema | coinc. | palabras |
|---:|---|---:|---:|
| 6 | fases de instalación | 3 | 143 |
| 9 | elección de fase | 4 | 160 |
| 18 | creación de ISO | 3 | 38 |
| 19 | inyección en ISO | 6 | 0 |
| 20 | actualización del sistema | 0 | 1 |
| 30 | trabajos en segundo plano | 58 | 153 |
| 35 | registro de ejecución | 99 | 48 |
| 36 | creación de USB | 15 | 62 |
| 38 | actualización del programa | 116 | 535 |

## T0b — Estado inicial

```
git rev-parse HEAD            -> 38d13eb...
git ls-remote origin HEAD     -> 38d13eb...
sha256sum docs/requirements/INVENTARIO_USUARIO.md
  -> 0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709
```

## T0c — `atlas-files.tsv`: 1 081 → 1 082

```
wc -l inventory/ledger/atlas-files.tsv   -> 1083   (1083 - 1 cabecera = 1 082)
sha256sum inventory/ledger/atlas-files.tsv
  -> 1d17b98d9dc2f807f346afda8cc171cff6045878879ee449121c353a2c3c9a20
```

`docs/reports/paso3b.md` citaba **1 081** en cinco lugares. **Desviación
corregida en este paso**, junto con las cifras derivadas:

| dato | 3b decía | real | comprobación |
|---|---:|---:|---|
| filas `atlas-files.tsv` | 1 081 | **1 082** | `wc -l` |
| `package/` | 802 | **803** | conteo por prefijo de `source_ref` |
| `app/` | 152 | 152 | idem |
| `tests/` | 124 | 124 | idem |
| raíz | 3 | 3 | idem |
| con hechos de contenido | 1 072 | **1 073** | `coverage_check_atlas.py --json` |

`coverage_check_atlas.py --json`: `extract_files 1082`, `in_ledger 1082`,
`with_facts 1073`, `without_facts 9`, `unexplained []`,
`missing_from_ledger []`, `reg_entries 327`. El octavo fichero del T0 de 3b
también se corrige: extract 1 073 → 1 082 (**+9**, no +8).

---

## T1a — ADR-0002 aceptado

`docs/adr/ADR-0002-datos-de-atlas-y-gpl.md`: estado **Aceptado — opción C**
(2026-11-24). Seis consecuencias registradas: EVO CLEAN es GPLv3;
`THIRD_PARTY_NOTICES` obligatorio (se crea en la base .NET, no ahora);
atribución por dato `atlas@<pin>:<ruta>`; prohibido usar nombre, logos o
imágenes de AtlasOS; las herramientas de terceros (O&O ShutUp10++, Process
Explorer, NVCleanstall) **no se redistribuyen**; un cambio a licencia no-GPL
obligaría a rehacer el catálogo sin datos de Atlas.

## T1b — Licencias de upstream

`docs/legal/upstream-licenses.md`. Evidencia:

```
head /tmp/upstream/atlas/LICENSE          -> 674 líneas, GPLv3
git grep -n '^license' -- '*.toml'        -> app/Cargo.toml:8 = GPL-3.0-only
                                             services/reports-mcp/Cargo.toml:5 = GPL-3.0-only
git grep -n 'any later version'            -> 3 ficheros, todos texto de plantilla
head /tmp/upstream/winutil/LICENSE        -> 21 líneas, MIT (CT Tech Group LLC)
dependency-inventory.json                 -> 391 paquetes, unresolved: 0
```

`app/licenses/` contiene las licencias de las dependencias, no del producto:
MIT OR Apache-2.0 192, MIT 54, Apache-2.0 OR MIT 36, Unicode-3.0 34,
Apache-2.0 13, BSD-3-Clause 8, resto menores.

---

## T2 — Funciones (`.ps1` / `.psm1`)

`extract_atlas_functions.py` → `inventory/ledger/atlas-functions.tsv`.

| métrica | valor |
|---|---:|
| funciones | **1 563** |
| ficheros con funciones | 254 |
| `scope=product` | 1 173 |
| `scope=test` | 390 |
| `scope=tooling` | 0 |
| de `package/` | 1 100 |
| de `app/` | 73 |
| de `tests/` | 390 |
| en `Scripts/` | 985 (909 `.ps1` + 76 `.psm1`) |
| nombres repetidos en ficheros distintos | 117 |
| pares (ruta, nombre) redefinidos | 14 → 29 filas con sufijo `#<línea>` |

sha256 `3cb09176e777dcb118b1e0a04112a74b832a511efee819f7be8125b05389f199`.

Conciliación con el paso 3b ("909 funciones en 169 `.ps1`"): exacta. Las 909
son solo `.ps1`; los otros 76 vienen de 4 `.psm1`; de los 169 `.ps1` solo 112
definen funciones. Los 376 ficheros de partida (357 `.ps1` + 19 `.psm1`) se
reparten en app 22, package 245, tests 109.

**Método.** Parser por líneas con conteo de llaves. Dos correcciones reales:
(a) avanzar `i = end` tras cada función perdía las **16 funciones anidadas**;
se cambia a `i += 1`. (b) 14 pares (ruta, nombre) aparecen definidos dos veces
en el mismo fichero (mocks de Pester que redefinen la función); para mantener 0
duplicados de `item_id` sin inventar nombres se añade `#<line_start>` **solo**
a esos casos.

## T3 — Puente catálogo → script

`extract_atlas_bridge.py` → `inventory/ledger/atlas-toggle-bridge.tsv`, sobre el
campo `work.machineAction` del catálogo.

| métrica | valor |
|---|---:|
| referencias | **92** |
| nombres distintos | **74** |
| `match_kind=function` | 92 |
| sin resolver | **0** |
| ambiguos (mismo nombre en varias rutas) | 0 |
| rutas alcanzadas | 52 |
| nombres declarados en `.psd1` | 182 (183 stems, 0 sin `Name`) |

sha256 `1721cd0a4e7e6db490a7797ba992871458e4639b416cb5db471a4764052abe0e`.

**Hallazgo.** La intersección entre los 92 `machineAction` y los `Name` de los
`.psd1` es **0**: el catálogo alcanza scripts `.ps1`, pero **ningún `.psd1`**
(183/183 no alcanzados por el puente). Los `.psd1` se cargan por otra vía, no
por `machineAction`.

## T4 — Operaciones declaradas en el catálogo

`extract_atlas_toggle_ops.py` → `inventory/ledger/atlas-toggle-ops.tsv`.

| métrica | valor |
|---|---:|
| operaciones | **303** |
| declaradas por `work.registry` | 303 |
| toggles+estados con operaciones | 94 |
| `action=unresolved` | 303 |
| `hive` / `key` declarados | **0** |

sha256 `a18dc134ba5b9ad4f289d63df3641a04771b419d42505ad88516438b181ced19`.

El catálogo **solo declara el conteo** (`work.registry` = número de operaciones),
no las claves. No se inventan: quedan como `unresolved`.

## T5 — Operaciones en `.psd1` y cruce

`extract_atlas_tweak_ops.py` → `inventory/ledger/atlas-tweak-ops.tsv`.
`cross_atlas_ops.py` → cruce con T4.

| métrica | valor |
|---|---:|
| `.psd1` de Tweaks | 183 |
| con bloque `Registry` | **154** (esperado 154 ✓) |
| operaciones parseadas | **408** |
| `parse_status=ok` | 408 |
| sin parsear | **0** |
| claves distintas (hive, key, nombre) | 404 en bruto / 403 normalizadas |
| duplicadas entre ficheros | 4 |

Por hive: HKLM 160, HKCU 177, HKCR 67, HKU 4.
Por tipo: DWord 262, String 87, ExpandString 7, None 6, Binary 1,
MultiString 1, sin `Type` 44.
Por área de Tweaks: qol 251, privacy 90, debloat 32, performance 17, misc 9,
networking 4, security 4, scripts 1.

sha256 `e001ea14a0dfea550e546b86a9ecaf57e0d3174d713e333a7c02538a5d1a55d5`.

**Método y dos correcciones reales.** (a) Muchas claves contienen GUIDs entre
llaves (`CLSID\{1d6437d-…}`), así que un regex `@\{.*?\}` cortaba la entrada
antes de tiempo; se sustituye por recorrido manual con conteo de llaves y se
recuperan 8 operaciones (`disable-scheduled-tasks` pasaba de 1 a 6, etc.).
(b) Las rutas vienen en tres formas —`HKCU\…`, `HKLM:\…` y
`Registry::HKEY_LOCAL_MACHINE\…`—; sin normalizar, los hives salían partidos
(`HKLM:` 43, `Registry::…` 25). Normalizado: 4 hives limpios.
(c) Las 37 entradas con `Operation` y sin `Name` (`DeleteKey` 35, `AddKey` 2) son
operaciones **sobre la clave**, no sobre un valor: se conservan con
`value_name` vacío y `unparsed_reason=key-operation:<op>`, en vez de perderlas.
Comprobación cruzada del conteo: 416 apariciones de `Path =` en ficheros con
`Registry`, menos 8 que pertenecen a bloques `ScheduledTasks` (que también usan
`Path`) = **408** operaciones de registro. Cuadra.

### Cruce catálogo ↔ `.psd1`

```
python3 tools/ledger_extract/cross_atlas_ops.py --json
{"toggle_ops_total": 303, "toggle_ops_con_hive_y_key": 0,
 "tweak_ops_total": 408, "claves_normalizadas_toggle": 0,
 "claves_normalizadas_tweak": 403, "en_ambos": 0,
 "solo_catalogo": 0, "solo_psd1": 403,
 "veredicto": "NO COMPARABLE: el catalogo no declara hive/key ..."}
```

**NO VERIFICADO.** El cruce (hive, key, nombre de valor) entre catálogo y
`.psd1` **no es medible** con estas fuentes: el catálogo no declara claves y
además el puente no alcanza ningún `.psd1` (T3). No se afirma ni equivalencia
ni divergencia. Para cerrarlo haría falta o bien un catálogo que declare las
claves, o bien ejecutar los `.psd1` en Windows; ninguna de las dos cosas se ha
hecho.

---

## Guardarraíles

- `docs/requirements/INVENTARIO_USUARIO.md` **intacto**:
  `0b6aeaef…f709` antes y después.
- Sin datos literales en el ledger: la columna de valor es `value_sha256`, no el
  dato. Ni descripciones, ni cuerpos de script de Atlas.
- Determinismo: cada extractor se ejecuta dos veces en CI y se compara el
  `sha256sum` (`ci-out/paso4c-sha-run{1,2}.txt`); `cmp` local también OK.
  Orden por `item_id`, LF, UTF-8 sin BOM.
- El extractor de T5 no usa PowerShell (no hay en el sandbox): es un parser por
  líneas. Se declara como tal; no se presenta como evaluador de PowerShell.

## Suite

`python3 -m pytest tools/ledger_extract/tests/ -q` → **128 passed**
(101 previos + 27 nuevos de `test_paso4c.py`, con 22 casos parametrizados).

## Deuda que queda

- **Semántica** de las 1 563 funciones (qué hace cada una) y de los 91 toggles:
  sin extraer. Solo hay estructura.
- **Cruce catálogo↔`.psd1`**: NO VERIFICADO, ver arriba.
- Los **29** `.psd1` de Tweaks sin bloque `Registry` no generan operaciones. De
  ellos 15 declaran `Script` y 1 `ScheduledTasks`; el resto no declara ninguna de
  las claves medidas (`Script`, `Policy`, `Category`, `ScheduledTasks`,
  `Services`, `Appx`). No se ha extraído qué hacen: deuda.
