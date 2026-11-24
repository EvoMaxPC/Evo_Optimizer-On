# PASO 9 — Oleada 2 del catálogo: Sección 10 (Explorador de archivos e interfaz)

Fecha: 2026-11-24 (reloj del agente, UTC). Rama `arena/ab2d6de7-evo-optimizer-on`.
Pins: Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`,
WinUtil `70c23c80641d7370532af2f619b2842658600842`.

## T0 — Estado de partida (medido antes de tocar nada)

```
git rev-parse HEAD                          | 55c1bb4f75f80c3df4176dc0e416fe0e6e91086f
git ls-remote origin (rama de trabajo)      | 55c1bb4f75f80c3df4176dc0e416fe0e6e91086f
git ls-remote origin refs/heads/main        | 402af190e10a120dc893fa74f0a1d7b7d55b0c75
git ls-remote origin refs/pull/1/head       | 55c1bb4f75f80c3df4176dc0e416fe0e6e91086f
sha256 inventory/ledger/inventory-recon…   | c35c1791056f4348a664b91f1299d56f0df0cfd2c2209412cfe712e8b1f8a46a
sha256 docs/requirements/INVENTARIO_USUARIO.md | 0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709
pytest (línea base)                         | 479 passed
xUnit (línea base, CI run 45334353337)      | 144 passed / 0 failed (windows-2025 y windows-11-arm)
Sección 10 en inventory-reconciliation.tsv  | 48 líneas: 25 Mapped / 21 Absent-At-Pin / 2 Informative-Header
Ítems de Sección 10 en item-section-map.tsv  | 143 (81 atlas-manifest, 30 atlas-toggle, 32 winutil)
```

El SHA de `INVENTARIO_USUARIO.md` es el de partida y **no se ha modificado**: al
cierre del paso sigue siendo `0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709`.

## Resumen

La Sección 10 (EXPLORADOR DE ARCHIVOS E INTERFAZ) queda catalogada: **29
capacidades y 56 acciones**, generadas desde los dos pins por
`tools/ledger_extract/build_section10_catalog.py` (ningún literal escrito a mano,
ningún JSON editado a mano). El verificador de cobertura pasa de 26/26 a
**55/55** líneas `Mapped` cubiertas (3 de §1 + 17 de §2 + 6 de §3 + 29 de §10),
con **0 huecos no declarados** y **0 huecos declarados** (no hace falta declarar
ninguno: los seis que el paso 4e daba por `Absent-At-Pin` resultaron ser `Mapped`
y se corrigieron en la conciliación con justificación línea a línea).

Cifras al cierre, todas medidas:

```
capacidades del catálogo | 68 (39 de las secciones 1-3 + 29 de la sección 10)
acciones de la sección 10 | 56 en 29 capacidades (máx. 11 en ui.visual-effects.minimal)
verificador de cobertura  | 55 Mapped, 55 cubiertas, 0 huecos, veredicto OK
auditoría de valores      | 161 filas, 145 equals-apply / 12 equals-on / 1 equals-off / 3 no-source, 0 ambiguous, 0 sin justificar
pytest                    | 502 passed (línea base 479; +23 de tests/test_paso9.py)
xUnit                     | 161 passed / 0 failed en windows-2025 y windows-11-arm (línea base 144; +17)
```

## T0-bis — Cómo se trabajó (y un aviso de honestidad)

El sandbox **no tiene dotnet**: toda la parte .NET se ha validado por el CI real
(`.github/workflows/dotnet-ci.yml`, runners `windows-2025` y `windows-11-arm`) y
leyendo el informe publicado en la rama `ci-report`. El CI encontró tres defectos
reales que el sandbox no podía ver y que ya están corregidos (ver Desviaciones).

A mitad del paso el sandbox se reinició y `/tmp/upstream` desapareció: se
recuperó con `tools/ledger_extract/fetch_upstream.py --dest /tmp/upstream`
(método `fetch --depth 1 <sha>`, ambos pins verificados por `rev-parse`).

## Ficheros

```
catalog/capabilities/section10_explorer_ui.json        | nuevo: 29 capacidades / 56 acciones (generado)
tools/ledger_extract/build_section10_catalog.py        | nuevo: generador; lee los literales del pin, --check
tools/ledger_extract/build_build_ranges_report.py      | nuevo: genera docs/reports/rangos-build.md, --check
tools/ledger_extract/verify_catalog_coverage.py        | COMPLETED_SECTIONS=("1","2","3","10"); supporters_of_row() compartido
tools/ledger_extract/build_final_reconciliation.py     | MAPPED_OVERRIDES: 6 líneas de §10 corregidas (326,339,341,343,344,347)
tools/ledger_extract/audit_catalog_values.py           | estados de Toggles, binarios base64, recuento por sección
tools/ledger_extract/build_wave_plan.py                | usa supporters_of_row(); §10 marcada cerrada; cifras no escritas a mano
catalog/exceptions/value-deviations.json               | queda con 1 excepción (debloat.settings.home); la redundante se retiró
inventory/ledger/inventory-reconciliation.tsv          | 6 filas de §10 pasan de Absent-At-Pin a Mapped
inventory/ledger/catalog-value-audit.tsv               | regenerado: 161 filas (antes 121)
inventory/ledger/upstream-capability-map.tsv           | regenerado
docs/reports/plan-oleadas.md                           | regenerado: §10 con 29/29 Mapped cubiertas
docs/reports/rangos-build.md                           | regenerado desde el catálogo (68 caps, 7 recortadas)
docs/reports/matriz-cobertura.md                       | regenerado con el sha de conciliación nuevo
docs/requirements/CONCILIACION_INVENTARIO.md           | regenerado (Mapped 153, Absent-At-Pin 322)
tests/Evo.Catalog.Tests/Wave2CatalogTests.cs           | nuevo: 11 xUnit de catálogo
tests/Evo.Engine.Tests/Wave2EngineTests.cs             | nuevo: 6 xUnit de motor contra fakes
tests/test_paso9.py                                    | nuevo: 23 pruebas Python
tests/Evo.Catalog.Tests/Wave1CatalogTests.cs           | 68 capacidades; SecurityImpact Neutral o Improves (recorre todo el catálogo)
tests/test_paso8b.py, test_paso8c.py, test_paso8d.py   | cifras de referencia puestas al día (39→68, 26→55, §10 excluida del assert de rangos de 1-3)
.github/workflows/ledger-verify.yml                    | nuevo job «Paso 9»: doble ejecución + sha256 + --check + gate de cifras
```

Documentos de pasos anteriores (`paso8*.md`) **no** se han tocado: son el acta de
lo que se midió entonces.

## Comandos con salida real

Generación del catálogo desde el pin (idempotente, `--check` compara byte a byte):

```
$ python3 tools/ledger_extract/build_section10_catalog.py
capacidades: 29 | acciones: 56
$ python3 tools/ledger_extract/build_section10_catalog.py --check
section10_explorer_ui.json reproducible: OK (29 capacidades)
```

Cobertura del inventario:

```
$ python3 tools/ledger_extract/verify_catalog_coverage.py
capacidades del catalogo : 68
lineas Mapped 1+2+3+10   : 55
  cubiertas             : 55
  huecos declarados     : 0 (de 0 declarados)
  seccion 1: 3 Mapped, 3 cubiertas, 0 huecos
  seccion 2: 17 Mapped, 17 cubiertas, 0 huecos
  seccion 3: 6 Mapped, 6 cubiertas, 0 huecos
  seccion 10: 29 Mapped, 29 cubiertas, 0 huecos

