# Informe ETAPA 7 — Catálogo, ola 1 (estado y decisiones)

## Rama y estado de commits subidos

- Rama: `arena/ab2d6de7-evo-optimizer-on` (branched from `402af190e10a120dc893fa74f0a1d7b7d55b0c75` de `main`).
- Estado: `pr_open`, PR #1 DRAFT, `merged: false`, nunca `gh pr ready`.
- HEAD: `1d353422` (`fix: etapa 7 - retirar section4_services.json del catálogo`).

### Commits de la etapa 7 (2 pushes de código, YA están en origin)

| # | Sha completo (40 chars) | Mensaje | En origin |
|---|---|---|---|
| 1 | `a8fce8e725787ddb0174b568bc4ead14e7c34ee5` | feat: etapa 7 - sección 4 servicios: generador de capacidades con evidencia de pins | sí |
| 2 | `1d353422` | fix: etapa 7 - retirar section4_services.json del catálogo (rompe barrido de 88 capacidades del test .NET; se reintegra al cerrar formalmente la sección 4) | sí |

## CI en HEAD final (`1d353422`)

Todos los runners `completed/success`:

| Workflow | Conclusión |
|---|---|
| dotnet (windows-2025) | success |
| dotnet (windows-11-arm) | success |
| ledger-verify (ubuntu-latest) | success |
| Publish exe win-x64 | success |
| paso 12g (reconciliacion verificable de 12c) | success |

No se registraron fallos en ningún runner.

## pytest local (salida real, tras revert de `inventory/*.tsv`)

Comando: `python -m pytest -q tools/ledger_extract/tests/ tests/` (repo completo), python 3.11.

Resultado real:
```
573 passed in 20.13s
```

- 0 fallos. Las fallas vistas antes del revert (`inventory/ledger/toggle-state-audit.tsv` y `upstream-capability-map.tsv` modificados por ejecución local) desaparecieron al revertir esos ficheros con `git checkout --`. Ninguno de los dos TSVs queda modificado (`git status --short` vacío).
- Los 32 fallos preexistentes citados en estados anteriores (test_paso8b/8c/9/12, test_paso4c/4e) no reproducen en este estado con `/tmp/upstream` poblado (`fetch_upstream.py --only winutil --only atlas` OK en paso 0-upstream).

## Decisión paso 3 — Sección 4 "Optimización de Servicios"

`build_section4_catalog.py` está corregido y genera `catalog/capabilities/section4_services.json` determinista (8 capacidades, 66 acciones; `--check` reproducible). Pero el JSON fue **retirado del catálogo** en `1d353422` porque rompe el test .NET:

```csharp
Assert.Equal(88, all.Count);                              // Wave4CatalogTests.cs:299
Assert.Equal(new[] { 1, 2, 3, 9, 10 }, sections);         // Wave4CatalogTests.cs:302-303
```

Reintegrar sección 4 exigiría:
1. Añadir `section4_services.json` a `catalog/capabilities/`;
2. Actualizar el test .NET a `96` caps (88 + 8) y secciones `[1, 2, 3, 4, 9, 10]`;
3. Que las 8 capacidades de sección 4 cumplan **las mismas invariantes** que el resto (el test barre TODO el catálogo).

Cuando se intentó integrar (commit `a8fce8e7`), `dotnet-ci` falló. No hay .NET SDK en el sandbox, por lo que no se pueden compilar ni ejecutar los tests .NET localmente, ni confirmar qué invariantes rompen las capacidades de sección 4 mediante `test-console.txt`.

**Decisión: la sección 4 se DEJA FUERA del catálogo hasta el cierre formal de la sección 4.** Queda registrada como "generada, no en catálogo". No se toca el test .NET (no se relajan asserts; un test es PASA solo si lo confirma `test-console.txt`, imposible de obtener sin .NET SDK).

## Decisiones pendientes sección 9

### (A) Línea 278 "System Tray Configuration."

