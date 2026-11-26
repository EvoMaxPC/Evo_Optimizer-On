PASO 12d — dotnet-ci en verde tras reconciliación 12c (diagnóstico + arreglo mínimo)

Rama: arena/ab2d6de7-evo-optimizer-on, base 402af190e10a120dc893fa74f0a1d7b7d55b0c75, HEAD 4d09ba17c757bcc3971c5aae5ac93d5be204b198.
PR #1: open, draft=true, merged=false, head=4d09ba1. Sin `gh pr ready` ni merge.

T0 — estado previo:
- git rev-parse HEAD: 4d09ba17c757bcc3971c5aae5ac93d5be204b198
- git ls-remote origin refs/heads/arena/ab2d6de7-evo-optimizer-on: 4d09ba17c757bcc3971c5aae5ac93d5be204b198 (40 chars, coincide)
- git status --short: árbol limpio (solo informe-paso12d-*.md y informe-paso12c-*.md untracked)
- gh api repos/EvoMaxPC/Evo_Optimizer-On/pulls/1: {state: open, draft: true, merged: false, head: 4d09ba17c757bcc3971c5aae5ac93d5be204b198}

D1 — Primer commit que rompe dotnet-ci:
Último verde: run 45695047501 sobre 231564b (239/239 en windows-2025 y windows-11-arm).
Primer rojo: run 45706361095 sobre f997941 (commit de 12c). Tabla de runs dotnet-ci:

| run id | head_sha corto | workflow | conclusión |
| 45713989429 | 4d09ba1 | dotnet-ci (PR) | success |
| 45713977641 | 4d09ba1 | dotnet-ci (push) | success |
| 45713977577 | 4d09ba1 | ledger-verify (push) | success |
| 45713604788 | f45f6e8 | dotnet-ci (PR) | failure |
| 45713592405 | f45f6e8 | dotnet-ci (push) | failure |
| 45713592416 | f45f6e8 | ledger-verify (push) | success |
| 45709694585 | fef2dbf | dotnet-ci (PR) | failure |
| 45709683634 | fef2dbf | ledger-verify (push) | success |
| 45706361095 | f997941 | dotnet-ci (PR) | failure ← PRIMER ROJO |
| 45706353058 | f997941 | dotnet-ci (push) | failure |
| 45695047501 | 231564b | dotnet-ci (PR) | success (último verde) |

Cambio en f997941 (12c): catálogo pasó de 86 a 88 capacidades, `system.time.ntp-servers` y `system.oem-information.identify` pasaron a Specified (R1), `explorer.home.hide` y `explorer.home.restore` ganaron `conflictsWith` simétrico.

D2 — Lectura del error sin logs (vía ci-report):
a) Jobs/pasos (run 45706361095): `dotnet test` falla en ambos runners (windows-2025 job 139529256013, windows-11-arm job 139529256407). `dotnet build` y `dotnet restore` pasan.
b) Anotaciones: solo "Process completed with exit code 1" (sin detalle de compilador).
c) ci-report (runs/45706361095-*): test-summary muestra total=239 passed=236 failed=3 en ambos runners. Los 3 fallos están en Evo.Catalog.Tests.

Los 3 tests fallantes (error literal, idéntico en ambos runners):

1. Wave3CatalogTests.cs:302 `TestWave3Catalog_NoSpecifiedLeftAndThePinLiteralsStay`:
   Expected: ["system.hibernation.hide","system.location.consent-deny","system.mitigations.disable","system.registry-backup.enable"]
   Actual:   [...,"system.oem-information.identify","system.registry-backup.enable","system.time.ntp-servers"]

2. Wave4CatalogTests.cs:185 `TestWave4Catalog_TimeServersStartTheServiceAndSayWhatIsLeftOut`:
   Expected: Implemented
   Actual:   Specified

3. Wave4CatalogTests.cs:54 `TestWave4Catalog_ValidatorRejectsMalformedKeyDeletions`:
   Expected: True
   Actual: False (CatalogValidator falla al validar explorer.home.hide solo, que tiene ConflictsWith: ['explorer.home.restore'] no presente en catálogo de 1 capacidad → error R-REF)

D3 — Análisis estático (causa confirmada):
Los 3 asserts tienen valores pre-12c que el catálogo actualizado (tras 12c) invalida. Ningún assert se relaja; se actualizan a los valores reales derivados del catálogo:

| test (fichero:línea) | espera (pre-12c) | catálogo real (tras 12c) | coincide |
| Wave3CatalogTests.cs:302 | 4 Specified | 6 Specified (añadidos oem-information, ntp-servers) | NO |
| Wave4CatalogTests.cs:185 | Implemented (ntp-servers) | Specified (R1: w32tm /config /update + /resync no son acciones del motor) | NO |
| Wave4CatalogTests.cs:54 | valida explorer.home.hide solo | explorer.home.hide tiene ConflictsWith: ['explorer.home.restore'] → necesita ambas en el catálogo para R-REF | NO |

El CatalogValidator no fue modificado; el fallo 3 es porque validar explorer.home.hide en solitario no puede resolver la referencia ConflictsWith a explorer.home.restore.

D4 — Arreglo mínimo (Cause A: asserts con cifras viejas):
1. Wave3CatalogTests.cs: actualizar expected array de 4 a 6 elementos (añadir system.oem-information.identify y system.time.ntp-servers), actualizar comentario.
2. Wave4CatalogTests.cs:185: `CapabilityState.Implemented` → `CapabilityState.Specified` para ntp-servers.
3. Wave4CatalogTests.cs:54: validar ambas capacidades juntas (CatalogOf({hide, restore})) para que R-REF resuelva ConflictsWith.
4. Wave3CatalogTests.cs:340 (residual): `Assert.Equal(CapabilityState.Implemented, ntp.State)` → `CapabilityState.Specified`.

Se aplicaron 2 commits: f45f6e8 (fixes 1-3) y 4d09ba1 (fix 4). Ningún assert se relajó; todos se corrigieron con valores derivados del catálogo tras 12c.
D5 — Verificación final:

pytest: 559 passed, 0 failed (tools/ledger_extract/tests tests). Sin tests eliminados ni asserts relajados.

xUnit (ci-report, run 45713977641 push / 45713989429 PR):

| runner | proyecto | total | passed | failed |
| windows-2025 | Evo.Catalog.Tests | 79 | 79 | 0 |
| windows-2025 | Evo.Core.Tests | 34 | 34 | 0 |
| windows-2025 | Evo.Detection.Tests | 35 | 35 | 0 |
| windows-2025 | Evo.Engine.Tests | 91 | 91 | 0 |
| windows-2025 | TOTAL | 239 | 239 | 0 |
| windows-11-arm | Evo.Catalog.Tests | 79 | 79 | 0 |
| windows-11-arm | Evo.Core.Tests | 34 | 34 | 0 |
| windows-11-arm | Evo.Detection.Tests | 35 | 35 | 0 |
| windows-11-arm | Evo.Engine.Tests | 91 | 91 | 0 |
| windows-11-arm | TOTAL | 239 | 239 | 0 |

Run IDs finales sobre head 4d09ba1:
- dotnet-ci (push): 45713977641 → success
- dotnet-ci (PR): 45713989429 → success
- ledger-verify (push): 45713977577 → success (todos los pasos, incluido Paso 12c)

Commit final: 4d09ba1 `fix: paso 12d - ntp-servers es Specified (no Implemented) en assert residual`
Commit anterior de 12d: f45f6e8 `fix: paso 12d - dotnet-ci en verde tras reconciliacion 12c`

PR #1: state=open, draft=true, merged=false, head=4d09ba17c757bcc3971c5aae5ac93d5be204b198. Sin `gh pr ready` ni merge.

Criterios de aceptación:

| criterio | estado | evidencia |
| U1 causa del fallo identificada con error literal | CUMPLIDO | 3 asserts con valores pre-12c; error literal extraído de ci-report test-Evo.Catalog.Tests.txt |
| U2 primer commit rojo identificado | CUMPLIDO | f997941 (run 45706361095), después de 231564b (run 45695047501 verde) |
| U3 arreglo mínimo sin relajar asserts | CUMPLIDO | 3 asserts actualizados a valores reales del catálogo tras 12c; 1 assert residual corregido |
| U4 dotnet-ci success en windows-2025 y windows-11-arm | CUMPLIDO | run 45713977641 (push) success; run 45713989429 (PR) success; 239/239 ambos runners |
| U5 ledger-verify success sobre head final | CUMPLIDO | run 45713977577 success, todos los pasos verdes |
| U6 PR sigue draft, sin merge | CUMPLIDO | draft=true, merged=false, state=open |

Desviaciones: Ninguna. Todos los criterios U1–U6 cumplidos.
Supuestos: Ninguno nuevo; todos los valores se derivaron del catálogo y de ci-report.
Riesgos: Los reports de 12c (informe-paso12c-parte1.md, informe-paso12c-parte2.md) quedan como archivos untracked; no forman parte del commit de 12d.
Preguntas abiertas: Ninguna.
Commit: 4d09ba1 (head de PR #1, sobre rama arena/ab2d6de7-evo-optimizer-on).