veredicto: OK
```

Auditoría de valores contra los pins:

```
$ python3 tools/ledger_extract/audit_catalog_values.py
acciones de registro auditadas : 161
  distribucion                 : {'equals-apply': 145, 'equals-off': 1, 'equals-on': 12, 'no-source': 3}
  por seccion del catalogo     : {'1': 3, '10': 56, '2': 80, '3': 22}
  excepciones declaradas       : 1
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
informe: docs/reports/matriz-cobertura.md
filas  : 588  estados: 5  secciones: 17
  Mapped 153 / Mapped-To-App 5 / EVO-Exclusive 37 / Absent-At-Pin 322 / Informative-Header 71
```

Fila de la Sección 10 en el plan de oleadas (medida, no estimada):

```
| § | Título | Líneas | Mapped | Mapped-To-App | EVO-Exclusive | Absent-At-Pin | Informative | Mapped cubiertas | Mapped sin cubrir | Trabajo (medido) | Pending upstream |
| 10 | Explorador de archivos e interfaz | 48 | 29 | 0 | 0 | 17 | 2 | 29 | 0 | 17 | 105 |
```

Suites completas (sandbox y CI):

```
$ python3 -m pytest tools/ledger_extract/tests tests -q
502 passed

CI run 45480164634 (sha b7a9201) — .github/workflows/dotnet-ci.yml
  windows-2025     : total=161 passed=161 failed=0
                     Evo.Catalog.Tests 47 · Evo.Core.Tests 34 · Evo.Detection.Tests 35 · Evo.Engine.Tests 45
  windows-11-arm   : total=161 passed=161 failed=0
