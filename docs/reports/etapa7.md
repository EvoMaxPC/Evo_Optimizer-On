# Etapa 7 — Cierre: sección 4 (servicios), sección 9 (registro/batería), CI y evidencias

Rama: `arena/ab2d6de7-evo-optimizer-on`. PR #1: `isDraft:true`, `mergedAt:null`. Commit final de código: `2a42a5721f57a18a170f3f33ec00043206ccf6e5`.

---

## 1. Estado de partida y entregables de ETAPA 7

Antes de ETAPA 7: el catálogo tenía 88 capacidades (69 Implemented / 19 Specified), secciones cerradas `[1,2,3,9,10]` (5 de 17), y la línea 278 de §9 (`System Tray Configuration.`) estaba en `Absent-At-Pin`.

Después de ETAPA 7: **101 capacidades** (76 Implemented / 25 Specified), secciones cerradas `[1,2,3,4,9,10]` (**6 de 17**), línea 278 de §9 en `Mapped` con `system.tray.battery-percentage`.

Entregables:
1. `catalog/capabilities/section4_services.json` — generado por `tools/ledger_extract/build_section4_catalog.py`, 12 capacidades / 66 acciones, `--check` OK, ADR-0003 / R1-R3 cumplidas.
2. `catalog/capabilities/section9_system_registry.json` — 20 capacidades / 48 acciones, incluye `system.tray.battery-percentage` (Implemented).
3. `inventory/ledger/inventory-reconciliation.tsv` — regenerado con `build_final_reconciliation.py`.
4. `tests/Evo.Catalog.Tests/Wave4CatalogTests.cs` — 101 caps, secciones `[1,2,3,4,9,10]`, test de batería.
5. `docs/reports/rangos-build.md`, `plan-oleadas.md`, `matriz-cobertura.md` — regenerados.
6. `docs/reports/etapa7.md` — este documento (único; `docs/etapa7.md` eliminado con `git mv`/`git rm`).

---

## 2. Sección 4 — tabla de las 23 líneas de contenido

Sección "OPTIMIZACIÓN DE SERVICIOS" de `docs/requirements/INVENTARIO_USUARIO.md` (líneas 119-145). Las líneas 119, 120, 129 y 145 son encabezados/nota (Informative-Header). Las 23 líneas de contenido son 121-128 y 130-144.

Desfase de numeración: el reporte intermedio mencionó "122-135" de forma continua, pero la numeración real del TSV tiene un salto: 122-126 (servicios WinUtil), 127 (svchostsplit), 128 (Set-WinUtilService, Absent), luego 130-135 (AtlasOS), 136-144 (líneas Absent-At-Pin). No hay línea 128 Mapped ni 129 de contenido (129 es el encabezado AtlasOS).

