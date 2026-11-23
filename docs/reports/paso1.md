# Paso 1 — Estructura, licencias, fijación de upstream y canal CI

Fecha: 2026-11-23 · Rama: `arena/ab2d6de7-evo-optimizer-on`
Contrato vigente: `docs/AGENT_CONTRACT.md`

## Resumen

* Estructura y contrato creados. **ANEXO B no llegó** (el mensaje traía el
  marcador `<<<PEGA AQUÍ ...>>>`): `docs/requirements/INVENTARIO_USUARIO.md`
  queda marcado NO RECIBIDO, sin inventar contenido (REQ-002).
* `LICENSE` es copia byte a byte del LICENSE de Atlas: sha256
  `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986` en ambos.
* `fetch_upstream.py` reproduce los dos SHAs del lock con `fetch --depth 1 <sha>`
  sin fallback, y es idempotente (segunda ejecución: `método: cache`, 0,07 s).
* Canal `ci-report` con 5 pruebas + 3 extra: **23 PASS / 0 FAIL** en sandbox.
* **5/5 runners publicaron** en dos runs consecutivos; 11 commits acumulados,
  sin force-push (`ad7dd85` sigue siendo ancestro).

## Árbol creado

```
docs/AGENT_CONTRACT.md                     42 líneas (ANEXO A + ERRATA-EVO-001)
docs/architecture.md                        7 (stub)
docs/adr/.gitkeep                           0
docs/reports/paso1.md                     este fichero
docs/requirements/INVENTARIO_USUARIO.md    19 (ANEXO B no recibido)
inventory/upstream.lock.json               33 (schema 1, 2 fuentes)
inventory/raw/.gitkeep + ci-reports/*      12 ficheros de evidencia (45 KB)
inventory/ledger/.gitkeep                   0
catalog/modules/.gitkeep                    0
tools/ledger_extract/fetch_upstream.py    219
tools/ci/publish-report.sh                305
tests/ci/test_publish_report.sh           196
THIRD_PARTY_NOTICES.md                     64
LICENSE                                   674 (idéntico a Atlas)
README.md, CONTRIBUTING.md                  ver repo
.github/workflows/probe.yml               285 (reemplaza la sonda anterior)
```

## Salidas reales

### fetch_upstream.py (run limpio)

```
[OK] winutil  (ChrisTitusTech/winutil)
  esperado: 70c23c80641d7370532af2f619b2842658600842
  real    : 70c23c80641d7370532af2f619b2842658600842
  método  : fetch --depth 1 <sha>
[OK] atlas  (Atlas-OS/Atlas)
  esperado: ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f
  real    : ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f
  método  : fetch --depth 1 <sha>
EXIT=0
```

Segunda ejecución (idempotencia): `método: cache` para ambas, `real 0m0.066s`.

Fallback (probado por inyección de fallo, ver desviaciones D2):

```
[fallback] depth1 por SHA rechazado: Server does not allow request for unadvertised object
ladder probado: intentos depth = [1, 50] | método declarado = fetch --depth 50 (rama por defecto)
[fallback] depth50 rechazado: not our ref
ladder completo: intentos depth = [1, 50] | método = fetch completo (sin --depth)
```

### tests/ci/test_publish_report.sh

```
(a) primera publicación crea la rama           PASS (rama + 4 rutas)
(b) segunda publicación NO force-push          PASS ancestro d98a3b3b -> ad127c40, 2 commits
(c) dos concurrentes                           PASS ambas exit=0, linealidad preservada
(d) retención 35 runs -> 30                    PASS quedan 30, rangos 3002..3031
(e) truncado > 200 KB                          PASS 480042 -> 120138 bytes con marca
(f) redacción de secretos                      PASS token=***REDACTED***
(g) no-redacción de identidad (regresión)      PASS RUNNER_NAME/GITHUB_SHA intactos
(h) allowlist no bloquea secretos              PASS ***REDACTED***
PASS=23 FAIL=0 · commits en la rama: 39
```

Reintento real observado en la prueba (c):

```
[pub] push rechazado (intento 1/5): remote: error: cannot lock ref
      'refs/heads/ci-report': reference already exists ... [remote rejected]
[pub] publicado: runs/2-lbl (primer envío=0, intento=2)
```

### Runs de CI

| Run | SHA | Jobs | Resultado |
|---|---|---|---|
| 45266067393 | b4d4cd1 | 5 | 5/5 success (windows-latest necesitó attempt 2) |
| 45267030334 | 49bfc3f | 5 | 5/5 success, attempt 1 |

Todos los steps `outcome=success` (verificado con `gh api .../jobs`, campo
`outcome`, no solo `conclusion`).

## Criterios

