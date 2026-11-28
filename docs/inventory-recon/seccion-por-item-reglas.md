# Reglas de sección por ítem upstream (paso 8d)

Este documento define **cómo** `tools/ledger_extract/build_item_section_map.py`
decide la sección (1-17) de cada uno de los 435 ítems de
`inventory/ledger/upstream-capability-map.tsv` cuando la categoría del ítem no
basta (categorías `mixed`) o no existe.

Regla de oro: **ninguna regla se aplica por parecido débil**. Cada fila del mapa
declara con qué regla se decidió y con qué evidencia concreta (una palabra clave,
una ruta del pin o un efecto del ledger). Cuando no hay evidencia, la sección es
`unassigned` y `basis = manual-review`.

Orden de decisión (se para en la primera que dé evidencia):

1. `category` — la categoría del ítem tiene una sección 1-17 en
   `inventory/partition/category-section-map.tsv` (paso 8c).
2. `manifest-path` — la ruta del `.psd1` está en un directorio cuyo nombre
   identifica el área (p. ej. `Tweaks/qol/explorer/`). Sólo se usa aquí para
   ítems de categorías `mixed`, porque el paso 8c ya se lo aplicó a los demás.
3. `effect` — los efectos medidos del ítem (claves de registro, servicios,
   características y paquetes AppX de `atlas-tweak-ops.tsv`,
   `atlas-toggle-keys.tsv`, `winutil-tweak-ops.tsv`, `winutil-feature-ops.tsv`,
   `winutil-appx-ops.tsv`) coinciden con una regla de la tabla de abajo.
4. `name-rule` — el nombre del ítem contiene un término **propio** del área
   (lista cerrada de abajo, cada uno con su ejemplo real).
5. `unassigned` — nada de lo anterior. `basis = manual-review`.

## Tabla de reglas

`key` es lo que aparece en la columna `evidence` del TSV. El orden de las listas
es el orden de evaluación: gana la primera que casa.

### Efectos (basis = `effect`)

Se evalúan sobre las señales medidas del ítem, ya en minúsculas: `svc:<servicio>`,
`key:<hive>\<clave>\<valor>`, `feat:<característica>` y `appx:<paquete>`.

