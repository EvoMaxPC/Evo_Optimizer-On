# Etapa 8 — Arreglos de motor/app + catálogo sección 12 (Windows Update y Mantenimiento)

Rama: `arena/ab2d6de7-evo-optimizer-on`. PR #1: `isDraft:true`, `mergedAt:null`. Nunca `gh pr ready`, nunca merge. Commit final de código: `7aa3628` (Parte B). Commit de docs: este documento (pendiente de push).

SHA de referencia (40 chars, `git rev-parse HEAD`): `7aa36285bab0de29d2f26c64a9bbd93f7d43f0ba`.

---\n\n## 1. Estado de partida y entregables de ETAPA 8

Antes de ETAPA 8: el catálogo tenía 101 capacidades (76 Implemented / 25 Specified), secciones cerradas `[1,2,3,4,9,10]` (6 de 17), `ServiceActionExecutor` sin idempotencia, los botones de CapabilityViewModel no condicionados a `State==Implemented && IsExecutable`, y las descripciones de sección 4 con jerga interna (`WinUtil`, `State=`, `pin`, etc.).

Después de ETAPA 8: **106 capacidades** (las 101 previas + 5 de sección 12, todas Specified), secciones cerradas `[1,2,3,4,9,10,12]` (7 de 17), idempotencia A1-A2 del motor, botones A3-A4, descripciones de sección 4 limpias (sin jerga interna, con `technicalNote`), catálogo sección 12 generado y conciliado.

Entregables (Parte A — toca `src/`, dispara `release-exe`):
1. `src/Evo.Engine/Executors/ServiceActionExecutor.cs` — reescrito completo:
   - A1: Stop/StartupType/Start sobre servicio ya en estado destino → `Omitido` sin journal ni mutación; servicio inexistente (estado `Unknown`) → `Omitido`, no `Fallo`. Fallo real (acceso denegado) sigue siendo `Fallo` con rollback aislado.
   - A2: mensaje de error con cadena de causas (`InnerException` + Win32 vía `Marshal.GetHRForException`, `FACILITY_WIN32=7`).
2. `src/Evo.App/CapabilityViewModel.cs` — A3: `CanSimulate`/`CanApply`/`CanUndo` condicionados a `State==CapabilityState.Implemented && IsExecutable`; `CanApply` añade `Confirmation != ConfirmationType.TypeOperationName`; `NotAvailableText = "No disponible todavía"` para Specified/Stub.
3. `src/Evo.Core/Models/CapabilityContract.cs` — `TechnicalNote` (`required string`).
4. `src/Evo.Catalog/Model/CapabilityDefinition.cs` — `TechnicalNote` + proyección `ToContract()`.
5. `tools/ledger_extract/build_section4_catalog.py` — `technical_note` en `base()`; `apply_r1` deja `Description` limpia y pone el gap R1 en `TechnicalNote`; todas las descripciones `WINUTIL_SPECS` y `ATLAS_SPECS` limpiadas (sin `WinUtil`, nombres de servicio entre paréntesis, `psd1`, `pin`, `State=`, etc.); `technical_note` añadido a specs y llamadas a `base()` actualizadas.
6. `catalog/capabilities/section4_services.json` — regenerado: 12 capacidades / 66 acciones, `--check` OK (reproducible).
7. `tests/Evo.Engine.Tests/ExecutorTests.cs` — A5: test dedicado `services.atlas.networkdiscovery` (8 acciones, omitidos e inversa contra fakes); A6: tests nombrados `ServiceStop_YaDetenido_OmitidoSinJournal`, `ServiceSetStartupType_MismoTipo_OmitidoSinJournal`, `ServiceInexistente_OmitidoNoFallo`, `ServiceStart_YaCorriendo_OmitidoSinJournal`, `ServiceStop_FalloReal_SigueSiendoFalloConRollback`, `ServiceError_ConCadenaDeCausas_IncluyeInnerException`, `NetworkDiscovery_DedicatedTest_AccionesYInversa`.
8. `tests/Evo.App.Tests/Tests.cs` — A3/A4: `Specified_No_Ejecutable` (botones desactivados + "No disponible todavía"), `Implemented_Ejecutable_ConBotones`, `TechnicalNote_Cargado_PeroNoSeMuestraEnUI`.
9. Cifras fijas de tests .NET actualizadas (101 caps, secciones `[1,2,3,4,9,10]`).

