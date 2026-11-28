# Matriz de cobertura maestra — paso 5

Generado por `tools/ledger_extract/generate_coverage_matrix.py`. No editar a mano.

- Filas de la conciliacion: **588**
- `inventory/ledger/inventory-reconciliation.tsv` sha256 `a4673908d164cacf026f86078af47d768c3f89c393cfce384addff846c009f81`
- Pins: Atlas `ec3c4058`, WinUtil `70c23c80`

## 1. Totales por estado

| Estado | Filas | % |
|---|---:|---:|
| `Mapped` | 160 | 27.2 % |
| `Mapped-To-App` | 5 | 0.9 % |
| `EVO-Exclusive` | 37 | 6.3 % |
| `Absent-At-Pin` | 315 | 53.6 % |
| `Informative-Header` | 71 | 12.1 % |
| **Total** | **588** | 100.0 % |

## 2. Tabla cruzada seccion x estado

| Sec | Mapped | M-App | EVO | Ausente | Info | Total |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 0 | 1 | 23 | 2 | 29 |
| 2 | 17 | 0 | 0 | 23 | 2 | 42 |
| 3 | 6 | 0 | 0 | 34 | 2 | 42 |
| 4 | 13 | 0 | 0 | 10 | 3 | 26 |
| 5 | 7 | 0 | 0 | 18 | 3 | 28 |
| 6 | 6 | 0 | 11 | 12 | 3 | 32 |
| 7 | 7 | 0 | 10 | 10 | 2 | 29 |
| 8 | 4 | 0 | 0 | 15 | 2 | 21 |
| 9 | 31 | 0 | 0 | 25 | 2 | 58 |
| 10 | 29 | 0 | 0 | 17 | 2 | 48 |
| 11 | 4 | 0 | 0 | 20 | 2 | 26 |
| 12 | 5 | 0 | 0 | 21 | 2 | 28 |
| 13 | 9 | 0 | 0 | 13 | 3 | 25 |
| 14 | 13 | 0 | 0 | 14 | 2 | 29 |
| 15 | 1 | 5 | 0 | 23 | 3 | 32 |
| 16 | 5 | 0 | 0 | 35 | 4 | 44 |
| 17 | 0 | 0 | 15 | 2 | 32 | 49 |
| **Total** | **160** | **5** | **37** | **315** | **71** | **588** |

## 3. Cobertura WinUtil

| Conjunto | Total | Mapeados | Cobertura |
|---|---:|---:|---:|
| Items de WinUtil | 162 | 53 | 32.7 % |
| Operaciones de tweak de WinUtil | 179 | 16 | 8.9 % |
| Apps de WinUtil | 239 | 5 | 2.1 % |

Las apps se referencian con `winutil:catalog-entry:<id>` desde la seccion 15; los items con `winutil:item:*` / `winutil:tweak-op:*` / `winutil:feature:*`.

## 4. Cobertura Atlas

| Conjunto | Total | Mapeados | Cobertura |
|---|---:|---:|---:|
| Toggles | 91 | 17 | 18.7 % |
| Entradas de manifiesto | 182 (177 habilitadas) | 3 | 1.6 % |
| Valores `.reg` (`atlas-reg-entries.tsv`) | 327 | 0 | 0.0 % |
| Ficheros `.reg` | 11 | — | n/d |
| Efectos de script (`atlas-effects.tsv`) | 986 | 10 | 1.0 % |
| Ficheros inventariados (`atlas-files.tsv`) | 1082 | — | n/d |

## 5. Capacidades atomicas para el catalogo EVO

| Concepto | Valor |
|---|---:|
| `mapped_ids` distintos en toda la conciliacion | 104 |
| De ellos, apps de WinUtil | 5 |
| De ellos, items de WinUtil | 53 |
| De ellos, toggles Atlas | 17 |
| De ellos, entradas de manifiesto Atlas | 3 |
| De ellos, operaciones de tweak de WinUtil | 16 |
| De ellos, efectos de script de Atlas | 10 |
| De ellos, valores `.reg` de Atlas | 0 |
| De ellos, sin ledger de origen reconocido | 0 |

Ademas, las filas `EVO-Exclusive` (37) son capacidades que el catalogo EVO debe aportar por si mismo, sin contraparte en los pins.

