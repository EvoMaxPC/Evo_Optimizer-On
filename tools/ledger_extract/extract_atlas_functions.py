#!/usr/bin/env python3
"""Funciones definidas en los .ps1/.psm1 de Atlas (solo metadatos).

Salida:
    inventory/ledger/atlas-functions.tsv
        item_id  path  name  line_start  line_end  scope  sha256_body

- Una fila por función definida con `function <nombre>` en cualquier `.ps1` o
  `.psm1` con tratamiento `extract` (no solo `Scripts/`).
- `line_start` es la línea de la declaración; `line_end` la de la llave de
  cierre (si no se puede delimitar, se marca con `-` y el motivo en `scope` no
  cambia: se cuenta como NO delimitada).
- `sha256_body` = sha256 del cuerpo (líneas entre la declaración y el cierre).
  **El cuerpo no se emite nunca**: solo su hash.
- `scope`: `product` (package/ y app/), `test` (tests/), `tooling` (resto),
  mismo criterio que `winutil-functions.tsv`.

Salida determinista: orden por `item_id`, LF, UTF-8 sin BOM.

Uso:
    python3 tools/ledger_extract/extract_atlas_functions.py [--root DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = Path("/tmp/upstream/atlas")
PART = ROOT / "inventory" / "partition" / "results" / "atlas.tsv"
OUT_DIR = ROOT / "inventory" / "ledger"

COLUMNS = ("item_id", "path", "name", "line_start", "line_end", "scope",
           "sha256_body")

FUNC_RE = re.compile(r"^\s*function\s+([\w-]+)", re.IGNORECASE)
OPEN_RE = re.compile(r"\{")


def scope_class(path: str) -> str:
    if path.startswith(("package/", "app/")):
        return "product"
    if path.startswith("tests/"):
        return "test"
    return "tooling"


def find_functions(text: str) -> list[tuple[str, int, int, str]]:
    """Devuelve (nombre, linea_inicio, linea_fin, cuerpo). Índices 1-based."""
    lines = text.splitlines()
    out: list[tuple[str, int, int, str]] = []
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        start = i + 1
        # localizar la primera '{' desde la declaración
        depth = 0
        started = False
        end = None
        j = i
        while j < len(lines):
            seg = lines[j]
            if not started:
                k = seg.find("{")
                if k >= 0:
                    started = True
                    depth += seg[k:].count("{") - seg[k:].count("}")
            else:
                depth += seg.count("{") - seg.count("}")
            if started and depth <= 0:
                end = j + 1
                break
            j += 1
        if end is None:
            end = len(lines)
        body = "\n".join(lines[start:end - 1]) if end > start else ""
        out.append((name, start, end, body))
        # seguir linea a linea para capturar funciones ANIDADAS (16 en Atlas)
        i += 1
    return out


def targets(part: Path) -> list[str]:
    with part.open(encoding="utf-8") as fh:
        return sorted(r["path"] for r in csv.DictReader(fh, delimiter="\t")
                      if r["treatment"] == "extract"
                      and r["path"].endswith((".ps1", ".psm1")))


def build_rows(root: Path, part: Path) -> list[dict]:
    rows: list[dict] = []
    for rel in targets(part):
        raw = (root / rel).read_bytes()
        text = raw.decode("utf-8", errors="replace")
        for name, start, end, body in find_functions(text):
            rows.append({
                "item_id": f"atlas:function:{rel}::{name}",
                "path": rel,
                "name": name,
                "line_start": start,
                "line_end": end,
                "scope": scope_class(rel),
                "sha256_body": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            })
    # 14 pares (ruta, nombre) se repiten de verdad (mocks de Pester que
    # redefinen la misma función en bloques distintos). Para mantener 0
    # duplicados de item_id sin inventar nombres, se añade "#<linea>" SOLO a
    # esos casos y se deja constancia en el informe.
    from collections import Counter
    seen = Counter((r["path"], r["name"]) for r in rows)
    for r in rows:
        if seen[(r["path"], r["name"])] > 1:
            r["item_id"] = f"{r['item_id']}#{r['line_start']}"
    rows.sort(key=lambda r: (r["item_id"], r["line_start"]))
    return rows


def write_tsv(path: Path, rows: list[dict]) -> None:
    lines = ["\t".join(COLUMNS)]
    for r in rows:
        lines.append("\t".join(str(r[c]) for c in COLUMNS))
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ATLAS)
    ap.add_argument("--part", type=Path, default=PART)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not args.part.is_file():
        print(f"ERROR: falta {args.part}", file=sys.stderr)
        return 2

    rows = build_rows(args.root, args.part)
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "atlas-functions.tsv"
    write_tsv(out, rows)

    from collections import Counter
    by_scope = Counter(r["scope"] for r in rows)
    by_top = Counter(r["path"].split("/")[0] if "/" in r["path"] else "(raiz)"
                     for r in rows)
    scripts_only = sum(1 for r in rows
                       if r["path"].startswith(
                           "package/Executables/AtlasModules/Scripts/"))
    dup_names = {n: c for n, c in Counter(r["name"] for r in rows).items()
                 if c > 1}
    summary = {
        "functions": len(rows),
        "files": len({r["path"] for r in rows}),
        "by_scope": dict(sorted(by_scope.items())),
        "by_top": dict(sorted(by_top.items())),
        "scripts_only": scripts_only,
        "duplicate_names_across_files": len(dup_names),
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"funciones             : {len(rows)} en {summary['files']} ficheros")
        for k, v in summary["by_scope"].items():
            print(f"  scope {k:8s}      : {v}")
        for k, v in summary["by_top"].items():
            print(f"  top   {k:8s}      : {v}")
        print(f"solo Scripts/         : {scripts_only}")
        print(f"nombres repetidos     : {len(dup_names)}")
        print(f"sha256                : {summary['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