CI run 45480164499 — .github/workflows/ledger-verify.yml
  pytest: 502 passed, 3 warnings  (pytest_exit=0)
  determinismo paso 9: OK
```

Doble ejecución de los generadores y `diff` de sha256 en CI (`paso9-sha-run1.txt`
contra `paso9-sha-run2.txt`, idénticos):

```
58f20e75a1e4395b42eb8b54830cd8ee03089c08d6a303449bd5028195c6df0d  catalog/capabilities/section10_explorer_ui.json
7559075e5ed0f17f0396c30b0ae2d8fefbd6fc86668227eff9bb34030a382b45  inventory/ledger/catalog-value-audit.tsv
8ef75995221e55e02f052f57b8d13515dbb87c45d1b005e148a13eb3043e717f  inventory/ledger/upstream-capability-map.tsv
c35c1791056f4348a664b91f1299d56f0df0cfd2c2209412cfe712e8b1f8a46a  inventory/ledger/inventory-reconciliation.tsv
4fff6979e66f6ff73ea69b6584a4a28367623cdb2783fb3b7bb2e69ee18d3ce6  docs/reports/matriz-cobertura.md
e2a76817bf9ba61dabaec84439c7af85299de213bc53a32ff830bcc9e788c5ae  docs/reports/plan-oleadas.md
f5fb23afd959823050c2a882834bdf9ade85685159b6995978363c479c217934  docs/reports/rangos-build.md
```

## Las 29 capacidades (medido del JSON)

```
id                                  | risk | sec    | priv  | conf        | builds                     | acc | variantes
explorer.app-icon-thumbnails.hide   | Safe | Neutral| User  | None        | 19045,22631,26100,26200    |  1  | Evo,Atlas
explorer.check-boxes.disable        | Safe | Neutral| User  | None        | 19045,22631,26100,26200    |  1  | Evo,Atlas
explorer.compact-view.enable        | Safe | Neutral| User  | None        | 19045,22631,26100,26200    |  1  | Evo,Atlas
explorer.extract-context-menu.add   | Safe | Neutral| Admin | None        | 19045,22631,26100,26200    |  4  | Evo,Atlas
explorer.file-extensions.show       | Safe | Improves| User | None        | 19045,22631,26100,26200    |  1  | Evo,WinUtil
explorer.gallery.hide               | Safe | Neutral| User  | None        | 22631,26100,26200          |  1  | Evo,Atlas
explorer.hidden-files.show          | Safe | Improves| User | None        | 19045,22631,26100,26200    |  1  | Evo,WinUtil
explorer.home.hide                  | Low  | Neutral| User  | SimpleClick | 22631,26100,26200          |  2  | Evo,Atlas
explorer.long-paths.enable          | Low  | Neutral| Admin | SimpleClick | 19045,22631,26100,26200    |  1  | Evo,Atlas
explorer.quick-access.hide          | Safe | Neutral| Admin | None        | 19045,22631,26100,26200    |  1  | Evo,Atlas
explorer.recent-items.disable       | Low  | Improves| Admin| SimpleClick | 19045,22631,26100,26200    |  9  | Evo,Atlas
explorer.removable-drives.sidebar   | Safe | Neutral| Admin | None        | 19045,22631,26100,26200    |  2  | Evo,Atlas
explorer.shortcut-icon.classic      | Safe | Neutral| Admin | None        | 19045,22631,26100,26200    |  1  | Evo,Atlas
explorer.shortcut-text.hide         | Safe | Neutral| User  | None        | 19045,22631,26100,26200    |  1  | Evo,Atlas
ui.context-menu.classic             | Low  | Neutral| User  | SimpleClick | 22631,26100,26200          |  1  | Evo,Atlas,WinUtil
ui.lockscreen.hide                  | Low  | Neutral| Admin | SimpleClick | 19045,22631,26100,26200    |  1  | Evo,WinUtil
ui.logon.acrylic-blur               | Safe | Neutral| Admin | None        | 19045,22631,26100,26200    |  1  | Evo,WinUtil
ui.notifications.center-hide        | Low  | Neutral| User  | SimpleClick | 19045,22631,26100,26200    |  2  | Evo,WinUtil
ui.numlock.startup                  | Safe | Neutral| Admin | None        | 19045,22631,26100,26200    |  2  | Evo,WinUtil
ui.scrollbars.always-visible        | Safe | Neutral| User  | None        | 19045,22631,26100,26200    |  1  | Evo,WinUtil
ui.snap-layouts.disable             | Safe | Neutral| User  | None        | 19045,22631,26100,26200    |  2  | Evo,Atlas
ui.snapping.windows                 | Safe | Neutral| User  | None        | 19045,22631,26100,26200    |  1  | Evo,WinUtil
ui.taskbar.end-task                 | Low  | Neutral| User  | SimpleClick | 22631,26100,26200          |  1  | Evo,WinUtil
ui.taskbar.icons-centered           | Safe | Neutral| User  | None        | 22631,26100,26200          |  1  | Evo,WinUtil
ui.taskbar.search-icon              | Safe | Neutral| User  | None        | 19045,22631,26100,26200    |  1  | Evo,WinUtil
ui.taskbar.task-view-button         | Safe | Neutral| User  | None        | 19045,22631,26100,26200    |  1  | Evo,WinUtil
ui.theme.dark                       | Safe | Neutral| User  | None        | 19045,22631,26100,26200    |  2  | Evo,WinUtil
ui.verbose-messages.enable          | Safe | Neutral| Admin | None        | 19045,22631,26100,26200    |  1  | Evo,Atlas
ui.visual-effects.minimal           | Low  | Neutral| User  | SimpleClick | 19045,22631,26100,26200    | 11  | Evo,Atlas
Todas: state=Implemented, reversibility=Reversible, restore=SessionUndo, conflictsWith=[], dependsOn=[]
```

Privilegio `Admin` (10): `explorer.extract-context-menu.add`,
`explorer.long-paths.enable`, `explorer.quick-access.hide`,
`explorer.recent-items.disable`, `explorer.removable-drives.sidebar`,
`explorer.shortcut-icon.classic`, `ui.lockscreen.hide`, `ui.logon.acrylic-blur`,
`ui.numlock.startup`, `ui.verbose-messages.enable` — todas escriben HKLM o HKU.

## Las 6 líneas de §10 que pasan de `Absent-At-Pin` a `Mapped`

```
linea | id que la cubre                                 | por qué estaba mal y por qué ahora es Mapped
326   | winutil:tweak:WPFTweaksRightClickMenu           | Set-WinUtilClassicContextMenu.ps1 escribe el CLSID {86ca1aa0-…} (tweaks.json:1172); el paso 4e no cruzaba el script
339   | atlas:toggle:AppIconThumbnail                   | ShowTypeOverlay=0 en el estado Disable del toggle
341   | atlas:toggle:CompactView                        | UseCompactMode=1 en el estado Enable del toggle
343   | winutil:tweak-op:WPFTweaksEdgeDebloat:registry:0| efecto en Edge ya Mapped en 9:291; la línea es la misma op
344   | atlas:toggle:ExtractContextMenu                 | Context Menus\Extract: 4 Delete en Shell Extensions\Blocked
347   | winutil:tweak-op:WPFToggleNumLock:registry:0    | único efecto de la familia de atajos del Toggle de Bloq Num
```

Se corrigieron con `MAPPED_OVERRIDES` (por `(seccion, linea)`, no relajando la
regla ni tocando el texto del inventario).

## Criterios U0–U6

```
U0 | Estado de partida impreso y verificable                | CUMPLIDO
   |   HEAD 55c1bb4, sha del inventario 0b6aeaef…f709, pytest 479, xUnit 144, §10 48 líneas / 143 ítems, todo medido antes de tocar nada
