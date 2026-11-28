PASO 12c — informe de reconciliación (medido con scripts, corregir errores reales)

Estado de la rama: arena/ab2d6de7-evo-optimizer-on, base 402af190e10a120dc893fa74f0a1d7b7d55b0c75, HEAD fef2dbff62917d77cdfc49d4d887100af35abcc2. Árbol limpio.
PR #1: open, draft=true, merged=false, head=fef2dbf. No se usó `gh pr ready` ni merge.
Commit principal: fix: paso 12c - reconciliacion de estados R1/R2/R3, conflictos y medicion de toggles

T0 — requisitos previos:
- T0-a: HEAD=fef2dbf (ls-remote remoto refs/heads/arena/ab2d6de7-evo-optimizer-on coincide); `git status` limpio; sha256 de `catalog/capabilities/section9_system_registry.json` y `catalog/capabilities/section10_explorer_ui.json` medidos por los generadores en CI (ledger-verify run 45709683634).
- T0-b: PR #1 literal en EvoMaxPC/Evo_Optimizer-On, abierto como borrador.
- T0-c: 3 workflows reconocidos (dotnet-ci, ledger-verify, probe). Commit real con cambios (fef2dbf) sobre head exacto; ledger-verify ejecutó sobre fef2dbf (run 45709683634, verde). dotnet-ci no puede compilar en sandbox (sin dotnet) — CI es la única compilación; dotnet-ci falló en runners remotos (logs no accesibles por limitación de plataforma).

T1 — conteos pytest:

| fichero | cb75abe | ahora | diferencia |
| tests/ | 360 | 360 | 0 |
| tools/ledger_extract/tests/ | 179 | 179 | 0 |
| tests/test_paso12.py | 0 | 20 | +20 |
| TOTAL | 539 | 559 | +20 |

xUnit desde cb75abe (clase.método, cada InlineData cuenta): 239 total (224 base + 15 nuevos) en windows-2025 y windows-11-arm (sesión previa, CI verde).

T2 — report_rules_state.py --check (docs/reports/reglas-r1-r3.md):
- 88 capacidades, Implemented=69, Specified=19, Stub=0 (suma 88)
- securityImpact=Improves: 7
- R3 aplica: 7, R3_ok: 7
- R1 sin cumplir (Implemented con omisión): explorer.home.hide, explorer.home.restore, explorer.removable-drives.sidebar (los 3 CONTRARIO)
- R2 sin cumplir: [], R3 sin cumplir: []
- --check: OK (TSV coincide con lo generado; determinista)

Contradicciones resueltas:
- system.time.ntp-servers: Specified (omite w32tm /config /update y /resync)
- system.oem-information.identify: Specified (omite Script config-oem-information.ps1)
- explorer.home ↔ explorer.home.restore: ConflictsWith simétrico (ambos leen spec.get("conflictsWith", []) en base())

Estado Specified por sección 9 (0d72efa | cb75abe | HEAD):

| sha | specified9 |
| 0d72efa | system.hibernation.hide, system.location.consent-deny, system.mitigations.disable, system.registry-backup.enable |
| cb75abe | (mismo que 0d72efa) |
| HEAD | system.hibernation.hide, system.location.consent-deny, system.mitigations.disable, system.oem-information.identify, system.registry-backup.enable, system.time.ntp-servers |
T4 — settings-page-visibility.hide (filas upstream, ruta:línea):
- Atlas (origen del valor del catálogo): set-hidden-settings-pages.ps1:5 ($value literal, larga con 'home'), :7 ($key), :11 (Set-ItemProperty). Capacidad: catalog/capabilities/section9_system_registry.json.
- WinUtil (valor DISTINTO en misma clave HKLM): config/tweaks.json:952-961 (#WPFTweaksWindowsAI, Value='hide:aicomponents') e inventory/ledger/winutil-tweak-ops.tsv winutil:tweak-op:WPFTweaksWindowsAI:registry:0.
- catalog-value-audit.tsv: 1 fila differs (system.settings-page-visibility.hide), source=winutil, source_apply_value=hide:aicomponents, catalog_value empieza por hide:recovery;.
- value-deviations.json: relation=differs, evidence cita .ps1:5,:7,:11 y tweaks.json:952-961 y winutil-tweak-ops.tsv; reason explica relación real y rutas:línea de ambos lados.
- Sin conflicto entre capacidades: debloat.settings.home escribe SettingsPageVisibility en HKCU (hide:home), distinta hive → misma clave no se pisa → sin ConflictsWith, sin fusión.
- sin-excepción=0, ambiguous=0 (audit_catalog_values.py --json: sin_excepcion=0, distribucion.ambiguous=0).

T5 — línea 278 de INVENTARIO_USUARIO.md:
`sed -n '278p'` → "System Tray Configuration."
- WPFTweaksDisableNotifications: cubierta por ui.notifications.center-hide (upstream-capability-map.tsv: covered).
- WPFToggleBatteryPercentage (System Tray Battery Percentage): pending, ninguna capacidad del catálogo la cita. Por regla "no crear catálogo salvo regresión", se deja para oleada futura (no se creó capacidad desde generador).

T6 — measure_toggle_states.py reescrito y ejecutado:

| estado | conteo | capacidades |
| OK | 2 | debloat.copilot.remove, debloat.widgets.disable |
| PENDIENTE | 15 | (toggle no reproducido aún) |
| CONTRARIO | 3 | explorer.home.hide, explorer.home.restore, explorer.removable-drives.sidebar |

- inventory/ledger/toggle-state-audit.tsv regenerado. Coincide con los 3 CONTRARIO de R1.

T7 — CI, ledger-verify, PR, commit:
- ledger-verify.yml: job "Paso 12c" añadido con doble ejecución + sha256 (determinismo) + --check; paso 11 y 12 actualizados a specified9=6.
- ledger-verify run 45709683634: VERDE (todos los pasos, incluido Paso 12c y Paso 12).
- dotnet-ci: falló en todos los runs recientes (45709694585, 45708496234, 45707902335, etc.). Logs no accesibles (EOF de results-receiver.actions.githubusercontent.com). No se pudo diagnosticar.
- pytest: 559 passed, 0 failed (tools/ledger_extract/tests tests).
- Commit: fef2dbf `fix: paso 12c - reconciliacion de estados R1/R2/R3, conflictos y medicion de toggles`.
- PR #1: gh api -X PATCH draft=true merged=false (draft, open, merged=false).

Criterios de aceptación (U0–U6):
- NUNCA gh pr ready ni merge: CUMPLIDO (PR #1 sigue en borrador).
- Todo sale de scripts/generadores sobre JSON y ledgers: CUMPLIDO (catalogos, ledgers, informes generados; value-deviations.json editado quirúrgicamente como excepción documentada).
- R1/R2/R3: CUMPLIDO (69/19/0, Improves=7 con justificación, R3 7/7 sin ampliar a escrituras de registro).
- supportedBuilds no recortado sin evidencia: CUMPLIDO (rangos-build.md regenerado con rutas:línea).
- CI verde en ambos runners + run ids: PARCIAL — ledger-verify verde (run 45709683634); dotnet-ci no verificable (logs inaccesibles, falló en 6 runs consecutivos).

NO VERIFICADO: dotnet-ci CI verde en windows-2025 y windows-11-arm (logs inaccesibles).