| key | Sección | Regla | Ejemplo real (ítem del pin) |
| --- | --- | --- | --- |
| `svc:diagtrack` | 3 | Servicio `DiagTrack` o `WerSvc` = telemetría. | `winutil:tweak:WPFTweaksTelemetry` |
| `svc:wsearch` | 9 | Servicio `WSearch` = indexación del sistema. | `winutil:tweak:WPFTweaksDisableSearchIndexing` |
| `svc:lfsvc` | 3 | Servicio `lfsvc` (ubicación) = privacidad. | `winutil:tweak:WPFTweaksLocation` |
| `key:WindowsUpdate` | 12 | Clave bajo `WindowsUpdate`, `UpdatePolicy` o `Windows\Update`. | `atlas:toggle:PauseUpdates` |
| `key:DeliveryOptimization` | 12 | Clave `DeliveryOptimization` = mantenimiento de Windows. | `atlas:toggle:DeliveryOptimisation` |
| `key:WindowsAI` | 2 | Clave `WindowsAI` o `\AIA\` (Recall, Copilot, Click To Do). | `atlas:toggle:Recall` |
| `key:CloudContent` | 3 | `CloudContent` o `ContentDeliveryManager` = sugerencias. | `atlas:manifest:qol/disable-windows-spotlight` |
| `key:Search` | 10 | Clave bajo `CurrentVersion\Search` o `Windows Search` = búsqueda del shell. | `winutil:tweak:WPFToggleBingSearch` |
| `key:Explorer\Advanced` | 10 | `Explorer\Advanced` = interfaz del Explorador. | `winutil:tweak:WPFToggleShowExt` |
| `key:Explorer` | 10 | Otra clave bajo `CurrentVersion\Explorer` o su rama `Policies\Explorer`. | `winutil:tweak:WPFTweaksRemoveHomeAndGallery` |
| `key:Control Panel` | 10 | Claves de `Control Panel` (ratón, teclado, escritorio, cursores). | `atlas:manifest:qol/disable-mouse-accel` |
| `key:Policies\Personalization` | 10 | Política de personalización (pantalla de bloqueo). | `winutil:tweak:WPFToggleDisableLockscreen` |
| `key:GraphicsDrivers` | 10 | `GraphicsDrivers` o `\Dwm` = efectos visuales. | `winutil:tweak:WPFMultiplaneOverlay` |
| `key:Keyboard Layout` | 10 | `Keyboard Layout` = métodos de entrada. | `atlas:toggle:KeyboardShortcuts` |
| `key:SystemRestore` | 14 | Clave de System Restore = reparación. | `atlas:toggle:SystemRestore` |
| `key:Memory Management` | 5 | Mitigaciones de memoria = rendimiento. | `atlas:toggle:Mitigations` |
| `key:Defender` | 13 | Clave de Defender o `Windows Defender Security Center`. | `atlas:toggle:HideAppBrowserControl` |
| `key:Session Manager\Power` | 5 | Energía (`PlatformAoAcOverride`, `Session Manager\Power`). | `winutil:tweak:WPFToggleS3Sleep` |
| `key:Control\Power` | 5 | Claves de energía del panel de control. | `winutil:tweak:WPFToggleStandbyFix` |
| `feat:net` | 11 | Característica de red (`ServicesForNFS*`, `ClientForNFS*`, `NFS-*`). | `winutil:feature:WPFFeaturenfs` |
| `feat:virt` | 16 | Virtualización y desarrollo (`Hyper-V`, `WSL`, Sandbox, `.NET`). | `winutil:feature:WPFFeatureswsl` |
| `feat:media` | 15 | Componente multimedia heredado (WMP, DirectPlay). | `winutil:feature:WPFFeatureslegacymedia` |
| `appx:*` | 15 | Operación de paquete AppX. | `winutil:tweak:WPFTweaksWidget` |
| `svc:set-multiple` | 4 | Tres o más servicios distintos en el mismo ítem: el objeto es la optimización de servicios. | `winutil:tweak:WPFTweaksServices` |
| `svc:set` | 4 | Cualquier otra operación de servicio. | `winutil:tweak:WPFTweaksServices` |
| `effect:power` / `boot` / `network` / `dism` / `file` | 5 / 8 / 11 / 1 / 1 | Tipo de efecto declarado en el ledger de WinUtil cuando es de una sola área. | `winutil:tweak:WPFTweaksHiber` (`power` → 5) |

**Regla de conflicto:** si los efectos de un ítem apuntan a **más de una**
sección (por ejemplo `Explorer\Advanced` y un paquete AppX), el efecto **no**
decide y se pasa a la regla de nombre. Nunca se elige «la primera clave que
aparezca».

### Nombres (basis = `name-rule`)

El nombre del ítem se trocea por camelCase y separadores (`BitLocker` →
`bit`+`locker`) y se busca la **secuencia de tokens contiguos que concatena el
término**. Así `BitLocker` casa con `bitlocker`, y `Windows Restore` **no** casa
con `store` (la concatenación sería `windowsrestore`).

| key | Sección | Términos | Ejemplo real |
| --- | --- | --- | --- |
| `name:security` | 13 | mitigation, core-isolation, bitlocker, firewall, uac, defender, wpbt, secure-boot | `winutil:tweak:WPFTweaksDisableBitLocker` |
| `name:telemetry` | 3 | telemetry, feedback, activity, location, advertising, consumer, spotlight, privacy, diagnostic | `winutil:tweak:WPFTweaksActivity` |
| `name:debloat-apps` | 2 | adobe, razer, logitech, brave, edge-debloat | `winutil:tweak:WPFTweaksRazerBlock` |
| `name:ai` | 2 | windows ai, copilot, recall, click to do | `winutil:tweak:WPFTweaksWindowsAI` |
| `name:update` | 12 | windows-update(s), update reset, pause update, delivery optimi[sz]ation, cbs, dism, update/ driver updates | `winutil:feature:WPFFixesUpdate` |
| `name:boot` | 8 | boot, bcdedit, autologon, legacy-recovery | `atlas:manifest:qol/bcdedit-tweaks` |
| `name:network` | 11 | network, dns, sharing, wifi, teredo, ipv6, ntp, rdp, netbios, smb, device metadata | `winutil:feature:WPFFixesNetwork` |
| `name:gaming` | 6 | game, gaming, xbox, fsogamebar | `atlas:toggle:FSOGameBar` |
| `name:memory` | 7 | background (app), hiber, sleep, memory, svchost | `winutil:tweak:WPFTweaksDisableBGapps` |
| `name:power` | 5 | power, cpu idle, timer resolution, performance plan, sleep study | `atlas:toggle:TimerResolution` |
| `name:repair` | 14 | repair, reset, corruption, perf-counter, restore point, system restore, verbose, bsod, safe mode, error | `winutil:feature:WPFPanelDISM` |
| `name:cleanup` | 1 | temp, temporary, cleanup, recycle, reserved storage, storage sense | `winutil:tweak:WPFTweaksDeleteTempFiles` |
| `name:service` | 4 | service | `atlas:manifest:scripts/backup-services` |
| `name:admin` | 16 | winget, powershell profile, shutup | `winutil:feature:WPFFixesWinget` |
| `name:apps` | 15 | appx, store, onedrive, copilot, office, outlook, phone link, process explorer, app archival, edge, windows ai | `winutil:tweak:WPFTweaksRemoveOneDrive` |
| `name:explorer` | 10 | explorer, start menu, taskbar, wallpaper, visual effects, mouse, touch, sound, dark, scrollbar, shortcut, context/right-click menu, lock screen, animation, bing, logon, widget, notifications, recomendaciones, extensiones/asociaciones de fichero, etc. | `atlas:manifest:qol/visual-effects` |
| `name:system` | 9 | registry backup, indexing, time, keyboard switching, oem, work or school, workplace | `winutil:tweak:WPFTweaksUTC` |

### Lo que estas reglas NO hacen

- No usan parecido textual (`difflib`, `fuzzy`, distancia de edición) ni la
  descripción del ítem.
- No asignan sección a un preset (`winutil:preset:*`): un preset es una lista de
  claves de varias secciones.
- No asignan sección a los paneles heredados de WinUtil (`WPFPanel*`): abrir
  `Control Panel` o `Firewall` no cambia nada del sistema.
- No asignan sección a las entradas de navegación (`winutil:nav-entry:*`).
- Los ítems sin efecto propio y sin evidencia quedan `unassigned` con el motivo
  escrito en `evidence` (tabla `NO_EFFECT_REASON` del script).

## Recuento que produce el generador

Los conteos por regla y por sección se imprimen en la salida de
`build_item_section_map.py` (`--json`) y se publican en
`docs/reports/plan-oleadas.md`. Este documento no repite cifras: si cambian,
manda la salida del script.
