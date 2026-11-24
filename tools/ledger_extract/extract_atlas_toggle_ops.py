#!/usr/bin/env python3
"""Operaciones de registro que declara el catálogo de toggles de Atlas.

Fuente: `Toggles/catalog.json`, campo `states[].work.registry` de cada toggle.
Ese campo es un **contador** en el catálogo (ver
`docs/inventory-recon/atlas-settings-schema.md`): no contiene las claves.

Salida:
    inventory/ledger/atlas-toggle-ops.tsv
        item_id  toggle_id  state  hive  key  value_name  value_type
        action  value_sha256

- Una fila por operación declarada (`work.registry`).
- Como el catálogo no dice QUÉ clave toca cada operación, las columnas
  `hive`/`key`/`value_name`/`value_type` quedan **vacías** y `action` =
  `unresolved`. No se inventan claves: la fila afirma solo "este estado declara
  N operaciones de registro", que es lo que el fichero dice.
- `value_sha256` = sha256 de `"<toggle>|<estado>|<indice>"`: identifica la
  operación sin copiar ningún dato.
- `item_id = atlas:toggle-op:<toggle_id>:<estado>:<indice>` (índice 0-based).

Salida determinista: orden por `item_id`, LF, UTF-8 sin BOM.

Uso:
    python3 tools/ledger_extract/extract_atlas_toggle_ops.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = Path("/tmp/upstream/atlas")
CATALOG = "package/Executables/AtlasModules/Toggles/catalog.json"
OUT_DIR = ROOT / "inventory" / "ledger"

COLUMNS = ("item_id", "toggle_id", "state", "hive", "key", "value_name",
           "value_type", "action", "value_sha256")


def build_rows(root: Path) -> tuple[list[dict], dict]:
    data = json.loads((root / CATALOG).read_text(encoding="utf-8-sig"))
    rows: list[dict] = []
    declared = 0
    with_ops = 0
    for entry in data["toggles"]:
        tid = entry["name"]
        for state in entry.get("states") or []:
            n = int((state.get("work") or {}).get("registry") or 0)
            declared += n
            if n:
                with_ops += 1
            for i in range(n):
                rows.append({
                    "item_id": f"atlas:toggle-op:{tid}:{state.get('name','')}:{i}",
                    "toggle_id": tid,
                    "state": state.get("name", ""),
                    "hive": "",
                    "key": "",
                    "value_name": "",
                    "value_type": "",
                    "action": "unresolved",
                    "value_sha256": hashlib.sha256(
                        f"{tid}|{state.get('name','')}|{i}".encode()).hexdigest(),
                })
    rows.sort(key=lambda r: r["item_id"])
    meta = {
        "operaciones": len(rows),
        "declaradas_por_el_catalogo": declared,
        "estados_con_operaciones": with_ops,
        "actions": dict(sorted(Counter(r["action"] for r in rows).items())),
        "hives": dict(sorted(Counter(r["hive"] for r in rows).items())),
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
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not (args.root / CATALOG).is_file():
        print(f"ERROR: falta {args.root / CATALOG}", file=sys.stderr)
        return 2

    rows, meta = build_rows(args.root)
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "atlas-toggle-ops.tsv"
    write_tsv(out, rows)
    summary = {**meta,
               "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"operaciones           : {len(rows)} (declaradas {meta['declaradas_por_el_catalogo']})")
        print(f"estados con operaciones: {meta['estados_con_operaciones']}")
        for k, v in meta["actions"].items():
            print(f"  action {k:12s}  : {v}")
        print("distribucion por hive : (vacia: el catalogo solo declara conteos)")
        print(f"sha256                : {summary['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
