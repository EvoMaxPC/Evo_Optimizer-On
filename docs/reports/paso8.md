# Paso 8 — Oleada 1 del catálogo: limpieza, debloat y telemetría (secciones 1, 2 y 3)

Fecha: 2026-11-23. Rama `arena/ab2d6de7-evo-optimizer-on`.
Pins: Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f` (GPL-3.0-only),
WinUtil `70c23c80641d7370532af2f619b2842658600842` (MIT).

## T0 — Evidencia

```
$ git rev-parse HEAD
c8e3cf731e00f8365a630c4aaa1dd6207648da7c
$ git ls-remote origin refs/heads/arena/ab2d6de7-evo-optimizer-on
c8e3cf731e00f8365a630c4aaa1dd6207648da7c
$ sha256sum docs/requirements/INVENTARIO_USUARIO.md
0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709
$ git status --short
(vacío)
```

El inventario no se tocó (mismo sha al final del paso).

## Ficheros y cifras

| Fichero | Capacidades | Acciones |
|---|---|---|
| `catalog/capabilities/section1_cleanup.json` | 7 | 10 |
| `catalog/capabilities/section2_debloat.json` | 8 | 59 |
| `catalog/capabilities/section3_telemetry.json` | 9 | 30 |
| **total** | **24** | **99** |

`State=Implemented` en las 24, `SecurityImpact=Neutral` en las 24,
`SupportedBuilds=[19045, 22631, 26100, 26200]` en todas salvo
`debloat.windows.ai` (`[22631, 26100, 26200]`: Recall/Copilot no existen en
Windows 10 22H2). Todas declaran `provenance` con el pin y la ruta exacta.

`conflictsWith` y `dependsOn` están vacíos en las 24: no hay dos capacidades de
esta oleada que se pisen (las de limpieza escriben `VolumeCaches`, las de
privacidad claves distintas) y ninguna necesita de otra para poder aplicarse.
La simetría se cumple por vacuidad y el grafo es un DAG trivial; los tests lo
comprueban igualmente.

### Sección 1 — limpieza

| Id | Riesgo | Restore | Privilege | Base |
|---|---|---|---|---|
| `cleanup.temp.user` | Safe | None | User | WinUtil `WPFTweaksDeleteTempFiles` + Atlas `Invoke-DiskCleanup -Scope CurrentUser` |
| `cleanup.temp.system` | Safe | None | Admin | ídem, `%SystemRoot%\Temp` |
| `cleanup.delivery.optimization` | Low | SessionUndo | Admin | WinUtil `WPFTweaksDeliveryOptimization` (`DODownloadMode=0`) |
| `cleanup.wer.reports` | Safe | None | Admin | Atlas, categoría `Windows Error Reporting Files` + `cleanmgr /sagerun:64` |
| `cleanup.recycle.bin` | Safe | None | Admin | Atlas, categoría `Recycle Bin` |
| `cleanup.winsxs.component` | Medium | RestorePoint | Admin | Atlas `Invoke-FeaturesPhase.ps1:128` (sin `/ResetBase`) |
| `cleanup.memory.dumps` | Safe | None | Admin | Atlas, categorías de volcados de `cleanmgr` |

### Sección 2 — debloat

| Id | Riesgo | Restore | Base |
|---|---|---|---|
| `debloat.appx.consumer` | Medium | RestorePoint | Atlas `Atlas.Appx/Domain/Removal.ps1` + WinUtil `config/appx.json` (13 familias) |
| `debloat.cortana.remove` | Medium | RestorePoint | Atlas `Microsoft.549981C3F5F10*` (`AllowMissingProvisioningFiles`) |
| `debloat.onedrive.uninstall` | Medium | RestorePoint | WinUtil `WPFTweaksRemoveOneDrive` |
| `debloat.edge.policies` | Low | SessionUndo | WinUtil `WPFTweaksEdgeDebloat` (17 políticas) |
| `debloat.start.websearch` | Low | SessionUndo | Atlas `privacy/search-settings.psd1` (10 valores) |
| `debloat.windows.ai` | Medium | RestorePoint | Atlas Recall / Settings Agent / Click To Do / Copilot + WinUtil `WPFTweaksWindowsAI` |
| `debloat.content.delivery` | Low | SessionUndo | Atlas `debloat/config-content-delivery.psd1` (19) + WinUtil `WPFTweaksConsumerFeatures` |
| `debloat.telemetry.appx` | Medium | RestorePoint | WinUtil `WPFAppxMicrosoft_WindowsFeedbackHub`/`_GetHelp` + Atlas Removal.ps1 |

### Sección 3 — telemetría y privacidad

| Id | Riesgo | Restore | Base |
|---|---|---|---|
| `privacy.telemetry.diagtrack` | Low | SessionUndo | WinUtil `WPFTweaksTelemetry` (service) + Atlas `disallow-data-collection.psd1` |
| `privacy.telemetry.dmwappush` | Low | SessionUndo | WinUtil `Invoke-WinUtilISOScript.ps1:561` (única fuente) |
| `privacy.advertising.id` | Low | SessionUndo | Atlas `disable-advertising-info.psd1` (3 valores) |
| `privacy.activity.history` | Low | SessionUndo | Atlas `disable-activity-feed` + `disallow-user-activity-upload` |
| `privacy.feedback.frequency` | Low | SessionUndo | Atlas `qol/disable-windows-feedback.psd1` + WinUtil `Siuf\Rules` |
| `privacy.location.sensors` | Low | SessionUndo | WinUtil `WPFTweaksLocation` (3 valores + `lfsvc`) |
| `privacy.ceip.tasks` | Medium | RestorePoint | Atlas `debloat/disable-scheduled-tasks.psd1` (5 tareas + `Ubpm`) |
| `privacy.diagnostic.data.level` | Low | SessionUndo | Atlas `disallow-data-collection` + `disable-diagnostic-tracing` + `disable-tailored-experiences` + WinUtil espejo `CurrentVersion\Policies\DataCollection` |
| `privacy.kms.activation.telemetry` | Low | SessionUndo | Atlas `disable-activation-telemetry.psd1` (`NoGenTicket=1`) |

## Cobertura del ledger — `tools/ledger_extract/verify_catalog_coverage.py`

```
$ python3 tools/ledger_extract/verify_catalog_coverage.py
capacidades del catalogo : 24
lineas Mapped 1-3       : 26
  cubiertas             : 12
  huecos declarados     : 14 (de 14 declarados)
  seccion 1: 3 Mapped, 3 cubiertas, 0 huecos
  seccion 2: 17 Mapped, 5 cubiertas, 12 huecos
  seccion 3: 6 Mapped, 4 cubiertas, 2 huecos

