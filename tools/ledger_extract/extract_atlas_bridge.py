#!/usr/bin/env python3
"""Puente toggle -> función de Atlas (solo metadatos).

Lee `Toggles/catalog.json` (91 entradas) y, para cada (toggle, estado), emite una
fila con el nombre de función que declara `work.machineAction`.

Salida:
    inventory/ledger/atlas-toggle-bridge.tsv
        toggle_id  state  function_name  resolved_in  match_kind

- `resolved_in`: ruta del `.ps1`/`.psm1` donde se define la función, si está en
  `atlas-functions.tsv`. Si hay varias, se listan separadas por `;` (ambiguo).
- `match_kind`:
    `function`  el nombre aparece como función definida en algun `.ps1`/`.psm1`
    `psd1-name` el nombre coincide con el `Name` de algún `.psd1` de Tweaks
    `both`      las dos cosas
    `none`      ninguna
- No se inventan referencias: si `machineAction` es null no hay fila.

Salida determinista: orden por (toggle_id, state), LF, UTF-8 sin BOM.

Uso:
    python3 tools/ledger_extract/extract_atlas_bridge.py [--root DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = Path("/tmp/upstream/atlas")
CATALOG = "package/Executables/AtlasModules/Toggles/catalog.json"
TWEAKS_DIR = "package/Executables/AtlasModules/Scripts/Tweaks"
FUNCS = ROOT / "inventory" / "ledger" / "atlas-functions.tsv"
OUT_DIR = ROOT / "inventory" / "ledger"

COLUMNS = ("toggle_id", "state", "function_name", "resolved_in", "match_kind")

# Nombre de primer nivel en los .psd1 (mismo regex que el ledger de tweaks).
PSD1_NAME_RE = re.compile(r"^[ \t]*Name[ \t]*=[ \t]*['\"]([^'\"]+)['\"]",
                          re.MULTILINE)


def psd1_names(root: Path) -> set[str]:
    names: set[str] = set()
    for p in sorted((root / TWEAKS_DIR).rglob("*.psd1")):
        txt = p.read_text(encoding="utf-8", errors="replace")
        names.update(PSD1_NAME_RE.findall(txt))
    return names


def function_index(tsv: Path) -> dict[str, list[str]]:
    idx: dict[str, list[str]] = defaultdict(list)
    with tsv.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            idx[r["name"]].append(r["path"])
    return {k: sorted(set(v)) for k, v in idx.items()}


def build_rows(root: Path, funcs: Path) -> tuple[list[dict], dict]:
    data = json.loads((root / CATALOG).read_text(encoding="utf-8-sig"))
    fidx = function_index(funcs)
    pnames = psd1_names(root)
    rows: list[dict] = []
    for entry in data["toggles"]:
        tid = entry["name"]
        for state in entry.get("states") or []:
            fn = (state.get("work") or {}).get("machineAction")
            if not fn:
                continue
            paths = fidx.get(fn, [])
            in_func = bool(paths)
            in_psd1 = fn in pnames
            if in_func and in_psd1:
                kind = "both"
            elif in_func:
                kind = "function"
            elif in_psd1:
                kind = "psd1-name"
            else:
                kind = "none"
            rows.append({
                "toggle_id": tid,
                "state": state.get("name", ""),
                "function_name": fn,
                "resolved_in": ";".join(paths),
                "match_kind": kind,
            })
    rows.sort(key=lambda r: (r["toggle_id"], r["state"], r["function_name"]))
    meta = {
        "referencias": len(rows),
        "nombres_distintos": len({r["function_name"] for r in rows}),
        "kinds": dict(sorted(Counter(r["match_kind"] for r in rows).items())),
        "psd1_names": len(pnames),
        "toggles": len(data["toggles"]),
    }
    return rows, meta


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
    ap.add_argument("--funcs", type=Path, default=FUNCS)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not args.funcs.is_file():
        print(f"ERROR: falta {args.funcs}; ejecuta extract_atlas_functions.py",
              file=sys.stderr)
        return 2

    rows, meta = build_rows(args.root, args.funcs)
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "atlas-toggle-bridge.tsv"
    write_tsv(out, rows)

    unresolved = sorted({r["function_name"] for r in rows
                         if r["match_kind"] == "none"})
    ambiguous = sorted({r["function_name"] for r in rows
                        if ";" in r["resolved_in"]})
    reached_paths = {p for r in rows for p in r["resolved_in"].split(";") if p}
    reached_psd1 = {r["function_name"] for r in rows
                    if r["match_kind"] in ("psd1-name", "both")}
    summary = {
        **meta,
        "sin_resolver": len(unresolved),
        "sin_resolver_lista": unresolved,
        "ambiguos": len(ambiguous),
        "rutas_alcanzadas": len(reached_paths),
        "psd1_alcanzados_por_nombre": len(reached_psd1),
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"referencias           : {meta['referencias']}")
        print(f"nombres distintos     : {meta['nombres_distintos']} (esperado 74)")
        for k, v in meta["kinds"].items():
            print(f"  {k:10s}          : {v}")
        print(f"sin resolver          : {len(unresolved)}")
        for n in unresolved:
            print(f"   ! {n}")
        print(f"ambiguos (varias rutas): {len(ambiguous)}")
        print(f"rutas alcanzadas      : {len(reached_paths)}")
        print(f"sha256                : {summary['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
