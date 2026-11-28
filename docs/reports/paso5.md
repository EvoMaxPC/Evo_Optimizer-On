# Paso 5 — Conciliación definitiva del inventario y matriz de cobertura maestra

Fecha: 2026-11-23 · Rama `arena/ab2d6de7-evo-optimizer-on` · HEAD de partida `893482b`.
Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f` · WinUtil `70c23c80641d7370532af2f619b2842658600842`.

---

## T0 — Evidencia

```
$ git rev-parse HEAD
893482bc7cc77caeebac2b2b9cff20597947bb3b
$ git ls-remote origin refs/heads/arena/ab2d6de7-evo-optimizer-on
893482bc7cc77caeebac2b2b9cff20597947bb3b	refs/heads/arena/ab2d6de7-evo-optimizer-on
$ sha256sum docs/requirements/INVENTARIO_USUARIO.md
0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709  docs/requirements/INVENTARIO_USUARIO.md
```

El inventario se abre en **solo lectura** (`html.unescape`, se quita el prefijo
`"- "`, se descartan las notas) y no se ha escrito ni un byte.

---

## T1 — Conciliación definitiva (`inventory/ledger/inventory-reconciliation.tsv`)

```
$ python3 tools/ledger_extract/build_final_reconciliation.py
filas          : 588 (esperado 588)
por estado     : {'Mapped': 149, 'Mapped-To-App': 5, 'EVO-Exclusive': 37,
                  'Absent-At-Pin': 326, 'Informative-Header': 71}
sha256         : a6ae2b260aa84108423e3168fac78ae0b184ea2be71317cd1d26eedcad08e27b
```

Columnas exactas: `seccion`, `linea`, `fuente_declarada`, `texto` (≤200),
`status`, `mapped_ids`, `confidence`, `rationale`. LF, UTF-8 sin BOM, orden por
`linea`. **Cero filas sin estado.**

### Tabla 17 × 5

| Sec | Mapped | Mapped-To-App | EVO-Exclusive | Absent-At-Pin | Informative-Header | Total |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 0 | 1 | 23 | 2 | 29 |
| 2 | 17 | 0 | 0 | 23 | 2 | 42 |
| 3 | 6 | 0 | 0 | 34 | 2 | 42 |
| 4 | 9 | 0 | 0 | 14 | 3 | 26 |
| 5 | 7 | 0 | 0 | 18 | 3 | 28 |
| 6 | 6 | 0 | 11 | 12 | 3 | 32 |
| 7 | 7 | 0 | 10 | 10 | 2 | 29 |
| 8 | 4 | 0 | 0 | 15 | 2 | 21 |
| 9 | 28 | 0 | 0 | 28 | 2 | 58 |
| 10 | 25 | 0 | 0 | 21 | 2 | 48 |
| 11 | 4 | 0 | 0 | 20 | 2 | 26 |
| 12 | 5 | 0 | 0 | 21 | 2 | 28 |
| 13 | 9 | 0 | 0 | 13 | 3 | 25 |
| 14 | 13 | 0 | 0 | 14 | 2 | 29 |
| 15 | 1 | 5 | 0 | 23 | 3 | 32 |
| 16 | 5 | 0 | 0 | 35 | 4 | 44 |
| 17 | 0 | 0 | 15 | 2 | 32 | 49 |
| **Σ** | **149** | **5** | **37** | **326** | **71** | **588** |

### Reglas

1. `Informative-Header`: encabezados de sección, cabeceras de modo
   (`WinUtil`/`AtlasOS`), notas («Importante:», «Observación:»), referencias y
   las celdas `Sí`/`No` de la tabla aplanada de la sección 17.
2. `EVO-Exclusive`: bloque entre `EVO CLEAN`/`Capacidad EVO a desarrollar:` y
   la nota «Estas últimas capacidades…» o el siguiente encabezado de modo
   (secciones 6, 7, 1), más las 15 filas-requisito de la sección 17 que ningún
   pin implementa.
3. `Mapped`: R1/R2/R3 del paso 4e + `apps_in_text()` (nombre de producto de
   `winutil-apps.tsv`, ≥4 car., límites de palabra, máx. 5) + `service_index()`
   (servicios de `winutil-tweak-ops.tsv` × `value_name` de
   `atlas-tweak-ops.tsv`), siempre con candidato existente en los ledgers.
4. `Mapped-To-App`: sección 15 → `winutil:catalog-entry:<id>`
   (`edge`, `processexplorer` ×2, `nvclean`, `librewolf`).
5. `Absent-At-Pin`: sonda `atlas=0`/dudosa de
   `docs/inventory-recon/seccion16-17-probe.tsv`, o texto que cae en
   `ABSENT_KEYWORDS` (AME Wizard, playbook, ISO creation/injection, USB, fases
   de instalación, shell refresh, AppX support, windows transition, environment
   phase, pre-install, new user initialization, Atlas Manager,
   TrustedInstaller Broker, «No como motor propio») sin candidato.

---

## T2 — Matriz de cobertura (`docs/reports/matriz-cobertura.md`)

```
$ python3 tools/ledger_extract/generate_coverage_matrix.py --json
filas: 588 | secciones: 17
{"winutil_items": 162, "winutil_items_hit": 51,
 "winutil_ops": 179, "winutil_ops_hit": 17,
 "winutil_apps": 239, "winutil_apps_hit": 5,
 "atlas_toggles": 91, "atlas_toggles_hit": 8,
 "atlas_manifest": 182, "atlas_manifest_enabled": 177, "atlas_manifest_hit": 0,
 "atlas_regs": 327, "atlas_regs_files": 11, "atlas_regs_hit": 0,
 "atlas_effects": 986, "atlas_effects_hit": 11,
 "atomicos": 92, "ids_otros": 0}