U1 | Catálogo §10 con el contrato estricto de ADR-0003       | CUMPLIDO
   |   29 capacidades explorer.*/ui.*, Id ^[a-z0-9]+(\.[a-z0-9\-]+)+$, Risk/SecurityImpact/Privilege/Confirmation/State/Variants completos, SupportedBuilds explícito en las 29
U2 | Semántica Toggle 8c y desviaciones declaradas           | CUMPLIDO
   |   cada .psd1 de Toggles se cita con su estado; value-deviations.json queda con la única desviación real (debloat.settings.home, switch-meaning)
U3 | Cobertura 100% de las líneas Mapped de §10              | CUMPLIDO
   |   29/29 cubiertas, 0 huecos no declarados, veredicto OK; auditoría 0 ambiguous / 0 sin justificar
U4 | xUnit nuevos + suite completa por encima de la base     | CUMPLIDO
   |   144 → 161 xUnit (17 nuevos), 161/161 en windows-2025 y windows-11-arm; carga y validación estricta, ADR-0003, restricción de build, Execute/SessionUndo contra FakeRegistryAccessor
U5 | tests/test_paso9.py ≥15 y suite completa > 479          | CUMPLIDO
   |   23 pruebas nuevas (pedidas ≥15); 502 passed en sandbox y en CI
