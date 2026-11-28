# Paso 4d — Evidencia pendiente, efectos de Atlas y operaciones de WinUtil

Fecha: 2026-11-24 · Rama `arena/ab2d6de7-evo-optimizer-on` · HEAD de partida `d6c4b49`.
Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f` (GPL-3.0-only).
WinUtil `70c23c80641d7370532af2f619b2842658600842` (MIT).

Solo se guardan metadatos: rutas, nombres, claves, tipos, hashes y, como mucho,
valores literales cortos. **Nunca** cuerpos de función ni scripts.

---

## T0 — Evidencia que faltaba

### a) `seccion16-17-probe.tsv` — 39 filas

Comando:

```
python3 -c "import csv;[print(r['item'],r['winutil_ficheros'],r['atlas_ficheros']) \
  for r in csv.DictReader(open('docs/inventory-recon/seccion16-17-probe.tsv'),delimiter='\t')]"
```

| # | item | WinUtil | Atlas | dudoso |
|---:|---|---:|---:|:--:|
| 1 | Atlas Playbook | 0 | 19 | |
| 2 | AME Wizard | 0 | 8 | |
| 3 | TrustedInstaller Broker | 0 | 35 | |
| 4 | Install Plan | 0 | 41 | |
| 5 | Install Session | 0 | 19 | |
| 6 | Installation Phases | 3 | 143 | ✔ |
| 7 | Pre-Install | 8 | 14 | |
| 8 | Environment Phase | 0 | 3 | |
| 9 | Choices Phase | 4 | 160 | ✔ |
| 10 | Features Phase | 0 | 6 | |
| 11 | Services Phase | 0 | 3 | |
| 12 | Tweaks Phase | 0 | 10 | |
| 13 | Components Phase | 0 | 9 | |
| 14 | Software Phase | 0 | 3 | |
| 15 | Shell Refresh Phase | 0 | 28 | |
| 16 | AppX Support Phase | 0 | 18 | |
| 17 | Windows Transition | 0 | 58 | |
| 18 | ISO Creation | 3 | 38 | ✔ |
| 19 | ISO Injection | 6 | 0 | ✔ |
| 20 | Upgrade System | 0 | 1 | ✔ |
| 21 | New User Initialization | 1 | 28 | |
| 22 | Atlas Health | 0 | 21 | |
| 23 | Toggle State Persistence | 5 | 91 | |
| 24 | Package Verification | 0 | 5 | |
| 25 | Component Servicing | 1 | 61 | |
| 26 | PowerShell Module Initialization | 4 | 185 | |
| 27 | Compile.ps1 | 14 | 0 | |
| 28 | inicialización WPF | 33 | 0 | |
| 29 | Runspaces | 48 | 3 | |
| 30 | trabajos en segundo plano | 58 | 153 | ✔ |
| 31 | presets | 35 | 7 | |
| 32 | importación/exportación | 13 | 268 | |
| 33 | deshacer ajustes | 61 | 47 | |
| 34 | detección de cambios revertidos | 24 | 9 | |
| 35 | registro de ejecución | 99 | 48 | ✔ |
| 36 | creación de USB | 15 | 62 | ✔ |
| 37 | instalación de ISO | 54 | 252 | |
| 38 | actualización del programa | 116 | 535 | ✔ |
| 39 | informes de entorno | 11 | 0 | |

**9 dudosos** (no 11): items 6, 9, 18, 19, 20, 30, 35, 36, 38.

### b) Estado y hashes

```
$ git rev-parse HEAD
d6c4b4977e1132d11e149cbb0f174c03e1bf479f
$ git ls-remote origin refs/heads/arena/ab2d6de7-evo-optimizer-on
d6c4b4977e1132d11e149cbb0f174c03e1bf479f	refs/heads/arena/ab2d6de7-evo-optimizer-on
$ sha256sum docs/requirements/INVENTARIO_USUARIO.md
0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709
```

`ci-report` del run anterior (4c, `45297200475`): `git show
FETCH_HEAD:runs/45297200475-ledger-verify/meta.json` → sha del commit
`d6c4b49`, `determinismo 4c: OK`. El run del 4d se lista al final.

### c) Discrepancias explicadas

**1. 909 vs 985 funciones en `Scripts/`.** No era una pérdida de 60.

```
$ python3 -c "...re.findall(r'^\s*function\s+[\w-]+', ...)"   # .ps1 de Scripts/
909                       # conteo bruto del paso 3b
$ python3 tools/ledger_extract/extract_atlas_functions.py --json
"scripts_only": 984       # 908 .ps1 + 76 .psm1
```

La cifra del 3b (909) es el **conteo bruto de líneas `function`** en los 169
`.ps1` de `Scripts/`; la del 4c (985 → ahora 984) es el **ledger con parser**,
que además incluye los `.psm1`. Desglose exacto: 908 en `.ps1` + 76 en `.psm1`
= 984. Las 16 anidadas ya estaban en ambos conteos (el regex bruto también las
ve). La diferencia de 1 entre 909 y 908 es la frase `function definitions`
dentro de un bloque `<# ... #>` de `Atlas.Toggles/Domain/Definition.ps1:104`,
que el regex bruto contaba como definición.

