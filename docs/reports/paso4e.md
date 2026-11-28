# Paso 4e — Manifiesto de Atlas, verificación de WinUtil y borrador de conciliación

Fecha: 2026-11-24 · Rama `arena/ab2d6de7-evo-optimizer-on` · HEAD de partida `edffa74`.
Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f` · WinUtil `70c23c80641d7370532af2f619b2842658600842`.

---

## T0 — Evidencia

### b) Estado y hashes

```
$ git rev-parse HEAD
edffa74b03db5e0e891a43632560841d2811f041
$ git ls-remote origin refs/heads/arena/ab2d6de7-evo-optimizer-on
edffa74b03db5e0e891a43632560841d2811f041	refs/heads/arena/ab2d6de7-evo-optimizer-on
$ sha256sum docs/requirements/INVENTARIO_USUARIO.md
0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709
```

El run de CI y su `ci-report` se listan al final (T4).

### a) Tabla de 39 filas

Está impresa en el mensaje de respuesta (obligatoria). Reproducible con:

```
python3 -c "import csv;[print(r['item'],r['winutil_ficheros'],r['atlas_ficheros']) for r in csv.DictReader(open('docs/inventory-recon/seccion16-17-probe.tsv'),delimiter='\t')]"
```

9 dudosos: items 6, 9, 18, 19, 20, 30, 35, 36, 38.

---

## T1 — Verificación de las operaciones de WinUtil

Comando independiente (json puro, **no** el extractor):

```
python3 - <<'EOF'
import json, collections
d = json.loads(open('config/tweaks.json', encoding='utf-8-sig').read(), strict=False)
c = collections.Counter(k for v in d.values() for k in v)
tot = collections.Counter()
for v in d.values():
    for k, val in v.items():
        if isinstance(val, list): tot[k] += len(val)