| Criterio | Estado | Evidencia |
|---|---|---|
| **B1** estructura y contrato, INVENTARIO sin modificar | **PARCIAL** | Estructura y contrato CUMPLIDO. INVENTARIO_USUARIO.md **no se pudo guardar** porque el ANEXO B no llegó: el mensaje contenía el marcador literal. Se documenta como NO RECIBIDO, sin inventar. |
| **B2** LICENSE idéntico + THIRD_PARTY_NOTICES | **CUMPLIDO** | `sha256sum` → `3972dc97...` idéntico; `cmp` → exit 0; 674 líneas / 35149 bytes en ambos. MIT literal de WinUtil embebido y verificado por subcadena (`True`). |
| **B3** lock con SHAs reales reproducidos | **CUMPLIDO** | `[OK]` para ambos, `real == esperado`, exit 0. Idempotencia y escalera de fallback probadas. |
| **B4** 5 pruebas de publish-report | **CUMPLIDO** | `PASS=23 FAIL=0` (a–h). |
| **B5** dos runs seguidos sin force-push | **CUMPLIDO** | `git rev-list --count origin/ci-report` = 11; `git log` muestra los 10 commits de ambos runs + el inicial `ad7dd85` como ancestro. |
| **B6** tabla de runners completa, cliente vs Server | **CUMPLIDO** | 4 Windows + 1 Ubuntu; `InstallationType` distingue `Server` (3) de `Client` (1, windows-11-arm). Store: AUSENTE en Server, PRESENTE en cliente. |

## Tabla de runners

| Etiqueta | Job | OS real | Build | EditionID | InstallationType | Arch | explorer | Store | .NET SDKs |
|---|---|---|---|---|---|---|---|---|---|
| windows-latest | success | Windows Server 2025 Datacenter | 26100.33828 (24H2) | ServerDatacenter | Server | AMD64 | corre (pid 7124) | AUSENTE | 8.0.134/206/319/428, 9.0.124/205/321, 10.0.115/204/303/404, 11.0.100 |
| windows-2025 | success | Windows Server 2025 Datacenter | 26100.33828 (24H2) | ServerDatacenter | Server | AMD64 | corre (pid 1324) | AUSENTE | idem |
| windows-2022 | success | Windows Server 2022 Datacenter | 20348.5870 (21H2) | ServerDatacenter | Server | AMD64 | corre (pid 4344) | AUSENTE | idem |
| windows-11-arm | success | Windows 11 Enterprise | 26200.9974 (25H2) | Enterprise | **Client** | ARM64 | corre (pid 7772) | **PRESENTE 22609.1401.13.0** | idem |
| ubuntu-latest | success | Linux 7.0.0-1020-azure | n/a | n/a | n/a | x86_64 | n/a | n/a | n/a |

`windows-latest` y `windows-2025` resuelven a la **misma** imagen
(`win25-vs2026`, 20261116.315.1) — son duplicados operativos.

Servicios (estado/tipo de inicio):

| Etiqueta | WSearch | SysMain | DiagTrack | wuauserv | BthServ | Spooler | Tareas prog. |
|---|---|---|---|---|---|---|---|
| windows-latest | Stopped/Disabled | Stopped/Disabled | Stopped/Disabled | Running/Manual | Stopped/Manual | Running/Auto | 210 (121 Ready) |
| windows-2025 | Stopped/Disabled | Stopped/Disabled | Stopped/Disabled | Running/Manual | Stopped/Manual | Running/Auto | 210 (121 Ready) |
| windows-2022 | Stopped/Disabled | Stopped/Disabled | Stopped/Disabled | Stopped/Disabled | Stopped/Manual | Running/Auto | 163 (77 Ready) |
| windows-11-arm | Running/Auto | Running/Auto | Stopped/Disabled | Running/Manual | Stopped/Manual | Running/Auto | 253 (167 Ready) |

`powercfg /list` exit=0 y `bcdedit /enum` exit=0 en los 4 Windows (contenido
íntegro en `inventory/raw/ci-reports/*.runner-matrix.md`).

Datos adicionales: winget `v1.11.510` (win25/win22) vs `v1.29.380` (win25-vs2026
duplicado), choco `2.7.5`, git `2.56.1.windows.1`, pwsh 7 presente en los 4,
PowerShell del shell `5.1.x`.

## Desviaciones y datos asumidos

* **D1 — ANEXO B ausente.** El mensaje incluye el marcador sin texto. B1 PARCIAL.
  Acción: pegar las 17 secciones.
* **D2 — Fallback de fetch probado por inyección, no contra un remoto real.**
  Intenté forzar el rechazo con un repo bare local y
  `uploadpack.allowReachableSHA1InWant=false`, pero el transporte local **ignora**
  esas restricciones: `git fetch --depth 1 origin <sha>` devolvió
  `* branch b7349d49... -> FETCH_HEAD` (exit 0). Por eso la escalera se verificó
  inyectando el error en `try_fetch_sha` (salida arriba). Con GitHub reales el
  fetch por SHA funcionó a la primera, así que el fallback **no se ha ejercitado
  contra GitHub**. Estado: lógica verificada, integración real NO VERIFICADA.
