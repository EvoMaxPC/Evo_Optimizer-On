# PASO 10 — Oleada 3 del catálogo: Sección 9 (Registro de Windows y configuración del sistema)

Fecha: 2026-11-23 (reloj del agente, UTC). Rama `arena/ab2d6de7-evo-optimizer-on`.
Pins: Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`,
WinUtil `70c23c80641d7370532af2f619b2842658600842`.

## T0 — Estado de partida (medido antes de tocar nada)

```
git rev-parse HEAD                          | 830290cb79de4fc287b8b63d5be525eaf95f2e71
git ls-remote origin (rama de trabajo)      | 830290cb79de4fc287b8b63d5be525eaf95f2e71
git ls-remote origin refs/heads/main        | 402af190e10a120dc893fa74f0a1d7b7d55b0c75
git ls-remote origin refs/pull/1/head       | 830290cb79de4fc287b8b63d5be525eaf95f2e71
sha256 docs/requirements/INVENTARIO_USUARIO.md | 0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709
sha256 inventory/ledger/inventory-recon…   | c35c1791056f4348a664b91f1299d56f0df0cfd2c2209412cfe712e8b1f8a46a
pytest (línea base)                         | 502 passed
xUnit (línea base, CI del paso 9)           | 161 passed / 0 failed (windows-2025 y windows-11-arm)
Sección 9 en inventory-reconciliation.tsv   | 58 líneas: 28 Mapped / 28 Absent-At-Pin / 2 Informative-Header
Ítems de Sección 9 en item-section-map.tsv  | 11 (5 atlas-manifest, 2 atlas-toggle, 4 winutil)
Verificador de cobertura (línea base)       | 15 de las 28 líneas Mapped de §9 sin capacidad que las respalde
```

El SHA de `INVENTARIO_USUARIO.md` es el de partida y **no se ha modificado**: al
cierre del paso sigue siendo `0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709`.

## Resumen

La Sección 9 (REGISTRO DE WINDOWS Y CONFIGURACIÓN DEL SISTEMA) queda catalogada:
**18 capacidades y 39 acciones** (33 de registro y 6 de servicio), generadas desde
los dos pins por `tools/ledger_extract/build_section9_catalog.py` — ningún literal
escrito a mano, ningún JSON editado a mano.

El verificador de cobertura pasa de **55/55** a **82/82** líneas `Mapped`
cubiertas (3 de §1 + 17 de §2 + 6 de §3 + **27 de §9** + 29 de §10), con **0
huecos no declarados** y **0 huecos declarados**. Las 28 líneas `Mapped` de
partida se resolvieron así: 15 ya estaban cubiertas por capacidades de §2/§3/§10
(no se duplican), **12 se cubren con capacidad nueva** y **1 (`Services.`) se
remide a `Mapped` con otro `mapped_id`**. Además **3 líneas que el paso 4e había
mapeado mal se corrigen** y **1 pasa a `Absent-At-Pin`** por medición del pin:

```
linea | texto                            | antes            | ahora
------+----------------------------------+------------------+----------------------------------------
265   | Services.                        | Mapped (test)    | Mapped → winutil:tweak:WPFTweaksServices
278   | System Tray Configuration.       | Mapped           | Absent-At-Pin (el pin no tiene esa función)
308   | Keyboard Shortcuts.              | Mapped (NumLock) | Mapped → atlas:toggle:KeyboardShortcuts
316   | Settings Page Visibility.         | Mapped (telemetría) | Mapped → atlas:manifest:qol/set-hidden-settings-pages
```

Cifras al cierre, todas medidas:

```
capacidades del catálogo | 86 (39 de las secciones 1-3 + 29 de la 10 + 18 de la 9)
acciones de la sección 9 | 39 en 18 capacidades (máx. 5 en crash-control, servicios y mitigaciones)
verificador de cobertura | 82 Mapped, 82 cubiertas, 0 huecos, veredicto OK
auditoría de valores     | 194 filas, 168 equals-apply / 19 equals-on / 1 equals-off / 1 differs / 5 no-source, 0 ambiguous, 0 sin justificar
pytest                   | 518 passed (línea base 502; +16 de tests/test_paso10.py)
xUnit                    | 161 → 187 previstos (+15 de catálogo, +11 de motor), pendiente del CI
```

## T0-bis — Cómo se trabajó (y un aviso de honestidad)

El sandbox **no tiene dotnet**: la parte .NET se valida por el CI real
(`.github/workflows/dotnet-ci.yml`, runners `windows-2025` y `windows-11-arm`)
leyendo el informe de la rama `ci-report`. Para no entregar código .NET a ciegas
se ha hecho una pasada manual contra las APIs reales del repo (`CapabilityAction`
polimórfica con `"type"`, `CapabilityRules.MinimumRestore/MinimumConfirmation`,
`EngineCoordinator.RequiresRestorePoint`, `FakeServiceAccessor.GetStartupType`,
`FakeRestorePointService.Calls`) y se ha comprobado que cada tipo es asignable al
fake (`FakeRegistryAccessor.SupportedKinds` incluye `QWord` y `String`).

**Cambio de criterio respecto del paso 9, declarado:** en §10 todas las
capacidades quedaron en `Restore=SessionUndo` porque todas eran de HKCU. Aquí hay
capacidades de HKLM con `Risk=Medium`/`High`, y ADR-0003 exige
`Restore >= RestorePoint` en esos casos; se ha seguido la regla
(`RestorePoint` en las cuatro afectadas) en vez de forzar `SessionUndo`, y eso
obliga a que el motor cree punto de restauración antes de escribir. Está probado
en `TestWave3Catalog_RestorePointIsRequiredBeforeTouchingHklm`.

## Ficheros

```
catalog/capabilities/section9_system_registry.json    | nuevo: 18 capacidades / 39 acciones (generado)
tools/ledger_extract/build_section9_catalog.py        | nuevo: generador; lee los literales del pin, --check
tools/ledger_extract/build_final_reconciliation.py    | 3 correcciones de mapeo (§9: 265, 308, 316) + ABSENT_OVERRIDES (§9: 278)
tools/ledger_extract/verify_catalog_coverage.py       | COMPLETED_SECTIONS=("1","2","3","9","10")
tools/ledger_extract/build_wave_plan.py               | §9 marcada cerrada con las cifras medidas (no escritas a mano)
catalog/exceptions/value-deviations.json              | 2ª desviación: system.settings-page-visibility.hide (value)
inventory/ledger/inventory-reconciliation.tsv         | §9: 27 Mapped / 29 Absent-At-Pin / 2 Header (era 28/28/2)
inventory/ledger/catalog-value-audit.tsv              | regenerado: 194 filas (antes 161)
inventory/ledger/upstream-capability-map.tsv          | regenerado: §9 con 8 covered / 3 pending
docs/reports/plan-oleadas.md                          | regenerado: §9 con 27/27 Mapped cubiertas
docs/reports/rangos-build.md                          | regenerado: 86 caps, 8 recortadas (+ system.hibernation.hide)
docs/reports/matriz-cobertura.md                      | regenerado con la conciliación nueva
docs/requirements/CONCILIACION_INVENTARIO.md          | regenerado (Mapped 152, Absent-At-Pin 323)
tests/Evo.Catalog.Tests/Wave3CatalogTests.cs          | nuevo: 15 xUnit de catálogo
tests/Evo.Engine.Tests/Wave3EngineTests.cs            | nuevo: 11 xUnit de motor contra fakes
tests/test_paso10.py                                  | nuevo: 16 pruebas Python
tests/test_paso8b.py, test_paso8c.py, test_paso9.py   | cifras de referencia puestas al día (68→86, 55→82, 68→86 caps)
.github/workflows/ledger-verify.yml                   | nuevo job «Paso 10»: doble ejecución + sha256 + --check + gate de cifras
```

Los informes de pasos anteriores (`paso8*.md`, `paso9.md`) **no** se han tocado:
son el acta de lo que se midió entonces.

## Comandos con salida real

Generación del catálogo desde el pin (idempotente, `--check` compara byte a byte):

```
$ python3 tools/ledger_extract/build_section9_catalog.py
capacidades: 18 | acciones: 39
$ python3 tools/ledger_extract/build_section9_catalog.py --check
section9_system_registry.json reproducible: OK (18 capacidades)
```

Cobertura del inventario:

```
$ python3 tools/ledger_extract/verify_catalog_coverage.py
capacidades del catalogo : 86
lineas Mapped 1+2+3+9+10 : 82
  cubiertas             : 82
  huecos declarados     : 0 (de 0 declarados)
  seccion 1: 3 Mapped, 3 cubiertas, 0 huecos
  seccion 2: 17 Mapped, 17 cubiertas, 0 huecos
  seccion 3: 6 Mapped, 6 cubiertas, 0 huecos
  seccion 9: 27 Mapped, 27 cubiertas, 0 huecos
  seccion 10: 29 Mapped, 29 cubiertas, 0 huecos

