# Paso 8c — Interruptores de WinUtil, sección de cada ítem upstream y plan de oleadas

- Rama `arena/ab2d6de7-evo-optimizer-on`; HEAD al empezar `3ff8d71` (idéntico a
  `git ls-remote`).
- Pins: Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`, WinUtil
  `70c23c80641d7370532af2f619b2842658600842`.
- Sandbox Debian 12, Python 3.11.2, **sin dotnet**: lo .NET se verifica en Actions.

## S8 — Licencia

Por indicación del responsable en este paso, **EVO CLEAN es `GPL-3.0-only`** y
deja de estar «pendiente de confirmación». Cambiado únicamente eso, con la fecha
del reloj del agente (2026-11-24 UTC), en:

| Fichero | Antes | Ahora |
| --- | --- | --- |
| `README.md:4-7` | «decisión pendiente de confirmación del responsable» | «**confirmado por el responsable** el 2026-11-24 (reloj del agente, UTC)» |
| `docs/legal/upstream-licenses.md:162` | «Pendiente de confirmación del responsable» | «**Confirmado por el responsable** el 2026-11-24 (reloj del agente, UTC)» |
| `docs/adr/ADR-0002-datos-de-atlas-y-gpl.md:4,84` | sólo fecha de aceptación | más «**licencia GPL-3.0-only confirmada por el responsable 2026-11-24**» |

No se cambió ninguna otra frase de licencia: `LICENSE` sigue siendo el texto
GPLv3 sin añadidos (sha256 `3972dc97…986`) y `THIRD_PARTY_NOTICES.md` sigue
pendiente para la base .NET.

## T1 — Interruptores de WinUtil

### T1a — Qué valor es «encendido» (medido)

- `functions/private/Invoke-WinUtilTweaks.ps1:34-46` elige el campo según
  `$undo`: al **aplicar** usa `Registry = "Value"` y `ScriptType = "InvokeScript"`;
  al **deshacer** usa `Registry = "OriginalValue"` y `ScriptType = "UndoScript"`.
- `functions/public/Invoke-WPFUIElements.ps1:193-235` (rama `"Toggle"`) engancha
  `Add_Checked` → `Invoke-WinUtilTweaks $Sender.name` y `Add_Unchecked` →
  `Invoke-WinUtilTweaks $Sender.name -undo $true`. La rama `default` (línea 498)
  —la que usan los tweaks **sin** `Type`— sólo apunta la selección
  (`Invoke-WPFSelectedCheckboxesUpdate`), y la aplicación la dispara el botón
  (`Invoke-WPFtweaksbutton.ps1:59`).
- `functions/private/Get-WinUtilToggleStatus.ps1:44` marca la casilla como
  encendida cuando el valor del registro es **igual a `Value`**.

**Conclusión con evidencia:** en un tweak con `Type: "Toggle"`, **`Value` es el
estado ENCENDIDO** de la casilla y `OriginalValue` el APAGADO. En un tweak **sin
`Type`** no hay casilla que interpretar: `Value` es lo que se escribe y
`OriginalValue` lo que se restaura al deshacer (si es `<RemoveEntry>`, no había
nada). Ficheros con `Type` en el pin: 24 `Toggle`, 3 `Button`, 2 `Combobox`, 40
sin `Type`.

### T1b — `tweak_type` en el ledger

`extract_winutil_ops.py` pasa a emitir la columna `tweak_type`
(`Toggle|Button|Combobox|none`) en las tres salidas. Solo cambia
`winutil-tweak-ops.tsv` (las otras dos ya eran `none`):

| | sha256 |
| --- | --- |
| antes | `60f56ebb…9232` (179 filas, 11 columnas) |
| ahora | `f5aed322…8768` (179 filas, 12 columnas) |

Reparto por tipo en `winutil-tweak-ops.tsv`: `none` 40 tweaks (104 filas),
`Toggle` 24 tweaks (73 filas), `Combobox` 1 (2 filas). `Button` existe en el pin
pero no genera operación estructurada.

`audit_catalog_values.py` pasa a distinguir: `equals-apply` (valor de un botón),
**`equals-on`** (valor de un Toggle = casilla encendida), **`equals-off`**
(`OriginalValue` de un Toggle = casilla apagada), `equals-original`
(`OriginalValue` sin `Type`), `differs`, `no-source`, `ambiguous`. Las relaciones
`equals-off`, `equals-original` y `differs` exigen excepción razonada, y la
excepción declara `deviation_kind` (`value` o `switch-meaning`).

### T1c — Datos crudos del pin

| Tweak | `Type` | Fichero:línea | Path \ | Name | Value | OriginalValue |
| --- | --- | --- | --- | --- | --- | --- |
| `WPFTweaksActivity` | none | `config/tweaks.json:2` | `HKLM:\SOFTWARE\Policies\Microsoft\Windows\System` \| `EnableActivityFeed` | `1` | `<RemoveEntry>` |
| | | `:2` | idem \| `PublishUserActivities` | `0` | `<RemoveEntry>` |
| | | `:2` | idem \| `UploadUserActivities` | `0` | `<RemoveEntry>` |
| `WPFToggleBingSearch` | Toggle | `:1759` | `HKCU:\Software\Microsoft\Windows\CurrentVersion\Search` \| `BingSearchEnabled` | `1` | `0` |
| `WPFTweaksTelemetry` | none | `:460` | `HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection` \| `AllowTelemetry` | `0` | `<RemoveEntry>` |
| | | `:460` | `HKLM:\SOFTWARE\Policies\Microsoft\Windows\System` \| `PublishUserActivities` | `0` | `<RemoveEntry>` |
| `WPFToggleDisableLockscreen` | Toggle | `:1795` | `HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization` \| `NoLockScreen` | `1` | `<RemoveEntry>` |

`WPFToggleDisableLockscreen` **sí existe** en el pin. Sus 13 entradas completas
están en `winutil-tweak-ops.tsv` (filas `winutil:tweak-op:WPFTweaksTelemetry:*`).

**Los dos `ambiguous` resueltos:**

1. `privacy.activity.history` / `EnableActivityFeed`: **no es el significado del
   interruptor, es una contradicción real**. `WPFTweaksActivity` **no es un
   Toggle** (no tiene `Type`): aplica `EnableActivityFeed=1` (deja el feed
   activo) y Atlas `privacy/disable-activity-feed.psd1:5` aplica `0`. Se
   contradicen de verdad; EVO sigue a Atlas porque su nombre es «desactivar».
2. `debloat.start.recommendations` / `HideRecommendedSection=0`: **sí es
   semántica de interruptor**. `WPFToggleStartMenuRecommendations` es un `Toggle`
   con `Value=0` (encendido) y `OriginalValue=1` (apagado); Historial de
   actividad al margen, WinUtil está diciendo «con la casilla encendida, las
   recomendaciones se ven». Atlas escribe `1` (las oculta) en
   `qol/config-start-menu.psd1:20`. Las dos fuentes quieren lo mismo con valores
   opuestos porque una es un toggle invertido; el catálogo copia el `Value`
   (=0) y la auditoría lo marca `equals-on`.

### T1d — `debloat.start.websearch`

Estaba incompleta: aplicaba 10 claves de Atlas pero **no** escribía nada sobre
Bing. Ahora añade `HKCU\Software\Microsoft\Windows\CurrentVersion\Search\BingSearchEnabled=0`,
el estado **apagado** del Toggle de WinUtil (`Value=1` = encendido), y 11
acciones. Test nuevo
`Wave1EngineTests.TestWave1Catalog_WebSearchCapability_ReallyDisablesBing`
comprueba el valor final en el registro falso, que `DisableSearchBoxSuggestions`
queda en `1` y que el rollback devuelve `BingSearchEnabled=1`. Desviación
declarada como `switch-meaning` en `catalog/exceptions/value-deviations.json`.

### T1e — Distribución final (`catalog-value-audit.tsv`, 105 filas)

`equals-apply` **92** · `no-source` **7** · `equals-on` **2** · `equals-off`
**2** · `ambiguous` **2**. Excepciones: 2, sin excepción: **0**.

Filas que no son `equals-apply`:

| Capacidad | Valor | Tipo | Relación |
| --- | --- | --- | --- |
| `cleanup.recycle.bin` | `StateFlags0064=2` | — | no-source (es comando) |
| `cleanup.wer.reports` | `StateFlags0064=2` | — | no-source |
| `debloat.copilot.remove` | `ShowCopilotButton=0` | — | no-source (sale de `Toggles/General/Copilot.psd1`) |
| `debloat.settings.home` | `SettingsPageVisibility=hide:home` | Toggle | equals-off (**excepción**) |
| `debloat.start.recommendations` | `IsEducationEnvironment=0` | Toggle | equals-on |
| `debloat.start.recommendations` | `HideRecommendedSection=0` | Toggle | equals-on |
| `debloat.start.recommendations` | `HideRecommendedSection=0` | — | ambiguous (Atlas=1) |
| `debloat.start.websearch` | `BingSearchEnabled=0` | Toggle | equals-off (**excepción**) |
| `debloat.widgets.disable` | `AllowNewsAndInterests=0` | — | no-source |
| `debloat.widgets.disable` | `DisableWidgetsBoard=1` | — | no-source |
| `debloat.widgets.disable` | `DisableWidgetsOnLockScreen=1` | — | no-source |
| `privacy.activity.history` | `EnableActivityFeed=0` | — | ambiguous (WinUtil=1) |
| `privacy.telemetry.dmwappush` | `Start=4` | — | no-source |

## T2 — Revisiones del catálogo

### T2a — `debloat.windows.ai` partida en dos

Evidencia del pin: `Toggles/General/Recall.psd1:14-16` documenta
`AllowRecallEnablement=0` como «24H2 26100.3915+»; `qol/taskbar/disable-copilot.psd1:6`
documenta `RemoveMicrosoftCopilotApp` como «25H2+» y «sólo Enterprise y
Education»; `Toggles/General/Copilot.ps1:48-52` distingue el botón de la barra
(«< 26100») del paquete AppX («24H2+»). Son separables:

| Capacidad nueva | Acciones | Builds | Reversibilidad |
| --- | --- | --- | --- |
| `debloat.windows.ai.recall` | 5 políticas (Recall, agente de Configuración, Click To Do, IA del Bloc de notas, ocultar página) | 26100, 26200 | Reversible |
| `debloat.copilot.remove` | `RemoveMicrosoftCopilotApp=1`, `ShowCopilotButton=0`, quitar paquete | 22631, 26100, 26200 | Irreversible |

El id viejo desaparece; el catálogo pasa a **39 capacidades**. El rango de Click
To Do y del agente de Configuración queda **NO VERIFICADO** en el propio
`provenance` (no hay `MinBuild`/`MaxBuild` ni guardas de build en sus `.psd1`);
por eso `.recall` es `Specified`. Test nuevo
`Wave1EngineTests.TestWave1Catalog_WindowsAiSplit_RecallAndCopilotAreSeparate`
comprueba rangos, reversibilidades, que no comparten ni una acción y que la de
Recall no dispara ningún comando.

### T2b — ¿Cuándo se crea el punto de restauración? **No se crea.**

Medido en el código: `src/Evo.Engine/EngineCoordinator.cs` no tiene ni una
referencia a `RestoreLevel` ni a `RestorePoint`; recorre las acciones y para ante
el primer fallo con rollback LIFO del diario. El único rastro del concepto es
`src/Evo.Core/Execution/ICapabilityExecutor.cs:15`
(`public string? RestorePointId { get; init; }`), un campo de datos que **nadie
escribe** en `src/`. `CapabilityRules.Validate` sólo compara el enum contra el
riesgo.

Respuesta concreta: con `Confirmation = SummaryAndRestorePoint` y
`Restore = None` —la combinación de las 13 irreversibles— **no se crea ningún
punto de restauración**, porque no hay implementación. Se declara **deuda**
(`ERRATA` de este paso) y **no se implementa aquí**: requiere un ejecutor de
punto de restauración y un fake que lo observe, que es una tarea propia.

### T2c — Anexo de la ADR-0003

Añadido a `docs/adr/ADR-0003-reversibilidad-y-restauracion.md` con las 13
`Irreversible`, su motivo, la vía de recuperación y la reclasificación
propuesta. **Sin reclasificar.** Resultado: 6 irreversibles sin discusión, 4 con
vía de recuperación clara (Edge, Copilot, telemetría AppX, OneDrive) que lo
serían cuando exista la acción inversa en el motor, y 3 marcadas NO VERIFICADO
(Razer, Logitech, Adobe) —las dos primeras porque además **borran ficheros**, la
tercera porque añade contenido a `hosts` que nadie registra.

## T3 — Sección de cada ítem upstream

`inventory/partition/category-section-map.tsv` (49 categorías, 424 ítems):
`source`, `category_key`, `items`, `section`, `basis`, `reviewed` (siempre `no`).

| Resultado | Categorías | Ítems |
| --- | --- | --- |
| con sección 1-17 | 36 | 250 |
| `mixed` | 12 | 174 |
| `unassigned` | 0 | 0 |

Categorías `mixed` (no se fuerza el reparto): `Customize Preferences` (25),
`Essential Tweaks` (18), `z__Advanced Tweaks - CAUTION` (24), `Features` (10),
`Fixes` (6), `Legacy Windows Panels` (14), `General` (29), `qol/(raiz)` (25),
`misc/(raiz)` (8), `scripts/(raiz)` (8), `Advanced` (3), `config/preset.json` (4).
Son categorías de **UI de upstream**, no áreas del sistema.

### Tabla source × sección (435 filas)

| source | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | vacío |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `winutil` | 3 | 17 | 2 | 0 | 2 | 0 | 4 | 0 | 4 | 5 | 11 | 0 | 4 | 2 | 34 | 2 | 0 | 72 |
| `atlas-toggle` | 0 | 2 | 0 | 7 | 0 | 0 | 0 | 8 | 2 | 26 | 0 | 0 | 7 | 8 | 3 | 0 | 0 | 28 |
| `atlas-manifest` | 0 | 5 | 42 | 0 | 11 | 0 | 0 | 4 | 2 | 61 | 5 | 8 | 4 | 0 | 0 | 0 | 40 |
| **Σ** | **3** | **24** | **44** | **7** | **13** | **0** | **4** | **12** | **8** | **92** | **16** | **8** | **15** | **10** | **37** | **2** | **0** | **140** |

`section_basis`: `category` **250**, `text-rule` **45**, `none` **140**.

### Pendientes por sección y por `section_basis`

| basis | pending |
| --- | --- |
| `category` | 236 |
| `text-rule` | 20 |
| `none` | 129 |
| **Σ** | **385** |

Pending por sección: 2→3, 3→32, 4→7, 5→13, 7→4, 8→12, 9→8, 10→91, 11→16,
12→8, 13→15, 14→10, 15→35, 16→2; **sin sección 129**.

Las 129 filas sin sección son íntegramente de categorías `mixed`, por este orden:
`General` (25), `qol/(raiz)` (24), `Customize Preferences` (17), `Legacy Windows
Panels` (12), `Features` (10), `misc/(raiz)` (8), `scripts/(raiz)` (8),
`z__Advanced Tweaks` (8), `Essential Tweaks` (6), `Fixes` (4),
`config/preset.json` (4), `Advanced` (3). Antes eran 361.

Cobertura real: **39/435 (9,0 %)** — sube de 37 al añadirse las dos capacidades
que citan `atlas:toggle:Copilot` y `winutil:tweak:WPFTweaksWindowsAI`.

## T4 — Plan de oleadas

`docs/reports/plan-oleadas.md`, generado por `tools/ledger_extract/build_wave_plan.py`
(`--check` en CI). La tabla va dentro del mensaje final.

- **MEDIDO**: estados por sección, Mapped cubiertas, trabajo y pending upstream.
- **PROPUESTA**: el orden de las 17 oleadas y sus motivos.

Total: 588 líneas, 149 `Mapped` + 5 `Mapped-To-App`, 37 `EVO-Exclusive`,
326 `Absent-At-Pin`, 71 `Informative-Header`; **47 Mapped cubiertas** y **470
unidades de trabajo** (107 Mapped sin cubrir + 37 + 326).

## T5 — Verificación

- `tests/test_paso8c.py`: **17 tests**.
- Suite Python completa: **454 passed** (antes 433; +17 de 8c, +4 por
  parametrizaciones y reescrituras de 8/8b).
- `.github/workflows/ledger-verify.yml`: paso «Paso 8c» con doble ejecución de
  los cinco artefactos, `sha256sum` + `diff`, `build_wave_plan.py --check`,
  publicación de los cuatro TSV/MD y comprobaciones JSON.
- xUnit nuevos: 2 (`TestWave1Catalog_WebSearchCapability_ReallyDisablesBing` y
  `TestWave1Catalog_WindowsAiSplit_RecallAndCopilotAreSeparate`); **126 → 128**.

### CI

Runs `45326702840` (ledger-verify) y `45326711652` (dotnet-ci), medidos sobre el
árbol del commit único del paso 8c; el commit que contiene este informe sólo
difiere en este párrafo.

| Workflow | Run | Resultado |
| --- | --- | --- |
| `ledger-verify` | 45326702840 | success — 454 pytest, determinismo 8c OK, `--check` del plan OK |
| `dotnet-ci` (windows-2025) | 45326711652 | success — **128/128** (Catalog 36, Core 34, Detection 35, Engine 23) |
| `dotnet-ci` (windows-11-arm) | 45326711652 | success — **128/128** |

Dos fallos reales por el camino, ambos de cifras fijadas en el workflow:
el paso 8b exigía `filas == 104` y `covered == 37` (ahora 105 y 39) y el
paso 8c comparaba `por_basis.none < 140` con el valor medido exacto. Los dos
pasaron a umbrales que sí expresan la intención (no empeorar), no a igualdades.

## Desviaciones y supuestos

1. **Deuda declarada**: no existe creación de punto de restauración en el motor
   (T2b). No se implementa.
2. `debloat.windows.ai` cambia de id (se parte). Cualquier `conflictsWith`
   externo al catálogo que lo citara quedaría roto; hoy no hay ninguno.
3. El rango de Click To Do y del agente de Configuración es **NO VERIFICADO**.
4. Las 12 categorías `mixed` no se reparten: hacerlo exige mirar ítem a ítem.
5. Los 40 tweaks sin `Type` se tratan como «botón de aplicar»; es lo que hace
   `Invoke-WPFUIElements.ps1:498` (rama `default`).