(cifra informativa) capacidades que no respaldan ninguna linea Mapped: 18
veredicto: OK
```

El cruce es por `mapped_ids`: cada capacidad lista los `item_id` del ledger de
los que sale en un sufijo `ledger_refs:` de su `provenance`. Una línea Mapped
queda cubierta si comparte al menos un `item_id` con alguna capacidad.

**Los 14 huecos son reales y están declarados uno a uno en `DECLARED_GAPS`**
(no es una lista de conveniencia: si aparece un hueco nuevo el script falla, y
si una capacidad los cubre en el futuro también falla hasta borrar la
declaración — hay un test para cada dirección). Todos corresponden a líneas
Mapped del inventario que **no están entre las 24 capacidades que pide el
enunciado**: desinstalar Edge (1:8, 1:19, 1:20), Widgets (2:38), Explorer
Home/Gallery (2:44), recomendaciones de Inicio (2:45), Store search (2:46),
auto-descubrimiento de carpetas (2:47), Companion apps (2:49), Razer (2:50),
Logitech (2:51), Adobe (2:52, 3:86), Brave (2:53, 3:84), Start Menu de Atlas
(2:74) y `WPFToggleHideSettingsHome` (2:75). No se inventaron IDs fuera del
enunciado para taparlos.

Las 18 capacidades sin línea Mapped propia nacen de líneas **Absent-At-Pin** del
inventario (Atlas sobre todo, y la limpieza de disco). Se informa como cifra,
no como fallo: no son cobertura, son catálogo nuevo.

## Tests

- **xUnit (CI, Windows)**: `tests/Evo.Catalog.Tests/Wave1CatalogTests.cs`
  (`TestWave1Catalog_LoadsAndValidates` + `…IdsAreUniqueAndActionsAreSupported`)
  y `tests/Evo.Engine.Tests/Wave1EngineTests.cs`
  (`TestWave1Catalog_DryRun_NoSystemMutation`,
  `TestWave1Catalog_ExecuteAndRollback_RestoresState`,
  `TestWave1Catalog_CommandCapability_UsesInjectedRunnerOnly`).
  Los dos proyectos copian `catalog/capabilities/*.json` al directorio de salida:
  los tests cargan el catálogo **real**, no un JSON de mentira.
- **pytest local**: `tests/test_paso8.py`, 114 casos, todos verdes; suite
  completa `353 passed`.

## CI

SHA final `b65f5c7`:

```
dotnet-ci     45316207443  push          success
dotnet-ci     45316213354  pull_request  success
ledger-verify 45316207352  push          success

dotnet (windows-2025)   success
dotnet (windows-11-arm) success
```

`ci-report` (run `45316213354`), idéntico en los dos runners:

```
Evo.Catalog.Tests:   total=34 passed=34 failed=0
Evo.Core.Tests:      total=19 passed=19 failed=0
Evo.Detection.Tests: total=35 passed=35 failed=0
Evo.Engine.Tests:    total=21 passed=21 failed=0
total=109 passed=109 failed=0
```

`ledger-verify` run `45316207352`: `353 passed` · `pytest_exit=0`.

Con el informe ya escrito (`a32e1ea`): `dotnet-ci` run `45316592984` success
(windows-2025 y windows-11-arm, `total=109 passed=109 failed=0` en los dos) y
`ledger-verify` run `45316586774` success (`353 passed`, `pytest_exit=0`).

**Ultimo commit medido: `1702807`** — `dotnet-ci` run `45318689893` **success**
en `windows-2025` y en `windows-11-arm` (`total=109 passed=109 failed=0` en los
dos) y `ledger-verify` run `45318683544` **success** (`353 passed`,
`pytest_exit=0`).

Los commits posteriores a `b65f5c7` son **solo documentacion** (`a32e1ea`,
`6260f92`, `1702807`) y este mismo: el codigo, los JSON del catalogo y los tests
medidos son byte a byte los de `b65f5c7`. Las cifras se replicaron en las tres
ejecuciones (`45316213354`, `45316592984`, `45318689893`).

PR #1: `state=open`, `draft=true`, cuerpo de 13 192 caracteres con la seccion
del paso 8. Inventario sin tocar: `sha256 = 0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709`.

## Incidencias reales detectadas por CI

1. **Primer run (`450aee8`) en rojo**: `TestWave1Catalog_ExecuteAndRollback_RestoresState`
   esperaba `AllowTelemetry == 1` y el catálogo escribe `0` (el 1 es del valor
   `EnableActivityFeed` que se había mirado de la fila de al lado). Expectativa
   errónea, no bug del motor → corregida en `b65f5c7`. Es el tercer fallo de test
   de la serie que resulta ser una expectativa mal escrita.
2. El primer borrador de `verify_catalog_coverage.py` daba por buenas todas las
   líneas porque la regex de `item_id` capturaba `winutil` a secas (el grupo
   `(winutil|atlas):` sin `?:` convierte la alternancia en grupo de captura y el
   prefijo del `item_id` se perdía). Corregido a `(?:…)`: la cobertura real es
   12/26, no 26/26. Sin ese fallo el informe habría declarado cobertura total.

## Desviaciones

1. **`/ResetBase` fuera.** WinUtil `WPFTweaksDiskCleanup` ejecuta
   `DISM /StartComponentCleanup /ResetBase`. EVO declara solo
   `/StartComponentCleanup` (como Atlas): con `/ResetBase` las actualizaciones
   instaladas dejan de poder desinstalarse y el punto de restauración no lo
   arregla. Consecuencia: la capacidad limpia menos de lo que limpia WinUtil.
2. **`cleanup.*` con `Restore=None` y riesgo Safe**: el enunciado permite
   `None ≈ Safe`, pero el efecto es irreversible de verdad. Se declara así
   y `Confirmation=None`, con el texto de la capacidad diciendo "irreversible".
   Las que tocan el sistema de ficheros del usuario (`temp.user`) son `User`.
3. **`debloat.start.websearch` no copia `BingSearchEnabled`.** En el pin,
   `WPFToggleBingSearch` aplica `BingSearchEnabled=1` (activar), lo contrario de
   lo que anuncia su etiqueta. Se usa la política de Atlas
   (`DisableSearchBoxSuggestions=1` y las 9 restantes) y se deja constancia en la
   `provenance`.
4. **`privacy.activity.history` sigue a Atlas, no a WinUtil**:
   `WPFTweaksActivity` escribe `EnableActivityFeed=1` (activar el feed) y solo
   desactiva publicación y subida. Atlas escribe `0`. Discrepancia anotada.
5. **`privacy.diagnostic.data.level` absorbe la línea 117.** Esa línea del
   inventario Mapped a `WPFTweaksTelemetry:registry:1`, que es
   `TailoredExperiencesWithDiagnosticDataEnabled=0`, no `AllowTelemetry`. Por eso
   la capacidad añade esa pareja de valores (acciones 6 y 7) además de
   `AllowTelemetry`, y `privacy.advertising.id` deja de reclamar esa línea (no la
   respalda: la suya es Absent-At-Pin).
6. **`debloat.windows.ai` limitada a build ≥ 22631** (Recall y el paquete Copilot
   no existen en 19045).
7. **`privacy.telemetry.dmwappush` con una sola fuente** y de una superficie que
   el ledger no extrae (script de ISO de WinUtil). Marcado **NO VERIFICADO** como
   tweak de catálogo en la propia `provenance`.

## Supuestos

- `privacy.ceip.tasks` deshabilita 5 tareas; si alguna no existe en un build,
  `TaskActionExecutor` la marca como fallida y el motor dispara rollback. Se
  declara Medium + RestorePoint por eso, no por el daño intrínseco.
- Los valores `String` del catálogo (`Value=Deny`, `SettingsPageVisibility`,
  `ExtensionInstallBlocklist\1`) se serializan tal cual; el fake registra
  `String` y el ejecutor de registro real usa `REG_SZ`.
- `cleanmgr /sagerun:64` con `ignoreExitCode=true`: `cleanmgr` devuelve códigos
  no documentados y su fallo no cambia el estado que EVO declara.

## Riesgos

- La cobertura del ledger es 12/26 en secciones 1-3. Cerrarla exige capacidades
  nuevas (Edge remove, Widgets, Explorer, Razer/Logitech/Adobe/Brave, Start Menu)
  que hoy no existen: es trabajo de la oleada 2, no un defecto del catálogo.
- `debloat.appx.consumer` y `debloat.cortana.remove` usan `powershell.exe` con
  un script embebido: el motor no puede deshacerlo (solo restaura el punto), y
  la salida del script se ignora. La verificación real de que el paquete
  desapareció queda para la validación en VM.
- `/StartComponentCleanup` tarda minutos y puede fallar con `ERROR_ACCESS_DENIED`
  si hay actualizaciones pendientes: el comando devuelve el código, pero EVO no
  lo traduce a un mensaje de usuario todavía.