* **D3 — Errata propia corregida (ERRATA-EVO-002).** La primera versión de
  `publish-report.sh` redactaba **todas** las variables de entorno (un `case`
  vacío actuaba como comodín), lo que borró `RUNNER_NAME`, `GITHUB_SHA` e
  `ImageOS` del primer informe publicado (evidencia: run 45266067393,
  `latest/windows-latest/runner-matrix.md` mostraba `# Runner: ***REDACTED***`).
  Corregido con allowlist; añadidas pruebas (g) y (h) de regresión. El dato
  autoritativo se publica además en `meta.json` (no pasa por la redacción).
* **D4 — `runner.temp` como work dir.** `publish-report.sh` aborta si el origen
  está dentro de `CI_REPORT_WORK`; el workflow publica `ci-out/` con work en
  `$RUNNER_TEMP/ci-report-work` (guard añadido tras detectar el riesgo).
* **D5 — Redacción con `perl`.** Se usa `perl -0pi -e` como primera opción y
  `sed` como fallback. En `windows-latest` el paso de publicación terminó
  `conclusion=success`, así que ambos caminos son válidos; no verifiqué cuál se
  ejecutó. Estado: NO VERIFICADO cuál de los dos se usó en cada imagen.
* **D6 — Errata al contrato.** Añadí `ERRATA-EVO-001` al §4 de
  `AGENT_CONTRACT.md`: `git fetch origin ci-report` **no** crea
  `origin/ci-report` (verificado: `fatal: invalid object name 'origin/ci-report'`).
  Se usa `git show FETCH_HEAD:<ruta>` o refspec explícito. El texto del ANEXO A
  queda intacto salvo esta nota marcada.
* **D7 — `InstallationType` es la fuente de verdad**, no `ProductName`:
  en `windows-11-arm` ProductName dice `Windows 10 Enterprise` mientras que
  `OSCaption` dice `Windows 11 Enterprise` y `InstallationType` = `Client`.
  El registro lleva el nombre heredado de Win10.

## Riesgos

1. **Ningún runner hosted es Windows 10 22H2 ni Windows 11 23H2/24H2 cliente.**
   Los 3 Server + 1 cliente ARM64 cubren compilación y `net10.0-windows`, **no**
   la matriz de destino de REQ-003. La validación real depende de VM propias.
2. **`ci-report` crece sin límite de tamaño** (solo se limitan nº de runs y
   tamaño por fichero). Con 30 runs × varios ficheros puede engordar; vigilar
   `diskUsage`. Mitigación futura: límite de bytes totales por run.
3. **Concurrencia**: la prueba (c) pasa, pero el mecanismo es
   `pull --rebase` + reintento; un conflicto en `latest/<misma etiqueta>/`
   aborta el job (por diseño: no se pisan datos silenciosamente).
4. **`windows-11-arm` es más lento** (3m53s vs ~45s) por emulación/cola;
   consumirá cuota si se añade a cada push.
5. **GPL-3.0 + MIT**: el aviso MIT se conserva; cualquier copia de código de
   Atlas exige ADR (§5 del contrato). Riesgo de contaminación si alguien pega
   fragmentos GPL sin ADR.

## Preguntas abiertas

1. ¿Pegas el ANEXO B (17 secciones) para cerrar B1?
2. ¿Mantengo `windows-11-arm` en la matriz de cada push o solo en
   `workflow_dispatch` (coste/tiempo)?
3. ¿Añado un job de sondeo con `runs-on: windows-2022` fijado como "canónico"
   para evitar que `windows-latest` cambie de imagen bajo los pies?
4. La retención es 30 runs; ¿prefieres 30 días o un límite de MB totales?
5. ¿Autorizas un ADR para admitir `upstream.lock.json` con campo `pinned_at`
   y comprobación semanal de nuevos SHAs?

## Commits

```
b4d4cd1 feat: paso 1 - contrato, licencias, lock upstream, canal ci-report y matriz de runners
49bfc3f fix(ci): redaccion por allowlist, guard de recursion y meta.txt con identidad del runner
(+ commit de este informe)
```

Rama: `arena/ab2d6de7-evo-optimizer-on` (sin merge a `main`).


## Cierre de B1 (inventario importado)

- `docs/requirements/INVENTARIO_USUARIO.md`: 607 líneas, 15.921 bytes,
  sha256 `0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709`.
  Cabecera + línea en blanco + 605 líneas literales; `cmp` de `tail -n +3`
  contra el texto recibido: idénticos (exit 0). Sin `<<<PEGA`.
- 17 secciones `- TÍTULO` (el regex numérico da 0: ver ERRATA-EVO-004).
- Conteo (`docs/reports/inventario-usuario-conteo.tsv`, 7 columnas):
  no_vacias=588, winutil=212, atlas=351, evo=23, general=2. Invariante OK en 17/17.
- Sección 17: 49 no vacías, 2 generales (4,1 %).
- `tools/ledger_extract/tests/test_count_inventory.py`: 9 passed.