veredicto: OK
```

Auditoría de valores contra los pins:

```
$ python3 tools/ledger_extract/audit_catalog_values.py
acciones de registro auditadas : 194
  distribucion                 : {'differs': 1, 'equals-apply': 168, 'equals-off': 1, 'equals-on': 19, 'no-source': 5}
  por seccion del catalogo     : {'1': 3, '10': 56, '2': 80, '3': 22, '9': 33}
  excepciones declaradas       : 2
  sin excepcion (debe ser 0)   : 0

veredicto: OK
```

Informes regenerados (los tres con `--check` reproducible):

```
$ python3 tools/ledger_extract/build_wave_plan.py --check
plan-oleadas.md reproducible: OK
$ python3 tools/ledger_extract/build_build_ranges_report.py --check
rangos-build.md reproducible: OK
$ python3 tools/ledger_extract/generate_coverage_matrix.py
filas  : 588  estados: 5  secciones: 17
  Mapped 152 / Mapped-To-App 5 / EVO-Exclusive 37 / Absent-At-Pin 323 / Informative-Header 71
```

Fila de la Sección 9 en el plan de oleadas (medida, no estimada):

```
| § | Título | Líneas | Mapped | Mapped-To-App | EVO-Exclusive | Absent-At-Pin | Informative | Mapped cubiertas | Mapped sin cubrir | Trabajo (medido) | Pending upstream |
| 9 | Registro de Windows y configuración del sistema | 58 | 27 | 0 | 0 | 29 | 2 | 27 | 0 | 29 | 3 |
```

Doble ejecución de los generadores y `diff` de sha256 (simulado en local con el
mismo bucle del job; el CI lo repite en `paso10-sha-run1.txt` contra
`paso10-sha-run2.txt`, idénticos):

```
1113394d11c196561b581e2ff42ef3f883216512f0ff3f37db56f77ac5fea9f8  catalog/capabilities/section9_system_registry.json
28e5521de1f1b4ef04e86165adf81781094dbea45643a32df8c507579804ee57  inventory/ledger/catalog-value-audit.tsv
5ab76db21473d638514d6c764169dc263a751d029b8b58cd29dd5df0dc367268  inventory/ledger/upstream-capability-map.tsv
bc188fdc0abe5e1931de3d847b6585a4c47506242f849981f21af17e0e910880  inventory/ledger/inventory-reconciliation.tsv
0b02e67a19096463aacd11c856fca751ee400a74fc953c529ec30cdbbedf4b50  docs/reports/matriz-cobertura.md
8b03c72dbd5748a535a72889f30a919e6caf8cd2c1080d142e261d395bf7576e  docs/reports/plan-oleadas.md
e1c004f80e9d2a13d2528b09a29c52e45df60de920e0c4b78ae951d241bae1ce  docs/reports/rangos-build.md
```

Suites completas:

```
$ python3 -m pytest tools/ledger_extract/tests tests -q
518 passed
```

## Las 18 capacidades (medido del JSON)

```
id                                    | risk   | sec      | priv  | restore      | conf                   | state       | acc | builds
system.error-reporting.crash-control  | Medium | Reduces  | Admin | RestorePoint | Summary                | Implemented |  5  | 19045,22631,26100,26200
system.error-reporting.wpbt-disable   | Medium | Improves | Admin | RestorePoint | Summary                | Implemented |  1  | 19045,22631,26100,26200
system.game-mode.enable               | Safe   | Neutral  | User  | SessionUndo  | None                   | Implemented |  2  | 19045,22631,26100,26200
system.hibernation.hide               | Low    | Neutral  | Admin | SessionUndo  | SimpleClick            | Implemented |  1  | 22631,26100,26200
system.keyboard-shortcuts.disable     | Safe   | Neutral  | User  | SessionUndo  | None                   | Implemented |  3  | 19045,22631,26100,26200
system.location.consent-deny          | Low    | Improves | Admin | SessionUndo  | SimpleClick            | Implemented |  2  | 19045,22631,26100,26200
system.menu-delay.disable             | Safe   | Neutral  | User  | SessionUndo  | None                   | Implemented |  1  | 19045,22631,26100,26200
system.mitigations.disable            | High   | Reduces  | Admin | RestorePoint | SummaryAndRestorePoint | Implemented |  4  | 19045,22631,26100,26200
system.mouse-acceleration.enable      | Safe   | Neutral  | User  | SessionUndo  | None                   | Implemented |  3  | 19045,22631,26100,26200
system.oem-information.identify       | Safe   | Neutral  | Admin | SessionUndo  | None                   | Implemented |  3  | 19045,22631,26100,26200
system.registry-backup.enable         | Safe   | Improves | Admin | SessionUndo  | None                   | Specified   |  2  | 19045,22631,26100,26200
system.search-indexing.disable        | Low    | Neutral  | Admin | SessionUndo  | SimpleClick            | Implemented |  1  | 19045,22631,26100,26200
system.services.manual-profile        | Low    | Improves | Admin | SessionUndo  | SimpleClick            | Implemented |  5  | 19045,22631,26100,26200
system.settings-page-visibility.hide  | Low    | Neutral  | Admin | SessionUndo  | SimpleClick            | Implemented |  1  | 19045,22631,26100,26200
system.sleep.s0-network-keep          | Safe   | Neutral  | User  | SessionUndo  | None                   | Implemented |  1  | 19045,22631,26100,26200
system.sleep.s3-enable                | Medium | Neutral  | Admin | RestorePoint | Summary                | Implemented |  1  | 19045,22631,26100,26200
system.time.ntp-servers               | Low    | Neutral  | Admin | SessionUndo  | SimpleClick            | Specified   |  2  | 19045,22631,26100,26200
system.time.utc-rtc                   | Low    | Neutral  | Admin | SessionUndo  | SimpleClick            | Implemented |  1  | 19045,22631,26100,26200
Todas: reversibility=Reversible, conflictsWith=[], dependsOn=[], variantes Evo + (Atlas|WinUtil)
```

Las 16 de Atlas llevan `Variants=[Evo, Atlas]`; las 8 de WinUtil,
`Variants=[Evo, WinUtil]` (una capacidad puede citar ambos orígenes cuando el pin
los tiene, y aquí no ocurre).

## Las 4 correcciones de la conciliación de §9

```
linea | antes                             | ahora                                    | evidencia
------+-----------------------------------+------------------------------------------+-----------------------------------------------
265   | Mapped → atlas:effect:…Tests.ps1  | Mapped → winutil:tweak:WPFTweaksServices | config/tweaks.json: CscService, DiagTrack, MapsBroker, StorSvc, SharedAccess
278   | Mapped → WPFToggleLoginBlur       | Absent-At-Pin                            | tweaks.json sólo tiene "System Tray Notifications" y "System Tray Battery Percentage"; xaml/ sin página de bandeja
308   | Mapped → WPFToggleNumLock         | Mapped → atlas:toggle:KeyboardShortcuts  | Toggles/Interface/KeyboardShortcuts.psd1 (Hotkey/Language Hotkey/Layout Hotkey)
316   | Mapped → WPFTweaksTelemetry:7     | Mapped → atlas:manifest:qol/set-hidden-settings-pages | Scripts/Tweaks/qol/set-hidden-settings-pages.ps1 ($key + $value)
```

Se aplican por `(seccion, linea)` en `build_final_reconciliation.py`
(`MAPPED_OVERRIDES` para las tres que pasan a un mapeo medido y
`ABSENT_OVERRIDES` para la que deja de estar implementada), sin relajar ninguna
regla ni tocar el texto del inventario. `265` no es un `Absent`: su `mapped_id`
anterior citaba un artefacto de las **pruebas** de Atlas
(`tests/Atlas.Toggles.Tests.ps1`), que no es producto; la línea dice «Services.»
y el pin tiene `WPFTweaksServices` con cinco servicios medidos.

## Criterios U0–U6

```
U0 | Estado de partida impreso y verificable                 | CUMPLIDO
   |   HEAD 830290c, inventario 0b6aeaef…f709 intacto, pytest 502, xUnit 161, §9 58 líneas (28 Mapped) / 11 ítems, 15 Mapped sin cubrir: todo medido antes de tocar nada
