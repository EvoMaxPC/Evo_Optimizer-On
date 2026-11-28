#!/usr/bin/env python3
"""Cobertura de extract de Atlas (criterio de ADR-0001).

Dos niveles, porque en Atlas "cobertura" no puede significar lo mismo que en
WinUtil (Solo hechos, licencia GPL-3.0):

  * ESTRUCTURAL — cada fichero extract llega a `inventory/ledger/atlas-files.tsv`
    (identidad: ruta, tamaño, líneas, sha256). Si además aporta hechos de
    contenido (funciones, valores de registro, líneas de texto) se cuenta como
    "con hechos"; si no (binarios), exige motivo declarado.
  * SEMÁNTICA — qué hace cada script y qué toggles expone la app. **NO se
    extrae en este paso** (Paso 4b). Se declara como deuda, no como cobertura.

Exit 1 si algún extract sin hechos no tiene motivo declarado.

Uso:
    python3 tools/ledger_extract/coverage_check_atlas.py [--json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "inventory" / "partition" / "results" / "atlas.tsv"
FILES = ROOT / "inventory" / "ledger" / "atlas-files.tsv"
REG = ROOT / "inventory" / "ledger" / "atlas-reg-entries.tsv"

# Motivos para ficheros extract que no aportan hechos de contenido.
# Clave: sufijo de extensión (los binarios son intercambiables por nombre).
REASONS = {
    ".cab": "paquete CAB de Windows Update: solo indice de miembros (nombres y "
            "tamanos), sin contenido de Atlas; no se descomprime (GPL-3.0)",
    ".exe": "binario compilado de terceros (herramienta de medida): no hay "
            "fuente en el repo; solo tamano y sha256",
    ".lnk": "acceso directo de Windows: puntero a un panel de Configuracion; "
            "sin comportamiento propio",
}


def read_tsv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    for p in (RESULTS, FILES):
        if not p.is_file():
            print(f"ERROR: falta {p}", file=sys.stderr)
            return 2

    extracts = [r["path"] for r in read_tsv(RESULTS)
                if r["treatment"] == "extract"]
    rows = {r["source_ref"]: r for r in read_tsv(FILES)}
    reg_count = len(read_tsv(REG)) if REG.is_file() else 0

    missing = [p for p in extracts if p not in rows]
    with_facts: list[str] = []
    without: list[dict] = []
    for p in extracts:
        r = rows.get(p)
        if r is None:
            continue
        facts = (
            (r["functions_json"] or "").strip() != ""
            or (r["reg_values"] or "").strip() not in ("", "0")
            or int(r["lines"] or 0) > 0
        )
        if facts:
            with_facts.append(p)
        else:
            ext = Path(p).suffix.lower()
            reason = REASONS.get(ext)
            if reason is None:
                reason = "NO VERIFICADO: extract sin hechos y sin motivo"
            without.append({"path": p, "reason": reason})

    unexplained = [o for o in without if o["reason"].startswith("NO VERIFICADO")]
    result = {
        "extract_files": len(extracts),
        "in_ledger": len(rows),
        "with_facts": len(with_facts),
        "without_facts": len(without),
        "unexplained": [o["path"] for o in unexplained],
        "missing_from_ledger": missing,
        "reg_entries": reg_count,
        "semantic_extraction": "DEUDA — Paso 4b (que hace cada script, que "
                               "toggles expone la app)",
        "orphans": without,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"ficheros extract      : {len(extracts)}")
        print(f"en el ledger          : {len(rows)}")
        print(f"con hechos de contenido: {len(with_facts)}")
        print(f"sin hechos (binarios) : {len(without)}")
        print(f"sin motivo declarado  : {len(unexplained)}")
        print(f"entradas de registro  : {reg_count}")
        print("\nsin hechos (path -> motivo):")
        for o in without:
            print(f"  - {o['path']}: {o['reason']}")
        print("\nextract que no llegan al ledger:", missing or "ninguno")
        print("\nSEMANTICA (que hace cada script, que toggles expone la app):")
        print("  DEUDA declarada para el Paso 4b; no se ha extraido nada.")
    return 0 if not unexplained and not missing else 1


if __name__ == "__main__":
    sys.exit(main())
