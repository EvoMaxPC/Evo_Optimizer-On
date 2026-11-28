# Paso 2 — Fijación de upstream y partición

Fecha: 2026-11-23 · Rama: `arena/ab2d6de7-evo-optimizer-on`
Contrato: `docs/AGENT_CONTRACT.md` · Paso 1: `docs/reports/paso1.md`

## Resumen

- `list_files.py` extrae el árbol completo de ambos repos en su SHA fijado y
  escribe `inventory/upstream/{winutil,atlas}.files.tsv`. SHA del clon == SHA
  del lock en los dos casos (si no, aborta).
- Recon generado con comando trazable para cada cifra; **las 17 cifras del
  reconocimiento previo coinciden exactamente**.
- Sonda de 88 términos en `docs/inventory-recon/keyword-probe.tsv`.
- Partición: 704 + 1550 = 2254 ficheros, **0 sin clasificar**, **0 reglas
  muertas**, **0 excludes sobre comportamiento**.
- `docs/adr/ADR-0001-granularidad-de-items.md` fija la unidad de item.
- `ledger-verify.yml` en ubuntu-latest: pytest + partition_check + publicación
  en `ci-report`.
- Suite: 50 tests (24 previos + 26 nuevos).

## Cifras

| | winutil | atlas |
|---|---:|---:|
| ficheros | 704 | 1550 |
| extract | 206 | 1051 |
| reference | 495 | 496 |
| exclude | 3 | 3 |
| reglas en la partición | 17 | 34 |

Excluidos de winutil: `.gitattributes`, `.gitignore`, `LICENSE`.
Excluidos de atlas: `.gitattributes`, `.gitignore`, `LICENSE`.

## Hallazgos de implementación

1. `fnmatch` no sirve para estos globs: traduce `*` a `.*` (cruza `/`) y `*`
   inicial no casa con `/` inicial. Se sustituyó por un traductor propio
   (`*` no cruza `/`, `**` sí). Sin ese cambio, reglas como
   `package/**/*.cmd` y `tools/**/*.yaml` quedaban muertas.
2. Las reglas por extensión deben ir **antes** que las de directorio, o quedan
   muertas por solapamiento (gana la primera). Reordenado en atlas.
3. Sin catch-all a propósito: un fichero nuevo en upstream rompe el check en
   vez de caer en un cubo invisible (REQ-005).

## Diferencias con el reconocimiento previo

Ninguna: 239/69/33/34/3/4/11/8 claves de config, 197 `.ps1` (35+90), 372 `.ps1`,
188 `.cmd`, 11 `.reg`, 24 `.yml`, 6 `.yaml`, 109 tests Pester. Todo `OK`.