U1 | Generador reproducible (nada a mano, --check byte a byte) | CUMPLIDO
   |   build_section9_catalog.py lee los literales de los pins; `--check` OK; doble ejecución con sha256 idéntico en 7 artefactos
U2 | Cobertura 100% de las líneas Mapped de §9                | CUMPLIDO
   |   27/27 cubiertas, 0 huecos no declarados, veredicto OK; 15 ya cubiertas por §2/§3/§10 no se duplican
U3 | Ledgers sin ambigüedad                                  | CUMPLIDO
   |   auditoría 194 filas, 0 ambiguous, 0 sin justificar; 2 desviaciones declaradas con evidencia; upstream-capability-map §9 con 8 covered / 3 pending explicados
U4 | xUnit nuevos y suite por encima de la base              | PENDIENTE DEL CI
   |   26 xUnit nuevos (15 catálogo + 11 motor); total previsto 187 > 161, a confirmar en windows-2025 y windows-11-arm
U5 | tests/test_paso10.py >= 15 y suite completa > 502       | CUMPLIDO
   |   16 pruebas nuevas; 518 passed en el sandbox
U6 | Determinismo y mensaje de commit convencional           | CUMPLIDO
   |   dos ejecuciones con sha256 idéntico (job «Paso 10»), --check en los tres generadores; commit `feat: paso 10 - oleada 3 catalogo seccion 9 registro y sistema`