**Corrección real del parser (4d).** Dos fallos del 4c, ya arreglados:

- `function script:Foo` / `function global:Foo` se registraban con nombre
  `script` / `global` (6 casos, todos en `tests/`). Ahora se descarta el
  calificador de ámbito.
- Una frase `function definitions` en un comentario de bloque contaba como
  definición. Ahora se ignoran los bloques `<# ... #>`.

Total de funciones: **1 563 → 1 562**; `product` 1 173 → **1 172**;
nombres repetidos 117 → **118**. El bridge no cambia (sha idéntico).

**2. 173 estados vs 94.** Cuentan cosas distintas:

| cifra | qué cuenta | comando |
|---:|---|---|
| **173** | objetos `states[]` del catálogo (`catalog.json`), todos | `len([s for t in d['toggles'] for s in t['states']])` |
| **94** | pares `(toggle, estado)` con `work.registry > 0` | filas de `atlas-toggle-ops.tsv` |

De los 173 estados, **79** tienen `work.registry = 0` y no generan ninguna
operación; los 94 restantes suman las 303 operaciones (1 a 15 por estado). No
es una discrepancia: es «todos los estados» frente a «estados con trabajo de
registro».

**3. 408 vs 403.** 408 operaciones en `atlas-tweak-ops.tsv`, 403 claves
distintas tras normalizar:

- **4 claves repetidas** literalmente entre ficheros (`SubscribedContent-353694Enabled`,
  `-353696Enabled`, `-338387Enabled`, `RotatingLockScreenOverlayEnabled`, las
  cuatro bajo `ContentDeliveryManager`): 408 − 4 = 404;
- **1 más** por normalización a minúsculas en el cruce (`…\CLSID\…` vs
  `…\clsid\…`): 404 → **403**.

Las 5 «restantes» no se pierden: son cuatro duplicados de declaración y una
diferencia de caja.

**4. `work.registry` = 303.** No es un entero: es un **contador por estado** que
suma 303. Tres ejemplos reales, recortados a `work`:

```json
{"name":"AppStoreArchiving","state":"Disable","work":{"registry":1,"machineAction":null}}
{"name":"BackgroundApps","state":"Disable","work":{"registry":2,"machineAction":null}}
{"name":"Animation","state":"Disable","work":{"registry":12,"machineAction":null}}
```

Distribución: 0→79, 1→51, 2→14, 12→4, 15→3, 6→2, 13→2, 7→3, 3→7, 4→5,
11→2, 9→1. Las claves **no** se declaran; el código que las aplica está en los
`.psd1` y en los `.ps1`.

---

## T1 — Licencia por directorio y licencia de EVO

Tabla completa y comandos en `docs/legal/upstream-licenses.md`. Resumen:

| directorio | licencia declarada | evidencia |
|---|---|---|
| `(raíz)` | GPLv3 (texto) | `LICENSE`, 674 L, sha `3972dc97…` |
| `package/` | **la misma que la raíz** | `cmp LICENSE package/…/AtlasModules/LICENSE` → idénticos; 2 cabeceras `GPL-3.0-only` en ficheros adaptados de terceros |
| `app/` | `GPL-3.0-only` | `app/Cargo.toml:8`; 4 `LICENSE-*` de dependencias vendorizadas (Apache-2.0 / MIT) |
| `services/` | `GPL-3.0-only` | `reports/Cargo.toml`, `reports-mcp/Cargo.toml` |
| `tests/`, `tools/`, `docs/` | **sin declaración propia** | 0 ficheros de licencia, 0 cabeceras |