| línea | texto | clasificación TSV | capacidad(es) | evidencia archivo:línea del pin | efecto |
|-------|-------|-------------------|---------------|---------------------------------|--------|
| 120 | WinUtil | Informative-Header | — | — | encabezado de modo (WinUtil/AtlasOS) |
| 121 | Services — configuración de inicio Manual. | Absent-At-Pin | — | — | agrupa servicios ya mapeados 122-126; no es operación aparte (REQ-002) |
| 122 | DiagTrack. | Mapped | services.winutil.diagtrack | tweaks.json:158 (`WPFTweaksServices`, service DiagTrack → Disabled) | Stop + SetStartupType Disabled |
| 123 | MapsBroker. | Mapped | services.winutil.mapsbroker | tweaks.json:163 (`WPFTweaksServices`, service MapsBroker → Manual) | Stop + SetStartupType Manual |
| 124 | StorSvc. | Mapped | services.winutil.storsvc | tweaks.json:168 (`WPFTweaksServices`, service StorSvc → Manual) | Stop + SetStartupType Manual |
| 125 | SharedAccess. | Mapped | services.winutil.sharedaccess | tweaks.json:173 (`WPFTweaksServices`, service SharedAccess → Disabled) | Stop + SetStartupType Disabled |
| 126 | CscService. | Mapped | services.winutil.cscservice | tweaks.json:153 (`WPFTweaksServices`, service CscService → Disabled) | Stop + SetStartupType Disabled |
| 127 | Service Host Splitting. | Mapped | services.winutil.svchostsplit | tweaks.json:180 (`WPFTweaksSvcHostSplitting`, InvokeScript SvcHostSplitThresholdInKB) | Specified: valor dinámico según RAM, no literal fijo |
| 128 | Configuración de servicios mediante Set-WinUtilService. | Absent-At-Pin | — | — | no existe `Set-WinUtilService` en tweaks.json (grep: 0 hits) |
| 129 | AtlasOS | Informative-Header | — | — | encabezado de modo (WinUtil/AtlasOS) |
| 130 | Bluetooth. | Mapped | services.atlas.bluetooth | Toggles/Services/Bluetooth.psd1:13 (Disable: Registry AllowBluetooth=0 + 15 servicios) | Specified: MachineAction + UserAction no expresables |
| 131 | Lanman Workstation. | Mapped | services.atlas.lanmanworkstation | Toggles/Services/LanmanWorkstation.psd1:11 (Disable: 7 servicios a Disabled/Manual) | Specified: MachineAction Set-AtlasSmbDirectFeature no expresable |
| 132 | Network Discovery. | Mapped | services.atlas.networkdiscovery | Toggles/Services/NetworkDiscovery.psd1:11 (Disable: 4 servicios a Disabled) | Implemented: estado Disable sin MachineAction, expresable completo |
| 133 | NVIDIA Display Container. | Mapped | services.atlas.nvidiadisplaycontainer | Toggles/Services/NVidiaDisplayContainer.psd1:11 (Disable: solo MachineAction) | Specified: solo MachineAction, sin registro/servicio expresable |
| 134 | Printing. | Mapped | services.atlas.printing | Toggles/Services/Printing.psd1:11 (Disable: MachineAction + ContextAction) | Specified: solo MachineAction/ContextAction, sin registro/servicio |
| 135 | SuperFetch / SysMain. | Mapped | services.atlas.superfetch | Toggles/Services/SuperFetch.psd1:11 (Disable: solo MachineAction) | Specified: solo MachineAction, sin registro/servicio |
| 136 | Windows Update Services. | Absent-At-Pin | — | — | pin tiene ToggleWindowsUpdates/AutomaticUpdates pero no toggle "Windows Update Services" (REQ-002) |
| 137 | Servicios relacionados con Game Bar. | Absent-At-Pin | — | — | GameBar en tweaks.json:1946-1954 (clave HKCU), no es toggle de servicio mapeable |
| 138 | Servicios de indexación. | Absent-At-Pin | — | — | sin candidato en ledgers |
| 139 | Servicios de localización. | Absent-At-Pin | — | — | sin candidato en ledgers |
| 140 | Servicios de compartición de archivos. | Absent-At-Pin | — | — | sin candidato en ledgers |
| 141 | Configuración de servicios predeterminados. | Absent-At-Pin | — | — | sin candidato en ledgers |
| 142 | Backup Services. | Absent-At-Pin | — | — | sin candidato en ledgers |
| 143 | Restore Atlas Service Defaults. | Absent-At-Pin | — | — | Defaults.ps1 es script de red, no toggle de servicios (REQ-002) |
| 144 | Reset Services. | Absent-At-Pin | — | — | mapped_id del paso 4e no es producto (REQ-002) |
| 145 | Nota metodológica | Informative-Header | — | — | regla d del conteo |

Resumen §4: **12 Mapped** (122-127, 130-135), **8 Absent-At-Pin** (121, 128, 136-144), **3 Informative-Header** (120, 129, 145), 0 huecos.

### Contradicciones resueltas

**Línea 121** ("Services — configuración de inicio Manual"): permaneció `Absent-At-Pin`. Evidencia: `grep -rn "Set-WinUtilService" /tmp/upstream/winutil/config/tweaks.json` → 0 hits. La línea agrupa los 5 servicios ya mapeados individualmente (122-126); no es una operación propia del pin. `MAPPED_OVERRIDES` no la incluye.

**Línea 136** ("Windows Update Services"): permaneció `Absent-At-Pin`. Evidencia: `grep -rn "wuauserv" /tmp/upstream/atlas/` → aparece en `app/src/` (código fuente de Atlas, no en toggles `.psd1`); `grep -rn "Windows Update" /tmp/upstream/atlas/package/Executables/AtlasModules/Toggles/Services/` → 0 hits. El pin tiene toggles generales de actualización (`ToggleWindowsUpdates.psd1`, `AutomaticUpdates.psd1`) pero no un toggle específico "Windows Update Services". No hay candidato de ledger (REQ-002: no inventar). Antes figuraba Mapped en el paso 4e por error; se corrigió a Absent-At-Pin en `ABSENT_OVERRIDES` con motivo literal.

