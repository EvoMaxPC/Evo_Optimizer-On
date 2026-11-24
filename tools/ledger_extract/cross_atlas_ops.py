#!/usr/bin/env python3
"""Cruce entre las operaciones del catálogo de toggles y las de los .psd1.

Compara `(hive, key, value_name)` normalizados entre:

    inventory/ledger/atlas-toggle-ops.tsv   (work.registry del catálogo)
    inventory/ledger/atlas-tweak-ops.tsv    (bloques Registry de los .psd1)

Solo mide. No concluye causalidad: si el catálogo no declara claves, el cruce
no puede decir nada sobre equivalencia semántica.

Salida: por stdout (JSON con --json) y, opcionalmente, TSV.

Uso:
    python3 tools/ledger_extract/cross_atlas_ops.py [--json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "inventory" / "ledger"
TOGGLE_OPS = LEDGER / "atlas-toggle-ops.tsv"
TWEAK_OPS = LEDGER / "atlas-tweak-ops.tsv"


def norm(v: str) -> str:
    return (v or "").strip().strip("\\").lower()


def key_of(row: dict) -> tuple[str, str, str]:
    return (norm(row["hive"]), norm(row["key"]), norm(row["value_name"]))


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    for p in (TOGGLE_OPS, TWEAK_OPS):
        if not p.is_file():
            print(f"ERROR: falta {p}", file=sys.stderr)
            return 2

    tg = load(TOGGLE_OPS)
    tw = load(TWEAK_OPS)
    # El catálogo puede no declarar claves: se cuentan solo las filas con datos.
    tg_known = [r for r in tg if r["hive"] and r["key"]]
    tg_keys = {key_of(r) for r in tg_known}
    tw_keys = {key_of(r) for r in tw if r["hive"] or r["key"]}

    both = tg_keys & tw_keys
    only_tg = tg_keys - tw_keys
    only_tw = tw_keys - tg_keys

    result = {
        "toggle_ops_total": len(tg),
        "toggle_ops_con_hive_y_key": len(tg_known),
        "tweak_ops_total": len(tw),
        "claves_normalizadas_toggle": len(tg_keys),
        "claves_normalizadas_tweak": len(tw_keys),
        "en_ambos": len(both),
        "solo_catalogo": len(only_tg),
        "solo_psd1": len(only_tw),
        "veredicto": (
            "NO COMPARABLE: el catalogo no declara hive/key "
            "(work.registry es un contador)"
            if not tg_keys else "comparable"
        ),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"ops del catalogo         : {result['toggle_ops_total']} "
              f"(con hive+key: {result['toggle_ops_con_hive_y_key']})")
        print(f"ops de los .psd1         : {result['tweak_ops_total']}")
        print(f"claves normalizadas      : catalogo {result['claves_normalizadas_toggle']} "
              f"| psd1 {result['claves_normalizadas_tweak']}")
        print(f"en ambos                 : {result['en_ambos']}")
        print(f"solo en el catalogo      : {result['solo_catalogo']}")
        print(f"solo en .psd1            : {result['solo_psd1']}")
        print(f"veredicto                : {result['veredicto']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