```

`atomicos = 92` ids **distintos** (no ocurrencias) y `ids_otros = 0`: todo id
referenciado existe en un ledger de origen. Las cifras de base coinciden con
las de los pasos 3b–4e: 162 items, 239 apps, 91 toggles, 182 entradas de
manifiesto (177 habilitadas), 327 valores `.reg` en 11 ficheros, 986 efectos.

---

## T3 — Validador (`tools/ledger_extract/validate_reconciliation.py`)

```
$ python3 tools/ledger_extract/validate_reconciliation.py
filas      : 588
  Mapped               149
  Mapped-To-App        5
  EVO-Exclusive        37
  Absent-At-Pin        326
  Informative-Header   71
determinismo: OK  sha256=a6ae2b260aa84108…
$ echo $?
0
```

Comprueba: 588 filas, suma de estados == 588, cero estados desconocidos,
líneas únicas, cero caracteres de control, celdas ≤400 caracteres, `texto`
≤200, `confidence` en el enum, `mapped_ids` existentes en los 10 ledgers de
origen, `Mapped`/`Mapped-To-App` con ≥1 id, `Mapped-To-App` solo en la 15 y
con prefijo `winutil:catalog-entry:`, y determinismo por doble ejecución del
extractor.

---

## T4 — Tests y CI

```
$ python3 -m pytest tools/ledger_extract/tests/ -q
199 passed in 3.85s
```

177 previos + 22 nuevos en `tools/ledger_extract/tests/test_paso5.py`
(≥189 exigidos). El workflow `ledger-verify` gana el step
«Paso 5 (conciliacion definitiva + matriz de cobertura)»: doble ejecución del
extractor + `diff` de sha256, regeneración de la matriz y `diff` contra el
fichero versionado, validador y comprobación JSON (588 filas, 5 estados, 17
secciones, `ids_otros == 0`). Publica en `ci-report`:
`inventory-reconciliation.tsv`, `matriz-cobertura.md`,
`CONCILIACION_INVENTARIO.md`, `paso5-recon.json`, `paso5-matriz.json`,
`paso5-validate.txt`, `paso5-sha-run{1,2}.txt`, `paso5-determinism.txt`.

---

## Criterios

| # | Criterio | Estado |
|---|---|---|
| N0 | Estado y sha del inventario | CUMPLIDO |
| N1 | 588 líneas, 0 huérfanos, 5 estados | CUMPLIDO |
| N2 | Matriz 17×5 con totales de fila y columna | CUMPLIDO |
| N3 | Validador exit 0 | CUMPLIDO |
| N4 | Suite ≥189 tests | CUMPLIDO (199) |
| N5 | CI verde con `ci-report` del mismo sha | pendiente del push |
| N6 | PR #1 actualizado y en draft | pendiente del push |

---

## Desviaciones

1. **324 → 326 `Absent-At-Pin` y 22 → 37 `EVO-Exclusive`** respecto al primer
   borrador. Motivo: revisión manual fila a fila de las secciones 14, 16 y 17.
   La sección 17 es una tabla aplanada (una celda por línea): sus 15 filas de
   «Funcionalidad» son requisitos del responsable sin código en los pins y
   pasan a `EVO-Exclusive`; `No como motor propio` (fila *Operaciones
   TrustedInstaller*) queda `Absent-At-Pin`. Las 32 celdas de columna
   (`Sí`/`No`/cabeceras) son `Informative-Header`. No se ha inflado ningún
   estado: cada fila conserva su `rationale`.
2. **`Mapped-To-App` = 5** y no más: solo 5 de los nombres de app de la
   sección 15 existen literalmente en `winutil-apps.tsv`; el resto de la
   sección son descripciones de categorías, no productos.
3. `Absent-At-Pin` es la etiqueta mayoritaria (55,4 %). Es una **propiedad
   honesta del inventario**: el responsable pide más de lo que los dos pins
   implementan. No se ha reclasificado nada para maquillar la cifra.

## Supuestos

- El pin de Atlas no incluye creador de USB ni motor de ISO propio: la sonda
  (`Build-Iso.ps1`, `Desktop.ps1`) describe un flujo de instalación existente
  pero sin motor reutilizable; se marca `Absent-At-Pin`.
- Los nombres de producto de la sección 15 se comparan sin distinguir
  mayúsculas ni acentos contra la columna `label` de `winutil-apps.tsv`.

## Riesgos

- R1/R2 siguen siendo heurísticos: un `Mapped` puede ser un falso positivo por
  coincidencia de etiqueta. Mitigación: `mapped_ids` es auditable fila a fila y
  el validador exige que el id exista.
- Las 326 filas `Absent-At-Pin` no dicen «no existe en Windows», solo «no hay
  código ni parser en el pin»; el catálogo EVO deberá revalidarlas contra los
  requisitos reales antes de prometerlas.

## Commit

`feat: paso 5 - conciliacion definitiva del inventario y matriz de cobertura maestra`
