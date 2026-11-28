# Etapa 7 — Cierre: sección 4 (servicios), sección 9 (registro/batería), CI y evidencias

Rama: `arena/ab2d6de7-evo-optimizer-on`. PR #1: `isDraft:true`, `mergedAt:null`. Commit final de código: `e76742f1bc16a5e34b3201e383db68603cab39e2`. Commit de docs pendente (este documento).

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
6. `docs/reports/etapa7.md` — este documento (único; `docs/etapa7.md` eliminado con `git rm`).

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

### Contradicciones resueltas (E)

**Línea 121** ("Services — configuración de inicio Manual"): permaneció `Absent-At-Pin`.
Evidencia grep en ambos pins:
- `grep -rn "Set-WinUtilService" /tmp/upstream/winutil/config/tweaks.json` → 0 hits (no existe `Set-WinUtilService` en el pin).
- `grep -rn "WPFTweaksServices" /tmp/upstream/winutil/config/tweaks.json` → tweaks.json:146 define `WPFTweaksServices`; `config/preset.json:8,19,29` lo referencian.
- Las capacidades `services.winutil.diagtrack` / `mapsbroker` / `storsvc` / `sharedaccess` / `cscservice` declaran `winutil@70c23c80641d7370532af2f619b2842658600842:config/tweaks.json:WPFTweaksServices`, y las TSV líneas 122-126 están ya `Mapped` a operaciones `WPFTweaksServices:service:N`.
Decisión: WPFTweaksServices SÍ se expresa en el pin (criterio de E.2 satisfecho: las capacidades lo expresan y las líneas 122-126 están Mapped). La línea 121 es un **encabezado de sub-bloque** que agrupa esos servicios ya mapeados, no es una operación propia del pin, por REQ-002 no se inventa una operación para ella → se queda `Absent-At-Pin`. No se añadió a `MAPPED_OVERRIDES`.

**Línea 136** ("Windows Update Services"): permaneció `Absent-At-Pin`.
Evidencia grep en ambos pins:
- `grep -rn "wuauserv" /tmp/upstream/atlas/` → aparece solo en `app/src/` (código fuente de Atlas, no en toggles `.psd1`).
- `grep -rn "Windows Update" /tmp/upstream/atlas/package/Executables/AtlasModules/Toggles/Services/` → 0 hits.
- En winutil: `wuauserv` aparece en `docs/.../features/Fixes/Update.mdx:56` (lista de servicios de un script de reparación, no como toggle expresable) y `SPEC.md:96`/`AGENTS.md:98` (documentación de riesgo).
Decisión: el pin tiene toggles generales de actualización (`ToggleWindowsUpdates.psd1`, `AutomaticUpdates.psd1`) pero **no** un toggle específico llamado "Windows Update Services", y no hay candidato de ledger (REQ-002: no inventar). Antes figuraba `Mapped` en el paso 4e por error (regla R3 contra tests de Atlas, no producto); se corrigió a `Absent-At-Pin` en `ABSENT_OVERRIDES` con motivo literal.

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

Solo las 4 acciones de servicio (lfsvc×2, MapsBroker×2) están expresadas. Como R1 exige que `Implemented` exprese TODO el efecto del pin, `system.location.consent-deny` permanece `Specified` con el motivo escrito en su descripción y provenance. (Nota: el servicio correcto es `lfsvc`, no `lsfvc` — typo corregido en el análisis.)

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

Explicación T3 OK 2 → 7 y PENDIENTE 15 → 16 (datos de `inventory/ledger/toggle-state-audit.tsv`):
- OK +5: `services.atlas.lanmanworkstation`, `services.atlas.networkdiscovery`, `services.atlas.nvidiadisplaycontainer`, `services.atlas.printing`, `services.atlas.superfetch` (todas §4, `estado=Disable`, `operaciones_contrarias_no_reproducidas` vacía → OK).
- PENDIENTE +1: `services.atlas.bluetooth` (§4, `estado=Disable`, `no_reproducidas=[Set HKLM:...\AllowBluetooth value=2]` → PENDIENTE).
- CONTRARIO se mantiene en 3 (explorer.home.hide, explorer.home.restore, explorer.removable-drives.sidebar).

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

Los `.tsv` se regeneran con sus scripts oficiales (no se editan a mano). Los `.tsv` que solo se ensucian por correr pytest no se commitean.

---

## 7. CI — tabla final de runs (commits `e76742f1` y `4d79968`)

