# ADR-0001 — Granularidad de items del ledger

- **Estado**: aceptado
- **Fecha**: 2026-11-23
- **Contexto**: REQ-005 exige que cada fichero de upstream quede clasificado y
  que ninguno se ignore en silencio. Un ledger por fichero es demasiado grueso
  (un `tweaks.json` con 69 claves esconde 69 operaciones) y un ledger por línea
  es inmanejable. Hace falta una unidad de trabajo estable y auditable.

## Decisión

**Un item del ledger = una unidad de comportamiento o de dato identificable por
su propia clave dentro de upstream**, no un fichero. Concretamente:

| kind | qué es | ejemplo (WinUtil) | ejemplo (Atlas) |
|---|---|---|---|
| `tweak` | una clave de `tweaks.json` / `feature.json` | `WPFTweaksTelemetry` | una acción de un `.ps1` de `Scripts/Tweaks` |
| `function` | una función PowerShell con nombre propio | `Invoke-WPFtweaksbutton` | `Install-Atlas`, `Set-SettingsPageVisibility` |
| `script` | un script ejecutable sin función exportada | `Compile.ps1`, `windev.ps1` | `DisableSuperFetch.cmd` |
| `reg-entry` | un fichero `.reg` completo (y sus claves) | — | `Scripts/Registry/SecurityHealthTray/enable.reg` |
| `catalog-entry` | una entrada de catálogo de software | una de las **239** de `applications.json` | `Install Software` del AtlasDesktop |
| `config-key` | una clave de configuración de UI/estado | `preset.json` → `Standard`/`Minimal`/`Advanced` | `.atlasPsModulesPath` |
| `i18n-key` | una clave de traducción, **solo si** el proyecto la usa como contrato | — | `app/i18n/*` (claves FTL) |

### Regla de las 239 aplicaciones

Las **239 entradas de `config/applications.json`** se cuentan **aparte** como
`kind: catalog-entry`, no como tweaks. Un catálogo de software no es una
optimización de Windows: mezclarlos inflaría artificialmente la cobertura de
REQ-000. Cada `catalog-entry` se mapea a un paquete instalable (winget/choco o
AppX) y se somete a REQ-001 (incorporar ≠ ejecutar).

### Items `kind: implementation-detail`

Los detalles de implementación —`Compile.ps1` (concatenación de scripts),
`Runspaces` (ejecución concurrente en WinUtil), el *Broker* de TrustedInstaller
en Atlas— **permanecen en el ledger** con `kind: implementation-detail`
mapeados a la capacidad EVO que cubre su función. No se descartan porque
REQ-000 prohíbe descartar nada, pero tampoco se presentan como optimizaciones
de Windows: son mecanismos del motor.

Ejemplos de mapeo:

| item upstream | capacidad EVO que cubre |
|---|---|
| `Compile.ps1` | empaquetado de un único artefacto / build reproducible |
| `Invoke-WPFRunspace` | orquestación concurrente con feedback de progreso |
| `TrustedInstaller Broker` | elevación controlada sobre componentes protegidos |
| `Export-AtlasCatalog` | exportación de catálogo para auditoría |

### Items `absent-at-pin`

Los items de las **secciones 16 y 17** del inventario del usuario que no
existan en el SHA fijado se registran como **`absent-at-pin`** y **no se
descartan**: la sección 17 es explícitamente una lista de "capacidades que no
debemos perder", así que su ausencia en upstream es un dato, no una excusa.
Se cubrirán con un equivalente EVO y quedan en el ledger con
`status: absent-at-pin` + `evidence: "no aparece en <repo>@<sha>"`.

## Licencia

Atlas es **GPL-3.0** y este repositorio también, así que la incorporación es
compatible. Para WinUtil (**MIT**) se conserva el aviso en
`THIRD_PARTY_NOTICES.md`. En ambos casos **el ledger guarda metadatos, claves y
hashes, no cuerpos de código**: copiar código de upstream requiere un ADR
específico (AGENT_CONTRACT §5).

## Consecuencias

- El ledger se puede auditar contra `inventory/upstream/*.files.tsv` +
  `inventory/partition/results/*.tsv`: cada fichero `extract` debe aportar al
  menos un item o declarar `no-items` con razón.
- Un fichero nuevo en upstream rompe `partition_check.py` (no hay catch-all),
  lo que fuerza a revisar la partición en vez de ignorarlo.
- El conteo de cobertura de REQ-000 se hace por `kind`, nunca por número de
  ficheros.