EOF
```

### 1. Claves de nivel 2 en los 69 tweaks (mayúsculas respetadas)

| clave | tweaks |
|---|---:|
| `Content` | 69 |
| `category` | 69 |
| `panel` | 69 |
| `link` | 69 |
| `Description` | 66 |
| `registry` | 50 |
| `Type` | 29 |
| `InvokeScript` | 27 |
| `UndoScript` | 22 |
| `service` | 4 |
| `ComboItems` | 2 |
| `ButtonWidth` | 2 |
| `Checked` | 1 |
| `ComboDescriptions` | 1 |

No existen `ScheduledTask`, `scheduledtask` ni `appx` en `tweaks.json`.

### 2. Entradas en bruto (suma de `len()`)

`registry` **121** · `InvokeScript` **27** · `UndoScript` **22** · `service` **9**.

### 3. Comparación con `winutil-tweak-ops.tsv`

| clave | JSON en bruto | TSV | coincide |
|---|---:|---:|:--:|
| registry | 121 | 121 | ✔ |
| service | 9 | 9 | ✔ |
| InvokeScript | 27 | 27 (`direction=apply`) | ✔ |
| UndoScript | 22 | 22 (`direction=undo`) | ✔ |
| scheduledtask | **0** | 0 | ✔ |
| appx | **0** | 0 | ✔ |

**No hay infraconteo.** El extractor no fallaba: el formato es el que es. Dos
matices de nomenclatura, ya documentados en el TSV: `kind=script` con
`direction=apply|undo` (no dos `kind` distintos), y `scheduledtask`/`appx` a 0
porque esas claves no existen.

### 4. Control de `feature.json` y `appx.json`

| fichero | ítems | campos con lista | filas del TSV | explicación |
|---|---:|---|---:|---|
| `feature.json` | 33 | `feature` 9 ítems → **13** nombres; `InvokeScript` 21 ítems → **22** cadenas | **31** | 13 + 22 − 4 ítems con `InvokeScript` vacío (`[]`) = 31 |
| `appx.json` | 34 | ninguna lista; 34 `PackageId` | **34** | una fila `appx-package` por ítem |

Los 3 ítems con `InvokeScript: []` (`WPFFeaturesdotnet`,
`WPFFeatureslegacymedia`, `WPFFeaturewsl`) aportan solo sus `feature` (0 scripts).
Los **10** que aportan **0 filas** son los que solo declaran `function`:
`WPFFixesNTPPool`, `WPFFeatureInstall`, `WPFPanelAutologin`, `WPFFixesUpdate`,
`WPFFixesNetwork`, `WPFPanelDISM`, `WPFFixesWinget`, `WPFWinUtilInstallPSProfile`,
`WPFWinUtilUninstallPSProfile`, `WPFWinUtilSSHServer`. Ahí la operación vive en
una función de PowerShell, no en el JSON, y **no se inventa**:
**NO VERIFICADO** su contenido.

### 5. Los 4 tweaks sin estructura ni script

| tweak | campos literales | qué es |
|---|---|---|
| `WPFAddUltPerf` | `Content: "Ultimate Performance Profile - Enable"`, `Type: Button`, `category: "Performance Plans - NOT FOR LAPTOPS"` | botón; sin `Description` ni datos |
| `WPFRemoveUltPerf` | `Content: "Ultimate Performance Profile - Disable"`, `Type: Button`, misma categoría | botón; sin `Description` ni datos |
| `WPFOOSUbutton` | `Content: "O&O ShutUp10++ - Run"`, `Type: Button`, `Description: "Downloads O&O ShutUp10++ (about 82 MB) … Nothing is installed…"` | descarga y ejecuta un `.exe` externo |
| `WPFchangedns` | `Content: "DNS - Set to:"`, `Type: Combobox`, `ComboItems: "Default DHCP Fastest Google Cloudflare …"` | selector; los valores viven en el código |

Que no tengan operaciones **no es un fallo de extracción**: su acción está en el
código de WinUtil o en un binario de terceros.

---

## T2 — Manifiesto y enlace toggle → `.psd1`

### 1. ¿Cuántos toggles llegan al puente? ¿Qué es el «52»?

`atlas-toggle-bridge.tsv` tiene 92 filas y **52 `toggle_id` distintos**;
`atlas-toggle-effects.tsv` también 52. **El 52 son toggles, no rutas** (las
rutas son 52 `resolved_in` distintas, coincidencia numérica).

De los **91** toggles del catálogo, **39 no aparecen** en el puente. Todos
tienen en común: **`machineAction` vacío en todos sus estados**. Tienen
`work.registry` (contador), `work.user` o `work.action`:

`Animation` (2 estados, registry 2, user 2) · `AppIconThumbnail` (2) ·
`AppStoreArchiving` (2) · `AutomaticFolderDiscovery` (2) · `AutomaticUpdates` (2) ·
`BackgroundApps` (2) · `ClickToDo` (2) · `CompactView` (2) · `ConfigVBS` (1,
solo `action`) · `CpuIdleContextMenu` (2) · `DeliveryOptimisation` (2) ·
`EdgeSwipe` (2) · `ExtractContextMenu` (2) · `FaultTolerantHeap` (2) ·
`FixExplorerRuntimeError` (1) · `Gallery` (2) · `GiveAccessToMenu` (2) ·
`HideAppBrowserControl` (2) · `Home` (2) · `InstallSoftware` (1) ·
`KeyboardShortcuts` (2) · `ModernBatteryFlyout` (2) · `ModernDateTime` (2) ·
`ModernVolumeFlyout` (2) · `NetworkNavigationPane` (2) · `OldContextMenu` (2) ·
`PauseUpdates` (2) · `QuickAccess` (2) · `Recall` (2) · `RemovableDrivesInSidebar` (2) ·
`RemovePythonStorePrompt` (1) · `RestartExplorer` (1) · `SendToContextMenu` (1) ·
`ShortcutIcon` (3) · `ShortcutText` (2) · `SnapLayouts` (2) ·
`UpdateNotifications` (2) · `VerboseMessages` (2) · `WindowsSpotlight` (2).

### 2. Esquema del manifiesto

`docs/inventory-recon/atlas-manifest-schema.md`. Resumen: tres formas
(`Categories[].Tweaks` con slug relativo, `Standalone` con slug completo,
`Disabled` con `Slug`+`Reason`); el contrato lo declara
`Manifest.ps1:10-13`; la ruta se compone en `Manifest.ps1:181`
(`(($Slug -replace '/','\') + '.psd1')` bajo `Scripts\Tweaks\`); la carga real
es `Invoke-TweaksPhase.ps1:130` → `Data.ps1:16`
(`Import-PowerShellDataFile`).

### 3. `atlas-manifest.tsv`

182 filas: 174 `Categories` + 3 `Standalone` + 5 `Disabled`; 177 habilitadas,
5 deshabilitadas; 0 duplicados; 0 ids sin `.psd1`.

**Fallo corregido del 4d.** El 4d informó «108 .psd1 en el manifiesto». Era
falso: el regex `Tweaks\s*=\s*@\((.*?)\)` cortaba en el primer `)` **de la
propia lista** (`# Initialize-NewUser at first sign-in (interactive shell COM)`
dentro de `qol`, y otros paréntesis en los comentarios). Al ir en `qol` tras
`privacy`, se perdían 77 slugs y los que faltaban en `networking`/`performance`
eran 1 y 1. Cifra correcta: **182**. El `.psd1` nº 183 es el propio
`tweaks.manifest.psd1`, que no se declara a sí mismo.

### 4. Cruces

| cruce | resultado |
|---|---|
| ids de manifiesto ∩ `toggle_id` del catálogo | **0** (ni exacto ni normalizado) |
| ids de manifiesto ∩ nombres de las 74 funciones `machineAction` | **0** |
| argumentos de esas 74 funciones que reciban un slug/nombre de tweak | **0** (`param($Toggle)`, sin slug) |
| ids de manifiesto sin `.psd1` | **0** |
| `.psd1` sin entrada de manifiesto | **1** (`tweaks.manifest.psd1`), no cuenta |
| `.psd1` sin ninguna referencia textual | **0** (con el parser corregido) |
| menciones de ids de manifiesto fuera del manifiesto | 34, en 8 ficheros: `tests/Atlas.WindowsTransition.Tests.ps1` 10, `docs/catalog/tweaks.md` 8, el propio manifiesto 8, `docs/architecture.md` 3, `Tweaks/README.md` 2, `docs/preparation.md` 1, `docs/windows-transition.md` 1, `tests/Atlas.InstallOrchestrator.Tests.ps1` 1 |

El aplicador no recibe el nombre del tweak: recibe un objeto `$Toggle`
(`Invoke-TweaksPhase.ps1:119-148`, `Invoke.ps1:238`). La ruta
`id → .psd1 → claves` pasa por el **manifiesto**, no por el catálogo.

### 5. Conclusión medida

- Un toggle del catálogo **con `machineAction`** (52 de 91) llega a un script
  `.ps1` por nombre de función → **(a) por función directa**.
- Un toggle **sin `machineAction`** (39 de 91) declara solo el **contador**
  `work.registry`; sus claves están en los `.psd1`, que se aplican por el
  **manifiesto** → **(b) por manifiesto + `.psd1`**, pero **el vínculo
  catálogo → id de manifiesto no está declarado en el pin**: 0 coincidencias.
- Por tanto: **(d) NO VERIFICADO** cómo se empareja un toggle sin
  `machineAction` con su `.psd1`. No se afirma equivalencia alguna.

---

## T3 — Borrador de conciliación

`inventory/ledger/conciliacion-borrador.tsv` (588 filas, sha `4a18d8fc…`).
Reglas y umbrales: `docs/inventory-recon/conciliacion-reglas.md`.

```
por regla     : R1 96 · R2 65 · R3 67 · R4 360
por confianza : alta 134 · media 94 · ninguna 360
por estado    : propuesto-mapped 228 · sin-evidencia 360
por fuente    : atlas 271 · winutil 197 · general 98 · evo 22
```

Dos correcciones de las reglas, declaradas antes de mirar resultados finales:
R2 pasó de «mismos tokens» a «subcadena contigua con un token discriminante
(df ≤ 10)» porque `Install Software.` casaba con
`Razer Software Auto-Install - Disable`. Con el criterio final,
`Right-Click Menu.` sigue casando con `WPFTweaksEndTaskOnTaskbar`: es un falso
positivo **conocido y declarado**, no corregido a mano.

Ninguna celda vale `Mapped`; la columna `estado_propuesto` no toma nunca ese
valor. Comprobado en CI.

---

## T4 — Tests, CI, PR

- `pytest` → **177 passed** (161 previos + **16** nuevos de `test_paso4e.py`).
- Paso de CI `Extractores de 4e`: doble ejecución + `diff` de sha256, publicación
  en `ci-report` y aserción de 588 filas / 182 entradas / 0 `Mapped`.
- 3 tests del 4d actualizados porque dependían de la cifra errónea 108.

## Desviaciones

1. `atlas-psd1-refs.tsv` cambia: «sin ninguna referencia» pasa de 63 a **0** y
   «en el manifiesto» de 108 a 182. Era un error del 4d.
2. `atlas-toggle-effects.tsv` **no** cambia de sha (no depende del manifiesto).
3. El «52» del informe 4d estaba descrito de forma ambigua; aquí queda fijado:
   52 toggles.
4. `feature.json`: los 10 ítems con solo `function` quedan sin fila.

## Supuestos

- Un `.psd1` = una entrada de manifiesto (0 duplicados lo respalda).
- Los ids de `Standalone` y `Disabled` llevan la ruta completa; los de
  `Categories`, relativa al `Name` de la categoría (`Test-Slug`,
  `Manifest.ps1:98-118`).

## Riesgos

- **R1** R3 cita a veces una operación concreta en lugar del tweak que la
  contiene: es evidencia del objeto, no del ajuste.
- **R2** 360 líneas `sin-evidencia` significan «sin evidencia con estas reglas»,
  no «no existe».
- **R3** El vínculo catálogo ↔ manifiesto sigue sin medir.

## Preguntas abiertas

1. ¿Se acepta el mapa `wpftweaks*` → inventario del borrador para revisión?
2. ¿Hay que instrumentar los `.psd1` para cerrar el vínculo toggle → claves?
3. ¿Se confirma GPL-3.0-only para EVO CLEAN?
