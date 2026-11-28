# Reconocimiento estructural de Atlas (GPL-3.0)

SHA fijado: `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`.
Fuente: `inventory/partition/results/atlas.tsv` (tratamientos) cruzado con
`inventory/upstream/atlas.files.tsv` (tamaño, extensión, top_dir).

**Límite de licencia (GPL-3.0).** Este documento y `inventory/ledger/atlas-*.tsv`
contienen **solo** rutas, nombres de fichero, extensiones, tamaños, líneas,
conteos y hashes. No se reproduce ni un fragmento de script, de Rust, de `.cmd`
ni de `.reg`. Las claves de registro se registran como *referencia* y los valores
solo como tipo + sha256 del dato, nunca el dato literal.

## 1. Ficheros extract: 1 081

Comando: `partition_review.py` + cruce con `atlas.files.tsv`.

### Por directorio de primer nivel

| directorio | ficheros |
|---|---:|
| `package/` | 802 |
| `app/` | 152 |
| `tests/` | 124 |
| `.atlasPsModulesPath` | 1 |
| `build.cmd` | 1 |
| `build.sh` | 1 |
| **total** | **1 081** |

### Por directorio de segundo nivel (los 6 mayores)

| directorio | ficheros |
|---|---:|
| `package/Executables/` | 802 |
| `app/src/` | 128 |
| `app/tools/` | 14 |
| `tests/fixtures/` | 14 |
| `app/resources/` | 8 |
| (resto: 115 grupos de 1 fichero, en su mayoría `tests/*.Tests.ps1`) | 115 |

### Por directorio de tercer nivel (los mayores)

| directorio | ficheros |
|---|---:|
| `package/Executables/AtlasModules/` | 585 |
| `package/Executables/AtlasDesktop/` | 217 |
| `app/src/services/` | 39 |
| `app/src/model/` | 32 |
| `app/src/ui/` | 23 |
| `app/src/pages/` | 17 |
| `tests/fixtures/windows-transition/` | 13 |
| `app/src/i18n/` | 8 |
| `app/resources/iso/` | 7 |

### Por extensión

| ext | ficheros | | ext | ficheros |
|---|---:|---|---|---:|
| `.ps1` | 357 | | `.json` | 17 |
| `.psd1` | 295 | | `.reg` | 11 |
| `.cmd` | 188 | | `.md` | 6 |
| `.rs` | 128 | | `.lnk` | 4 |
| `.url` | 40 | | `.cab` | 4 |
| `.psm1` | 19 | | `.vbs` | 3 |
| `.toml` | 2 | | `.xml` | 2 |
| sin extensión | 1 | | `.sh` | 1 |
| `.exe` | 1 | | `.cs` | 1 |
| `.txt` | 1 | | | |

Total 1 081.

## 2. `package/Executables/AtlasModules/Scripts/*`

416 ficheros bajo esa ruta, con **169** `.ps1`, **8** `.cmd`, **7** `.reg`,
203 `.psd1`, 19 `.psm1`, 2 `.json`, 4 `.md`, 3 `.vbs` y 1 `.cs`.

Funciones definidas por `^\s*function\s+([\w-]+)` en los 169 `.ps1`: **909**.

| subdirectorio | ficheros | .ps1 | .cmd | .reg | funciones |
|---|---:|---:|---:|---:|---:|
| `.` (raíz) | 2 | 1 | 1 | 0 | 0 |
| `Compatibility` | 2 | 1 | 0 | 0 | 4 |
| `Entry` | 29 | 19 | 7 | 0 | 55 |
| `Install` | 3 | 2 | 0 | 0 | 8 |
| `Install/Compat` | 1 | 1 | 0 | 0 | 8 |
| `Install/Phases` | 11 | 11 | 0 | 0 | 9 |
| `Install/Tasks` | 24 | 23 | 0 | 0 | 39 |
| `Modules/*/Domain` (14 módulos) | 67 | 67 | 0 | 0 | 439 |
| `Modules/*` (18 × psd1+psm1) | 36 | 0 | 0 | 0 | 0 |
| `Modules/Atlas.Core/Native` | 1 | 0 | 0 | 0 | 0 (1 `.cs`) |
| `Operations` | 19 | 18 | 0 | 0 | 121 |
| `Preparation` | 3 | 3 | 0 | 0 | 216 |
| `Registry/**` (3 subdirs) | 7 | 0 | 0 | 7 | 0 |
| `Tweaks/**` total | 222 | 23 | 0 | 0 | 10 |
| **total** | **416** | **169** | **8** | **7** | **909** |

