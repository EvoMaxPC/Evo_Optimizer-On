# Etapa 7 — Integración de sección 4 (servicios) y sección 9 (registro/batería)

Estado: resumen de la etapa ejecutada. PR `isDraft:true`, `mergedAt:null`.

## Alcance cumplido

1. **`catalog/capabilities/section4_services.json`** (generado por `tools/ledger_extract/build_section4_catalog.py`, ADR-0003 / R1-R3):
   - 12 capacidades, 66 acciones.
   - 6 Atlas (Bluetooth, LanmanWorkstation, NetworkDiscovery, NVidiaDisplayContainer, Printing, SuperFetch): `Specified` (0 acciones, solo `MachineAction`) y `Implemented` (NetworkDiscovery).
   - 5 WinUtil (CscService, DiagTrack, MapsBroker, SharedAccess, StorSvc): `Implemented`, 1 acción `service` cada una (Stop + SetStartupType).
   - `svchostsplit` (WinUtil, `WPFTweaksSvcHostSplitting`): `Specified`, 0 acciones, valor dinámico según RAM.
   - Cada capacidad con `ledger_refs` y procedencia `winutil@<pin>:config/tweaks.json:...` o `atlas@<pin>:...`.
   - `--check` reproducible OK.

2. **`Wave4CatalogTests.cs`**: 88 → **101** capacidades, secciones `[1, 2, 3, 4, 9, 10]`.

3. **PASO D-A** (línea 278 §9 a MAPPED + `WPFToggleBatteryPercentage`):
   - `catalog/capabilities/section9_system_registry.json`: 20 capacidades, 48 acciones; `system.tray.battery-percentage` = `Implemented`, 1 acción `registry Set IsBatteryPercentageEnabled=1` (DWord), `winutil_tweak=WPFToggleBatteryPercentage`, `Reversibilidad (ADR-0003)`, `ledger_refs: winutil:tweak:WPFToggleBatteryPercentage`.
   - `inventory-reconciliation.tsv` §9 línea 278: `Mapped` con `winutil:tweak:WPFToggleBatteryPercentage`.
   - Test nuevo `TestWave4Catalog_BatteryPercentageImplemented`.

4. **PASO D-B** (`system.location.consent-deny`, R1): `Specified` (queda en §9 como Specified). Decisión R1: el pin de ubicación declara efectos `ownership\|process\|registry\|service` sobre `lfsvc` y `MapsBroker` (Location.ps1:113) que el motor no expresa íntegramente, por R1 la capacidad no puede ser `Implemented`; queda `Specified` con motivo escrito en la descripción y la provenance. Tabla de efectos documentada en el provenance de la capacidad.

5. **`inventory-reconciliation.tsv` regenerado** con `build_final_reconciliation.py`:
   - §4: 12 Mapped (122-135 con `ledger_refs`), 121/128/136 Absent-At-Pin, 120/129/145 Informative-Header, 0 huecos.
   - §9 línea 278: Mapped (batería).
   - `reglas-r1-r3.tsv`, `capability-completeness.tsv`, `toggle-state-audit.tsv`, `upstream-capability-map.tsv`, `catalog-value-audit.tsv` regenerados/actualizados como consecuencia.

6. **Informes regenerados** (`docs/reports/`):
   - `rangos-build.md`: 101 capacidades, 76 Implemented, 25 Specified.
   - `plan-oleadas.md` y `matriz-cobertura.md`: sección 4 incluida; cobertura 98/98, 0 huecos, secciones terminadas `[1,2,3,4,9,10]`.
   - `CONCILIACION_INVENTARIO.md`: conteos actualizados (Mapped 155→159, Absent-At-Pin 320→316, §4 9→12, §9 30→31).

7. **Tests Python**: todos los asserts actualizados a los nuevos conteos (101 caps, 310 acciones, §9 20/48, §10 30/60, 76 Implemented / 25 Specified, 98 líneas mapped, 0 huecos, `test_t0_la_linea_278_es_mapped`).

8. **`verify_catalog_coverage.py`**: `COMPLETED_SECTIONS = ("1","2","3","4","9","10")`; `--check` OK, 0 huecos no declarados.

9. **`measure_capability_completeness.py`**: `winutil_service_pairs` devuelve lista ordenada; `pin_pairs` filtra por `winutil:tweak-op:<tweak>:service:<N>` para que cada capacidad WinUtil de §4 respalde solo su servicio del pin (R1 sin violaciones: 76 Implemented / 25 Specified, 0 R1-VIOLATION).

10. **CI**: `pytest` **573 passed / 0 failed** (≥ 325, cero fallos). .NET no se compila en sandbox (CI es el ejecutor).

## Desviaciones autorizadas (declaradas)

- `docs/requirements/CONCILIACION_INVENTARIO.md` actualizado (conteos derivados del ledger; `INVENTARIO_USUARIO.md` NO tocado, sha256 intacto).
- `inventory/ledger/*.tsv` regenerados con scripts de `tools/ledger_extract/` (no editados a mano); permitido por la tarea (reconciliación definitiva).
- PR se mantiene en `isDraft:true`, nunca `gh pr ready`.

## Próximo paso (fuera de esta sesión si aplica)

- `git push` de código (runners .NET ejecutan dotnet-ci + ledger-verify + release-exe).
- `git push` de docs con `docs/etapa7.md` (1 push de docs restante).
- No ejecutar `gh pr ready` (PR queda enDraft).