Entregables (Parte B — NO toca `src/`; solo `catalog/`, `tools/ledger_extract/`, `tests/Evo.Catalog.Tests`, `docs/reports/`):
10. `tools/ledger_extract/build_section12_catalog.py` — generador de la sección 12 del inventario (Windows Update y Mantenimiento). Lee de los pins WinUtil (`config/tweaks.json`, `config/feature.json`) y Atlas (`tests/`, `package/...`). No inventa literales.
11. `catalog/capabilities/section12_windows_update.json` — 5 capacidades / 0 acciones, todas `Specified` (R1: el pin hace operaciones que el motor no expresa como acciones). `--check` OK (reproducible).
12. `tools/ledger_extract/verify_catalog_coverage.py` — B5: se añade `"12"` a `COMPLETED_SECTIONS`.
13. `tests/Evo.Catalog.Tests/Wave4CatalogTests.cs` — tests .NET nuevos T12-1 a T12-6 para sección 12 (Specified, `technicalNote`, `provenance` con el `mapped_id` del ledger, `CapabilityRules.Validate` vacío, builds explícitas, descripción sin jerga interna).
14. `docs/reports/etapa8.md` — este documento.

---\n\n## 2. Parte A — criterios A1-A7 (motor y app)

| Criterio | Estado | Evidencia |
|----------|--------|-----------|
| A1: Stop/StartupType/Start/servicio inexistente = Omitido sin journal | HECHO | `ServiceActionExecutor.cs` + tests `Service*_OmitidoSinJournal` / `ServiceInexistente_OmitidoNoFallo` |
| A2: mensaje de error con cadena de causas + Win32 | HECHO | `ServiceActionExecutor.cs` + test `ServiceError_ConCadenaDeCausas_IncluyeInnerException` |
| A3: botones deshabilitados + "No disponible todavía" en Specified/Stub | HECHO | `CapabilityViewModel.cs` + tests `Specified_No_Ejecutable` / `Implemented_Ejecutable_ConBotones` |
| A4: `TechnicalNote` en contrato + Description sección 4 sin jerga interna | HECHO (salvo svchostsplit, ya limpio) | `build_section4_catalog.py` + `section4_services.json` (12/12 con technicalNote) |
| A5: test dedicado `networkdiscovery` | HECHO | `NetworkDiscovery_DedicatedTest_AccionesYInversa` |
| A6: tests con nombre y archivo | HECHO | `ExecutorTests.cs` (7 tests) + `Tests.cs` |
| Actualizar cifras fijas (tests .NET suben) | HECHO | 101 caps, secciones `[1,2,3,4,9,10]` |
| Push A toca `src/` → dispara `release-exe` | HECHO | commit `c971d12` (toca `src/`) |

svchostsplit (línea 127 del inventario): descripción limpia ("Este ajuste escribe un valor en el registro del sistema que depende de la memoria RAM del equipo..."), `technicalNote` con el origen dinámico, `State=Specified` con 0 acciones. Verificado: ninguna descripción de `section4_services.json` contiene jerga prohibida (`R1`, `MachineAction`, `UserAction`, `psd1`, `.ps1`, `ledger`, `pin`, `REQ-`, `WPFTweaks`, `State=`, `Specified`, `Implemented`, `Stub`).

---\n\n## 3. Parte B — sección 12 del inventario (Windows Update y Mantenimiento)

La sección 12 del `INVENTARIO_USUARIO.md` tiene 28 líneas del ledger: 5 `Mapped`, 23 `Absent-At-Pin`/`Informative-Header`.

Decisión (línea 136 del paso 4e, aplicada a sección 12): un item del inventario sin expresión en ninguno de los dos pins **no se declara como capacidad** (queda `Absent-At-Pin`). Las 23 líneas no-Mapped de sección 12 no generan capacidad.