## 3. `.reg`

11 `.reg` en extract; **7 de ellos bajo `Scripts/`** y 2 bajo `AtlasDesktop/`,
más 2 en `Toolbox/`.

Los `.reg` de Atlas están en **UTF-16 LE con BOM** (verificado con `od -c`:
bytes `377 376`), así que deben leerse con `utf-16` explícito; leerlos como
UTF-8 produce texto con `\0` intercalados y conteos falsos.

| fichero | líneas | claves `[HKEY…]` | valores `nombre=` |
|---|---:|---:|---:|
| `AtlasDesktop/2. Drivers/…/Disable Drivers from Windows Update.reg` | 30 | 9 | 11 |
| `AtlasDesktop/2. Drivers/…/Enable Drivers from Windows Update.reg` | 29 | 9 | 10 |
| `AtlasModules/Scripts/Registry/SecurityHealthTray/disable.reg` | 4 | 1 | 1 |
| `AtlasModules/Scripts/Registry/SecurityHealthTray/enable.reg` | 8 | 1 | 1 |
| `AtlasModules/Scripts/Registry/TakeOwnership/add.reg` | 39 | 8 | 23 |
| `AtlasModules/Scripts/Registry/TakeOwnership/remove.reg` | 9 | 4 | 0 |
| `AtlasModules/Scripts/Registry/Terminals/disabled.reg` | 14 | 6 | 1 |
| `AtlasModules/Scripts/Registry/Terminals/enabled.reg` | 294 | 70 | 153 |
| `AtlasModules/Scripts/Registry/Terminals/minimal.reg` | 234 | 54 | 125 |
| `AtlasModules/Toolbox/Scripts/SecurityHealthTray/AddTray.reg` | 8 | 1 | 1 |
| `AtlasModules/Toolbox/Scripts/SecurityHealthTray/RemoveTray.reg` | 4 | 1 | 1 |
| **total** | **673** | **164** | **327** |

## 4. Rust (`app/src`)

128 ficheros `.rs`, 2 597 197 bytes, 59 917 líneas. Tipos públicos por regex
`^\s*pub(?:\([^)]*\))?\s+(struct|enum|trait|fn|type|const|mod)\s+(\w+)`:

| clase | declaraciones |
|---|---:|
| `fn` | 916 |
| `struct` | 159 |
| `enum` | 86 |
| `const` | 74 |
| `mod` | 41 |
| `type` | 5 |
| `trait` | 2 |

Los 10 ficheros `.rs` mayores: `pages/iso.rs` (2 520 L), `i18n/describe.rs`
(1 633), `pages/report.rs` (1 495), `services/package.rs` (1 532),
`services/preparation.rs` (1 433), `model/tests/transition.rs` (1 347),
`pages/mod.rs` (1 228), `services/iso.rs` (1 210), `pages/home.rs` (1 247),
`services/system.rs` (923).

**Dónde se define la lista de ajustes que expone la UI.** Dos candidatos, con
conteo por regex (variantes de primer nivel de cada `pub enum`, sin leer cuerpos):