- Estado actual: `Absent-At-Pin` en `inventory/ledger/inventory-reconciliation.tsv` (línea `9 278`), confirmado por `test_paso10.py::test_las_correcciones_medidas_del_paso_10_estan_en_el_ledger` (awaits `rows["278"]["status"] == "Absent-At-Pin"`, 30 líneas Mapped, 58 filas en sección 9).
- Rationale medida (paso 10, en `build_final_reconciliation.py` `ABSENT_OVERRIDES`): el pin de WinUtil no tiene una función única de "configuración de bandeja"; `config/tweaks.json` declara dos ajustes concretos (`WPFTweaksDisableNotifications` y `WPFToggleBatteryPercentage`), y `WPFToggleBatteryPercentage` **no tiene línea propia en el inventario** (solo aparece en el pin, `tweaks.json:1395`). No hay página de bandeja en `xaml/`.
- **Decisión: se mantiene `Absent-At-Pin`.** No se mueve a `MAPPED_OVERRIDES` ni se añade `WPFToggleBatteryPercentage` como capacidad separada (rompería el patrón "cada capacidad cubre líneas de inventario" y el test de exactamente 19 capacidades de sección 9).

### (B) `system.location.consent-deny` (Specified, motivo)

- `reglas-r1-r3.tsv`: `system.location.consent-deny` = sección 9, state=`Specified`, Reversible, Low, Improves, Admin, `R1_ok=si, R2_ok=si, R3_aplica=si, R3_ok=si`.
- Datos locales del pin (no cuerpos de código de Atlas): `Toggles/General/Location.psd1` (ConsentStore `location`: `Value`=`Deny` en HKLM:16, `ShowGlobalPrompts` en HKCU:17); `Atlas.Privacy/Domain/Location.ps1` (`Set-AtlasLocationMachineState` en líneas 91-134, citado en la línea 113 de la provenance del test); efectos `ownership|process|registry|service` sobre `lfsvc` y `MapsBroker`.
- Test `TestWave4Catalog_LocationDeclaresStartupTypeAndStop` (Wave4CatalogTests.cs:208): confirma 4 acciones de servicio (`lfsvc`×2, `MapsBroker`×2), `Stop` → `SetStartupType(Disabled)`, privilegio `Admin`, `provenance` cita `Atlas.Privacy/Domain/Location.ps1:113`, 0 violaciones de `CapabilityRules.Validate`.
- **Decisión R1: `Specified` confirmado.** La capacidad declara los valores de registro que sí se pueden aplicar y documenta en `provenance`/`description` qué parte del pin queda sin declarar (estado de máquina y control de servicios más allá del registro). R1 no admite huecos silenciosos; el test lo verifica.

## Aceptación ETAPA 7

| Criterio | Estado |
|---|---|
| Secciones cerradas (6 de 17) | 5 de 17 cerradas (1, 2, 3, 9, 10); sección 4 generada pero **no en catálogo** (fuera hasta cierre formal) |
| Total tests ≥ 325 | base CI 6-K: 325 passed / 0 failed; CI actual de `1d353422`: 0 fallos en todos los runners |
| 0 fallos | CUMPLIDO (CI verde, pytest 573/0 local) |
| PR `draft: true`, `merged: false` | CUMPLIDO (no se ejecuta `gh pr ready`) |
| `inventory/*.tsv` sin modificar | CUMPLIDO (revertido con `git checkout --`) |
| JSON de catálogo solo vía scripts | CUMPLIDO (ningún JSON editado a mano; sección 4 no está en repo) |

## Desviaciones

- Sección 4 fuera del catálogo: limita el alcance de "6 de 17 secciones cerradas" a 5 de 17 hasta el cierre formal de sección 4 (requiere .NET SDK para validar invariantes y actualizar el test a 96 caps).
- SHA-256 del artefacto release-exe: NO VERIFICADO (artefactos no listables con el token disponible).

## Supuestos

- Los fallos de pytest observados en estados intermedios fueron debidos a los TSVs de inventory modificados por ejecución local (ya revertidos), no a cambios de etapa 7.
- La decisión de dejar sección 4 fuera se revisa cuando se disponga de .NET SDK para validar las invariantes del test .NET.

---\n\nFIN ETAPA 7