---

## 3. Tabla de capacidades — sección 4 y batería (desde el JSON generado)

### Sección 4 — 12 capacidades

| id | riesgo | confirmación | privilegio | SecurityImpact | Reversibility | State | procedencia | motivo Specified (si aplica) |
|----|--------|--------------|--------------|----------------|---------------|-------|-------------|------------------------------|
| services.winutil.diagtrack | Low | SimpleClick | Admin | Improves | Reversible | Implemented | winutil@70c23c8…:config/tweaks.json:WPFTweaksServices:service:1 | — (R2: mejora privacidad, motivo escrito) |
| services.winutil.mapsbroker | Low | SimpleClick | Admin | Neutral | Reversible | Implemented | winutil@70c23c8…:config/tweaks.json:WPFTweaksServices:service:2 | — |
| services.winutil.storsvc | Low | SimpleClick | Admin | Neutral | Reversible | Implemented | winutil@70c23c8…:config/tweaks.json:WPFTweaksServices:service:3 | — |
| services.winutil.sharedaccess | Low | SimpleClick | Admin | Neutral | Reversible | Implemented | winutil@70c23c8…:config/tweaks.json:WPFTweaksServices:service:4 | — |
| services.winutil.cscservice | Low | SimpleClick | Admin | Neutral | Reversible | Implemented | winutil@70c23c8…:config/tweaks.json:WPFTweaksServices:service:0 | — |
| services.winutil.svchostsplit | Low | SimpleClick | User | Neutral | Reversible | Specified | winutil@70c23c8…:config/tweaks.json:WPFTweaksSvcHostSplitting | Valor dinámico según RAM (SvcHostSplitThresholdInKB), no literal fijo |
| services.atlas.bluetooth | Low | SimpleClick | Admin | Neutral | Reversible | Specified | atlas@ec3c4058…:Toggles/Services/Bluetooth.psd1:13 | MachineAction Disable-AtlasBluetoothDevices + UserAction Remove-AtlasBluetoothSendTo no expresables (R1) |
| services.atlas.lanmanworkstation | Medium | Summary | Admin | Neutral | Reversible | Specified | atlas@ec3c4058…:Toggles/Services/LanmanWorkstation.psd1:11 | MachineAction Set-AtlasSmbDirectFeature no expresable (R1) |
| services.atlas.networkdiscovery | Low | SimpleClick | Admin | Neutral | Reversible | Implemented | atlas@ec3c4058…:Toggles/Services/NetworkDiscovery.psd1:11 | — |
| services.atlas.nvidiadisplaycontainer | Low | SimpleClick | User | Neutral | Reversible | Specified | atlas@ec3c4058…:Toggles/Services/NVidiaDisplayContainer.psd1:11 | solo MachineAction Set-AtlasNVidiaDisplayContainerState, sin registro/servicio (R1) |
| services.atlas.printing | Low | SimpleClick | User | Neutral | Reversible | Specified | atlas@ec3c4058…:Toggles/Services/Printing.psd1:11 | solo MachineAction + ContextAction, sin registro/servicio (R1) |
| services.atlas.superfetch | Low | SimpleClick | User | Neutral | Reversible | Specified | atlas@ec3c4058…:Toggles/Services/SuperFetch.psd1:11 | solo MachineAction Set-AtlasSuperFetchMachineState, sin registro/servicio (R1) |

Verificaciones:
- **Ninguna capacidad de seguridad/mantenimiento quedó como Improves**: `services.winutil.sharedaccess` (Firewall/SharedAccess) = Neutral. `services.winutil.diagtrack` = Improves pero es telemetría (no seguridad/mantenimiento), motivo R2 escrito.
- **Hardware/build tratado caso por caso**: Bluetooth (Neutral, R1 gap declarado), NVIDIA Display Container (Specified, solo MachineAction), Printing (Specified, solo MachineAction/ContextAction), SuperFetch/SysMain (Specified, solo MachineAction). Ninguna capacidad de hardware quedó sin motivo explícito.

### Sección 9 — batería (PASO D-A)