| fichero | tipo | variantes |
|---|---|---:|
| `app/src/model.rs` | `Page` | 6 (Home, Iso, Install, Settings, Report, Installed) |
| `app/src/model.rs` | `CloseGuard` | 9 |
| `app/src/model.rs` | `Notice` | 3 |
| `app/src/model.rs` | `ModelEvent` | 3 |
| `app/src/model/options.rs` | `ScreenKind` | 11 |
| `app/src/model/options.rs` | `FixedChoice` | 3 |
| `app/src/model/options.rs` | `UpdatePath` | 2 |
| `app/src/model/checks.rs` | `ReadyStatus` | 15 |
| `app/src/model/checks.rs` | `ReadyHelp` | 4 |
| `app/src/model/install.rs` | `Preflight` | 6 |

El catálogo real de ajustes **no está en Rust**: está en
`package/Executables/AtlasModules/Toggles/catalog.json`, con **91 entradas** y
campos `name, group, description, elevation, noStateRecord, menu, launcher,
warning, states`. Los `enum` de Rust describen pantallas y estados, no ajustes.
El número de ajustes por sí solo (91 en el catálogo) es dato contrastado; la
correspondencia catálogo↔UI **NO VERIFICADA** (requiere leer los `.psm1`).

## 5. i18n

`app/i18n/<idioma>/atlas.ftl`, formato Fluent (claves `nombre = valor`).

**15 ficheros de idioma**, no 18: `de, en-GB, en-US, es, fr, hi, id, ja, pl,
pt-BR, ru, th, tr, zh-Hans, zh-Hant`.

Conteo de claves por idioma: **956** en los 14 idiomas completos; **en-US tiene
solo 25** claves (es un stub parcial de referencia).

Conjunto de claves: los 14 idiomas completos tienen **exactamente el mismo
conjunto** (0 diferencias entre ellos). `en-US` es **subconjunto** de ellos
(25 ⊂ 956, 0 claves que no estén en el resto). Diferencias: ninguna más allá de
eso.

## 6. `tests/`

124 ficheros en extract: **109** `.ps1` (108 `.Tests.ps1` + `AtlasTestHost.ps1`),
13 `.json` (fixtures), 1 `.md`, 1 `.txt`.

Pester por regex `^\s*(Describe|Context|It)\s`: **437 Describe**, **37 Context**,
**2 017 It**. Agregado por fichero en `inventory/ledger/atlas-files.tsv`
(columnas `functions_json`).

## 7. Otros formatos en extract

| formato | ficheros | tratamiento |
|---|---:|---|
| `.psd1` | 295 | config (definiciones de tweak/toggle) |
| `.cmd` | 188 | cmd |
| `.psm1` | 19 | config (módulos) |
| `.json` | 17 | config |
| `.lnk` | 4 | package-binary |
| `.cab` | 4 | package-binary |
| `.vbs` | 3 | cmd |
| `.toml` | 2 | config |
| `.xml` | 2 | config |
| `.md` | 6 | config |
| `.cs` | 1 | other (`Atlas.Native.cs`) |
| `.exe` | 1 | package-binary |
| `.sh` | 1 | other |
| `.txt` | 1 | config |
| sin ext | 1 | other (`.atlasPsModulesPath`) |

## 8. `.cab` — miembros (ahora sí verificados)

Con `cabarchive` (PyPI, puro Python) se leyó el índice **sin escribir contenido
a disco**. Solo se listan nombres y tamaños:

| cab | miembros | suma bytes | composición |
|---|---:|---:|---|
| `Z-Atlas-NoDefender-…amd64….cab` | 168 | 159 116 | 1 `.mum` + 1 `.cat` + 166 `.manifest` |
| `Z-Atlas-NoDefender-…arm64….cab` | 204 | 192 876 | 1 `.mum` + 1 `.cat` + 202 `.manifest` |
| `Z-Atlas-NoTelemetry-…amd64….cab` | 100 | 93 760 | 1 `.mum` + 1 `.cat` + 98 `.manifest` |
| `Z-Atlas-NoTelemetry-…arm64….cab` | 106 | 100 283 | 1 `.mum` + 1 `.cat` + 104 `.manifest` |
| **total** | **578** | **546 035** | |

Los miembros son manifiestos de componente de Windows Update: no contienen
código de producto de Atlas.
