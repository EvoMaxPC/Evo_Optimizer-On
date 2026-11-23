#!/usr/bin/env python3
"""Descubre el esquema REAL de config/*.json de WinUtil (no lo supone).

Para cada fichero: nº de claves de primer nivel y, por cada nombre de campo de
las entradas, frecuencia y tipos observados. Genera
docs/inventory-recon/winutil-config-schema.md.

Carga tolerante: encoding='utf-8-sig' + json.loads(..., strict=False).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path("/tmp/upstream/winutil/config")
OUT = ROOT / "docs" / "inventory-recon" / "winutil-config-schema.md"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"), strict=False)


def json_type(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        inner = {json_type(v) for v in value}
        return "list[" + "|".join(sorted(inner)) + "]" if inner else "list[]"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def describe_entry(entry):
    """Devuelve (campos -> tipos) para una entrada, sea dict o lista de dicts."""
    if isinstance(entry, dict):
        return entry
    if isinstance(entry, list) and entry and isinstance(entry[0], dict):
        return entry[0]
    return None


def analyse(path: Path) -> dict:
    data = load_json(path)
    info = {"file": path.name, "top_keys": len(data) if isinstance(data, (dict, list)) else 0,
            "root_type": json_type(data), "fields": {}, "nested": {}}
    if not isinstance(data, dict):
        return info

    field_types: dict[str, Counter] = defaultdict(Counter)
    nested_keys: dict[str, Counter] = defaultdict(Counter)
    for key, entry in data.items():
        shape = describe_entry(entry)
        if shape is None:
            field_types["(valor escalar)"][json_type(entry)] += 1
            continue
        for fname, fvalue in shape.items():
            field_types[fname][json_type(fvalue)] += 1
            # un nivel más para objetos anidados conocidos (registry, service...)
            if isinstance(fvalue, dict):
                for sub in fvalue:
                    nested_keys[f"{fname}.{sub}"][json_type(fvalue[sub])] += 1
    info["fields"] = {k: dict(v) for k, v in field_types.items()}
    info["nested"] = {k: dict(v) for k, v in nested_keys.items()}
    return info


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    if not args.config.is_dir():
        print(f"ERROR: falta {args.config}; ejecuta fetch_upstream.py", file=sys.stderr)
        return 2

    files = sorted(args.config.glob("*.json"))
    reports = []
    for f in files:
        try:
            reports.append(analyse(f))
        except Exception as exc:  # noqa: BLE001
            reports.append({"file": f.name, "error": f"{type(exc).__name__}: {exc}"})
            print(f"[ERROR] {f.name}: {exc}", file=sys.stderr)

    md = ["# Esquema real de `config/*.json` de WinUtil", "",
          "Generado por `tools/ledger_extract/config_schema.py` sobre el clon en el "
          "SHA `70c23c80641d7370532af2f619b2842658600842`.",
          "", "Carga: `encoding='utf-8-sig'` + `json.loads(..., strict=False)`.",
          "", "Comando:", "```bash",
          "python3 tools/ledger_extract/config_schema.py",
          "```", ""]

    md += ["## Resumen", "", "| fichero | tipo raíz | claves nivel 1 | campos por entrada |",
           "|---|---|---:|---|"]
    for r in reports:
        if "error" in r:
            md.append(f"| `{r['file']}` | ERROR | - | {r['error']} |")
            continue
        md.append(f"| `{r['file']}` | {r['root_type']} | {r['top_keys']} | {len(r['fields'])} |")
    md.append("")

    for r in reports:
        if "error" in r:
            continue
        md += [f"## `{r['file']}` — {r['top_keys']} claves de nivel 1", ""]
        if not r["fields"]:
            md += ["_Entradas escalares; sin campos de objeto._", ""]
            continue
        md += ["| campo | frecuencia | tipos observados |", "|---|---:|---|"]
        for fname, types in sorted(r["fields"].items(), key=lambda kv: -sum(kv[1].values())):
            freq = sum(types.values())
            tstr = ", ".join(f"`{t}`×{n}" for t, n in sorted(types.items(), key=lambda kv: -kv[1]))
            md.append(f"| `{fname}` | {freq} | {tstr} |")
        if r["nested"]:
            md += ["", "<details><summary>Subcampos de objetos anidados</summary>", "",
                   "| subcampo | frecuencia | tipos |", "|---|---:|---|"]
            for sub, types in sorted(r["nested"].items(), key=lambda kv: -sum(kv[1].values())):
                freq = sum(types.values())
                tstr = ", ".join(f"`{t}`×{n}" for t, n in sorted(types.items(), key=lambda kv: -kv[1]))
                md.append(f"| `{sub}` | {freq} | {tstr} |")
            md += ["", "</details>", ""]
        md.append("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"escrito: {args.out}")
    for r in reports:
        if "error" in r:
            continue
        print(f"  {r['file']:22} top={r['top_keys']:<4} campos={len(r['fields'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
