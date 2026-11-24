#!/usr/bin/env python3
"""Operaciones estructuradas de WinUtil (config/*.json), sin copiar scripts.

Fuente: pin de WinUtil `70c23c8...`, `config/tweaks.json` (69 tweaks),
`config/feature.json` (33) y `config/appx.json` (34).

Salida:
    inventory/ledger/winutil-tweak-ops.tsv
        item_id  tweak_id  kind  direction  target  name  value
        original_value  type  effect_types  sha256

Una fila por operacion estructurada:
- `registry`        : Path, Name, Value, Type, OriginalValue
- `service`         : Name, StartupType, OriginalType
- `scheduledtask`   : Name / Path si existieran
- `appx`            : Name / PackageName si existieran
- `script`          : InvokeScript (apply) y UndoScript (undo). NO se copia el
  cuerpo: se guardan `line_count`, el sha256 y los `effect_types` detectados con
  las mismas reglas que `extract_atlas_effects.detect`.

Ademas, solo conteos para feature.json y appx.json (mismo formato de fila, en
`inventory/ledger/winutil-feature-ops.tsv` y `winutil-appx-ops.tsv`).

Uso:
    python3 tools/ledger_extract/extract_winutil_ops.py [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))
CONFIG = Path("/tmp/upstream/winutil/config")
LEDGER = ROOT / "inventory" / "ledger"

from extract_atlas_effects import detect  # noqa: E402  (mismas reglas)

COLUMNS = ("item_id", "tweak_id", "tweak_type", "kind", "direction", "target", "name",
           "value", "original_value", "type", "effect_types", "sha256")

# `Type` de la entrada en tweaks.json: gobierna el widget de la UI y, con él,
# cuál de los dos valores del registro es el estado ENCENDIDO (ver
# docs/reports/paso8c.md, T1a). Se normaliza aquí para no propagar variantes.
TWEAK_TYPES = ("Toggle", "Button", "Combobox")


def tweak_type(body: dict) -> str:
    declared = str(body.get("Type") or "").strip()
    return declared if declared in TWEAK_TYPES else "none"

APPS_COLUMNS = ("item_id", "source", "source_ref", "label", "kind", "sha256",
                "category", "winget", "choco")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"), strict=False)


def script_effects(code) -> tuple[int, list[str]]:
    """(lineas, tipos de efecto distintos) de un bloque de script.

    En WinUtil `InvokeScript`/`UndoScript` es una LISTA de cadenas (una por
    fragmento), no una unica cadena.
    """
    if isinstance(code, (list, tuple)):
        code = "\n".join(str(c) for c in code)
    lines = [ln for ln in code.splitlines() if ln.strip()]
    types: set[str] = set()
    for ln in lines:
        for etype, *_ in detect(ln):
            types.add(etype)
    return len(lines), sorted(types)


def sha_text(text) -> str:
    if isinstance(text, (list, tuple)):
        text = "\n".join(str(t) for t in text)
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def tweak_ops(data: dict) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    per_kind: Counter = Counter()
    per_dir: Counter = Counter()
    with_undo = 0
    script_only = 0
    for tid, body in sorted(data.items()):
        ttype = tweak_type(body)
        structured = 0
        # registry (solo apply: el undo vive en OriginalValue)
        for reg in body.get("registry") or []:
            payload = f"{reg.get('Path')}|{reg.get('Name')}|{reg.get('Value')}|{reg.get('Type')}"
            rows.append({
                "tweak_id": tid, "tweak_type": ttype, "kind": "registry", "direction": "apply",
                "target": reg.get("Path", ""), "name": reg.get("Name", ""),
                "value": str(reg.get("Value", "")),
                "original_value": str(reg.get("OriginalValue", "")),
                "type": reg.get("Type", ""), "effect_types": "",
                "sha256": sha_text(payload),
            })
            structured += 1
            per_kind["registry"] += 1
            per_dir["apply"] += 1
        for svc in body.get("service") or []:
            payload = f"{svc.get('Name')}|{svc.get('StartupType')}"
            rows.append({
                "tweak_id": tid, "tweak_type": ttype, "kind": "service", "direction": "apply",
                "target": "", "name": svc.get("Name", ""),
                "value": svc.get("StartupType", ""),
                "original_value": svc.get("OriginalType", ""),
                "type": "", "effect_types": "", "sha256": sha_text(payload),
            })
            structured += 1
            per_kind["service"] += 1
            per_dir["apply"] += 1
        # feature.json: `feature` es una lista de nombres de caracteristica y
        # `function` el nombre de la funcion que las instala.
        for feat in body.get("feature") or []:
            rows.append({
                "tweak_id": tid, "tweak_type": ttype, "kind": "feature", "direction": "apply",
                "target": "", "name": str(feat), "value": "",
                "original_value": "", "type": "", "effect_types": "",
                "sha256": sha_text(f"feature|{feat}"),
            })
            structured += 1
            per_kind["feature"] += 1
            per_dir["apply"] += 1
        for item in body.get("appx") or []:
            name = item.get("Name") or item.get("PackageName") or ""
            rows.append({
                "tweak_id": tid, "tweak_type": ttype, "kind": "appx", "direction": "apply",
                "target": "", "name": name, "value": "",
                "original_value": "", "type": "", "effect_types": "",
                "sha256": sha_text(f"appx|{name}"),
            })
            structured += 1
            per_kind["appx"] += 1
            per_dir["apply"] += 1
        # appx.json: PackageId + StoreId (el paquete lo instala/desinstala el
        # codigo de WinUtil, aqui solo se declara el identificador).
        for name in ([body["PackageId"]] if body.get("PackageId") else []):
            rows.append({
                "tweak_id": tid, "tweak_type": ttype, "kind": "appx-package", "direction": "apply",
                "target": body.get("StoreId", ""), "name": name, "value": "",
                "original_value": "", "type": "", "effect_types": "",
                "sha256": sha_text(f"appx-package|{name}|{body.get('StoreId','')}"),
            })
            structured += 1
            per_kind["appx-package"] += 1
            per_dir["apply"] += 1
        for kind in ("scheduledtask",):
            for item in body.get(kind) or []:
                name = item.get("Name") or item.get("PackageName") or ""
                payload = f"{kind}|{name}|{json.dumps(item, sort_keys=True)}"
                rows.append({
                    "tweak_id": tid, "tweak_type": ttype, "kind": kind, "direction": "apply",
                    "target": item.get("Path", "") or item.get("Path", ""),
                    "name": name, "value": str(item.get("Value", "")),
                    "original_value": str(item.get("OriginalValue", "")),
                    "type": item.get("Type", ""), "effect_types": "",
                    "sha256": sha_text(payload),
                })
                structured += 1
                per_kind[kind] += 1
                per_dir["apply"] += 1
        # scripts
        has_script = False
        for direction, field in (("apply", "InvokeScript"), ("undo", "UndoScript")):
            code = body.get(field)
            if not code:
                continue
            has_script = True
            nlines, types = script_effects(code)
            payload = f"{tid}|{field}|{nlines}"
            rows.append({
                "tweak_id": tid, "tweak_type": ttype, "kind": "script", "direction": direction,
                "target": "", "name": field, "value": str(nlines),
                "original_value": "", "type": "", "effect_types": "|".join(types),
                "sha256": sha_text(code),
            })
            per_kind[f"script-{field}"] += 1
            per_dir[direction] += 1
        if has_script and structured == 0:
            script_only += 1
        if body.get("UndoScript") or any(
                (r.get("OriginalValue") not in (None, "", "<RemoveEntry>"))
                for r in (body.get("registry") or [])):
            with_undo += 1
        if not has_script and structured == 0:
            script_only += 1
    for i, r in enumerate(rows):
        r["item_id"] = f"winutil:tweak-op:{r['tweak_id']}:{r['kind']}:{i}"
    rows.sort(key=lambda r: r["item_id"])
    # renumerar por tweak para que el item_id sea estable y legible
    seen: Counter = Counter()
    for r in rows:
        key = (r["tweak_id"], r["kind"])
        idx = seen[key]
        seen[key] += 1
        r["item_id"] = f"winutil:tweak-op:{r['tweak_id']}:{r['kind']}:{idx}"
    rows.sort(key=lambda r: r["item_id"])
    meta = {
        "tweaks": len(data),
        "filas": len(rows),
        "por_kind": dict(sorted(per_kind.items())),
        "por_direction": dict(sorted(per_dir.items())),
        "tweaks_con_undo": with_undo,
        "tweaks_solo_script": script_only,
    }
    return rows, meta


def write_tsv(path: Path, rows: list[dict]) -> None:
    lines = ["\t".join(COLUMNS)]
    for r in rows:
        lines.append("\t".join(str(r.get(c, "")) for c in COLUMNS))
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--out", type=Path, default=LEDGER)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    summary = {}
    for fname, label in (("tweaks.json", "tweaks"),
                         ("feature.json", "features"),
                         ("appx.json", "appx")):
        p = args.config / fname
        if not p.is_file():
            print(f"ERROR: falta {p}", file=sys.stderr)
            return 2
        data = load_json(p)
        rows, meta = tweak_ops(data)
        name = {"tweaks": "tweak", "features": "feature", "appx": "appx"}[label]
        out = args.out / f"winutil-{name}-ops.tsv"
        write_tsv(out, rows)
        summary[label] = {**meta,
                          "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    for label, m in summary.items():
        print(f"[{label}] tweaks/items: {m['tweaks']} | filas: {m['filas']}")
        print(f"  por kind      : {m['por_kind']}")
        print(f"  por direction : {m['por_direction']}")
        print(f"  con undo      : {m['tweaks_con_undo']} | solo script/sin estructura: {m['tweaks_solo_script']}")
        print(f"  sha256        : {m['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
