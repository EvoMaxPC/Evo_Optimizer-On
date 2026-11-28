#!/usr/bin/env python3
"""Claves de registro que declaran los .psd1 de los toggles de Atlas (paso 8d).

Por qué existe: `atlas-toggle-ops.tsv` (paso 4c) se alimenta de
`Toggles/catalog.json`, donde `states[].work.registry` es sólo un **contador**;
por eso sus 303 filas salen `unresolved` y no sirven para decidir la sección de
un toggle. Las claves literales sí están en los `.psd1` de
`Toggles/<grupo>/<Toggle>.psd1`, en el campo `Registry` de cada estado.

Este extractor NO interpreta semántica: copia ruta de la clave, nombre del
valor, tipo y operación, y calcula el sha256 del texto de la línea para poder
demostrar que el dato sale de ahí. Nunca copia cuerpos de script.

Salida:
    inventory/ledger/atlas-toggle-keys.tsv
        item_id  toggle_id  state  hive  key  value_name  value_type
        operation  source_ref  line  sha256_line

- `item_id = atlas:toggle-key:<Toggle>:<Estado>:<indice>` (índice 0-based).
- `operation` ∈ {Set, Delete} (lo que diga `Operation`, o `Set` si no hay).
- Determinista: orden por `item_id`, LF, UTF-8 sin BOM, celdas <= 400.

Uso:
    python3 tools/ledger_extract/extract_atlas_toggle_keys.py [--root DIR]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = Path("/tmp/upstream/atlas")
TOGGLES_DIR = "package/Executables/AtlasModules/Toggles"
OUT = ROOT / "inventory" / "ledger" / "atlas-toggle-keys.tsv"

COLUMNS = ("item_id", "toggle_id", "state", "hive", "key", "value_name",
           "value_type", "operation", "source_ref", "line", "sha256_line")
MAX_CELL = 400

# @{ Path = 'HKLM:\...'; Name = 'X'; Type = 'DWord'; Data = 1 }
REGISTRY_RE = re.compile(
    r"Path\s*=\s*'(?P<path>[^']+)'\s*;\s*Name\s*=\s*'(?P<name>[^']*)'(?P<rest>[^}]*)\}")
STATE_RE = re.compile(r"^\s*Name\s*=\s*'(?P<state>[A-Za-z][A-Za-z0-9]*)'\s*$")
HIVE_RE = re.compile(r"^(HKLM|HKCU|HKCR|HKU|HKCC):", re.IGNORECASE)
TYPE_RE = re.compile(r"Type\s*=\s*'(?P<type>[A-Za-z]+)'")
OPERATION_RE = re.compile(r"Operation\s*=\s*'(?P<operation>[A-Za-z]+)'")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_file(path: Path, relative: str) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    toggle_id = path.stem
    rows: list[dict] = []
    state: str | None = None
    in_states = False
    depth = 0
    index = 0

    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not in_states and re.match(r"States\s*=", stripped):
            in_states = True
            depth = stripped.count("(") - stripped.count(")")
            continue
        if in_states:
            # El bloque de estados acaba cuando se cierra su paréntesis; los
            # paréntesis de los arrays Registry/UserRegistry internos se cuentan
            # para no cortar en el cierre de un estado.
            depth += stripped.count("(") - stripped.count(")")
            if depth <= 0:
                in_states = False
                state = None
                continue
            if re.fullmatch(r"@\{", stripped):
                # Empieza un estado: se olvida el nombre anterior.
                state = None
            else:
                state_match = STATE_RE.search(line)
                if state_match:
                    state = state_match.group("state")
        match = REGISTRY_RE.search(stripped)
        if not match:
            continue

        raw_path = match.group("path")
        hive_match = HIVE_RE.match(raw_path)
        hive = hive_match.group(1).upper() if hive_match else ""
        key = HIVE_RE.sub("", raw_path).lstrip("\\")
        rest = match.group("rest")
        type_match = TYPE_RE.search(rest)
        operation = OPERATION_RE.search(rest)
        rows.append({
            "item_id": f"atlas:toggle-key:{toggle_id}:{state or '<top>'}:{index}",
            "toggle_id": toggle_id,
            "state": state or "<top>",
            "hive": hive,
            "key": key[:MAX_CELL],
            "value_name": match.group("name")[:MAX_CELL],
            "value_type": type_match.group("type") if type_match else "",
            "operation": operation.group("operation") if operation else "Set",
            "source_ref": relative,
            "line": number,
            "sha256_line": sha(stripped),
        })
        index += 1
    return rows


def build(root: Path) -> list[dict]:
    base = root / TOGGLES_DIR
    rows: list[dict] = []
    if not base.is_dir():
        return rows
    for path in sorted(base.glob("*/*.psd1")):
        rows.extend(parse_file(path, str(path.relative_to(root)).replace("\\", "/")))
    return sorted(rows, key=lambda r: r["item_id"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ATLAS))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not (root / TOGGLES_DIR).is_dir():
        print(f"ERROR: no hay pin de Atlas en {root}", file=sys.stderr)
        return 2

    rows = build(root)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    toggles = {r["toggle_id"] for r in rows}
    summary = {
        "filas": len(rows),
        "toggles_con_clave": len(toggles),
        "por_hive": dict(sorted(Counter(r["hive"] for r in rows).items())),
        "por_operacion": dict(sorted(Counter(r["operation"] for r in rows).items())),
        "por_tipo": dict(sorted(Counter(r["value_type"] for r in rows).items())),
    }
    if args.json:
        import json
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(f"claves declaradas : {summary['filas']} ({summary['toggles_con_clave']} toggles)")
    print(f"por hive          : {summary['por_hive']}")
    print(f"por operacion     : {summary['por_operacion']}")
    print(f"por tipo          : {summary['por_tipo']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