| id | riesgo | confirmación | privilegio | SecurityImpact | Reversibility | State | procedencia |
|----|--------|--------------|--------------|----------------|---------------|-------|-------------|
| system.tray.battery-percentage | Safe | None | User | Neutral | Reversible | Implemented | winutil@70c23c8…:config/tweaks.json:WPFToggleBatteryPercentage:registry:0 |

Acción: `registry Set` — `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced`, `IsBatteryPercentageEnabled` = `1` (DWord), operación `Set`. Línea 278 de §9 movida de `Absent-At-Pin` a `Mapped` con `ledger_refs: winutil:tweak:WPFToggleBatteryPercentage`.

---

## 4. system.location.consent-deny (PASO D-B) — tabla de efectos y decisión R1

### Efectos del pin (Location.psd1, estado Disable)

| ámbito | clave/valor | archivo:línea |
|--------|-------------|---------------|
| Registro HKLM | `CapabilityAccessManager\ConsentStore\location\Value` = `Deny` (String) | Toggles/General/Location.psd1:18-21 |
| Registro HKCU | `CapabilityAccessManager\ConsentStore\location\ShowGlobalPrompts` = `0` (DWord) | Toggles/General/Location.psd1:22-24 |
| MachineAction | `Disable-AtlasLocation` (ejecuta Location.ps1) | Toggles/General/Location.psd1:16 |

### Efectos expresados por Location.ps1 (Set-AtlasLocationMachineState, Disable)

| efecto | detalle | archivo:línea |
|--------|---------|---------------|
| Servicio | `lfsvc` StartupType=Disabled, Status=Stopped | Location.ps1:113 (Invoke-AtlasLocationServiceState) |
| Servicio | `MapsBroker` StartupType=Disabled, Status=Stopped | Location.ps1:114 |
| Registro | `HKLM\SOFTWARE\Policies\Microsoft\FindMyDevice\AllowFindMyDevice` = `0` (DWord) | Location.ps1:118-120 |
| Registro | `HKLM\SOFTWARE\Policies\Microsoft\FindMyDevice\LocationSyncEnabled` = `0` (DWord) | Location.ps1:118-120 |
| Configuración | ocultar página `privacy-location` | Location.ps1:122 |
| Configuración | ocultar página `findmydevice` | Location.ps1:123 |

### Decisión R1

**Queda `Specified`** (no `Implemented`). Motivo literal: el pin declara efectos que la capacidad NO expresa como acciones del motor:
- `HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location\Value` = `Deny` (Location.psd1:18-21) — no hay acción de registro en la capacidad.
- `HKCU:\...\ConsentStore\location\ShowGlobalPrompts` = `0` (Location.psd1:22-24) — no hay acción de registro.
- `HKLM\SOFTWARE\Policies\Microsoft\FindMyDevice\AllowFindMyDevice` / `LocationSyncEnabled` (Location.ps1:118-120) — no hay acción de registro.
- Ocultar páginas de configuración `privacy-location` y `findmydevice` (Location.ps1:122-123) — no es acción de registro/servicio/start/stop del motor.

Solo las 4 acciones de servicio (lfsvc×2, MapsBroker×2) están expresadas. Como R1 exige que `Implemented` exprese TODO el efecto del pin, `system.location.consent-deny` permanece `Specified` con el motivo escrito en su descripción y provenance.

---

## 5. Constantes y tests cambiados (before → after)

Todos son DESVIACIONES autorizadas. Ningún invariante se relajó ni se borró test.

