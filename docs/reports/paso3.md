# Paso 3 — Extractor determinista de WinUtil (MIT)

Fecha: 2026-11-23 · Rama: `arena/ab2d6de7-evo-optimizer-on`
Fuente: `ChrisTitusTech/winutil@70c23c80641d7370532af2f619b2842658600842`
Licencia: MIT. Solo se guardan rutas, claves, hashes y conteos: **ningún cuerpo
de código de upstream se copia** (§5 del contrato).

## T0 — Cierre del paso anterior

### a) Cifra 209 corregida

`docs/reports/paso2b.md` decía 208 A REVISAR con un desglose que sumaba 209.
Recuento real (**208**), verificado con `partition_review.py`:

| grupo | ficheros |
|---|---:|
| `app/vendor/**` | 189 |
| `package/Executables` | 7 |
| `app/licenses` | 2 |
| `.vscode/` | 3 |
| `.zed/` | 2 |
| sueltos (`build.rs`, `examples/`, `rustfmt.toml`, `lychee.toml`, `atlas.json`) | 5 |
| **total** | **208** |

El error estaba en el desglose (`package/Executables` son 7, no 8; `.vscode` son
3, no 2), no en el recuento.

### b) Las 39 filas de `seccion16-17-probe.tsv`

| item | winutil | atlas | dudoso |
|---|---:|---:|:---:|
| Atlas Playbook | 0 | 19 | n |
| AME Wizard | 0 | 8 | n |
| TrustedInstaller Broker | 0 | 35 | n |
| Install Plan | 0 | 41 | n |
| Install Session | 0 | 19 | n |
| Installation Phases | 3 | 143 | **s** |
| Pre-Install | 8 | 14 | n |
| Environment Phase | 0 | 3 | n |
| Choices Phase | 4 | 160 | **s** |
| Features Phase | 0 | 6 | n |
| Services Phase | 0 | 3 | n |
| Tweaks Phase | 0 | 10 | n |
| Components Phase | 0 | 9 | n |
| Software Phase | 0 | 3 | n |
| Shell Refresh Phase | 0 | 28 | n |
| AppX Support Phase | 0 | 18 | n |
| Windows Transition | 0 | 58 | n |
| ISO Creation | 3 | 38 | **s** |
| ISO Injection | 6 | 0 | **s** |
| Upgrade System | 0 | 1 | **s** |
| New User Initialization | 1 | 28 | n |
| Atlas Health | 0 | 21 | n |
| Toggle State Persistence | 5 | 91 | n |
| Package Verification | 0 | 5 | n |
| Component Servicing | 1 | 61 | n |
| PowerShell Module Initialization | 4 | 185 | n |
| Compile.ps1 | 14 | 0 | n |
| inicialización WPF | 33 | 0 | n |
| Runspaces | 48 | 3 | n |
| trabajos en segundo plano | 58 | 153 | **s** |
| presets | 35 | 7 | n |
| importación/exportación | 13 | 268 | n |
| deshacer ajustes | 61 | 47 | n |
| detección de cambios revertidos | 24 | 9 | n |
| registro de ejecución | 99 | 48 | **s** |
| creación de USB | 15 | 62 | **s** |
| instalación de ISO | 54 | 252 | n |
| actualización del programa | 116 | 535 | **s** |
| informes de entorno | 11 | 0 | n |

### c) Reclasificación de `package/Executables`

Los **7** ficheros con extensión de comportamiento en `reference` pasan a
`extract` (ninguno es documentación; los `.md`/`.url` siguen en `reference`):

| ruta | bytes |
|---|---:|
| `package/Executables/AtlasModules/Other/StartLayout.json` | 685 |
| `package/Executables/AtlasModules/Packages/Atlas-CbsHashes.psd1` | 1.078 |
| `package/Executables/AtlasModules/Toggles/catalog.json` | 115.595 |
| `package/Executables/AtlasModules/Packages/Z-Atlas-NoDefender-Package31bf3856ad364e35amd645.0.0.0.cab` | 43.743 |
| `package/Executables/AtlasModules/Packages/Z-Atlas-NoDefender-Package31bf3856ad364e35arm645.0.0.0.cab` | 52.230 |
| `package/Executables/AtlasModules/Packages/Z-Atlas-NoTelemetry-Package31bf3856ad364e35amd645.0.0.0.cab` | 27.817 |
| `package/Executables/AtlasModules/Packages/Z-Atlas-NoTelemetry-Package31bf3856ad364e35arm645.0.0.0.cab` | 29.376 |

Los `.cab` se registran **solo** por nombre, tamaño y sha256:

| cab | sha256 |
|---|---|
| NoDefender amd64 | `6a8d1f8788277b425766fad069a8192edc33eea2d6f7f9b061a42c941a21d2ec` |
| NoDefender arm64 | `39500fa6df403f162c02a9c36d37d2c787bf459c05376872b9962fa649f4e081` |
| NoTelemetry amd64 | `11c5e3502dcb962f2fae456712c7982dc1864d686b76194628cbff8d1cd77eca` |
| NoTelemetry arm64 | `c6526330f660e654b249b63a974793bae0e39f6714a0b79e03942145195e29a3` |

**Miembros de los CAB: NO VERIFICADO.** No hay `7z`, `cabextract`, `gcab` ni
`bsdtar` en el sandbox y `zipfile` de Python falla
(`BadZipFile: File is not a zip file`: es un CAB real, no un ZIP). No se
descomprime contenido de Atlas (GPL-3.0).

Conteos tras T0c (`partition_check.py`): winutil `extract=206 / reference=495 /
exclude=3`; atlas `extract=1081 / reference=466 / exclude=3`. **0 sin
clasificar, 0 reglas muertas, 0 excludes sobre comportamiento.** A REVISAR: 0
(winutil) y 201 (atlas, 189 son `app/vendor/**`).