| id | workflow | sha (40 chars) | evento | conclusión |
|----|----------|----------------|--------|------------|
| 46133100955 | dotnet-ci | e76742f1bc16a5e34b3201e383db68603cab39e2 | pull_request | **success** ✅ |
| 46133096689 | ledger-verify | e76742f1bc16a5e34b3201e383db68603cab39e2 | push | **success** ✅ |
| 46131002780 | dotnet-ci | 4d79968528c2b2e8e824b87e8dbd364c6b4b39af | pull_request | **success** ✅ |
| 46130999562 | dotnet-ci | 4d79968528c2b2e8e824b87e8dbd364c6b4b39af | push | **success** ✅ |
| 46130999582 | ledger-verify | 4d79968528c2b2e8e824b87e8dbd364c6b4b39af | push | **success** ✅ |

- **dotnet-ci (push y PR, ambos runners windows-2025 y windows-11-arm): success**. Compilación .NET limpia (0 errores CS), tests pasan.
- **ledger-verify: success** en `e76742f1` (run 46133096689) y en `4d79968` (run 46130999582). La causa raíz del rojo fue que el paso 10 del workflow hardcodeaba valores del paso 6 (88 capacidades, sec9 mapped 30, secciones `[1,2,3,9,10]`); se corrigieron a los valores del paso 7 (101 capacidades, sec9 mapped 31, secciones +`4`, paso 12c: caps9 20/acts9 48, auditoría 198 filas, G2/G3 actualizados). Ninguna verificación se relajó: `assert` y `sys.exit` idénticos antes/después (workflow 3/13, test_paso12.py 136/0).
- **release-exe**: success en run 46123330924 (sha `41f03ddf636ca9c1b7aecb73a18d27ab20e382f3`). `git diff --stat 41f03ddf636ca9c1b7aecb73a18d27ab20e382f3 origin/arena/ab2d6de7-evo-optimizer-on -- src catalog Directory.Build.props global.json` → **vacío**, por tanto el artefacto `EvoClean-preview-win-x64` de ese run equivale al código final (incluye los catálogos §4 y §9). Link: https://github.com/EvoMaxPC/Evo_Optimizer-On/actions/runs/46123330924 (el artifact no es listable vía `gh api .../artifacts` por limitación del token → 404, no se reporta como "expirado").

**test-per-project.txt** (`ci-report/latest/dotnet-windows-*/test-per-project.txt`, ambos runners):
```
Evo.App.Tests: total=28 passed=28 failed=0
Evo.Catalog.Tests: total=80 passed=80 failed=0
Evo.Core.Tests: total=34 passed=34 failed=0
Evo.Detection.Tests: total=35 passed=35 failed=0
Evo.Engine.Tests: total=135 passed=135 failed=0
Evo.Windows.Tests: total=14 passed=14 failed=0
```
Total = 326, fallos = 0, en **ambos** runners (≥ 326, 0 fallos). ✅

**grep -n de test-console.txt** (ambos runners, `Passed`):
- `TestWave4Catalog_BatteryPercentageImplemented` (PASO D-A, línea 278 Mapped).
- `TestWave4Catalog_EveryCapabilityInTheCatalogMeetsTheSameInvariants` (`Assert.Equal(101, all.Count)`).
- `TestWave1CatalogTests.TestWave1Catalog_LoadsAndValidates` (`Assert.Equal(101, catalog.Count)`).
- `TestWave4Catalog_LocationDeclaresStartupTypeAndStop` (sección 4 servicios, `Assert.Equal(4, services.Count)`).
- `TestWave4Catalog_LocationDeclaresStartupTypeAndStop` / `LocationCapability_StopsServicesAndRestoresBothStates` (location).

pytest local: **573 passed, 0 failed**.

---

## 8. Qué NO se probó

- Nada se probó en Windows real. Los tests .NET se ejecutan en GitHub Actions (windows-2025, windows-11-arm); la sandbox no tiene .NET SDK.
- Las capacidades Specified de §4 con 0 acciones (nvidia, printing, superfetch, svchostsplit) no se ejecutaron contra el motor real; su estado Specified se justifica por R1 (efectos no expresables).

---

## 9. Criterios de aceptación