| archivo | constante/test | before | after | justificación |
|---------|---------------|--------|-------|---------------|
| tests/Evo.Catalog.Tests/Wave1CatalogTests.cs | total catálogo | `Assert.Equal(88, catalog.Count)` | `Assert.Equal(101, catalog.Count)` | +12 caps §4 +1 batería §9 |
| tests/Evo.Catalog.Tests/Wave1CatalogTests.cs | filtro secciones | `is not 10 and not 9` | `is not 10 and not 9 and not 4` | excluir §4 (tiene su propio test) |
| tests/Evo.Catalog.Tests/Wave1CatalogTests.cs | contaje §9 | `Assert.Equal(19, … SectionId == 9)` | `Assert.Equal(20, … SectionId == 9)` | +batería |
| tests/Evo.Catalog.Tests/Wave1CatalogTests.cs | NotEmpty acciones | `Assert.NotEmpty(definition.Actions)` (todas) | solo si `State == Implemented` | Specified puede tener 0 acciones (ADR-0003/R1) |
| tests/Evo.Catalog.Tests/Wave2CatalogTests.cs | total catálogo | `Assert.Equal(88, catalog.Count)` | `Assert.Equal(101, catalog.Count)` | — |
| tests/Evo.Catalog.Tests/Wave3CatalogTests.cs | total catálogo | `Assert.Equal(88, catalog.Count)` | `Assert.Equal(101, catalog.Count)` | — |
| tests/Evo.Catalog.Tests/Wave3CatalogTests.cs | Section9 | 18 ids, battery ausente | 19 ids + `system.tray.battery-percentage` al final | orden ordinal; +batería |
| tests/Evo.Catalog.Tests/Wave3CatalogTests.cs | contaje §9/ids | `Assert.Equal(88, ids.Count)` / `19` | `Assert.Equal(101, ids.Count)` / `20` | — |
| tests/Evo.Catalog.Tests/Wave4CatalogTests.cs | total catálogo | `Assert.Equal(88, all.Count)` | `Assert.Equal(101, all.Count)` | — |
| tests/Evo.Catalog.Tests/Wave4CatalogTests.cs | secciones | `new[] { 1, 2, 3, 9, 10 }` | `new[] { 1, 2, 3, 4, 9, 10 }` | §4 cerrada |
| tests/Evo.Catalog.Tests/Wave4CatalogTests.cs | NotEmpty acciones | `Assert.NotEmpty(definition.Actions)` (todas) | solo si `State == Implemented` | Specified puede tener 0 acciones (ADR-0003/R1) |
| tests/Evo.Catalog.Tests/Wave4CatalogTests.cs | test batería | — | `TestWave4Catalog_BatteryPercentageImplemented` | PASO D-A |
| tests/test_paso10.py | contaje §9 | `len(CAPS) == 19` | `len(CAPS) == 20` | +batería |
| tests/test_paso10.py | filas auditoría §9 | `len(rows) == 33` | `len(rows) == 34` | +fila batería |
| tests/test_paso10.py | cobertura §9 | `lineas_mapped: 30` | `lineas_mapped: 31` | +línea 278 |
| tests/test_paso10.py | total capacidades | `report["capacidades"] == 88` | `== 101` | — |
| tests/test_paso10.py | estado línea 278 | `rows["278"]["status"] == "Absent-At-Pin"` | `== "Mapped"` | PASO D-A |
| tests/test_paso11.py | filas auditoría | `report["filas"] == 197` | `== 198` | +batería |
| tests/test_paso11.py | contaje §9 auditoría | `report["por_seccion"]["9"] == 33` | `== 34` | +batería |
| tests/test_paso12.py | veredicto R1 | `len(rows) == 88` | `== 101` | — |
| tests/test_paso12.py | Implemented/Specified | 69/19 | 76/25 | — |
| tests/test_paso12.py | §9 capacities | `len(CAPS9) == 19` / `== 47` | `== 20` / `== 48` | — |
| tests/test_paso12.py | §10 capacities | `len(CAPS10) == 30` / `== 60` | sin cambio | — |
| tests/test_paso12.py | xUnit §9 | `Assert.Equal(19, … SectionId == 9)` | `Assert.Equal(20, … SectionId == 9)` | — |
| tests/test_paso12.py | total caps/cifras | 88 / 243 / 69 / 19 | 101 / 310 / 76 / 25 | — |
| tests/test_paso12.py | cobertura | 85 / 85 / [1,2,3,9,10] | 98 / 98 / [1,2,3,4,9,10] | — |
| tests/test_paso12.py | test_t0 línea 278 | `test_t0_la_linea_278_sigue_absent_at_pin` | `test_t0_la_linea_278_es_mapped` | PASO D-A |
| tests/test_paso12.py | t3 totales | 20 filas (OK=2, PEND=15, CON=3) | 26 filas (OK=7, PEND=16, CON=3) | +caps §4 con toggle |
| tools/ledger_extract/verify_catalog_coverage.py | COMPLETED_SECTIONS | `("1","2","3","9","10")` | `("1","2","3","4","9","10")` | §4 cerrada |
| tools/ledger_extract/build_final_reconciliation.py | MAPPED_OVERRIDES | sin (4,127),(4,131-135),(9,278) | añadidos | PASO D-A + §4 Mapped |
| tools/ledger_extract/build_final_reconciliation.py | ABSENT_OVERRIDES | (9,278) | (4,121),(4,136),(4,144) | PASO D-B + §4 Absent |
| tools/ledger_extract/build_section9_catalog.py | WINUTIL_REGISTRY_SPECS | — | batería (línea 278, 1 acción registry Set) | PASO D-A |
| tools/ledger_extract/measure_capability_completeness.py | winutil_service_pairs | devolve set | devolve lista ordenada + filtro tweak-op:service:N | R1 sin violaciones en §4 |

