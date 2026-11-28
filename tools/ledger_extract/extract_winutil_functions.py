#!/usr/bin/env python3
"""Extractor de funciones y scripts .ps1 de WinUtil (tratamiento extract).

Salida: inventory/ledger/winutil-functions.tsv
    path  area  scope  lines  sha256  functions  n_functions

- area: 'public' (functions/public/), 'private' (functions/private/),
  'scripts' (scripts/), 'other' (resto en extract); es la clasificación
  histórica del paso 3 y se mantiene para no romper consumidores.
- scope: 'product' (functions/ y scripts/), 'test' (pester/),
  'tooling' (raíz, lint/, tools/). Es la lectura que separa capacidad de
  producto de ayudantes de test.
- functions: nombres definidos, separados por ';' y ordenados.
- Solo rutas, nombres, hashes y conteos: NUNCA el cuerpo del script.

Uso:
    python3 tools/ledger_extract/extract_winutil_functions.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WINUTIL = Path("/tmp/upstream/winutil")
PART = ROOT / "inventory" / "partition" / "results" / "winutil.tsv"
OUT = ROOT / "inventory" / "ledger" / "winutil-functions.tsv"

FUNC_RE = re.compile(r"^\s*function\s+([\w-]+)", re.IGNORECASE | re.MULTILINE)
COLUMNS = ("path", "area", "scope", "lines", "sha256", "functions", "n_functions")


def scope_class(path: str) -> str:
    """Separa producto de test y de herramientas."""
    if path.startswith(("functions/", "scripts/")):
        return "product"
    if path.startswith("pester/"):
        return "test"
    return "tooling"


def scope_of(path: str) -> str:
    if path.startswith("functions/public/"):
        return "public"
    if path.startswith("functions/private/"):
        return "private"
    if path.startswith("scripts/"):
        return "scripts"
    return "other"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=WINUTIL)
    ap.add_argument("--part", type=Path, default=PART)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    if not args.part.is_file():
        print(f"ERROR: falta {args.part}; ejecuta partition_check.py", file=sys.stderr)
        return 2

    with args.part.open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh, delimiter="\t")]

    targets = [r for r in rows if r["treatment"] == "extract" and r["path"].endswith(".ps1")]
    out_rows = []
    for r in targets:
        path = r["path"]
        f = args.root / path
        if not f.is_file():
            print(f"ERROR: no existe {f}", file=sys.stderr)
            return 2
        data = f.read_bytes()
        text = data.decode("utf-8", errors="ignore")
        funcs = sorted(set(FUNC_RE.findall(text)))
        out_rows.append({
            "path": path,
            "area": scope_of(path),
            "scope": scope_class(path),
            "lines": text.count("\n") + (1 if text and not text.endswith("\n") else 0),
            "sha256": hashlib.sha256(data).hexdigest(),
            "functions": ";".join(funcs),
            "n_functions": len(funcs),
        })

    out_rows.sort(key=lambda x: x["path"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(COLUMNS)]
    for r in out_rows:
        lines.append("\t".join(str(r[c]) for c in COLUMNS))
    args.out.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))

    totals: dict[str, dict[str, int]] = {}
    for r in out_rows:
        for key in (("area", r["area"]), ("scope", r["scope"])):
            t = totals.setdefault(key, {"files": 0, "functions": 0, "lines": 0})
            t["files"] += 1
            t["functions"] += r["n_functions"]
            t["lines"] += r["lines"]

    zero = [r["path"] for r in out_rows if r["n_functions"] == 0]

    print(f"ficheros .ps1 en extract: {len(out_rows)}")
    for (dim, label) in sorted(totals):
        t = totals[(dim, label)]
        print(f"  {dim:5} {label:8} ficheros={t['files']:<4} "
              f"funciones={t['functions']:<4} lineas={t['lines']}")
    print(f"sin funciones definidas: {len(zero)}")
    for p in zero:
        print(f"   - {p}")
    print(f"escrito: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
