# Informe ETAPA 6-C — Paso 5: conteo de capacidades `Implemented` bloqueadas

## Fuente y método

- Fuente: `catalog/capabilities/*.json` (lectura únicamente; no se toca `catalog/` ni `inventory/*.tsv`).
- Universo: 88 capacidades declaradas en el catálogo.
- Foco: las 69 capacidades con `"state": "Implemented"`.
- Regla de bloqueo: una capacidad `Implemented` se considera **bloqueada** si viola `CapabilityRules.Validate` / `ValidateReversibility` (src/Evo.Core/Models/CapabilityRules.cs), esto es, incoherencias entre riesgo, reversibilidad, restauración, confirmación, privilegio, securityImpact, SectionId (1-17), Variants, o autodependencia/autoconflicto.
- El desglose es por `Privilege` y por `Risk`.

## Resultado

| Métrica | Valor |
|---|---|
| Capacidades totales en catálogo | 88 |
| `Implemented` | 69 |
| `Specified` (no implementadas) | 19 |
| `Implemented` bloqueadas por motivo | **0** |
| `Implemented` sin violaciones | 69 |

## Desglose de las 69 capacidades `Implemented`

### Por `Privilege`

| Privilege | Total `Implemented` | Bloqueadas | % bloqueadas |
|---|---:|---:|---:|
| User | 23 | 0 | 0% |
| Admin | 46 | 0 | 0% |
| TrustedInstaller | 0 | 0 | — |

### Por `Risk`

| Risk | Total `Implemented` | Bloqueadas | % bloqueadas |
|---|---:|---:|---:|
| Safe | 30 | 0 | 0% |
| Low | 30 | 0 | 0% |
| Medium | 3 | 0 | 0% |
| High | 6 | 0 | 0% |
| Critical | 0 | 0 | — |

## Motivos de bloqueo

Ninguna. El catálogo de capacidades `Implemented` es consistente con `CapabilityRules.Validate`: no hay violaciones de reversibilidad/restauración/confirmación, ni SectionId fuera de rango, ni Variants vacío, ni SecurityImpact=Reduces con riesgo bajo, ni TrustedInstaller con riesgo bajo, ni autodependencias/autoconflictos.

## Conclusión

El Paso 5 no detectó capacidades `Implemented` bloqueadas por motivo. El desglose por Privilege y Risk queda registrado arriba. Las 19 capacidades `Specified` quedan fuera de alcance (aún no implementadas).