## T1 — Esquema real de config

`docs/inventory-recon/winutil-config-schema.md` (generado por
`tools/ledger_extract/config_schema.py`). Carga `utf-8-sig` + `strict=False`.

| fichero | claves nivel 1 | campos por entrada |
|---|---:|---:|
| applications.json | 239 | 8 |
| appnavigation.json | 11 | 7 |
| appx.json | 34 | 6 |
| dns.json | 8 | 6 |
| feature.json | 33 | 10 |
| preset.json | 4 | 1 |
| themes.json | 3 | 89 |
| tweaks.json | 69 | 14 |

`tweaks.json`: `Content` 69, `category` 69, `panel` 69, `link` 69,
`Description` 66, `registry` 50 (`list[object]`), `Type` 29, `InvokeScript` 27
(`list[str]`), `UndoScript` 22, `service` 4, `ComboItems` 2…

`applications.json`: `category` 239, `content` 239 (minúscula), `description`
239, `link` 239, `winget` 239, `foss` 238, `choco` 236, `_comment` 1.

## T2 — Items del ledger

`inventory/ledger/winutil-items.tsv` (162 filas) y `winutil-apps.tsv` (239).

| kind | items |
|---|---:|
| tweak | 69 |
| appx | 34 |
| feature | 33 |
| nav-entry | 11 |
| dns-provider | 8 |
| preset | 4 |
| theme | 3 |
| **total** | **162** |

**Predicción 69+33+34+3+4+11+8 = 162 ✓ y apps 239 ✓.** Coincide exactamente.

Comprobaciones cruzadas:
- Miembros de preset: **51** comprobados. **18** no están en `tweaks.json` pero
  **sí en `appx.json`** (son los `WPFAppx*` del preset `AppxDefault`).
  **0 inexistentes** en ambos ficheros.
- Claves duplicadas en el objeto raíz: **0** en los 7 ficheros.
- Entradas sin etiqueta: 11 (`dns.json` ×8 y `themes.json` ×3, que no tienen
  campo `Content`/`content`). Apps sin `winget` ni `choco`: **0**.

Apps por categoría: Utilities 53, Development 43, Pro Tools 24, Multimedia
Tools 21, Microsoft Tools 19, Communications 18, Document 17, Games 17,
Browsers 15, Selfhosted Tools 12.

**Determinismo:** dos ejecuciones consecutivas dan
`c4b980d71311c34ca008c00cd68538287a3cb9bedaa46d50b2d352c4e969378f`
(`winutil-items.tsv`) y
`463b4a308bc5b38f1aaea47821d6b700b98d5bc5dea7dbc3da99972a0697944f`
(`winutil-apps.tsv`). `cmp` byte a byte: idénticos. UTF-8 sin BOM, LF, orden
estable por `item_id`.

## T3 — Funciones y scripts

`inventory/ledger/winutil-functions.tsv`: **195** ficheros `.ps1` en extract.

| scope | ficheros | funciones | líneas |
|---|---:|---:|---:|
| public | 35 | 42 | 3.024 |
| private | 90 | 164 | 9.752 |
| scripts | 2 | 4 | 438 |
| other (raíz, pester, lint) | 68 | 204 | 16.506 |

**23 ficheros sin funciones definidas**: `Compile.ps1`, `windev.ps1`,
`lint/PSScriptAnalyser.ps1` y 20 `pester/*.Tests.ps1` (usan `Describe`/`It`,
no `function`).

**Corrección [paso 4b]:** el TSV gana la columna `scope`, que separa
`product` (127 ficheros, **210** funciones = 42 public + 164 private + 4
scripts), `test` (65 ficheros, **204** funciones) y `tooling` (3 ficheros, 0).
Decir que `pester/` "da 0 items" es impreciso: sus 204 funciones son
**ayudantes de test**, no capacidades de producto; el test en sí sí es
comportamiento ejecutable, por eso sigue en `extract`.

## T4 — Cobertura de extract (ADR-0001)

| | |
|---|---:|
| ficheros con tratamiento extract | **206** |
| con al menos un item | **180** |
| extract sin items (con motivo declarado) | **26** |
| sin motivo declarado | **0** |

Los 26: 20 tests Pester + `pester/fixtures/legacy-config.json` (fixture) +
`Compile.ps1` y `sign.bat` (implementation-detail de build) +
`lint/PSScriptAnalyser.ps1`, `windev.ps1`, `xaml/inputXML.xaml`.

**Atlas: NO evaluado en este paso.** Sus 1081 ficheros extract siguen sin
extractor; es deuda declarada para el Paso 4.

## T5 — Tests y CI

- `tools/ledger_extract/tests/test_paso3.py`: **16 tests nuevos**.
- Suite completa: **71 passed** (55 previos + 16).
- `ledger-verify.yml`: nuevos pasos "Extractor de WinUtil (determinismo)"
  (ejecuta dos veces y `diff` de sha256; falla si difieren), "Cobertura de
  extract" y "Esquema de config"; los TSV generados se copian a `ci-out/` y se
  publican en la rama `ci-report`.

Cierre: el workflow `ledger-verify` se ejecuta en cada push de esta capa. La
evidencia vive en la rama `ci-report`: `latest/ledger-verify/meta.json` (campo
`sha` = commit verificado, `files: 15`), `pytest.txt` (`71 passed`,
`pytest_exit=0`), `determinism.txt` (`determinismo: OK`), `coverage.txt`
(`sin motivo declarado: 0`, `coverage_exit=0`), `partition_check.txt`
(`VEREDICTO: OK` ×2) y los tres TSV publicados.
