# Paso 8b — Auditoría de valores, regla de restauración, huecos de la oleada 1 y mapa upstream→capacidad

- Rama `arena/ab2d6de7-evo-optimizer-on`, HEAD de partida `1d5a01b`.
- Pins: Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f` (GPL-3.0-only), WinUtil
  `70c23c80641d7370532af2f619b2842658600842` (MIT).
- Sandbox Debian 12, Python 3.11.2, **sin dotnet**: todo lo .NET se verifica en
  GitHub Actions (Windows + Linux).

## T0 — Estado del árbol

HEAD local `1d5a01b69d0d…f60a`, idéntico a `git ls-remote origin`. Los seis TSV del
paso 8 y el inventario de usuario conservan su sha256 (`0b6aeaef…f709` para
`docs/requirements/INVENTARIO_USUARIO.md`, no modificado). El recuento de partida
de las secciones 1-3 era 10+59+30 = 99 acciones.

| Comprobación | Resultado |
| --- | --- |
| R0 pin Atlas = inventario | OK |
| R1 pin WinUtil = inventario | OK |
| R2 sin texto de upstream en el catálogo | OK |
| R3 ids con namespace de sección | OK |
| **R4 reversibilidad declarada** | **NO CUMPLIDO al empezar: 12/26**. Ahora **38/38** (T2) |
| R5 restauración >= mínimo por riesgo | OK (verificado por `test_las_ramas_de_reversibilidad...`) |
| R6 ninguna capacidad `Implemented` sin test | 29 `Implemented`; 126 xUnit verdes en CI |

## T1 — Auditoría de valores (`catalog-value-audit.tsv`)

`tools/ledger_extract/audit_catalog_values.py` relee el literal de Atlas **del pin
en memoria** (`/tmp/upstream/atlas`), no de los TSV: `atlas-tweak-ops.tsv` no
guarda el literal `Data` y el parser `.psd1` hubo que arreglarlo (llave de cierre
`Data = … }`, hashtables anidados `VerifyWithToggle`, comentarios con comillas).

| Relación | Filas |
| --- | --- |
| `equals-apply` | 95 |
| `no-source` | 6 |
| `ambiguous` | 2 |
| `equals-original` | 1 |
| **total** | **104** |

Las 6 `no-source` son `cleanup.recycle.bin`, `cleanup.wer.reports`,
`privacy.telemetry.dmwappush`, y las tres claves `Policies\Microsoft\Dsh` de
`debloat.widgets.disable` (WinUtil no las escribe por registro; usa `Dsh` sólo vía
toggle de Atlas para `AllowNewsAndInterests`). Las 2 `ambiguous` son
`privacy.activity.history/EnableActivityFeed` y
`debloat.start.recommendations/HideRecommendedSection`, donde las dos fuentes
discrepan entre sí.

La única `equals-original` es una **desviación real y documentada** en
`catalog/exceptions/value-deviations.json`:

- `debloat.settings.home` — `SettingsPageVisibility`: el catálogo escribe
  `hide:home`; WinUtil aplica `show:home` y revierte a `hide:home`
  (`config/tweaks.json:1741-1755`). El nombre de la capacidad es «ocultar la
  página de Inicio», así que se copia el valor que produce ese efecto, no el que
  WinUtil aplica en su rama de toggle (que deja la página visible). Evidencia y
  motivo quedan en la excepción, y el script falla (exit 1) si aparece una
  desviación sin declarar: `sin_excepcion = 0`.

## T1c — Evidencias (ruta:línea en el pin)

| Capacidad | Valor catálogo | Evidencia |
| --- | --- | --- |
| `privacy.activity.history` | `EnableActivityFeed=0` | WinUtil `config/tweaks.json` `WPFTweaksActivity` L2 → L10 `=1` (OriginalValue `<RemoveEntry>`); Atlas `privacy/disable-activity-feed.psd1:5` `=0` → **discrepancia real** |
| `privacy.activity.history` | `PublishUserActivities=0` | WinUtil L460 → L550 `=0`; Atlas `privacy/disallow-user-activity-upload.psd1:5-6` |
| `privacy.activity.history` | `UploadUserActivities=0` | WinUtil L460 → L550 `=0` |
| `privacy.telemetry.diagtrack` | `AllowTelemetry=0` | WinUtil L460 → L536 `=0` (OriginalValue `1`); Atlas `privacy/telemetry/disallow-data-collection.psd1:5` |
| `debloat.start.websearch` | `BingSearchEnabled` **no se escribe** | `WPFToggleBingSearch` L1759 → L1768 aplica `=1` (activa Bing) y OriginalValue `0`; copiarlo invertiría el efecto. Atlas `privacy/search-settings.psd1:21-22` |
| `privacy.feedback.frequency` | `=0` | Atlas `qol/disable-windows-feedback.psd1:8` |
| `debloat.explorer.home-gallery` | CLSID + `LaunchTo=1` | Atlas `qol/taskbar/disable-copilot.psd1:9` |

## T2 — ADR-0003 (`docs/adr/ADR-0003-reversibilidad-y-restauracion.md`)

Enum `Reversibility { Reversible, NothingToRestore, Irreversible }` obligatorio en
el contrato y en el JSON. Tabla aplicada por `CapabilityRules.ValidateReversibility`
(error `R-RISK`, no aviso):

| Reversibilidad | Restore | Risk | Confirmation |
| --- | --- | --- | --- |
| `Reversible` | `>= SessionUndo` y `>=` mínimo por riesgo | cualquiera | mínimo por riesgo |
| `NothingToRestore` | exactamente `None` | `<= Medium` | mínimo por riesgo |
| `Irreversible` | exactamente `None` | `>= High` | `>= SummaryAndRestorePoint` |

Distribución final: **13 Irreversible**, **4 NothingToRestore**, **21 Reversible**.

Cambios de `Risk`/`Restore`/`Confirmation` respecto al paso 8 (todos suben aviso
porque el efecto es irrecuperable, salvo `privacy.ceip.tasks` que se puede deshacer):

| Capacidad | Cambio |
| --- | --- |
| `cleanup.recycle.bin` | Safe → High, None → SummaryAndRestorePoint |
| `cleanup.winsxs.component` | Medium → High, RestorePoint → None, Summary → SummaryAndRestorePoint |
| `debloat.{appx.consumer,cortana.remove,onedrive.uninstall,windows.ai,telemetry.appx}` | Medium → High, RestorePoint → None, Summary → SummaryAndRestorePoint (×5) |
| `privacy.ceip.tasks` | Medium → Low, RestorePoint → SessionUndo, Summary → SimpleClick |
| `debloat.explorer.auto-folder-discovery` | nace Medium → High (rama Irreversible) |
| `debloat.drivers.{razer,logitech}`, `debloat.network.adobe-blocklist` | nacen High/None |

Tests: `tests/Evo.Core.Tests/ReversibilityTests.cs` (13 `[Fact]`, incluye el mínimo
por riesgo, los tres rechazos y `MinimumRestore`), más la aserción de
`Enum.GetNames<Reversibility>()` en `CapabilityContractTests` y tres casos nuevos
en `CatalogValidatorTests` (falta `reversibility` → `R-RISK`).

## T3 — Huecos de la oleada 1

- `privacy.telemetry.dmwappush` → `Specified`: la única fuente es el servicio
  (`Start=4`) y no un tweak del pin; queda marcado `NO VERIFICADO` en `provenance`.
- `cleanup.winsxs.resetbase` (nueva, S1): `dism /StartComponentCleanup /ResetBase`,
  `Irreversible/High/None/SummaryAndRestorePoint`, `conflictsWith` simétrico con
  `cleanup.winsxs.component`.
- 13 capacidades nuevas en S2 (14 nuevas en total, catálogo **38**): ver conteo por
  fichero abajo. Las que sólo existen como script del pin se declaran `Specified`
  con `CommandAction`.

Cobertura del inventario: **26 Mapped · 26 cubiertas · 0 huecos · 0 no declarados ·
veredicto OK** (S1 3/3, S2 17/17, S3 6/6). `DECLARED_GAPS` queda vacía.

Conteo por fichero tras 8b:

| Fichero | Capacidades | Acciones | Implemented | Specified |
| --- | --- | --- | --- | --- |
| `section1_cleanup.json` | 8 | 11 | 7 | 1 |
| `section2_debloat.json` | 21 | 94 | 14 | 7 |
| `section3_telemetry.json` | 9 | 30 | 8 | 1 |
| **total** | **38** | **135** | **29** | **9** |

## T4 — Mapa upstream→capacidad (`upstream-capability-map.tsv`)

`build_upstream_capability_map.py` cruza las 435 entradas del ledger contra las 38
capacidades por tres vías: `ledger_refs` de `provenance`, nombres `WPF*` y slugs
`Tweaks/*.psd1`. `section_guess` **no** se deduce por parecido de texto: sólo se
rellena con la capacidad asociada o con la sección ya medida en
`inventory-reconciliation.tsv`.

| source | covered | pending | not-a-capability | total |
| --- | --- | --- | --- | --- |
| `winutil` | 24 | 127 | 11 | 162 |
| `atlas-toggle` | 1 | 90 | 0 | 91 |
| `atlas-manifest` | 12 | 170 | 0 | 182 |
| **total** | **37** | **387** | **11** | **435** |

**Cobertura real: 37/435 = 8,5 %.** Las 11 `not-a-capability` son entradas de
navegación de WinUtil (`nav-entry`). Pending por `section_guess`: sin sección 361,
S4 1, S7 4, S9 7, S10 5, S11 3, S13 4, S14 2. Ese 361 es el hueco de verdad: el
ledger no guarda sección para la mayoría de entradas, así que el mapa no puede
afirmar a qué sección sirven.

`coverage_gate.py`: `phase0` sale 0; `beta` sale 1 (pending 387) y 0 con
`--informational`; `release` exige pending 0. El workflow corre `phase0` y
`beta --informational` para no bloquear por un número que todavía no es exigible.

## T5 — Verificación

- `tests/test_paso8b.py`: 24 tests (auditoría, excepciones, ADR-0003 sobre el JSON
  real, cobertura 26/26, mapa, gate, LF/UTF-8 y compilación de los scripts).
- `tests/test_paso8.py` actualizado: 38 capacidades, `Implemented|Specified`, ids del
  paso 8 como subconjunto e invariantes de riesgo según ADR-0003. **170 verdes**.
- Suite completa: **433 pytest verdes**; `validate_dotnet_structure.py` OK.
- `.github/workflows/ledger-verify.yml`: nuevo paso «Paso 8b» que ejecuta los tres
  scripts dos veces, compara `sha256sum` de los dos TSV, publica ambos TSV y los
  JSON en `ci-report` y aplica los dos gates.
- .NET: los tests C# nuevos (`ReversibilityTests`, `CatalogValidatorTests`,
  `Wave1EngineTests`) **no se pudieron ejecutar en el sandbox** (sin dotnet); se
  verificaron en Actions.

### Resultado de CI

Medido en los runs sobre el árbol que se aplastó en el commit único del paso 8b
(sha `f7258cc` de la rama de trabajo); el commit final sólo difiere en este
informe. Los runs de ese sha fueron `ledger-verify` 45322017974 y `dotnet-ci`
45322024858.

| Workflow | Run | Resultado |
| --- | --- | --- |
| `ledger-verify` | 45322017974 | success — 433 pytest, determinismo 8b OK, gates OK |
| `dotnet-ci` (windows-2025) | 45322024858 | success — 126/126 (Catalog 36, Core 34, Detection 35, Engine 21) |
| `dotnet-ci` (windows-11-arm) | 45322024858 | success — 126/126 |

El primer intento sobre `f20465c` falló y sirvió para arreglar cosas reales:
`Wave1CatalogTests` listaba los 24 ids del paso 8 (ahora 38),
`CatalogLoaderTests` declaraba `reversibility=Irreversible` con
`RestorePoint/Medium`, y dos casos de `CapabilityContractTests` seguían
probando la regla antigua del paso 6. Los 13 `ReversibilityTests` pasaron a la
primera. Total xUnit: **126** (antes 109; +13 de reversibilidad y +4 de la
tabla de validador).

## Divergencias documentadas (no son bugs del catálogo)

- WinUtil aplica `EnableActivityFeed=1` (feed activo) y revierte a `<RemoveEntry>`;
  Atlas y EVO escriben `0`. Se sigue la intención (desactivar) y se registra.
- `WPFToggleBingSearch` aplica `BingSearchEnabled=1`: es un toggle inverso. EVO usa
  `DisableSearchBoxSuggestions=1` y no escribe `BingSearchEnabled`.
- `DiskCleanup` de WinUtil llama a `dism` con `/ResetBase`: se separa en su propia
  capacidad irreversible en vez de esconderlo dentro de `winsxs.component`.
- `RemoveMicrosoftCopilotApp` sólo existe para Enterprise/Education; no se modela.
