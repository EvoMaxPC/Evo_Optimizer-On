#!/usr/bin/env python3
"""Validador estricto de la conciliacion del inventario.

Comprueba, y falla con detalle si algo no cuadra:

1. `inventory/ledger/inventory-reconciliation.tsv` tiene **exactamente 588** filas.
2. La suma de los cinco estados == 588.
3. Cero estados desconocidos o vacios.
4. Cero celdas con caracteres de control o de mas de 400 caracteres.
5. Todos los `mapped_ids` existen en el TSV de origen correspondiente, y toda
   fila `Mapped`/`Mapped-To-App` tiene al menos un id.
6. Determinismo: dos ejecuciones del extractor dan el mismo sha256.

Exit 0 si todo pasa; exit 1 con el detalle del primer bloque de fallos.

Uso:
    python3 tools/ledger_extract/validate_reconciliation.py
    python3 tools/ledger_extract/validate_reconciliation.py --json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "inventory" / "ledger"
TSV = LEDGER / "inventory-reconciliation.tsv"
EXPECTED_ROWS = 588
STATUSES = ("Mapped", "Mapped-To-App", "EVO-Exclusive", "Absent-At-Pin",
            "Informative-Header")
MAX_CELL = 400


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def source_ids() -> dict[str, set[str]]:
    files = {
        "winutil-items": "winutil-items.tsv",
        "winutil-apps": "winutil-apps.tsv",
        "atlas-toggles": "atlas-toggles.tsv",
        "atlas-manifest": "atlas-manifest.tsv",
        "atlas-effects": "atlas-effects.tsv",
        "atlas-tweak-ops": "atlas-tweak-ops.tsv",
        "winutil-tweak-ops": "winutil-tweak-ops.tsv",
        "atlas-tweak-files": "atlas-tweak-files.tsv",
        "atlas-files": "atlas-files.tsv",
        "atlas-toggle-ops": "atlas-toggle-ops.tsv",
    }
    out: dict[str, set[str]] = {}
    for key, name in files.items():
        p = LEDGER / name
        out[key] = {r["item_id"] for r in read_tsv(p)} if p.is_file() else set()
    return out


def check(rows: list[dict], ids: dict[str, set[str]]) -> list[str]:
    errors: list[str] = []
    all_ids = set().union(*ids.values())

    if len(rows) != EXPECTED_ROWS:
        errors.append(f"filas: {len(rows)} != {EXPECTED_ROWS}")

    estados = Counter(r["status"] for r in rows)
    desconocidos = {k: v for k, v in estados.items() if k not in STATUSES}
    if desconocidos:
        errors.append(f"estados desconocidos o vacios: {desconocidos}")
    if sum(estados.values()) != EXPECTED_ROWS:
        errors.append(f"suma de estados {sum(estados.values())} != {EXPECTED_ROWS}")

    lineas = [r["linea"] for r in rows]
    if len(set(lineas)) != len(lineas):
        errors.append("hay numeros de linea repetidos")

    control = []
    largas = []
    for r in rows:
        for k, v in r.items():
            if v and any(ord(c) < 32 for c in v):
                control.append((r["linea"], k))
            if len(v or "") > MAX_CELL:
                largas.append((r["linea"], k, len(v)))
    if control:
        errors.append(f"celdas con caracteres de control: {control[:5]}")
    if largas:
        errors.append(f"celdas de mas de {MAX_CELL} caracteres: {largas[:5]}")

    for r in rows:
        st = r["status"]
        mids = [m for m in (r["mapped_ids"] or "").split("|") if m]
        if st in ("Mapped", "Mapped-To-App") and not mids:
            errors.append(f"linea {r['linea']}: {st} sin mapped_ids")
        if st == "Mapped-To-App" and not all(
                m.startswith("winutil:catalog-entry:") for m in mids):
            errors.append(f"linea {r['linea']}: Mapped-To-App con id que no es app")
        for m in mids:
            if m not in all_ids:
                errors.append(f"linea {r['linea']}: id inexistente {m}")

    return errors


def determinism() -> tuple[bool, str, str]:
    """Ejecuta el extractor dos veces y compara el sha256 del TSV."""
    cmd = [sys.executable,
           str(ROOT / "tools" / "ledger_extract" / "build_final_reconciliation.py")]
    shas = []
    for _ in range(2):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return False, "", res.stderr[-400:]
        shas.append(hashlib.sha256(TSV.read_bytes()).hexdigest())
    return shas[0] == shas[1], shas[0], shas[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--skip-determinism", action="store_true")
    args = ap.parse_args(argv)

    if not TSV.is_file():
        print(f"ERROR: falta {TSV}", file=sys.stderr)
        return 1

    rows = read_tsv(TSV)
    errors = check(rows, source_ids())

    det_ok, sha1, sha2 = (True, "", "")
    if not args.skip_determinism:
        det_ok, sha1, sha2 = determinism()
        if not det_ok:
            errors.append(f"determinismo: sha1={sha1[:16]} sha2={sha2[:16]}")

    resumen = {
        "filas": len(rows),
        "por_estado": {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES},
        "determinismo": det_ok,
        "sha256": hashlib.sha256(TSV.read_bytes()).hexdigest(),
        "errores": errors,
    }
    if args.json:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
    else:
        print(f"filas      : {resumen['filas']}")
        for s in STATUSES:
            print(f"  {s:20s} {resumen['por_estado'][s]}")
        print(f"determinismo: {'OK' if det_ok else 'ROTO'}  sha256={resumen['sha256'][:16]}…")
        if errors:
            print("FALLOS:", file=sys.stderr)
            for e in errors[:20]:
                print(f"  - {e}", file=sys.stderr)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
