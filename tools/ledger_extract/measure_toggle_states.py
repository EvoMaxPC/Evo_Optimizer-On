#!/usr/bin/env python3
"""
Medicion de estados CONTRARIOS de los toggles de Atlas frente al catalogo (paso 12c, T6).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

import build_section10_catalog as b10  # noqa: E402

CATALOG_DIR = ROOT / "catalog" / "capabilities"
OUT_TSV = ROOT / "inventory" / "ledger" / "toggle-state-audit.tsv"

COLUMNS = (
    "capability_id", "section", "toggle", "estado_aplicado",
    "operaciones_contrarias_no_reproducidas", "clasificacion",
)

OPPOSITE = {
    frozenset(("AddKey", "DeleteKey")),
    frozenset(("Set", "DeleteKey")),
}


def normalize_data(entry: dict) -> str:
    raw = entry.get("data")
    if raw is None:
        return ""
    text = str(raw).strip().strip("'\"")
    if re.fullmatch(r"-?\d+", text):
        return str(int(text))
    return text


def op_key(entry: dict) -> tuple:
    hive, key = b10.split_path(entry["path"])
    op = entry.get("op") or "Set"
    if op in ("AddKey", "DeleteKey"):
        return (hive, key, op, "", "")
    return (hive, key, op, entry.get("name") or "", normalize_data(entry))


def op_human(entry: dict) -> str:
    hive, key = b10.split_path(entry["path"])
    op = entry.get("op") or "Set"
    name = entry.get("name") or ""
    data = normalize_data(entry)
    if op in ("AddKey", "DeleteKey"):
        return f"{op} {hive}:{key}"
    return f"{op} {hive}:{key} {name}={data}"


def is_structural_opposite(applied: dict, contrary: dict) -> bool:
    ahive, akey = b10.split_path(applied["path"])
    chive, ckey = b10.split_path(contrary["path"])
    if ahive != chive or akey != ckey:
        return False
    aop = applied.get("op") or "Set"
    cop = contrary.get("op") or "Set"
    if frozenset((aop, cop)) in OPPOSITE:
        return True
    return False


def declared_state(capability: dict) -> str | None:
    match = re.search(r"\(estado '?(\w+)'?", capability["provenance"])
    return match.group(1) if match else None


def toggle_file(capability: dict) -> str | None:
    match = re.search(r"Toggles/([A-Za-z0-9_/]+\.psd1)", capability["provenance"])
    return match.group(1) if match else None


def measure() -> list[dict]:
    rows = []
    for path in sorted(CATALOG_DIR.glob("*.json"), key=lambda p: p.name):
        document = json.loads(path.read_text(encoding="utf-8"))
        for capability in document["capabilities"]:
            relative = toggle_file(capability)
            if not relative:
                continue
            source = b10.ATLAS_TOGGLES / relative
            if not source.is_file():
                continue
            text = source.read_text(encoding="utf-8", errors="replace")
            states = b10.split_states(text)
            declared = declared_state(capability)
            if not declared or declared not in states:
                continue
            applied_entries = {op_key(e): e for e in b10.parse_registry_block_text(states[declared])}
            contrary_entries: list[dict] = []
            for name, block in states.items():
                if name == declared:
                    continue
                contrary_entries.extend(b10.parse_registry_block_text(block))
            applied_keys = set(applied_entries)
            no_reproducidas = {op_key(e) for e in contrary_entries} - applied_keys
            no_repro_list = sorted(
                op_human(e) for e in contrary_entries if op_key(e) in no_reproducidas
            )
            structural_opposite = False
            for ce in contrary_entries:
                ck = op_key(ce)
                if ck not in no_reproducidas:
                    continue
                for ae in applied_entries.values():
                    if is_structural_opposite(ae, ce):
                        structural_opposite = True
                        break
                if structural_opposite:
                    break
            if not no_reproducidas:
                clasificacion = "OK"
            elif structural_opposite:
                clasificacion = "CONTRARIO"
            else:
                clasificacion = "PENDIENTE"
            rows.append({
                "capability_id": capability["id"],
                "section": str(capability["sectionId"]),
                "toggle": Path(relative).stem,
                "estado_aplicado": declared,
                "operaciones_contrarias_no_reproducidas": "; ".join(no_repro_list),
                "clasificacion": clasificacion,
            })
    rows.sort(key=lambda r: r["capability_id"])
    return rows


def dump_tsv(rows: list[dict]) -> str:
    lines = ["\t".join(COLUMNS)]
    for row in rows:
        lines.append("\t".join(str(row[c]).replace("\t", " ") for c in COLUMNS))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    rows = measure()
    tsv = dump_tsv(rows)
    contrarios = [r for r in rows if r["clasificacion"] == "CONTRARIO"]

    if args.check:
        current = OUT_TSV.read_text(encoding="utf-8") if OUT_TSV.is_file() else ""
        if current != tsv:
            print(
                f"el TSV de toggle-estados no coincide con {OUT_TSV}: ejecuta el script sin --check",
                file=sys.stderr,
            )
            return 1
    else:
        OUT_TSV.write_text(tsv, encoding="utf-8")

    if args.json:
        print(json.dumps({
            "capacidades_con_toggle": len(rows),
            "ok": [r["capability_id"] for r in rows if r["clasificacion"] == "OK"],
            "pendientes": [r["capability_id"] for r in rows if r["clasificacion"] == "PENDIENTE"],
            "contrarios": [r["capability_id"] for r in contrarios],
            "totales": {
                "OK": sum(1 for r in rows if r["clasificacion"] == "OK"),
                "PENDIENTE": sum(1 for r in rows if r["clasificacion"] == "PENDIENTE"),
                "CONTRARIO": len(contrarios),
            },
            "veredicto": "OK" if not contrarios else "CONTRARIOS_DETECTADOS",
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"capacidades que salen de un toggle : {len(rows)}")
    print(f"  OK (sin contrarias no reproducidas) : {sum(1 for r in rows if r['clasificacion'] == 'OK')}")
    print(f"  PENDIENTE (contrarias no declaradas): {sum(1 for r in rows if r['clasificacion'] == 'PENDIENTE')}")
    print(f"  CONTRARIO (opuesto estructural)     : {len(contrarios)}")
    for row in rows:
        if row["clasificacion"] != "OK":
            print(f"  {row['clasificacion']:<12} {row['capability_id']:<40} "
                  f"estado={row['estado_aplicado']} "
                  f"no_reproducidas=[{row['operaciones_contrarias_no_reproducidas']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
