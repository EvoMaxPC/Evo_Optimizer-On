# PASO 11 — Expresividad del motor y cierre de huecos de las oleadas 2 y 3

- Rama: `arena/ab2d6de7-evo-optimizer-on` (PR #1 **en borrador**, sin fusionar)
- Base: `0d72efa` (cierre del paso 10)
- Fecha: 2026-11-23

## T0 — Estado de partida medido

```
comando                                                  | salida
git rev-parse HEAD                                       | 0d72efa332950e82729d6cc8030270d76eeaba89
git ls-remote origin refs/heads/arena/…                  | 0d72efa332950e82729d6cc8030270d76eeaba89
gh api …/workflows/dotnet-ci.yml/runs?head_sha=0d72efa   | 45501299087 · success · 2 jobs
  ├ dotnet (windows-2025)                                | success
  └ dotnet (windows-11-arm)                               | success
gh api …/workflows/ledger-verify.yml/runs?head_sha=0d72efa | 45501293085 · success · 1 job
  └ ledger-verify (ubuntu-latest)                        | success
sha256 docs/requirements/INVENTARIO_USUARIO.md           | 0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709
sha256 inventory/ledger/inventory-reconciliation.tsv     | 876521e22780d898d48c… (cabecera; el sha completo en el job)
pytest (sandbox, línea base)                             | 518 passed
xUnit (CI del head de partida)                           | 187 passed / 0 failed en los dos runners
catálogo                                                 | 86 capacidades = 39 (§1-3) + 29 (§10) + 18 (§9)
sección 9                                                | 18 capacidades / 39 acciones / 16 Implemented + 2 Specified
sección 10                                               | 29 capacidades / 56 acciones
catálogo completo                                        | 86 capacidades / 231 acciones / 73 Implemented + 13 Specified
```

El inventario **no se ha tocado**: el sha256 sigue siendo el de partida.

## T0-b — Las seis incoherencias del informe del paso 10, con la medida

### b.1 Estados de las 18 capacidades de §9 (el informe decía «13 + 2»)

```
estado       | n  | ids
-------------+----+--------------------------------------------------------------
Implemented  | 16 | las 16 con acciones de registro o de servicio ya expresables
Specified    |  2 | system.registry-backup.enable, system.time.ntp-servers
-------------+----+--------------------------------------------------------------
total        | 18 |
```

La tabla de §9 del informe del paso 10 **sí** suma 18 (16 + 2). La cifra «13 + 2»
no sale de §9: sale de mezclar dos ámbitos distintos que el informe tenía en la
misma página.

```
medida (commit 0d72efa)                                   | Implemented | Specified | suma
----------------------------------------------------------+-------------+-----------+-----
sección 9 (18 capacidades)                                |     16      |     2     |  18
catálogo completo (86)                                    |     73      |    13     |  86
```

«13» es el `Specified` del **catálogo completo** y «2» el `Specified` de §9: sumar
13 + 2 no da nada. Lo que sí es cierto y medible: §9 tiene 16 + 2 = 18, y el
catálogo completo 73 + 13 = 86. Tras este paso, el catálogo queda en 75 / 11
(las dos de §9 se cierran) y §9 en 18 / 0.

### b.2 De las 28 líneas `Mapped` de partida de §9, cuántas ya estaban cubiertas

Se midió ejecutando el verificador del repo con el catálogo y la conciliación del
commit **`830290c`** (head del paso 9), no con los de ahora:

```
verificador con el catálogo de 830290c | §9: 28 Mapped, 17 cubiertas, 11 huecos
líneas Mapped de §9 ya cubiertas antes  | 17 (262, 274, 275, 279, 280, 281, 282, 283,
                                        |     284, 285, 288, 289, 290, 291, 303, 305, 309)
líneas Mapped de §9 sin cubrir antes     | 11 (263, 264, 265, 272, 273, 276, 277, 278,
                                        |     295, 308, 316)
```

El informe del paso 10 decía «15 ya cubiertas / 15 sin cubrir» y «12 se cubren con
capacidad nueva». La medida dice **17 ya cubiertas / 11 sin cubrir**; y de las 11,
diez se cubren con capacidad nueva y una (`278 System Tray Configuration.`) pasa a
`Absent-At-Pin` porque el pin no la implementa. El total cuadra de las dos formas
(17 + 11 = 28), pero la partición del informe está desplazada en dos líneas.

### b.3 Lista única de correcciones de conciliación (el informe decía 3 + 3 + 1 y «seis»)

```
#  | seccion:linea | antes (mapped_ids)                          | ahora
---+---------------+---------------------------------------------+------------------------------------------
1  | 9:265         | atlas:effect:tests/Atlas.Toggles.Tests…      | winutil:tweak:WPFTweaksServices
2  | 9:269         | (Absent-At-Pin)                              | atlas:manifest:qol/system/disable-wpbt
3  | 9:302         | (Absent-At-Pin)                              | atlas:manifest:misc/config-oem-information
4  | 9:307         | (Absent-At-Pin)                              | atlas:toggle:KeyboardShortcuts
5  | 9:308         | winutil:tweak-op:WPFToggleNumLock:registry:0 | atlas:toggle:KeyboardShortcuts
6  | 9:316         | winutil:tweak-op:WPFTweaksTelemetry:registry:7 | atlas:manifest:qol/set-hidden-settings-pages
7  | 9:278         | winutil:tweak-op:WPFToggleLoginBlur:registry:0 | (Absent-At-Pin)
```

Evidencia de cada una, línea a línea del pin:

```
1  config/tweaks.json (WPFTweaksServices: CscService, DiagTrack, MapsBroker, StorSvc, SharedAccess)
2  Tweaks/qol/system/disable-wpbt.psd1 (DisableWpbtExecution=1)
3  Tweaks/misc/config-oem-information.psd1:5-7 (Manufacturer, SupportURL, SupportPhone)
4  Toggles/Interface/KeyboardShortcuts.psd1:11 (Hotkey/Language Hotkey/Layout Hotkey = 3)
5  Toggles/Interface/KeyboardShortcuts.psd1:11 (misma fuente que 4: NumLock no era el ajuste)
6  Scripts/Tweaks/qol/set-hidden-settings-pages.ps1 ($key + $value)
7  config/tweaks.json sólo tiene WPFTweaksDisableNotifications y WPFToggleBatteryPercentage;
   xaml/ no tiene página de bandeja del sistema
```

Son **7 filas**, no 6: 6 `MAPPED_OVERRIDES` de §9 (265, 269, 302, 307, 308, 316) **y**
1 `ABSENT_OVERRIDES` (278). El informe las describía como «3 + 3 + 1» en un sitio y
«seis» en otro; ambas descripciones se refieren a lo mismo contado de forma
incompatible. La lista de arriba es la única.

### b.4 Los 18 ids y el prefijo de `services.manual-profile`

```
system.error-reporting.crash-control      system.menu-delay.disable
system.error-reporting.wpbt-disable       system.mitigations.disable
system.game-mode.enable                   system.mouse-acceleration.enable
system.hibernation.hide                   system.oem-information.identify
system.keyboard-shortcuts.disable         system.registry-backup.enable
system.location.consent-deny              system.search-indexing.disable
system.services.manual-profile            system.settings-page-visibility.hide
system.sleep.s0-network-keep              system.sleep.s3-enable
system.time.ntp-servers                   system.time.utc-rtc
```

Los 18 empiezan por `system.` — **incluida `system.services.manual-profile`**
(`catalog/capabilities/section9_system_registry.json`, `"id": "system.services.manual-profile"`).
No hay ninguna capacidad de §9 con prefijo `services.` ni `registry.`.

### b.5 Qué relajó el job «Paso 9» y qué dejó de enumerar `Wave1CatalogTests`

```
artefacto | antes (3debf39, paso 9)                          | ahora (0d72efa, paso 10)
----------+--------------------------------------------------+----------------------------------------
ledger-verify                                                
  «Paso 9»| ok = (cov["capacidades"] == 68                     | ok = (cov["capacidades"] >= 68
Wave1CatalogTests                                            
  L96-102 | .Where(d => d.SectionId != 10)                     | .Where(d => d.SectionId is not 10 and not 9)
          | Assert.Equal(29, Count(SectionId == 10))           | + Assert.Equal(18, Count(SectionId == 9))
```

**Sí reducen verificación, y se reparan en este paso:**

- `>= 68` no verifica nada del tamaño del catálogo: acepta 68, 86 o 500. En lugar de
  volver a `== 86` (que otra oleada tendría que volver a tocar y volvería a
  relajarse), el job «Paso 9» pasa a comprobar **invariantes propias de la sección
  10 leídas del JSON**: `len(caps10) == 29`, `acciones == 57`, todas
  `sectionId == 10`, estados válidos, presencia de `registryDeleteKey` y la
  cobertura 29/29 con 0 huecos. Así el job no depende del tamaño global.
- `Wave1CatalogTests` dejó de enumerar §9 (correcto: §9 tiene su propio
  `Wave3CatalogTests`) y ahora **cuenta** las 18 de §9 además de las 29 de §10.
  El hueco real que quedaba es que ninguna prueba recorría las 86 capacidades sin
  listas de ids, así que se añade
  `Wave4CatalogTests.TestWave4Catalog_EveryCapabilityInTheCatalogMeetsTheSameInvariants`
  (86 capacidades, secciones exactas {1,2,3,9,10}, validador limpio, orden de
  acciones 1..n, reversibilidad declarada, `CapabilityRules.Validate` vacío).

### b.6 Las filas `no-source` y `differs`, y las dos excepciones declaradas

```
capability_id                   | hive | clave (recortada)                                  | valor | nombre
--------------------------------+------+----------------------------------------------------+-------+---------------------
cleanup.recycle.bin             | HKLM | …\Explorer\VolumeCaches\Recycle Bin                 | 0     | StateFlags0064
cleanup.wer.reports             | HKLM | …\Explorer\VolumeCaches\Windows Error Reporting Files| 0    | StateFlags0064
privacy.telemetry.dmwappush     | HKLM | …\Services\dmwappushservice                         | 4     | Start
system.registry-backup.enable   | HKLM | …\Session Manager\Configuration Manager             | 2     | BackupCount
system.registry-backup.enable   | HKLM | …\Session Manager\Configuration Manager             | 1     | EnablePeriodicBackup
```

Son 5, todas con el motivo escrito en la `provenance` de su capacidad (categorías
de `cleanmgr` que se aplican con `Start-Process cleanmgr /sagerun:64`; un
`Set-WinUtilRegistryValue` dentro de un ISO script que el ledger marca NO
VERIFICADO; y los dos valores de `WPFFeatureRegBackup`, que el pin escribe desde un
`InvokeScript` y no desde un bloque `Registry`).

```
fila | capability_id                         | relation | catálogo                                             | fuente
-----+---------------------------------------+----------+------------------------------------------------------+--------------------
  85 | system.settings-page-visibility.hide   | differs  | hide:recovery;maps;…;deviceusage;home                 | hide:aicomponents
---  | debloat.settings.home                  | equals-original | hide:home                                      | show:home
     | system.settings-page-visibility.hide   | differs  | (la misma fila de arriba)                             | —
```

`catalog/exceptions/value-deviations.json` declara **2** desviaciones:

```
1 | debloat.settings.home                | equals-original | deviation_kind=switch-meaning
  |   WPFToggleHideSettingsHome es un Toggle: su casilla ENCENDIDA escribe 'show:home';
  |   el efecto que anuncia la capacidad es el estado apagado ('hide:home').
2 | system.settings-page-visibility.hide | differs         | deviation_kind=value
  |   el .ps1 del pin escribe la lista completa de una vez; WinUtil escribe
  |   'hide:aicomponents' sobre la misma clave. Se copia el literal del pin.
```

`equals-off` (1 fila) también exige excepción y la tiene; `sin excepción = 0`.

### b.7 Las 18 capacidades de §9 (medido del JSON, tras el paso 11)

```
id                                    | risk   | securityImpact | privilege | confirmation           | restore      | reversibility | state       | builds                  | acc
--------------------------------------+--------+----------------+-----------+------------------------+--------------+---------------+-------------+-------------------------+----
system.error-reporting.crash-control  | Medium | Reduces        | Admin     | Summary                | RestorePoint | Reversible    | Implemented | 19045,22631,26100,26200 |  5
system.error-reporting.wpbt-disable   | Medium | Improves       | Admin     | Summary                | RestorePoint | Reversible    | Implemented | 19045,22631,26100,26200 |  1
system.game-mode.enable               | Safe   | Neutral        | User      | None                   | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  2
system.hibernation.hide               | Low    | Neutral        | Admin     | SimpleClick            | SessionUndo  | Reversible    | Implemented | 22631,26100,26200       |  1
system.keyboard-shortcuts.disable     | Safe   | Neutral        | User      | None                   | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  3
system.location.consent-deny          | Low    | Improves       | Admin     | SimpleClick            | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  6
system.menu-delay.disable             | Safe   | Neutral        | User      | None                   | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  1
system.mitigations.disable            | High   | Reduces        | Admin     | SummaryAndRestorePoint | RestorePoint | Reversible    | Implemented | 19045,22631,26100,26200 |  4
system.mouse-acceleration.enable      | Safe   | Neutral        | User      | None                   | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  3
system.oem-information.identify       | Safe   | Neutral        | Admin     | None                   | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  3
system.registry-backup.enable         | Safe   | Improves       | Admin     | None                   | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  3
system.search-indexing.disable        | Low    | Neutral        | Admin     | SimpleClick            | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  1
system.services.manual-profile        | Low    | Improves       | Admin     | SimpleClick            | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  5
system.settings-page-visibility.hide  | Low    | Neutral        | Admin     | SimpleClick            | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  1
system.sleep.s0-network-keep          | Safe   | Neutral        | User      | None                   | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  1
system.sleep.s3-enable                | Medium | Neutral        | Admin     | Summary                | RestorePoint | Reversible    | Implemented | 19045,22631,26100,26200 |  1
system.time.ntp-servers               | Low    | Neutral        | Admin     | SimpleClick            | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  3
system.time.utc-rtc                   | Low    | Neutral        | Admin     | SimpleClick            | SessionUndo  | Reversible    | Implemented | 19045,22631,26100,26200 |  1
```

Total: 18 capacidades, **45 acciones**, **0 `Specified`**. Dos capacidades cambiaron
de estado en este paso (`Specified → Implemented`) y tres ganaron acciones: la
ubicación pasó de 2 a 6 y las otras dos de 2 a 3.

### b.8 Huecos de expresividad que quedan, recorriendo las 86 capacidades

Barrido automático de `provenance` + `description` de los 86 JSON, cruzado con las
operaciones del pin (`AddKey`, `DeleteKey`, `powercfg`, `w32tm`, `Register-ScheduledTask`,
`bcdedit`, scripts de instalación):

```
capacidad / item upstream                 | operación del pin                              | motivo del hueco
------------------------------------------+------------------------------------------------+---------------------------------------------
system.oem-information.identify           | Set-OemInformation.ps1: bcdedit /set description| comandos sin inversa + literales DINÁMICOS
  (misc/config-oem-information)           | + Model y RegisteredOrganization = "Atlas $ver" | que el build estampa: no se inventa un valor
------------------------------------------+------------------------------------------------+---------------------------------------------
system.time.ntp-servers (misc/config-time)| w32tm /config /update y w32tm /resync          | comandos sin inversa; NO se ejecutan y quedan
                                          |                                                | escritos en description y provenance
------------------------------------------+------------------------------------------------+---------------------------------------------
system.hibernation.hide                   | Disable-AtlasHibernation → powercfg /h off      | no hay acción de energía; el .psd1 sólo
  (General/Hibernation)                   |                                                | escribe ShowHibernateOption=0
------------------------------------------+------------------------------------------------+---------------------------------------------
explorer.home.hide (Interface/Home)       | estado ENABLE: AddKey de la clave Home          | el motor expresa DeleteKey con instantánea,
                                          |                                                | no "crear clave vacía": crear no tiene inversa
                                          |                                                | con estado previo (borrar lo recién creado sí,
                                          |                                                | pero no está declarado como acción)
------------------------------------------+------------------------------------------------+---------------------------------------------
explorer.removable-drives.sidebar         | estado ENABLE: escribe el valor por defecto     | expresable (caso ya cubierto); las DeleteKey
                                          | estado DISABLE: 2 DeleteKey                     | del pin están en el estado CONTRARIO, por eso
                                          |                                                | no se declaran (no se invierte el significado)
------------------------------------------+------------------------------------------------+---------------------------------------------
atlas:toggle:Indexing, :Workplace,        | settings de sección 9/10 sin capacidad          | no son valores de registro fijos: exigen
winutil:feature:WPFPanelTimedate          | (3 filas `pending` del mapa upstream)           | abrir un panel o escribir en varias claves
------------------------------------------+------------------------------------------------+---------------------------------------------
qol/shell/disable-network-location-wizard | AddKey de HKLM\…\Network\NewNetworkWindowOff    | crear una clave no es accionable con inversa
qol/taskbar/config-pins                   | AddKey de HKCU\…\Explorer\Taskband + pines      | y el resto del script es por usuario/estado
------------------------------------------+------------------------------------------------+---------------------------------------------
las 22 capacidades de las oleadas 1-3 con | verbos del pin (cleanmgr, Remove-AppxPackage,    | `command`/`process` SIN inversa: se declaran
`command` o `process`                     | winget, bcdedit, netsh…)                        | Irreversible/NothingToRestore y no se promete
                                          |                                                | deshacer (ADR-0003)
```

Los tres primeros están escritos en la `description` y en la `provenance` de su
capacidad; los de `AddKey` **no** tienen capacidad donde escribirse (§9 no los usa y
§10 declara el estado contrario) y se declaran aquí. De los 9 `AddKey` del pin, 3
están en producto y 6 en las pruebas de Atlas (`tests/`), que no son producto.

### b.9 `system.location.consent-deny`: tipo de inicio vs detener servicio

```
parte del pin                                   | ¿expresable? | cómo
------------------------------------------------+--------------+------------------------------------------
Set-Service -Name lfsvc -StartupType Disabled   | SÍ           | ServiceAction SetStartupType (paso 11)
$service.Stop() sobre lfsvc                     | SÍ           | ServiceAction Stop (paso 11)
Set-Service -Name MapsBroker -StartupType Disabled | SÍ        | ServiceAction SetStartupType
$service.Stop() sobre MapsBroker                | SÍ           | ServiceAction Stop
Find My Device (política) y ocultar páginas      | NO           | queda fuera; escrito en provenance
```

Evidencia: `Toggles/General/Location.psd1:13` (MachineAction `Disable-AtlasLocation`),
`Scripts/Modules/Atlas.Privacy/Domain/Location.ps1:91` (`Set-AtlasLocationMachineState`)
y `:113` / `:114` (`Invoke-AtlasLocationServiceState -Name lfsvc` / `-Name MapsBroker`).
La capacidad pasa de 2 a 6 acciones y sigue `Implemented`.

## Resumen

El motor aprende tres cosas que el catálogo ya necesitaba y no sabía pedir:
**borrar una clave completa con instantánea**, **crear una tarea programada** y
**arrancar o parar un servicio** guardando su estado de ejecución. Con eso,
`system.registry-backup.enable` y `system.time.ntp-servers` dejan de ser
`Specified`, `system.location.consent-deny` declara los servicios que el pin apaga
y `explorer.home.hide` declara el `DeleteKey` del pin. Los huecos que quedan (crear
claves, comandos sin inversa, valores dinámicos) siguen escritos con su motivo.

```
cifra                                             | antes (0d72efa) | ahora
--------------------------------------------------+-----------------+---------------------
capacidades del catálogo                          | 86              | 86
acciones del catálogo                             | 231             | 238
  §9                                              | 39 en 18 caps   | 45 en 18 caps
  §10                                             | 56 en 29 caps   | 57 en 29 caps
capacidades §9 en Specified                       | 2               | 0
catálogo Implemented / Specified                  | 73 / 13         | 75 / 11
acciones por tipo                                 | registry 194, service 9, task 5, command 23
                                                  | → registry 194, service 14, task 5, command 23, registryDeleteKey 1, taskCreate 1
cobertura                                         | 85/85, 0 huecos | 85/85, 0 huecos
auditoría de valores                              | 194 filas       | 195 filas (la clave de Inicio), veredicto OK
pytest                                            | 518             | 539 (+21)
xUnit                                             | 187             | 187 + 36 nuevos (23 motor + 13 catálogo) → 223 si compilan
rangos-build.md                                   | 73 Implemented / 13 Specified | 75 / 11
```

Las 86 capacidades del catálogo no cambian de número: cambian **dos estados**
(`system.registry-backup.enable` y `system.time.ntp-servers` dejan de ser
`Specified`) y **siete acciones** (2 de §9 que estaban en `Specified` suman 2, la
ubicación pasa de 2 a 6 y la sección 10 sube una).

## T1 — Qué se implementó (y qué no)

```
fichero                                              | cambio
-----------------------------------------------------+-------------------------------------------------------
src/Evo.Core/Actions/CapabilityAction.cs             | ActionKind += RegistryDeleteKey(5), TaskCreate(6)
src/Evo.Core/Actions/ConcreteActions.cs              | RegistryDeleteKeyAction, TaskCreateAction
src/Evo.Core/System/IRegistryAccessor.cs             | IRegistryTreeReader, IRegistryKeyCreator
src/Evo.Core/System/ITaskAccessor.cs                 | CreateTask/DeleteTask + TaskDefinition
src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs| nuevo: instantánea, fail-closed, dry-run, no-op
src/Evo.Engine/Executors/TaskCreateExecutor.cs       | nuevo: crear / overwrite con restauración
src/Evo.Engine/Executors/ServiceActionExecutor.cs    | Start/Stop con estado previo; SetStartupType aparte
src/Evo.Engine/Undo/UndoJournal.cs                   | RegistryDeleteKeyUndoEntry, TaskCreateUndoEntry, ServiceUndoEntry.StatusChanged
src/Evo.Catalog/CatalogValidator.cs                  | R-ACTION para las dos acciones nuevas
src/Evo.Testing/FakeRegistryAccessor.cs              | árbol (subclaves, tipos), EnsureKey, ClearLog
src/Evo.Testing/FakeTaskAccessor.cs                  | CreateTask/DeleteTask, FailCreateWith, Created
src/Evo.Testing/FakeServiceAccessor.cs               | FailStartWith / FailStopWith
docs/adr/ADR-0005-expresividad-del-motor.md          | nuevo, estado Propuesto
```

Reglas que se respetan y no se relajan:

- **Fail-closed**: si el accesor no sabe enumerar el árbol, si la instantánea
  lanza o si supera `RegistrySnapshotLimits` (16 de profundidad / 4096 valores /
  1024 claves), **no se borra**. Probado con tres fakes distintos.
- **Clave inexistente** = no-op registrado; el deshacer no crea nada.
- **Tarea existente sin `overwrite`** = fallo sin tocar nada; con `overwrite` se
  restaura el estado previo en vez de borrarla.
- **Servicio**: `SetStartupType` sólo cambia el arranque; `Start`/`Stop` sólo el
  estado; el deshacer devuelve primero el arranque y después el estado (al revés
  fallaría con `ERROR_SERVICE_DISABLED`).
- **Comandos y procesos siguen sin inversa**. No se ha tocado eso.
- **No hay accesores reales de Windows** (REQ-004): sólo interfaces y fakes.

## T2 — Cierre desde los generadores

Todo sale de `build_section9_catalog.py` y `build_section10_catalog.py`; ningún
JSON se tocó a mano (`--check` byte a byte en el job de CI).

```
capacidad                        | antes     | ahora     | acciones nuevas
---------------------------------+-----------+-----------+---------------------------------------------
explorer.home.hide               | Implemented | Implemented | + registryDeleteKey (recursive=false)
system.registry-backup.enable    | Specified | Implemented | + taskCreate AutoRegBackup
system.time.ntp-servers          | Specified | Implemented | + service Start w32time
system.location.consent-deny     | Implemented | Implemented | + 4 service (lfsvc/MapsBroker: startup + stop)
```

`explorer.removable-drives.sidebar`: **no** se toca. Sus dos `DeleteKey` están en
el estado `Disable` y la capacidad declara el estado `Enable`; incluirlas borraría
justo lo que la capacidad enciende. Queda escrito en la `description`.

`SecurityImpact` no cambia en ninguna capacidad: no hay evidencia nueva que lo
justifique.

### Hallazgo: el orden de las acciones de servicio importa para el deshacer

Al revisar el deshacer LIFO apareció un fallo real, no cosmético. Con el orden
natural («deshabilitar y luego parar»), el rollback deshace primero la parada e
intenta **arrancar** un servicio que todavía está deshabilitado: Windows devuelve
`ERROR_SERVICE_DISABLED` (1058) y el deshacer se queda a medias.

```
orden declarado                  | LIFO del rollback            | resultado
---------------------------------+------------------------------+-------------------------
Stop(3) → SetStartupType(4)      | startup(4) → start(3)        | OK (lo que declara el catálogo)
SetStartupType(4) → Stop(3)      | stop(3) → startup(4)         | arranca con el servicio aún
                                 |                              | deshabilitado → 1058
```

Se corrigió **en el generador** (`location_service_actions()` emite `Stop` antes de
`SetStartupType`) y el fake **imita ahora el 1058** para que el orden equivocado
falle en los tests y no sólo en producción. Hay dos pruebas nuevas: una que exige
que el orden del catálogo se deshaga entero y otra que documenta que el inverso
falla (declarado, no silenciado).

## T3 — Artefactos regenerados

```
artefacto                              | resultado
---------------------------------------+--------------------------------------------------
catalog/capabilities/section9_*.json   | 18 caps / 45 acciones / 0 Specified
catalog/capabilities/section10_*.json  | 29 caps / 57 acciones
inventory/ledger/catalog-value-audit.tsv | 195 filas, 0 ambiguous, 0 sin excepción, 2 excepciones, veredicto OK
inventory/ledger/upstream-capability-map.tsv | §9: 8 covered / 3 pending
docs/reports/matriz-cobertura.md       | 86 caps, 85 Mapped / 85 cubiertas, 0 huecos
docs/reports/plan-oleadas.md           | §1,2,3,9,10 cerradas
docs/reports/rangos-build.md           | 86 caps, 75 Implemented / 11 Specified
inventory/ledger/inventory-reconciliation.tsv | sin cambios (588 filas, 30 Mapped en §9)
```

Antes/después de los `pending` de §9/§10: **no cambia ninguno** (siguen 3 en §9 y
98 en §10). Este paso cierra expresividad del motor y capacidades ya declaradas, no
ítems de upstream nuevos.

## T4 — Pruebas

```
suite                                  | antes | ahora | detalle
---------------------------------------+-------+-------+----------------------------------------
pytest (tests + tools/ledger_extract/tests) | 518 | 539 | +21 de tests/test_paso11.py
xUnit Evo.Engine.Tests (Wave4EngineTests)   | —   | +23   | 23 [Fact]: DeleteKey 10, tareas 5, servicios 6, capacidades reales 2
xUnit Evo.Catalog.Tests (Wave4CatalogTests) | —   | +13   | 8 [Fact] + 5 [InlineData] = 13 casos; incluye el barrido de las 86
```

Los 23 del motor cubren, uno a uno, lo que el paso exige: ejecutar, deshacer
exacto (valores + **tipos** + subclaves + ramas vacías), dry-run, clave
inexistente, fallo de instantánea, límite superado, profundidad superada,
sin-recursión, audit sin mutar, rollback por coordinador, puerta de punto de
restauración, creación/overwrite/rechazos/fallo de tarea, arranque con deshacer,
cambio de arranque sin tocar el estado, fallo de arranque con reversión LIFO y las
tres capacidades reales de §9, más los dos del orden de servicios (1058).

**Aviso honesto (REQ-002)**: el sandbox **no tiene dotnet**. Los 36 casos xUnit nuevos se
han escrito y revisado contra las APIs reales por lectura y `grep`
(`RegistrySnapshotLimits`, `ServiceUndoEntry.StartupTypeChanged/StatusChanged`,
`TestHarness.Create(restorePointAvailable:)`, `FakeTaskAccessor.Created/Seed/
FailCreateWith`, `FakeRegistryAccessor.GetKind/EnsureKey/ClearLog`, `ActionContext`,
`UndoContext`, `TaskCreateAction` como record), pero **su compilación y ejecución
sólo se pueden verificar en CI**. No se citan resultados de CI de este paso hasta
que el push exista y los runs terminen.

## Criterios U0–U6

```
U0 | Estado de partida impreso                                | CUMPLIDO
   |   HEAD 0d72efa, ls-remote igual, inventario 0b6aeaef…f709, runs 45501299087 /
   |   45501293085 en success, 518 pytest, 187 xUnit
U1 | Las 6 incoherencias aclaradas con medida                  | CUMPLIDO
   |   b.1 (16+2, la cifra 13+2 no existe), b.2 (17/11, no 15/15), b.3 (7 filas),
   |   b.4 (18 ids con prefijo system.), b.5 (>= 68 reparado + barrido de las 86),
   |   b.6 (5 no-source + 1 differs + 2 excepciones)
U2 | ADR-0005 y expresividad del motor                         | CUMPLIDO
   |   Propuesto; DeleteKey con instantánea fail-closed, tarea con restauración,
   |   servicio con estado previo; comandos siguen sin inversa
U3 | Cierre desde los generadores                              | CUMPLIDO
   |   4 capacidades cerradas, 0 Specified en §9, 0 JSON a mano, --check byte a byte
U4 | Ledgers y cobertura al día                                | CUMPLIDO
   |   195 filas, 0 ambiguous, 0 sin excepción, 85/85 cubiertas, 0 huecos
U5 | Pruebas                                                   | CUMPLIDO (xUnit pendiente de CI)
   |   539 pytest (+21), 36 xUnit nuevos (23 del motor + 13 de catálogo)
U6 | Job «Paso 11» con doble ejecución, diff y sha256          | CUMPLIDO
   |   ledger-verify: dos pasadas, diff de sha256 de 8 artefactos, --check, y
   |   comprobación de invariantes de §9/§10 leídas de los JSON
```

## Riesgos y límites

- **La instantánea vive en memoria.** Una clave enorme no se borra (fail-closed)
  en vez de intentarlo sin deshacer. Está documentado en ADR-0005 y en los límites.
- **El borrado recursivo puede llevarse la clave padre vacía.** El diario devuelve
  el subárbol pedido; no promete más.
- **Crear una tarea no valida que Windows la acepte**; eso es del accesor real.
- **Los xUnit nuevos no se han compilado aquí** (no hay dotnet). Es el único punto
  del paso que queda pendiente de verificación externa.
- **El orden de declaración de los servicios es semántico**, no cosmético (ver
  «Hallazgo»): cualquier capacidad futura que combine `Stop` y `SetStartupType`
  debe declarar la parada primero.
- **`inventory-reconciliation.tsv` no cambia**, pero `catalog-value-audit.tsv` sí
  (195 filas): cualquier documento que citara 194 queda desfasado.

## Preguntas abiertas

1. **¿Se declara `AddKey`?** Crear una clave vacía tendría inversa (borrarla), pero
   sólo si la clave no existía; si existía, hay que capturarla antes, igual que el
   borrado. Cerraría los huecos de `disable-network-location-wizard`,
   `config-pins` y el estado `Enable` de `Home`.
2. **¿Se expresan los comandos?** `w32tm /config /update`, `powercfg /h off` y
   `bcdedit /set` siguen fuera porque no tienen inversa. Ninguna promesa de
   deshacer los cubre.
3. **¿Se sube `SecurityImpact` de `system.location.consent-deny`?** Ya es
   `Improves`; parar `MapsBroker` también reduce funcionalidad, pero no hay
   evidencia medida de impacto de seguridad. No se cambia.