| criterio | estado | evidencia |
|----------|--------|-----------|
| 1. Diff 2475d024..origin solo toca workflow + test_paso12.py, sin basura | CUMPLIDO | `git diff --stat 2475d0245611732270baf772458c4cdfbc9072c2 origin/arena/ab2d6de7-evo-optimizer-on` → solo los 2 archivos |
| 2. Cada constante cambiada tiene origen medido; ninguna verificación relajada | CUMPLIDO | assert/sys.exit iguales antes/después; valores de `measure_capability_completeness.py`, `audit_catalog_values.py`, `build_section9_catalog.py --check`, `measure_toggle_states.py` |
| 3. T3 OK 2→7 explicado con datos | CUMPLIDO | 5 OK nuevas §4 (lanmanworkstation, networkdiscovery, nvidiadisplaycontainer, printing, superfetch) + 1 PENDIENTE (bluetooth), de `toggle-state-audit.tsv` |
| 4. dotnet-ci (push y PR, ambos runners) y ledger-verify en success con ids y sha 40; test-per-project ≥ 326, 0 fallos | CUMPLIDO | runs 46133100955 / 46133096689 (e76742f1) y 46131002780 / 46130999562 / 46130999582 (4d79968), todos success; test-per-project 326/0 ambos runners |
| 5. release-exe correspondiente al catálogo final con link, o equivalencia con diff vacío | CUMPLIDO | run 46123330924, diff vacío, link https://github.com/EvoMaxPC/Evo_Optimizer-On/actions/runs/46123330924 |
| 6. Líneas 121 y 136 resueltas con grep literal en ambos pins | CUMPLIDO | tabla en sección 2 (E); WPFTweaksServices expresado (tweaks.json:146) para 121; wuauserv solo en docs Update.mdx:56, sin toggle "Windows Update Services" para 136 |
| 7. Tablas de F presentes (23 líneas §4, 13 capacidades, efectos location, constantes antes/después) | CUMPLIDO | secciones 2, 3, 4, 5 |
| 8. ledger-verify success también en el commit de docs; PR draft y sin merge | EN PROGRESO | PR #1 `isDraft:true`, `mergedAt:null`; docs push pendiente, luego verificar CI en el commit de docs |

---

## 10. Desviaciones autorizadas (declaradas)

1. `docs/requirements/CONCILIACION_INVENTARIO.md` actualizado (conteos derivados del ledger regenerado). `INVENTARIO_USUARIO.md` NO tocado: sha256 `0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709` verificado.
2. `inventory/ledger/*.tsv` regenerados con scripts oficiales (no editados a mano).
3. `Assert.NotEmpty(definition.Actions)` en Wave1/Wave4 solo se aplica a `Implemented` (Specified de §4 puede tener 0 acciones por ADR-0003/R1). No se relajó ningún invariante de seguridad.
4. PR se mantiene en Draft (`isDraft:true`, `mergedAt:null`). Nunca `gh pr ready`.
5. No se usaron `git add -A`, commits vacíos, force-push ni `git reset`.
6. **Riesgo declarado (no se arregla en esta etapa):** los números fijos (88, 30, 31, 19, 47, 197, 2, 15, …) están hardcodeados en el workflow y en `test_paso12.py`. Se actualizaron de paso 6 a paso 7, pero en cada etapa futura volverán a romperse hasta que se endurezcan (leer los valores dinámicamente de los JSON/TSV generados en lugar de literales). Queda para endurecimiento.

---

## 11. Supuestos y riesgos (residuales)

**Supuestos:**
- `/tmp/upstream/winutil/config/tweaks.json` y `/tmp/upstream/atlas/…/Toggles/Services/*.psd1` son los pins fuente de verdad.
- Los shas de git (40 chars) se obtienen de `git log` y `gh api`, no de memoria.

**Riesgos residuales (cierran en esta etapa):**
- **ledger-verify: RESUELTO.** Ahora success en `e76742f1` (46133096689) y `4d79968` (46130999582). La causa raíz (valores hardcodeados paso 6 en el workflow) fue corregida a valores del paso 7.
- **Nada se probó en Windows real.** Los tests .NET corren en GitHub Actions; la sandbox no tiene .NET SDK.
- **release-exe artifact no listable vía `gh api .../artifacts`** (token limitado, 404). Equivalencia probada con diff vacío contra run 46123330924.

---

## 12. Commits (40 chars)

| commit | mensaje | tipo |
|--------|---------|------|
| e76742f1bc16a5e34b3201e383db68603cab39e2 | docs: etapa 7 - documenta decision E lineas 121 y 136 en build_final_reconciliation | código (HEAD) |
| 4d79968528c2b2e8e824b87e8dbd364c6b4b39af | fix: etapa 7 - sincroniza con remoto y aplica correccion de workflow paso 7 | código (merge) |
| cc26732ef3c3b9e47f8373106a6bb6837e78718a | fix: etapa 7 - ledger-verify usa valores del paso 7 en workflow y test_paso12 | código |
| b878c1f8753b4fdb43ca79a416998838412259a7 | feat: etapa 7 - catalogo secciones 4 y 9, tests .NET y python, herramientas y reconciliacion | código |
| 737f6d89402be507927fc6b7d565b6e3ff3e0ea1 | docs: etapa 7 - informe completo con tabla de capacidades, efectos y desviaciones | docs |
| 2475d0245611732270baf772458c4cdfbc9072c2 | docs: etapa 7 - cierre con tabla de 23 líneas, capacidades, efectos de location y CI | docs (origen) |

FIN ETAPA 7