B2 — grep en ambos pins (verificado):
- WinUtil: `config/tweaks.json` (`WPFToggleLoginBlur`), `config/feature.json` (`WPFFixesUpdate`, `WPFFeatureRegBackup`).
- Atlas: `tests/Atlas.Verify.Tests.ps1` (Toggle Windows Updates, efecto #9) y `package/.../CbsPackages.ps1` (`Remove-AtlasCbsRepairSourcePolicy`, CBS).

B4 — reglas R1/R2/R3/ADR-0003 aplicadas a las 5 capacidades:
- R1: todas `State=Specified` con el gap declarado en `provenance` y `technicalNote` (ninguna expresa TODO el efecto del pin como acciones del motor).
- R2: `SecurityImpact=Neutral` en todas; no hay justificación `Improves` que escribir.
- R3: ninguna instala una tarea persistente con privilegios altos como acción declarada (quedan fuera por R1).
- ADR-0003: `Reversibility=Reversible`, `TechnicalNote` conserva el motivo interno (nunca se muestra en la UI), `supportedBuilds` explícito (`[19045, 22631, 26100, 26200]`), nunca `[]`.

Las 5 capacidades de sección 12:
- `services.winutil.windows-update-reset` (línea 397, `winutil:feature:WPFFixesUpdate`)
- `services.winutil.registry-backup` (línea 405, `winutil:feature:WPFFeatureRegBackup`)
- `services.winutil.system-restore-point` (línea 406, `winutil:tweak-op:WPFToggleLoginBlur:registry:0`)
- `services.atlas.toggle-windows-updates` (línea 410, `atlas:effect:tests/Atlas.Verify.Tests.ps1::<top>#9`)
- `services.atlas.cbs-repair-source-policy` (línea 423, `atlas:effect:.../CbsPackages.ps1::Remove-AtlasCbsRepairSourcePolicy#0`)

B5 — conciliación + 12 en `COMPLETED_SECTIONS`:
- `verify_catalog_coverage.py --strict`: **veredicto OK**. 104 líneas Mapped (1+2+3+4+9+10+12), 104 cubiertas, 0 huecos. Sección 12: 5 Mapped, 5 cubiertas, 0 huecos.
- `section12_windows_update.json` reproducible (`--check` OK).

---\n\n## 4. Cierre

- `docs/reports/etapa8.md` — este documento (HECHO).
- PR #1: DRAFT, `merged=false`, nunca `gh pr ready`, nunca merge. Los commits `c971d12` (Parte A) y `7aa3628` (Parte B) están push en `arena/ab2d6de7-evo-optimizer-on`; el PR se actualiza solo con cada push.
- SHA de inventario intacto: `docs/requirements/INVENTARIO_USUARIO.md` y `inventory/*.tsv` **no modificados** (salvo regeneración vía scripts oficiales, que no se aplicó a sección 12 porque el ledger ya tenía las 5 líneas Mapped).

---\n\n## 5. Commits de la etapa 8 (rama `arena/ab2d6de7-evo-optimizer-on`)

- `c971d12` `feat: etapa 8 - idempotencia de acciones de servicio y botones A3-A4` (Parte A, toca `src/`).
- `7aa3628` `feat: etapa 8 Parte B - catalogo seccion 12 (Windows Update y Mantenimiento)` (Parte B, no toca `src/`).
- `docs: etapa 8 - informe de cierre` (este documento, pendiente de push).

---\n\n## 6. Comandos de verificación

```bash
python3 tools/ledger_extract/build_section4_catalog.py --check
python3 tools/ledger_extract/build_section12_catalog.py --check
python3 tools/ledger_extract/verify_catalog_coverage.py --strict
python3 -m pytest tools/ledger_extract/tests/ -q
```

---\n\n> Nota: los tests .NET (ExecutorTests, Tests.cs, Wave4CatalogTests) se ejecutan en GitHub Actions (dotnet-ci) porque el sandbox no tiene `dotnet` instalado.