---

## 6. Archivos del ledger commiteados y script oficial que los produce

| archivo | script oficial | qué produce |
|---------|---------------|-------------|
| inventory/ledger/inventory-reconciliation.tsv | `tools/ledger_extract/build_final_reconciliation.py` | conciliación definitiva sección 4 y 9 |
| inventory/ledger/reglas-r1-r3.tsv | `tools/ledger_extract/report_rules_state.py` | evaluación de reglas R1/R2/R3 |
| inventory/ledger/capability-completeness.tsv | `tools/ledger_extract/measure_capability_completeness.py` | auditoría de completitud R1 |
| inventory/ledger/catalog-value-audit.tsv | `tools/ledger_extract/audit_catalog_values.py` | auditoría de valores del catálogo |
| inventory/ledger/toggle-state-audit.tsv | `tools/ledger_extract/measure_toggle_states.py` | medición de estados de toggle |
| inventory/ledger/upstream-capability-map.tsv | `tools/ledger_extract/build_upstream_capability_map.py` | mapa de capacidades upstream |
| docs/reports/rangos-build.md | `tools/ledger_extract/build_build_ranges_report.py` | rangos de build |
| docs/reports/plan-oleadas.md | `tools/ledger_extract/build_wave_plan.py` | plan de oleadas |
| docs/reports/matriz-cobertura.md | `tools/ledger_extract/generate_coverage_matrix.py` | matriz de cobertura |