```

## Desviaciones

1. **`system.mouse-acceleration.enable` se llama «activar», no «desactivar».**
   La casilla de WinUtil (`WPFToggleMouseAcceleration`) escribe
   `MouseSpeed=1`/`MouseThreshold1=6`/`MouseThreshold2=10`, que es el estado de
   aceleración **activa** (y el valor por defecto de Windows). El paso 10 tenía
   previsto una capacidad «desactivar la aceleración», pero el pin no la ofrece:
   se declara el efecto real con el nombre correcto en lugar de invertir el
   significado del valor. Si EVO quiere la capacidad contraria (`MouseSpeed=0`,
   `MouseThreshold*=0`), es una capacidad EVO-Exclusive, no una copia del pin.
2. **`system.hibernation.hide` sólo vale de 22631 en adelante.** El pin escribe
   `ShowHibernateOption=0` en `Explorer\FlyoutMenuSettings`, que es la clave del
   menú de energía de Windows 11; en 19045 el valor se escribe pero Windows no lo
   lee. Se recorta `supportedBuilds` y la procedencia lo justifica
   (`rangos-build.md` lo lista como recortada).
3. **Dos capacidades quedan en `Specified` aunque escriben sus valores.** El pin
   hace, además del registro, algo que el motor no sabe hacer:
   `system.time.ntp-servers` arranca el servicio `w32time` y ejecuta
   `w32tm /config /update` y `/resync`; `system.registry-backup.enable` registra
   la tarea `AutoRegBackup` con `Register-ScheduledTask` (crear una tarea no es
   una `TaskAction`, que sólo habilita/deshabilita). En ambos casos la capacidad
   declara los valores de registro, la `provenance` dice exactamente qué parte no
   se aplica y los tests fijan esa lista
   (`TestWave3Catalog_SpecifiedCapabilitiesSayWhatIsMissing`).
4. **`system.settings-page-visibility.hide` sobrescribe la lista del usuario.**
   El script del pin escribe el literal completo
   `hide:recovery;maps;…;deviceusage;home` de una vez, mientras que la función
   incremental de Atlas (`Set-AtlasSettingsPageVisibility`) edita una página por
   vez conservando las demás. Se copia el literal del pin (que es lo que hace el
   `.ps1`) y se advierte en la descripción. Está declarado como desviación de
   valor en `value-deviations.json` porque la auditoría casa por (clave, nombre)
   y WinUtil escribe la misma clave con otro valor (`hide:aicomponents`).
5. **`system.location.consent-deny` no declara los servicios.** El estado
   `Disable` del toggle ejecuta `Disable-AtlasLocation`, que apaga `lfsvc` y
   `MapsBroker`; esos servicios no se declaran como `ServiceAction` porque la
   capacidad se limita a lo que el bloque `Registry` del pin dice. Queda escrito
   en la descripción y en la procedencia. Los dos servicios ya se tocan en
   `privacy.location.sensors` (§3), así que duplicarlos aquí volvería a crear la
   ambigüedad que este paso evita.
6. **`system.mitigations.disable` es `High` + `Reduces` + `RestorePoint`.** Es la
   capacidad más agresiva de la sección: desactiva mitigaciones del kernel
   (SEHOP, validación del árbol de excepciones). El motor exigirá punto de
   restauración y confirmación con resumen, y fallará cerrado si la Protección del
   sistema no está disponible. El nombre y la descripción dicen «desactivar», no
   «optimizar».
7. **`system.error-reporting.crash-control` se declara `Reduces`.** Deja el
   minidump pequeño (256 KiB) y apaga el volcado de StorageTelemetry: menos
   diagnóstico tras un fallo. Riesgo `Medium` con `RestorePoint` y la palabra
   «REDUCE» en la descripción.
8. **Asserts viejos puestos al día en tres ficheros de tests anteriores.**
   `test_paso8b` (68→86 capacidades), `test_paso8c` (cobertura 55→82),
   `test_paso9` (secciones terminadas, 68→86 caps, 55→82 líneas, 1→2
   desviaciones, informe de rangos 78/8). Ninguno se relajó en lo que protegía:
   cada uno lleva el comentario de qué cambió y por qué.
9. **El job «Paso 9» se ha vuelto tolerante en una sola comparación.** Su gate
   comparaba `cov["capacidades"] == 68`; ahora comprueba `>= 68` (ese job mide la
   sección 10, no el tamaño del catálogo) y el gate estricto de las cifras vive en
   el job nuevo «Paso 10», que sí fija 86 y 27/27.

## Supuestos

- **El pin manda.** Los valores se copian del `.psd1` o del `tweaks.json` del SHA
  fijado; la `provenance` dice fichero y rango de líneas. Donde el pin no ofrece
  el efecto que el nombre de la fila del inventario sugiere, se declara lo que el
  pin hace (caso de la aceleración del ratón) o se deja la fila `Absent-At-Pin`
  con el motivo medido (caso de la bandeja del sistema).
- **§9 no reutiliza capacidades de otras secciones.** Quince líneas `Mapped` de
  §9 ya las cubrían capacidades de §2/§3/§10; crear duplicados habría roto
  `audit_catalog_values` (ids repetidos) y la propia idea de «cobertura». Esas
  quince se dejan donde están y el verificador lo demuestra (`82/82` con 0
  huecos).
- **`Implemented` significa «el motor la ejecuta contra fakes con tests»**, no
  «probada en un Windows real». La verificación en máquina real sigue pendiente y
  el catálogo no la promete.
- **Los 11 ítems de §9 en `item-section-map.tsv`** no se tocan: la sección por
  ítem es del paso 8d y su generador es determinista; este paso sólo consume las
  líneas del inventario. 8 de esos 11 quedan `covered` y 3 `pending`, y el motivo
  está escrito en el plan: la indización es una acción de TrustedInstaller, la
  página «workplace» se edita de forma incremental y el panel de fecha y hora sólo
  abre `timedate.cpl`.

## Riesgos

- **`system.mitigations.disable` es la capacidad más peligrosa del catálogo
  hasta ahora.** Desactiva mitigaciones del kernel y exige reinicio. Mitigación:
  `High` + `SummaryAndRestorePoint` + `RestorePoint`, y el motor falla cerrado sin
  Protección del sistema (probado). Aun así, conviene que la UI la agrupe aparte y
  no la ofrezca en un preset.
- **`system.settings-page-visibility.hide` oculta páginas de privacidad** y
  sobrescribe la lista previa del usuario. Es reversible por el diario (el valor
  previo se guarda entero), pero el usuario puede no saber qué había antes.
- **`system.services.manual-profile` toca cinco servicios con un solo clic.** Un
  fallo a mitad deja el perfil incompleto; el diario lo deshace servicio a
  servicio y hay test de ida y vuelta
  (`TestWave3Catalog_ServicesChangeStartupAndRollBack`).
- **El CI de .NET es el único que compila.** Los 26 xUnit nuevos se han
  revisado a mano contra las APIs reales, pero un fallo de compilación sólo lo
  verá `dotnet-ci`; el job «Paso 10» de `ledger-verify` no compila.
- **`inventory-reconciliation.tsv` cambia de sha** (`c35c1791` → `bc188fdc`):
  cualquier documento que citara el sha anterior queda desfasado. Se ha
  regenerado la matriz y la conciliación; los informes de pasos anteriores se
  dejan como acta y citan el sha que había entonces.

## Preguntas abiertas

1. **¿Se añade la capacidad contraria a la aceleración del ratón?** El pin sólo
   ofrece activarla. Una capacidad EVO («desactivar aceleración»,
   `MouseSpeed=0`) sería EVO-Exclusive y no copia de upstream: decide el titular.
2. **¿Debe el motor aprender a crear tareas programadas?** Eso convertiría
   `system.registry-backup.enable` en `Implemented` (hoy `Specified` porque el pin
   registra `AutoRegBackup`). Sin eso, la copia diaria del registro no ocurre
   aunque los valores estén escritos.
3. **¿Debe el motor poder arrancar servicios?** `system.time.ntp-servers` quedaría
   completa con un `ServiceAction` de `Start` sobre `w32time` y un
   `CommandAction` para `w32tm /resync` (ambos existen ya en el motor: el pin usa
   `IgnoreErrors`, que se traduce directo a `IgnoreExitCode`).
4. **¿La visibilidad de páginas debe ser incremental?** Hoy se copia el literal
   completo del pin (sobrescribe). Una versión incremental (leer, añadir la
   página, escribir) es más segura para el usuario, pero se aleja del `.ps1` y
   necesita una acción que no es «escribir un valor fijo».
5. **¿§9 está realmente cerrada?** Quedan **3 ítems de upstream** con
   `section_guess=9` en `pending` (Indexing, Workplace, panel de fecha y hora) y
   **29 líneas `Absent-At-Pin`** en el inventario. El inventario está al 100 % de
   lo mapeable; el upstream no, y ninguna de las tres pendientes es un valor de
   registro fijo.

## Commit

Rama `arena/ab2d6de7-evo-optimizer-on`, un commit (el PR #1 sigue **en draft**):

```
feat: paso 10 - oleada 3 catalogo seccion 9 registro y sistema
```

PR #1 (`gh api -X PATCH …/pulls/1`): título «Paso 10 — Oleada 3: catálogo de la
Sección 9 (Registro y configuración del sistema), 18 capacidades / 39 acciones»,
`state=OPEN`, `isDraft=true`. El estado del CI de este paso se anota al final del
informe en cuanto `dotnet-ci` y `ledger-verify` terminan; hasta entonces los
criterios U4 queda declarado como pendiente y no como cumplido.