U6 | Determinismo (doble ejecución + diff) y PR en draft     | CUMPLIDO
   |   dos ejecuciones seguidas con sha256 idéntico en 7 artefactos (job «Paso 9»), --check en los tres generadores; PR #1 sigue draft, PATCH aplicado
```

## Desviaciones

1. **`ui.lockscreen.hide` no se declara `SecurityImpact=Reduces`.** Se valoró
   declararlo (quitar la pantalla de bloqueo reduce una capa), pero el motor
   exige para `Reduces` riesgo >= Medium y por tanto `RestorePoint`, y la capa
   que se quita es la imagen del bloqueo, no la autenticación (Win+L sigue
   pidiendo credenciales). Queda `Neutral`/`Low`/`SimpleClick` con la decisión y
   su motivo escritos en la `description` de la capacidad, y probado en
   `test_omitir_la_pantalla_de_bloqueo_no_se_declara_como_reduccion` y en
   `TestWave2Catalog_SecurityReductionIsNeverUnderMediumRisk`. Está también en
   Preguntas abiertas: si el revisor prefiere `Reduces`+`Medium`, es un cambio de
   dos campos más `restore`.
2. **Tres defectos que sólo se ven compilando**, encontrados por el CI y
   corregidos en el mismo paso (el sandbox no tiene dotnet):
   - el generador no escribía el discriminador `"type": "registry"` en la rama de
     Atlas: el cargador estricto rechazaba el fichero entero (23 fallos);
   - por lo mismo, la auditoría de valores sólo veía **16 de las 56** acciones de
     §10 (filtraba por ese campo) y daba `ambiguous` en `UserPreferencesMask`
     porque `Data = @(0x90, …)` se capturaba a medias. Ahora audita las 56 y los
     binarios se comparan en base64, el mismo convenio que `RegistryAction.Value`;
   - el round-trip de deshacer comparaba claves y no valores: el diario deja
     atrás claves vacías que antes no existían (no había nada que restaurar). Se
     compara como en la oleada 1, valor a valor.
3. **`explorer.home.hide` y `explorer.removable-drives.sidebar` aplican la parte
   de valores y no la de claves.** Los estados del pin incluyen `DeleteKey` (borrar
   una CLAVE: `HKLM Desktop\NameSpace\{f874310e…}` y los dos
   `DelegateFolders\{F5FB2C77…}`), y el motor sólo sabe borrar valores. Las
   capacidades tienen 2 acciones cada una (valores) y la limitación está escrita
   en su `description` y en su `provenance`, no escondida.
4. **Rangos de build recortados en 5 capacidades.** 19045 no se declara en
   `explorer.gallery.hide`, `explorer.home.hide`, `ui.context-menu.classic`,
   `ui.taskbar.end-task` y `ui.taskbar.icons-centered`: las tres primeras tocan
   CLSID que Windows 10 no usa y las dos de la barra escriben claves que Windows 10
   no lee. Se retiró el recorte en `ui.taskbar.search-icon` y
   `ui.taskbar.task-view-button` porque su clave sí existe en 19045 y WinUtil no
   declara `Compatibility` para ellas: recortar sin evidencia era inventar.
5. **`value-deviations.json` baja de 2 a 1 excepciones.** La de
   `debloat.start.websearch` dejó de ser una desviación al separar los estados de
   los Toggles de Atlas: el catálogo copia literalmente el estado `Disable`
   (`BingSearchEnabled=0`), así que mantener la excepción habría sido declarar una
   desviación que ya no existe. Se retiró y el auditor quedó en `sin excepcion: 0`
   y `excepciones obsoletas: []`.
6. **Asserts viejos puestos al día en cuatro ficheros de tests anteriores.**
   `test_paso8b` (39→68 capacidades), `test_paso8c` (cobertura 26→55 con
   desglose por sección), `test_paso8d` (el assert de rangos incompletos se limita
   a las secciones 1-3; la §10 tiene sus propias pruebas) y `Wave1CatalogTests`
   (recorre todo el catálogo, así que ahora admite `Neutral` o `Improves`). Ninguno
   se relajó en lo que protegía; cada uno lleva el comentario de qué cambió y por qué.
7. **Se añadió trabajo no pedido explícitamente, por necesidad medida:** el job
   «Paso 9» en `ledger-verify.yml` y el generador `build_build_ranges_report.py`
   (antes `docs/reports/rangos-build.md` decía 39 capacidades y ningún script lo
   regeneraba, así que habría quedado mintiendo).

## Supuestos

- **El pin manda.** Donde WinUtil y Atlas discrepan se copia el estado que el pin
  anuncia para el efecto que pide la capacidad, y la `provenance` dice cuál. No se
  ha promediado ni elegido «el valor más bonito».
- **`(predeterminado)` es un nombre de valor vacío, no un valor inventado:** en
  `ui.context-menu.classic` y `explorer.removable-drives.sidebar` se declara
  `valueName: ""`, que es lo que el `.psd1` escribe.
- **Los binarios se guardan en base64** (`UserPreferencesMask`, 8 bytes): es el
  convenio que ya usa `RegistryAction.Value` en todo el catálogo. Se verificó que
  decodifica a exactamente los 8 bytes del pin.
- **`Implemented` significa «el motor la ejecuta contra fakes con tests»**, no
  «probada en un Windows real». La verificación en máquina real sigue pendiente y
  el catálogo no la promete.
- **Los 143 ítems de §10 en `item-section-map.tsv`** no se tocan: la sección por
  ítem es del paso 8d y su generador es determinista; este paso sólo consume las
  líneas del inventario.

## Riesgos

- **`explorer.recent-items.disable` (9 escrituras de política)** y
  `ui.visual-effects.minimal` (11 acciones, incluido un binario) son las dos más
  anchas: un fallo a mitad deja el sistema en un estado intermedio. Mitigación: el
  diario guarda el valor previo de cada acción y el rollback se probó entero
  (`TestWave2Catalog_LargestCapability_RoundTrips`).
- **`ui.context-menu.classic` cambia la UI de forma muy visible** y mucha gente lo
  pide justo al revés. Está en `Low` con `SimpleClick`, pero conviene que la UI lo
  presente como preferencia reversible y no como «mejora».
- **Cinco capacidades no aplican el `DeleteKey` del pin**: el efecto real es algo
  menor que el del upstream y así está declarado. Si el motor aprende a borrar
  claves, hay que revisar esas dos capacidades y sus pruebas.
- **El CI de .NET es el único que compila.** Un cambio de catálogo puede pasar
  pytest y romper la carga estricta (ya ocurrió con el discriminador `type`). El
  job «Paso 9» de `ledger-verify` no compila; la red está en `dotnet-ci`.
- **La rama `ci-report` es un artefacto compartido:** se lee con
  `git fetch origin ci-report:refs/remotes/origin/ci-report`, nunca con
  `gh run view --log` (no funciona en este repo).

## Preguntas abiertas

1. **¿`ui.lockscreen.hide` debería ser `SecurityImpact=Reduces` con `Risk=Medium`
   y `RestorePoint`?** Hoy es `Neutral`/`Low`/`SessionUndo` y el motivo está escrito.
   Cambiarlo son dos campos más `restore`, y obligaría a pedir punto de
   restauración para escribir un valor de HKCU.
2. **¿Se asume el `DeleteKey` en el motor?** Dos capacidades de esta sección
   (Inicio y unidades extraíbles en el panel) aplican sólo la mitad del efecto del
   pin. Sin `DeleteKey` en `RegistryAction`, la otra mitad no existe en EVO; con él,
   hay que decidir cómo se deshace (volver a crear la clave con sus valores).
3. **¿`explorer.file-extensions.show` y `explorer.hidden-files.show` deben subir a
   `SecurityImpact=Improves`?** Hoy lo están por criterio propio (ver extensiones
   reales y archivos ocultos ayuda a detectar un `.exe` disfrazado). Atlas y WinUtil
   no lo declaran; si el revisor prefiere `Neutral`, es un cambio de dos campos.
4. **¿Se normaliza `ui.logon.acrylic-blur`?** La casilla de WinUtil se llama «Logon
   Screen Acrylic Blur» y su eje es el contrario al del valor
   (`DisableAcrylicBackgroundOnLogon=0` = desenfoque activo). Hoy la capacidad se
   llama «Quitar el desenfoque acrílico…» y escribe 0, con la explicación en la
   descripción. Un nombre que diga «mantener el desenfoque» sería más honesto con el
   efecto, pero rompe la correspondencia con la casilla del upstream.
5. **¿§10 está realmente cerrada?** Quedan **105 ítems de upstream** con
   `section_guess=10` en `pending` (de 435 filas del mapa): son ítems de upstream
   sin efecto propio medido (navegación, presets, paneles). El inventario está al
   100%; el upstream no. Eso es la oleada 3, no este paso.

## Commit

Rama `arena/ab2d6de7-evo-optimizer-on`, cuatro commits (el PR #1 sigue **en draft**):

```
b7a9201 fix(catalog,tests): riesgo honesto de ui.lockscreen.hide y asserts del CI
fbbf6fd fix(audit): auditar las 56 acciones de la seccion 10 (binario base64 y Data con lista)
3c4a08f fix(catalog): discriminador 'type' en las acciones de la seccion 10
3debf39 feat: paso 9 - oleada 2 catalogo seccion 10 explorador e interfaz
```

PR #1 (`gh api -X PATCH …/pulls/1`): título «Paso 9 — Oleada 2: catálogo de la
Sección 10 (Explorador e interfaz), 29 capacidades / 56 acciones», `state=open`,
`draft=true`, head `b7a9201`.

CI al cierre del paso (sha `b7a9201`):

```
dotnet-ci run 45480164634        | success | 161/161 xUnit en windows-2025 y windows-11-arm
ledger-verify run 45480164499    | success | pytest 502 passed · determinismo paso 9: OK
```