`package/` **no declara nada distinto** del `LICENSE` de la raíz. Ningún
directorio declara «o posterior». **NO VERIFICADO**: no hay forma de medir una
licencia distinta sin un fichero que la declare.

**EVO CLEAN.** Ya existía `LICENSE` en la raíz (creado en el paso 1, commit
`b4d4cd1`), idéntico byte a byte al de Atlas: `diff` sin diferencias,
sha256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`,
674 líneas, encabezado `GNU GENERAL PUBLIC LICENSE / Version 3, 29 June 2007`
(texto oficial, sin añadidos). **No se copió nada nuevo**: se verificó lo
existente. `README.md` y `docs/legal/upstream-licenses.md` declaran
**EVO CLEAN: GPL-3.0-only** con el motivo (Atlas es GPL-3.0-only y sus datos
entran en el catálogo) y con la marca **«pendiente de confirmación del
responsable»**. No se ha creado `THIRD_PARTY_NOTICES.md`.

---

## T2 — Efectos de Atlas

`tools/ledger_extract/extract_atlas_effects.py` → `inventory/ledger/atlas-effects.tsv`
(sha256 `ddbc950b…e472`, **986 filas**, 192 ficheros).

Fuentes: 1 172 funciones `product` (152 con ≥1 efecto), 376 `.ps1`/`.psm1` de
nivel superior, 191 `.cmd`/`.vbs`, y **23 bloques `Script`** de `.psd1`
(los 29 sin `Registry`: 15 declaran `Script`; 23 bloques porque un fichero
puede tener varios).

| effect_type | filas |
|---|---:|
| other-exe | 359 |
| file | 212 |
| registry | 200 |
| ownership | 87 |
| appx | 43 |
| process | 41 |
| service | 33 |
| network | 3 |
| dism | 3 |
| scheduled-task | 2 |
| power | 2 |
| boot | 1 |

| target_kind | filas |
|---|---:|
| unresolved | 626 |
| variable | 332 |
| literal | 28 |

**unresolved por tipo**: other-exe 359 · ownership 87 · file 61 · process 41 ·
appx 41 · service 30 · registry 4 · power 2 · network 1.

`other-exe`: **109 ejecutables distintos**. Top: `setup.exe` 24, `msedge.exe`
24, `AtlasManager.exe` 19, `explorer.exe` 18, `tool.exe` 17,
`AtlasToolbox-Setup.exe` 15, `winget.exe` 10, `shutdown.exe` 9,
`librewolf-152.0.5-1-windows-x86_64-setup.exe` 9, `procexp.exe` 8,
`missing.exe` 8, `wscript.exe` 5, `choice.exe` 5, `vcredist_x64.exe` 5.

Funciones `product`: **1 172**, de las que **152 tienen ≥1 efecto** y **1 020
no**. Las 20 sin efecto con más líneas:

| líneas | función | fichero |
|---:|---|---|
| 381 | Test-AtlasTweakFileSchema | `…/Atlas.Tweaks/Domain/Schema.ps1` |
| 322 | Test-AtlasTweakManifest | `…/Atlas.Tweaks/Domain/Manifest.ps1` |
| 237 | Get-AtlasToggleDefinitionProblems | `…/Atlas.Toggles/Domain/Definition.ps1` |
| 221 | Test-AtlasReleasedVolatileValue | `…/Install/Compat/Remove-AtlasLegacyElevationArtifacts.ps1` |
| 220 | Test-AtlasInstallRequirement | `…/Entry/Install-Atlas.ps1` |
| 191 | Get-AtlasInstallPlan | `…/Install/Install-Plan.ps1` |
| 169 | Invoke-AtlasLegacyElevationMigrationCore | `…/Install/Compat/Remove-AtlasLegacyElevationArtifacts.ps1` |
| 160 | Get-AtlasContext | `…/Atlas.Core/Domain/Context.ps1` |
| 151 | Invoke-AtlasOpenShellThemeFileTransaction | `…/Operations/OpenShell-ThemeTransaction.ps1` |
| 140 | Show-AtlasSoftwarePicker | `…/Atlas.Software/Domain/SoftwarePicker.ps1` |
| 139 | Start-AtlasInstallState | `…/Atlas.InstallState/Atlas.InstallState.psm1` |
| 134 | Remove-AtlasOrphanedEdgeAutoLaunch | `…/Operations/Remove-EdgeCurrentUserData.ps1` |
| 129 | Invoke-AtlasTrustedInstaller | `…/Atlas.Core/Domain/Privilege.ps1` |
| 122 | Invoke-AtlasRegistryEntries | `…/Atlas.Registry/Domain/Entries.ps1` |
| 120 | Invoke-AtlasTweak | `…/Atlas.Tweaks/Domain/Invoke.ps1` |
| 117 | New-AtlasShortcut | `…/Atlas.Shortcuts/Atlas.Shortcuts.psm1` |
| 116 | Invoke-AtlasHiddenProcess | `…/Atlas.Core/Domain/Process.ps1` |
| 116 | Invoke-AtlasPowerSavingState | `…/Atlas.Hardware/Domain/Power.ps1` |
| 112 | Set-AtlasDefaultUserHiveState | `…/Install/Tasks/Default-UserHive.ps1` |
| 109 | Invoke-AtlasInstallPlanCore | `…/Entry/Invoke-AtlasInstall.ps1` |

Las más grandes son **validadoras** y **planificadoras**: delegan el efecto en
otra función, por eso no aparecen aquí (ver T3).

**Tres correcciones reales del detector** (sin ellas el resultado era falso):

1. `New-Item`/`Remove-Item`/`Set-Item` se clasificaban como `registry` con
   cualquier ruta (`Remove-Item -Path $x`): se exigió hive `HK*` o
   `REGISTRY:`. Efecto: `registry` 526 → 200 y `New-Item` de tests fuera.
2. `reg.exe import failed` dentro de un `throw "…"` contaba como operación de
   registro: ahora se ignoran las coincidencias dentro de cadenas (máscara de
   comillas de PowerShell). 1 432 → 1 002 filas.
3. `Remove-Item HKCU:\…` se contaba dos veces (registro y fichero): se
   descarta el `file` cuando la ruta es una unidad de PowerShell que no es de
   fichero. 1 002 → 986.

---

## T3 — Grafo de llamadas y efectos por toggle

`tools/ledger_extract/extract_atlas_toggle_effects.py` →
`atlas-toggle-effects.tsv` (92 filas, sha `c19a8281…`) y `atlas-psd1-refs.tsv`
(183 filas, sha `898b6746…`).

**Aproximación declarada**: una llamada es la aparición del nombre de otra
función como palabra completa en el cuerpo. No hay evaluación, ni alcances, ni
imports. Da falsos positivos (nombres dentro de cadenas) y falsos negativos
(`& $nombre`). Es una **cota superior**. Profundidad máxima 5.

| métrica | valor |
|---|---:|
| filas (toggle, estado, función) | 92 |
| toggles alcanzados | 52 |
| con 1 estado | 17 |
| con varios estados | 35 |
| filas con efecto directo | 19 |
| filas con algún efecto alcanzable | 53 |
| **filas sin ningún efecto** | **39** |
| filas con ciclo | 21 |
| nombres en el grafo | 1 383 |
| nombres con ≥1 llamada | 957 |

Tipos alcanzables (nº de filas que los alcanzan): registry 30 · ownership 25 ·
other-exe 19 · process 17 · service 13 · file 6 · appx 5 · network 4 · power 4 ·
dism 2.

**39 filas sin efecto alcanzable** (lista completa): AdvancedBootOptions/Disable,
AdvancedBootOptions/Enable, AtlasHealth/Run, AutomaticRepair/Disable,
AutomaticRepair/Enable, Bluetooth/Disable, Bluetooth/Enable, BootLogo/Disable,
BootLogo/Enable, ContextMenuTerminals/Add, ContextMenuTerminals/AddNoWindowsTerminal,
ContextMenuTerminals/Remove, CpuIdle/Disable, CpuIdle/Enable, HighestMode/Disable,
HighestMode/Enable, KernelParameters/Disable, KernelParameters/Enable,
LockScreen/Enable, Mitigations/WindowsDefault, NewBootMenu/Disable,
NewBootMenu/Enable, SafeMode/CommandPrompt, SafeMode/Exit, SafeMode/Minimal,
SafeMode/Networking, SecurityHealthTray/Disable, SecurityHealthTray/Enable,
SpinningAnimations/Disable, SpinningAnimations/Enable, SystemRestore/Enable,
TakeOwnership/Disable, TakeOwnership/Enable, TelemetryComponents/Run,
TimerResolution/Disable, TimerResolution/Enable, ToggleDefender/Run,
UpdateDrivers/Run, ViewCurrentValues/View.

**Ciclos.** 21 filas. Ejemplos verificables:
`Invoke-AtlasHiddenProcess → Resolve-AtlasProcessExecutable → Invoke-AtlasHiddenProcess`
y `Finish → Restart → Finish`. Son recursión real o parecido de nombres, no un
error del recorrido: se marcan y no se expanden.

**Corrección real del grafo.** `script`, `global` y `definitions` figuraban como
«funciones» (parser del 4c) y como palabra completa casaban con casi todo:
64 filas con ciclo y ciclos falsos del tipo `script → Test-Path → script`. Al
arreglar el parser de funciones bajan a 21 y los ciclos que quedan son reales.

### Los 183 `.psd1`: quién los referencia

Búsqueda textual (nombre del fichero sin extensión, valor `Name` y slug
`Tweaks/<ruta>`), con ruido reconocido: una mención en un comentario o en un
test cuenta igual que una carga real.

| procedencia | `.psd1` que los mencionan |
|---|---:|
| `.ps1` | 36 |
| `.psm1` | 3 |
| `.json` | 3 |
| `.rs` | 4 |
| **manifiesto de tweaks** | **108** (103 habilitados + 5 en `Disabled`) |
| con alguna referencia | 120 |
| **sin ninguna referencia** | **63** |

**Cómo se aplican (localizado).** No hace falta adivinar:

```
package/Executables/AtlasModules/Scripts/Tweaks/tweaks.manifest.psd1
  ├─ Categories = @( @{ Name = 'networking'; Tweaks = @( 'shares/…' … ) } … )
  └─ Disabled   = @( @{ Slug = '…'; Reason = '…' } … )

