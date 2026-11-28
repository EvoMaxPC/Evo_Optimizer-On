#!/usr/bin/env python3
"""Extractor de la semántica de ajustes de Atlas (GPL-3.0) — solo hechos.

Salida:
    inventory/ledger/atlas-toggles.tsv
        item_id  source  source_ref  label  kind  category  sha256  attrs_json
    inventory/ledger/atlas-tweak-files.tsv
        item_id  source_ref  lines  sha256  keys_json  hklm  hkcu  set_service
        schtasks  bcdedit  netsh

**Límite de licencia.** De Atlas se emiten únicamente: rutas, ids, nombres,
categorías, enumerados, tipos, conteos y hashes. Nunca se copia texto de
descripción, cuerpo de script, cadena de comando ni ruta de registro literal.
Las descripciones y los `warning` se reducen a su longitud y su sha256.

`attrs_json` (hechos estructurados de cada toggle):
    fields        campos presentes en la entrada (lista ordenada)
    groups        grupo declarado
    elevation     enumerado
    states        nº de estados
    state_names   nombres de estado (enumerado) con su frecuencia
    state_values  valores de estado observados
    reboot        valores de reinicio con su frecuencia
    ops           sumas de work.registry / services / scheduledTasks
    user_scope    nº de estados con work.user = true
    actions       nº de valores distintos de machineAction/userAction/action
    refs          nº de referencias a fichero y nº de referencias rotas
    desc_len, desc_sha256, warning_len, warning_sha256
    has_menu, no_state_record

Uso:
    python3 tools/ledger_extract/extract_atlas_toggles.py [--root DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = Path("/tmp/upstream/atlas")
PART = ROOT / "inventory" / "partition" / "results" / "atlas.tsv"
OUT_DIR = ROOT / "inventory" / "ledger"

CATALOG = "package/Executables/AtlasModules/Toggles/catalog.json"
TWEAKS_DIR = "package/Executables/AtlasModules/Scripts/Tweaks"
DESKTOP_DIR = "package/Executables/AtlasDesktop"
TOOLBOX_DIR = "package/Executables/AtlasModules/Toolbox"

TOGGLE_COLUMNS = ("item_id", "source", "source_ref", "label", "kind",
                  "category", "sha256", "attrs_json")
TWEAK_COLUMNS = ("item_id", "source_ref", "lines", "sha256", "keys_json",
                 "hklm", "hkcu", "set_service", "schtasks", "bcdedit", "netsh")

PSD1_KEY_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*=", re.MULTILINE)
MENTION_RE = {
    "hklm": re.compile(r"HKLM:", re.IGNORECASE),
    "hkcu": re.compile(r"HKCU:", re.IGNORECASE),
    "set_service": re.compile(r"\bSet-Service\b", re.IGNORECASE),
    "schtasks": re.compile(r"\bschtasks\b", re.IGNORECASE),
    "bcdedit": re.compile(r"\bbcdedit\b", re.IGNORECASE),
    "netsh": re.compile(r"\bnetsh\b", re.IGNORECASE),
}


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def sha_hex(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()[:16]


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def resolve_ref(root: Path, ref: str) -> bool:
    """Un launcher es relativo a AtlasDesktop/ o a Toolbox/."""
    rel = ref.replace("\\", "/")
    return ((root / DESKTOP_DIR / rel).exists()
            or (root / TOOLBOX_DIR / rel).exists())


def toggle_attrs(root: Path, entry: dict) -> tuple[dict, list[str]]:
    states = entry.get("states") or []
    broken: list[str] = []
    ref_total = 0
    for ref in [entry.get("launcher")] + [s.get("launcher") for s in states] \
            + [s.get("toolboxLauncher") for s in states]:
        if not ref:
            continue
        ref_total += 1
        if not resolve_ref(root, ref):
            broken.append(ref)

    work = [s.get("work") or {} for s in states]
    rebs = collections.Counter(str(s.get("reboot")) for s in states)
    snames = collections.Counter(str(s.get("name")) for s in states)
    svalues = collections.Counter(str(s.get("stateValue")) for s in states)

    attrs = {
        "fields": sorted(entry.keys()),
        "group": entry.get("group"),
        "elevation": entry.get("elevation"),
        "states": len(states),
        "state_names": dict(sorted(snames.items())),
        "state_values": dict(sorted(svalues.items())),
        "reboot": dict(sorted(rebs.items())),
        "ops": {
            "registry": sum(int(w.get("registry") or 0) for w in work),
            "services": sum(int(w.get("services") or 0) for w in work),
            "scheduled_tasks": sum(int(w.get("scheduledTasks") or 0) for w in work),
        },
        "user_scope": sum(1 for w in work if w.get("user") is True),
        "actions": {
            k: len({w.get(k) for w in work if w.get(k)})
            for k in ("machineAction", "userAction", "action")
        },
        "refs": {"total": ref_total, "broken": len(broken)},
        "desc_len": len(entry.get("description") or ""),
        "desc_sha256": sha_text(entry.get("description") or ""),
        "has_menu": bool(entry.get("menu")),
        "no_state_record": bool(entry.get("noStateRecord")),
    }
    if entry.get("warning"):
        attrs["warning_len"] = len(entry["warning"])
        attrs["warning_sha256"] = sha_text(entry["warning"])
    if any(s.get("menuLabel") for s in states):
        attrs["menu_labels"] = sum(1 for s in states if s.get("menuLabel"))
    if any(s.get("toolboxLauncher") for s in states):
        attrs["toolbox_launchers"] = sum(1 for s in states
                                         if s.get("toolboxLauncher"))
    return attrs, broken


def build_toggles(root: Path) -> tuple[list[dict], list[str], dict]:
    data = json.loads((root / CATALOG).read_text(encoding="utf-8-sig"))
    entries = data["toggles"]
    rows: list[dict] = []
    broken_all: list[str] = []
    for entry in entries:
        attrs, broken = toggle_attrs(root, entry)
        broken_all.extend(f"{entry['name']}:{b}" for b in broken)
        rows.append({
            "item_id": f"atlas:toggle:{entry['name']}",
            "source": "atlas",
            "source_ref": CATALOG,
            "label": entry["name"],
            "kind": "toggle",
            "category": entry.get("group") or "",
            "sha256": hashlib.sha256(canonical(entry)).hexdigest(),
            "attrs_json": json.dumps(attrs, ensure_ascii=False,
                                     sort_keys=True, separators=(",", ":")),
        })
    rows.sort(key=lambda r: r["item_id"])
    return rows, broken_all, data


def tweak_targets(part: Path) -> list[str]:
    import csv
    with part.open(encoding="utf-8") as fh:
        return sorted(
            r["path"] for r in csv.DictReader(fh, delimiter="\t")
            if r["treatment"] == "extract"
            and r["path"].startswith(TWEAKS_DIR) and r["path"].endswith(".psd1")
        )


def build_tweak_files(root: Path, part: Path) -> list[dict]:
    rows = []
    for rel in tweak_targets(part):
        raw = (root / rel).read_bytes()
        text = raw.decode("utf-8", errors="replace")
        keys = collections.Counter(PSD1_KEY_RE.findall(text))
        row = {
            "item_id": f"atlas:tweak-file:{rel}",
            "source_ref": rel,
            "lines": len(text.splitlines()),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "keys_json": json.dumps(sorted(keys), separators=(",", ":")),
        }
        for k, rx in MENTION_RE.items():
            row[k] = len(rx.findall(text))
        rows.append(row)
    rows.sort(key=lambda r: r["item_id"])
    return rows


def write_tsv(path: Path, rows: list[dict], columns: tuple[str, ...]) -> None:
    lines = ["\t".join(columns)]
    for r in rows:
        lines.append("\t".join(str(r.get(c, "")) for c in columns))
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def cross_checks(root: Path, toggles: list[dict], tweak_rows: list[dict],
                 data: dict) -> dict:
    names = [e["name"] for e in data["toggles"]]
    dupes = [n for n, c in collections.Counter(names).items() if c > 1]
    no_label = [t["item_id"] for t in toggles if not t["label"]]
    stems = {Path(r["source_ref"]).stem for r in tweak_rows}
    referenced = {s for s in stems
                  if any(s in t["attrs_json"] for t in toggles)}
    return {
        "toggles": len(toggles),
        "prediction": 91,
        "prediction_ok": len(toggles) == 91,
        "duplicate_ids": dupes,
        "unnamed": no_label,
        "broken_refs": [],
        "tweak_files": len(tweak_rows),
        "tweak_stems_not_in_catalog": len(stems - referenced),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ATLAS)
    ap.add_argument("--part", type=Path, default=PART)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not (args.root / CATALOG).is_file():
        print(f"ERROR: falta {args.root / CATALOG}", file=sys.stderr)
        return 2

    toggles, broken, data = build_toggles(args.root)
    tweak_rows = build_tweak_files(args.root, args.part)
    args.out.mkdir(parents=True, exist_ok=True)
    t_out = args.out / "atlas-toggles.tsv"
    f_out = args.out / "atlas-tweak-files.tsv"
    write_tsv(t_out, toggles, TOGGLE_COLUMNS)
    write_tsv(f_out, tweak_rows, TWEAK_COLUMNS)

    cross = cross_checks(args.root, toggles, tweak_rows, data)
    cross["broken_refs"] = broken
    summary = {
        "toggles": len(toggles),
        "prediction_ok": cross["prediction_ok"],
        "duplicate_ids": cross["duplicate_ids"],
        "unnamed": len(cross["unnamed"]),
        "broken_refs": len(broken),
        "tweak_files": len(tweak_rows),
        "toggles_sha256": hashlib.sha256(t_out.read_bytes()).hexdigest(),
        "tweaks_sha256": hashlib.sha256(f_out.read_bytes()).hexdigest(),
    }
    if args.json:
        print(json.dumps({"summary": summary, "cross": cross},
                         ensure_ascii=False, indent=2))
    else:
        print(f"atlas-toggles.tsv     : {len(toggles)} filas")
        print(f"  prediccion 91       : {'OK' if cross['prediction_ok'] else 'DIFIERE'}")
        print(f"  ids duplicados      : {len(cross['duplicate_ids'])}")
        print(f"  toggles sin etiqueta: {len(cross['unnamed'])}")
        print(f"  referencias rotas   : {len(broken)}")
        print(f"atlas-tweak-files.tsv : {len(tweak_rows)} filas")
        print(f"sha256 atl-toggles    : {summary['toggles_sha256']}")
        print(f"sha256 atl-tweaks     : {summary['tweaks_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