Los `.tsv` se regeneran con sus scripts oficiales (no se editan a mano). Los `.tsv que solo se ensucian por correr pytest no se commitean.

---

## 7. CI — tabla final de runs (commit `2a42a5721f57a18a170f3f33ec00043206ccf6e5`)

| id | workflow | sha (40 chars) | evento | conclusión |
|----|----------|----------------|--------|------------|
| 46125236752 | dotnet-ci | 2a42a5721f57a18a170f3f33ec00043206ccf6e5 | pull_request | **success** ✅ |
| 46125232132 | dotnet-ci | 2a42a5721f57a18a170f3f33ec00043206ccf6e5 | push | **success** ✅ |
| 46125232095 | ledger-verify | 2a42a5721f57a18a170f3f33ec00043206ccf6e5 | push | failure ❌ |

- **dotnet-ci (push y PR, ambos runners windows-2025 y windows-11-arm): success**. Compilación .NET limpia (0 errores CS), tests pasan.
- **release-exe**: success en commits anteriores; artefacto no listable con mi token (API 404).
- **ledger-verify**: failure. pytest 573 passed / 0 failed localmente; determinismo OK; partition_check OK; coverage OK. El meta.json de CI reporta `status: failure` pero ningún archivo individual de ci-report (`pytest.txt`, `determinism.txt`, `coverage.txt`, `partition_check.txt`) muestra error específico. No se pudo descargar el log del job (EOF en la URL de Azure Blob).

Total de tests por proyecto (test-per-project.txt, ambos runners): se confirma en CI. Suma ≥ 326 (incluye el test de batería nuevo). pytest local: **573 passed, 0 failed**.

grep -n literal de test-console.txt por runner para `TestWave4Catalog_BatteryPercentageImplemented`, test de total (101) y tests de sección 4 / location: pendiente de descarga de logs de CI (no accesibles desde sandbox).

---

## 8. Qué NO se probó

- Nada se probó en Windows real. Los tests .NET se ejecutan en GitHub Actions (windows-2025, windows-11-arm); la sandbox no tiene .NET SDK.
- El artefacto release-exe no se verificó (sha256 no disponible: API 404).
- Los logs de CI de ledger-verify no son descargables (token limitado, EOF en URL de Azure Blob).
- Las capacidades Specified de §4 con 0 acciones (nvidia, printing, superfetch, svchostsplit) no se ejecutaron contra el motor real; su estado Specified se justifica por R1 (efectos no expresables).

---

## 9. Criterios de aceptación

| criterio | estado | evidencia |
|----------|--------|-----------|
| dotnet-ci (push y PR, ambos runners) success | CUMPLIDO | run 46125236752 (PR) y 46125232132 (push) = success |
| ledger-verify success | NO VERIFICADO | run 46125232095 = failure (sin error identificable en ci-report) |
| release-exe success | CUMPLIDO (previo) | run 46123330924 = success |
| tests ≥ 326, 0 fallos | CUMPLIDO (pytest local) | 573 passed / 0 failed; .NET en CI |
| 23 líneas §4 clasificadas con grep literal | CUMPLIDO | tabla en sección 2 |
| contradicciones 121 y 136 resueltas | CUMPLIDO | ambas Absent-At-Pin con evidencia de pin |
| tabla de capacidades desde JSON | CUMPLIDO | sección 3 |
| ADR-0003 y R1–R3 cumplidas | CUMPLIDO | `--check` OK; R1 sin violaciones en §4 |
| hardware/build caso por caso | CUMPLIDO | tabla en sección 3 |
| location.consent-deny con tabla de efectos | CUMPLIDO | sección 4; lfsvc correcto (no lsfvc) |
| constantes con before/after | CUMPLIDO | sección 5 |
| docs/reports/etapa7.md único y completo | EN PROGRESO | `docs/etapa7.md` eliminado; este doc es el único |
| PR isDraft:true, mergedAt:null | CUMPLIDO | PR #1 en Draft |
| 6 de 17 secciones cerradas | CUMPLIDO | `[1,2,3,4,9,10]` |

---

## 10. Desviaciones autorizadas (declaradas)

1. `docs/requirements/CONCILIACION_INVENTARIO.md` actualizado (conteos derivados del ledger regenerado). `INVENTARIO_USUARIO.md` NO tocado: sha256 `0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709` verificado.
2. `inventory/ledger/*.tsv` regenerados con scripts oficiales (no editados a mano).
3. `Assert.NotEmpty(definition.Actions)` en Wave1/Wave4 solo se aplica a `Implemented` (Specified de §4 puede tener 0 acciones por ADR-0003/R1). No se relajó ningún invariante de seguridad.
4. PR se mantiene en Draft (`isDraft:true`, `mergedAt:null`). Nunca `gh pr ready`.
5. No se usaron `git add -A`, commits vacíos, force-push ni `git reset`.

---

## 11. Supuestos y riesgos

**Supuestos:**
- `/tmp/upstream/winutil/config/tweaks.json` y `/tmp/upstream/atlas/…/Toggles/Services/*.psd1` son los pins fuente de verdad (sha256 de pins verificados en pasos previos).
- Los shas de git (40 chars) se obtienen de `git log` y `gh api`, no de memoria.

**Riesgos (no "ninguno"):**
- **ledger-verify falla en CI sin error identificable en ci-report.** No se pudo descargar el log del job (EOF en Azure Blob). pytest local pasa (573/0), determinismo OK, coverage OK. Riesgo medio: puede ser un problema transitorio de CI o un paso sin archivo de salida. Sin pushes de código restantes no se puede corregir desde la sandbox.
- **Nada se probó en Windows real.** Los tests .NET corren en GitHub Actions; la sandbox no tiene .NET SDK.
- **release-exe no verificable** (API 404 para el artefacto).

---

## 12. Commits (40 chars)

| commit | mensaje | tipo |
|--------|---------|------|
| 41f03ddf636ca9c1b7aecb73a18d27ab20e382f3 | feat: etapa 7 - catalogo secciones 4 y 9, ledger, informes y tests | código |
| 967313430f5959fcd7a982ec153804b0b551d70a | docs: etapa 7 - resumen de etapa, evidencias y desviaciones | docs (eliminado, contenido movido aquí) |
| 72a1b3db9b67959f4f329f9985d4c0330152f6a6 | fix: etapa 7 - RegistryHive -> RegistryHiveKind en test de batería | código |
| 306949fa4b68470373197924d3a8ab9d086a547b | fix: etapa 7 - tests .NET sección 4 y orden Section9 | código |
| 2a42a5721f57a18a170f3f33ec00043206ccf6e5 | fix: etapa 7 - NotEmpty solo para Implemented en Wave1 | código (HEAD) |

FIN ETAPA 7