…/Modules/Atlas.Tweaks/Domain/Manifest.ps1:26
  $Path = Join-Path (Get-AtlasContext).AtlasModulesPath 'Scripts\Tweaks\tweaks.manifest.psd1'
…/Manifest.ps1:181
  $definitionPath = Join-Path $TweaksRoot (($Slug -replace '/','\') + '.psd1')
…/Manifest.ps1:351
  Get-ChildItem -LiteralPath $TweaksRoot -Filter '*.psd1' -Recurse -File
…/Data.ps1:16
  Microsoft.PowerShell.Utility\Import-PowerShellDataFile -LiteralPath $LiteralPath
…/Atlas.Tweaks/Domain/Schema.ps1:461
  Get-ChildItem -LiteralPath $Path -Filter '*.psd1' -Recurse -File
```

Lectura: el manifiesto lista los slugs; `Manifest.ps1:181` compone la ruta y
`Data.ps1:16` la carga con `Import-PowerShellDataFile`. Los 75 `.psd1` fuera
del manifiesto no se aplican por esta vía (**NO VERIFICADO** si alguna otra
los usa: la búsqueda textual no encontró ninguna referencia en 63 de ellos).

---

## T4 — Operaciones estructuradas de WinUtil

`tools/ledger_extract/extract_winutil_ops.py` → `winutil-tweak-ops.tsv`
(179 filas, sha `60f56ebb…`).

`InvokeScript`/`UndoScript` son **listas** de cadenas (no una cadena), y
`tweaks.json` no es JSON estricto (tiene caracteres de control): se lee con
`strict=False`.

| kind | filas |
|---|---:|
| registry | 121 |
| script-InvokeScript | 27 |
| script-UndoScript | 22 |
| service | 9 |
| scheduledtask | **0** |
| appx | **0** |

| direction | filas |
|---|---:|
| apply | 157 |
| undo | 22 |

- Tweaks con operaciones: **65 de 69**. Faltan `WPFAddUltPerf`,
  `WPFRemoveUltPerf` (botones sin datos), `WPFOOSUbutton` (lanza un `.exe`
  externo) y `WPFchangedns` (combobox): **no tienen ninguna operación
  estructurada**, y se declara así en vez de inventarla.
- Tweaks con `UndoScript` o con `OriginalValue` distinto de `<RemoveEntry>`:
  **45**. `OriginalValue = <RemoveEntry>` en 63 filas de registro.
- Tweaks con **solo script** (sin estructura): **no hay ninguno**; sí hay 17
  sin ninguna estructura ni script.
- Efectos detectados en los scripts: file 4 · registry 5 · network 3 ·
  service 5 · ownership 7 · dism 4 · other-exe 3 · power 2 · process 3 ·
  defender 2 · appx 2 (30 de 179 filas tienen `effect_types`).

### `feature.json` y `appx.json` (solo conteos)

| fichero | ítems | filas | kind | detalle |
|---|---:|---:|---|---|
| `feature.json` | 33 | 31 | `feature` 13, `script-InvokeScript` 18 | 9 ítems declaran `feature` (13 nombres) |
| `appx.json` | 34 | 34 | `appx-package` 34 | todos declaran `PackageId` (31 con `StoreId`) |

Ninguno de los 33 features ni de los 34 appx declara `scheduledtask` ni
`appx` como lista estructurada: los appx se identifican por `PackageId`.

---

## T5 — Tests, CI, PR

- `pytest` → **161 passed** (128 previos + **33** nuevos en `test_paso4d.py`,
  varios parametrizados): determinismo, columnas exactas, 0 duplicados de clave,
  ninguna celda > 400 caracteres, cifras esperadas, `function_name` existente en
  `atlas-functions.tsv`, `tweak_id` existente en `winutil-items.tsv`.
- Nuevo step `Extractores de 4d (determinismo + cifras)`: doble ejecución +
  `diff` de sha256 de los 6 TSV, publicación en `ci-report`, y un chequeo de
  cifras. Probado en local antes de subir (`determinismo 4d: OK`).
- 4 tests del 4c se actualizaron porque sus cifras **dependían del parser
  corregido** (1 563 → 1 562): se cambiaron a los valores reales con nota.

## Desviaciones de lo pedido

1. **`atlas-functions.tsv` cambia de sha** en este paso (no estaba previsto):
   el parser del 4c tenía dos fallos y hubo que arreglarlos para que el grafo
   no fuera ruido. Se aplica en cascada a `atlas-effects.tsv` y
   `atlas-toggle-effects.tsv`. El bridge no cambia.
2. El `.psd1` con `Script` son **15 ficheros / 23 bloques**, no 15 bloques.
3. `scheduledtask` y `appx` como listas estructuradas en `tweaks.json`: **0**.
   No se ha inventado nada para rellenar esas columnas.
4. Se añadió `atlas-psd1-refs.tsv` como artefacto propio (el encargo pedía el
   dato, no un fichero nuevo).

## Supuestos

- Los cinco `.cmd`/`.vbs` con `wscript`/`cscript` cuentan como `other-exe`.
- `feature` de `feature.json` es una lista de nombres de característica de
  Windows (no de operaciones): se emite una fila por nombre.
- Los 4 `.vbs` y 188 `.cmd` se tratan como código de nivel superior (`<top>`).

## Riesgos

- **R1** El detector de efectos es léxico: 626 de 986 filas son `unresolved` y
  no se puede afirmar el efecto real de ninguna.
- **R2** El grafo por nombre es cota superior; con nombres repetidos (118)
  puede unir funciones distintas.
- **R3** Los 63 `.psd1` sin referencia textual podrían aplicarse por una vía no
  textual (**NO VERIFICADO**).
- **R4** Que `package/` comparta el `LICENSE` de la raíz es una inferencia
  razonable, no una declaración explícita del proyecto.

## Preguntas abiertas

1. ¿Se confirma **GPL-3.0-only** para EVO CLEAN? Está escrito como pendiente.
2. ¿Hace falta medir efectos de las 1 020 funciones `product` sin efecto por
   análisis interprocedural real (no textual)?
3. ¿Se descarta `scheduledtask`/`appx` como kinds de `tweaks.json` o vienen de
   otra versión de WinUtil?
