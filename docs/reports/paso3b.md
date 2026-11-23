# Paso 3b/4a — Reconciliación del paso 3 y reconocimiento de Atlas

Fecha: 2026-11-23 · Rama `arena/ab2d6de7-evo-optimizer-on` · base `ddddb7f`.
Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f` (GPL-3.0), WinUtil
`70c23c80641d7370532af2f619b2842658600842` (MIT).

Licencia: de Atlas solo rutas, nombres, conteos, claves y hashes. **Ni un
carácter** de script, Rust, `.cmd` o `.reg` se transcribe. Detalle completo del
reconocimiento en `docs/inventory-recon/atlas-structure.md`.

## T0 — Reconciliación

### a) El octavo fichero

Comparando `atlas.tsv` de `605d8e7` con el actual (1 550 rutas en ambos, sin
altas ni bajas): extract 1 073 → 1 081 (+8), reference 474 → 466. **Ocho**
ficheros cambiaron de tratamiento (no 7):

| ruta | bytes | regla (605d8e7) | regla (actual) |
|---|---:|---|---|
| `…/AtlasModules/Other/Force Timer Resolution.xml` | 3 590 | `package/**` → reference | `package/Executables/**/*.xml` → extract |
| `…/AtlasModules/Other/StartLayout.json` | 685 | `package/**` → reference | `package/Executables/**/*.json` → extract |
| `…/AtlasModules/Toggles/catalog.json` | 115 595 | `package/**` → reference | `package/Executables/**/*.json` → extract |
| `…/Packages/Atlas-CbsHashes.psd1` | 1 078 | regla 3 (`…/Packages/*.psd1`), reference | misma regla 3, cambiada a extract |
| 4 `.cab` (NoDefender/NoTelemetry × amd64/arm64) | 43 743 / 52 230 / 27 817 / 29 376 | regla 17 (`package/**/*.cab`), reference | misma regla 17, cambiada a extract |

**El octavo es `Force Timer Resolution.xml`**: lo arrastró la regla nueva
`package/Executables/**/*.xml` que añadí para los `.xml` de esa carpeta, pero no
figuraba en mi recuento de "7 ficheros de comportamiento" porque **`.xml` no
estaba en la lista de extensiones de comportamiento** del paso 3 (sí lo estaba
`.json`, `.psd1` y `.cab`). No es un error de la partición: un `.xml` bajo
`package/Executables` que describe configuración es extract; el error era del
informe, que enumeró 7.

### b) A REVISAR = 201, sin "sueltos"

Definición exacta (código: `partition_review.behaviour_in_reference`): fichero
con `treatment == "reference"` y extensión en
`{ps1, psm1, psd1, cmd, bat, reg, json, rs, toml, cab}` cuya ruta **no** empieza
por `tests/`, `.github/`, `docs/`, `tools/` ni `services/`.

Recuento: 236 reference con extensión de comportamiento → **201** A REVISAR.

| prefijo | ficheros |
|---|---:|
| `app/vendor/` | 189 |
| `app/licenses/` | 2 |
| `app/build.rs` | 1 |
| `app/examples/` | 1 |
| `app/rustfmt.toml` | 1 |
| `.vscode/` | 3 |
| `.zed/` | 2 |
| `lychee.toml` | 1 |
| `package/atlas.json` | 1 |
| **total** | **201** |

Corregido en `docs/reports/paso2b.md` (tabla nueva) y en `paso3.md`.

### c) "other" de winutil: 68 ficheros, 204 funciones

| directorio | ficheros | funciones |
|---|---:|---:|
| `pester/` | 65 | 204 |
| `lint/` | 1 | 0 |
| raíz (`Compile.ps1`, `windev.ps1`) | 2 | 0 |
| **total** | **68** | **204** |

Totales de funciones: public 42 + private 164 + scripts 4 + other 204 =
**414**, en 195 `.ps1`.

**Por qué `pester/` está en extract.** `pester/**.Tests.ps1` son ficheros `.ps1`
ejecutables: definen funciones auxiliares (204 en 65 ficheros) y, sobre todo,
documentan el comportamiento esperado del producto. ADR-0001 dice que el
extract cubre "todo fichero con comportamiento", y un test Pester **tiene**
comportamiento observable (es código que se ejecuta). No contradice ADR-0001:
contradiría leerlo como "solo código de producto".

**Decisión: mantener en extract con motivo declarado, sin reclasificar.** No es
un error evidente (REQ: solo cambiar reglas ante error evidente). Además el
`kind: test` del ledger de Atlas ya los separa del producto, así que un
consumidor puede filtrarlos sin tocar la partición.

### d) sha256 de `winutil-apps.tsv`: historia del `463b4a30`

| momento | sha256 | causa |
|---|---|---|
| 1.ª ejecución local (paso 3) | `463b4a30…944f` | `extract_key()` devolvía label vacío en las 239 apps (`applications.json` usa `content` en minúscula) |
| tras corregir `extract_key()` | `620cfeb4…0336` | labels rellenos → cambia el contenido del TSV |
| CI (run 45288478064) | `620cfeb4…0336` | idéntico al local |
| ejecución local ahora (2 veces) | `620cfeb4…0336` | idéntico, `cmp` byte a byte |

O sea: **`463b4a30` fue el hash de la versión con el bug de labels vacíos y
nunca llegó a CI**; el `620cfeb4` que publicó `ci-report` es el correcto y
coincide con el fichero que está en el repo. Hoy el valor se reproduce bit a bit
desde el código actual. La primera vez que informé `463b4a30` estaba citando un
hash pre-corrección: **desviación declarada** y aquí corregida.

### e) Miembros de los `.cab`: ahora SÍ verificados

`cabarchive` (PyPI, puro Python) sí:
`pip install --break-system-packages cabarchive`, lectura del índice con
`CabArchive(bytes)` y `cab.items()`. **No se ha extraído ni escrito contenido a
disco**: solo se leyó la cabecera y los nombres/tamaños.

| cab | miembros | suma bytes | composición |
|---|---:|---:|---|
| NoDefender amd64 | 168 | 159 116 | 1 `.mum` + 1 `.cat` + 166 `.manifest` |
| NoDefender arm64 | 204 | 192 876 | 1 `.mum` + 1 `.cat` + 202 `.manifest` |
| NoTelemetry amd64 | 100 | 93 760 | 1 `.mum` + 1 `.cat` + 98 `.manifest` |
| NoTelemetry arm64 | 106 | 100 283 | 1 `.mum` + 1 `.cat` + 104 `.manifest` |
| **total** | **578** | **546 035** | |

Son paquetes de Windows Update (manifiestos de componente), no código de Atlas.
La cifra anterior ("NO VERIFICADO") queda resuelta.

### f) PR

`gh pr create --draft --base main --head arena/ab2d6de7-evo-optimizer-on`
→ **https://github.com/EvoMaxPC/Evo_Optimizer-On/pull/1**
(`isDraft: true`, `state: OPEN`, base `main`). No se fusiona nada.

## T1 — Reconocimiento de Atlas

Resumen; el detalle con todos los comandos está en
`docs/inventory-recon/atlas-structure.md`.

- **1 081** extract: `package/` 802, `app/` 152, `tests/` 124, raíz 3.
  Tercer nivel: `AtlasModules/` 585, `AtlasDesktop/` 217, `app/src/services/`
  39, `app/src/model/` 32, `app/src/ui/` 23, `app/src/pages/` 17.
- **Extensiones**: `.ps1` 357, `.psd1` 295, `.cmd` 188, `.rs` 128, `.url` 40,
  `.psm1` 19, `.json` 17, `.reg` 11, `.md` 6, `.lnk` 4, `.cab` 4, `.vbs` 3,
  `.toml` 2, `.xml` 2, `.sh`/`.exe`/`.cs`/`.txt`/sin ext 1 cada una.
- **`Scripts/*`**: 416 ficheros, 169 `.ps1` con **909** funciones, 8 `.cmd`,
  7 `.reg`, 203 `.psd1`, 19 `.psm1`.
- **`.reg`**: 11 ficheros, **673** líneas, **164** claves `[HKEY…]`, **327**
  valores `nombre=`. Están en **UTF-16 LE con BOM**: leerlos como UTF-8 da
  conteos falsos (fue mi primer error, corregido).
- **Rust**: 128 `.rs`, 2 597 197 B, 59 917 líneas; 1 252 declaraciones públicas
  únicas por fichero (916 `fn`, 159 `struct`, 86 `enum`, 74 `const`, 41 `mod`,
  5 `type`, 2 `trait`).
- **i18n**: **15** ficheros de idioma (no 18): `de, en-GB, en-US, es, fr, hi,
  id, ja, pl, pt-BR, ru, th, tr, zh-Hans, zh-Hant`. Los 14 completos tienen
  **956** claves y **conjunto idéntico** (0 diferencias); `en-US` es subset con
  **25** claves.
- **tests/**: 109 `.ps1` Pester, 437 `Describe`, 37 `Context`, 2 017 `It`.

**Dónde se define la lista de ajustes.** No en Rust: está en
`package/Executables/AtlasModules/Toggles/catalog.json`, con **91 entradas**
(campos `name, group, description, elevation, noStateRecord, menu, launcher,
warning, states`). Los `pub enum` de Rust son pantallas y estados
(`ScreenKind` 11 variantes, `Page` 6, `CloseGuard` 9, `ReadyStatus` 15). La
correspondencia catálogo↔UI **NO VERIFICADA** (exigiría leer los `.psm1`).

## T2 — Ledger de Atlas

`inventory/ledger/atlas-files.tsv` (**1 081** filas) y
`inventory/ledger/atlas-reg-entries.tsv` (**327** filas).

| kind | ficheros | entradas en `functions_json` |
|---|---:|---:|
| `script` | 248 | 1 097 |
| `config` | 327 | — |
| `cmd` | 192 | — |
| `test` | 124 | 375 |
| `rust` | 128 | 1 252 |
| `other` | 42 | — |
| `reg` | 11 | — |
| `package-binary` | 9 | — |
| **total** | **1 081** | **2 724** |

En `atlas-reg-entries.tsv` el dato **nunca** aparece: columnas `item_id, file,
key, name, type, value_sha256`. Tipos: 203 `sz`, 78 `default`, 30 `dword`,
14 `delete`, 2 `expand_sz`. `item_id = atlas:reg-entry:<fichero>#<clave>|<nombre>`.

Determinismo: dos ejecuciones consecutivas dan
`atlas-files.tsv` `4f3e67a4a24f566d7412c25a7530c1210907656875aab822efe5a247e7000d93`
y `atlas-reg-entries.tsv` `6f0a491f3895b5ea2934ef86d05d75d1f62333cb9aed83375f3cc9edb9e76eda`,
idénticos byte a byte (`cmp`), UTF-8 sin BOM, LF, orden por `item_id`.

**Nota de licencia para el catálogo.** Si el catálogo de EVO necesita los
*datos* de registro (no solo su existencia), hará falta un **ADR de licencia**
que separe hechos de configuración (rutas, nombres, tipos) de obra protegida
(los valores y los cuerpos de script). Hoy no se copia ninguno.

## T3 — Cobertura de extract de Atlas

`tools/ledger_extract/coverage_check_atlas.py`, exit 0:

| | |
|---|---:|
| ficheros extract | 1 081 |
| en el ledger | 1 081 |
| con hechos de contenido | 1 072 |
| sin hechos (binarios) | 9 |
| **sin motivo declarado** | **0** |
| entradas de registro | 327 |

Los 9 sin hechos de contenido: 4 `.cab`, 4 `.lnk`, 1 `.exe`, todos con motivo
(índice de miembros, puntero a panel de Windows, binario de terceros).

**Semántica NO extraída — deuda del Paso 4b**: qué hace cada script, qué
toggles expone la app, cómo se relacionan `catalog.json` (91 entradas), los 183
`.psd1` de `Tweaks/` y los módulos `Atlas.*`. No se ha inventado nada.

## T4 — Tests y CI

`tools/ledger_extract/tests/test_paso3b.py`: **16 tests nuevos** (`.reg` UTF-16
con claves y valores, borrado y `@`, no copia del dato, `item_id`, funciones en
`.ps1`, Pester sin `function`, tipos públicos de Rust, clasificación de `kind`,
binario, orden estable, determinismo, columnas exactas, cobertura OK / sin
motivo / binario con motivo / falta en ledger). Suite completa: **87 passed**
(71 previos + 16).

Workflow `ledger-verify`: +2 pasos (extractor de Atlas con doble ejecución y
`diff` de sha256; cobertura de Atlas). Se publican en `ci-report`
`atlas-files.tsv`, `atlas-reg-entries.tsv`, `atlas-sha-run1/2.txt`,
`atlas-determinism.txt` y `coverage-atlas.txt`.

## Desviaciones

1. **Informé 7 ficheros cuando eran 8**; el octavo es `Force Timer Resolution.xml`.
2. **El desglose de A REVISAR usaba categoría "sueltos"**; ahora es por prefijo.
3. **Cité `463b4a30` para `winutil-apps.tsv`**: era el hash pre-corrección.
4. **Conteos de `.reg` inicialmente en UTF-8**: los ficheros son UTF-16 LE.
   Corregido; el extractor decodifica por BOM.
5. **`pester/` en extract**: se mantiene con motivo, no se reclasifica.

## Supuestos

- `cabarchive` puede leer el índice sin descomprimir; se usó solo para nombres
  y tamaños, y no se escribió contenido de los `.cab` a disco.
- Los 14 idiomas completos son la referencia de i18n; `en-US` es un stub parcial.
- `tests/fixtures/*.json` son datos de entrada, no comportamiento de producto.

## Riesgos

- **R1** La semántica de Atlas (91 toggles, 183 `.psd1`) sigue sin extraer:
  Paso 4b.
- **R2** `atlas-files.tsv` es grande (1 081 filas con `functions_json`); si el
  catálogo necesita más detalle, sube el tamaño del artefacto.
- **R3** Si se decide usar datos de registro reales, la licencia GPL-3.0 puede
  alcanzar al catálogo: requiere ADR antes, no después.
