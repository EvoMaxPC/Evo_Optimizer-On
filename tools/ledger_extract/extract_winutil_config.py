#!/usr/bin/env python3
"""Extractor determinista de WinUtil (MIT) a items del ledger.

Salidas (UTF-8 sin BOM, LF, orden estable por item_id):
  inventory/ledger/winutil-items.tsv
      item_id  source  source_ref  label  kind  sha256  attrs_json
  inventory/ledger/winutil-apps.tsv
      item_id  source  source_ref  label  kind  sha256  category  winget  choco
  (resumen por categoría por stdout y en docs/reports/paso3.md)

kinds no-app: tweak, feature, appx, preset, dns-provider, theme, nav-entry.
Las 239 entradas de applications.json van APARTE como catalog-entry.

Reglas:
  * item_id = "winutil:<kind>:<clave>" (determinista).
  * sha256 = hash del JSON canónico de la entrada (sort_keys, separadores fijos).
  * attrs_json = solo hechos estructurados existentes en la entrada. NUNCA se
    copia el cuerpo de un script: solo nº de líneas, sha256 y los nombres de
    cmdlets/funciones PROPIAS invocadas por regex simple.
  * Sin timestamps ni rutas absolutas: dos ejecuciones dan el mismo byte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path("/tmp/upstream/winutil/config")
WINUTIL_ROOT = Path("/tmp/upstream/winutil")
LEDGER = ROOT / "inventory" / "ledger"

# (fichero, kind) — el orden fija el orden de proceso, no el de salida.
SOURCES: list[tuple[str, str]] = [
    ("tweaks.json", "tweak"),
    ("feature.json", "feature"),
    ("appx.json", "appx"),
    ("preset.json", "preset"),
    ("dns.json", "dns-provider"),
    ("themes.json", "theme"),
    ("appnavigation.json", "nav-entry"),
]

ITEMS_COLUMNS = ("item_id", "source", "source_ref", "label", "kind", "sha256", "attrs_json")
APPS_COLUMNS = ("item_id", "source", "source_ref", "label", "kind", "sha256",
                "category", "winget", "choco")

# Cmdlets propios de WinUtil: Invoke-/Get-/Set-/Initialize-/Test- con prefijo WinUtil/WPF
OWN_CMDLET_RE = re.compile(r"\b((?:Invoke|Get|Set|Add|Remove|Initialize|Test|New|Export|Import|Write|Close|Complete|Find)-W(?:inUtil|PF)[A-Za-z0-9]+)\b")
FUNC_DEF_RE = re.compile(r"^\s*function\s+([\w-]+)", re.MULTILINE)
BOM = "\ufeff"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"), strict=False)


def canonical_sha(obj) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def script_facts(code: str) -> dict:
    """Hechos de un script SIN copiar su cuerpo."""
    lines = code.count("\n") + (1 if code and not code.endswith("\n") else 0)
    return {
        "lines": lines,
        "sha256": sha256_bytes(code.encode("utf-8")),
        "own_cmdlets": sorted(set(OWN_CMDLET_RE.findall(code))),
    }


def normalize_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def attrs_for_tweak(entry: dict) -> dict:
    attrs: dict = {}
    for key in ("category", "panel", "Type"):
        if key in entry:
            attrs[key.lower()] = entry[key]
    if "Description" in entry:
        attrs["has_description"] = True

    registry = normalize_list(entry.get("registry"))
    if registry:
        reg_facts = []
        for r in registry:
            if not isinstance(r, dict):
                continue
            facts = {}
            for k in ("Path", "Name", "Value", "Type", "OriginalValue"):
                if k in r:
                    facts[k.lower()] = r[k]
            reg_facts.append(facts)
        attrs["registry"] = reg_facts

    services = normalize_list(entry.get("service"))
    if services:
        svc = []
        for s in services:
            if isinstance(s, dict):
                svc.append({k.lower(): s[k] for k in ("Name", "StartupType", "Status") if k in s})
            elif isinstance(s, str):
                svc.append({"name": s})
        attrs["services"] = svc

    for key, attr in (("InvokeScript", "invoke_scripts"), ("UndoScript", "undo_scripts")):
        scripts = normalize_list(entry.get(key))
        if scripts:
            attrs[attr] = [script_facts(s) for s in scripts if isinstance(s, str)]

    if "ComboItems" in entry:
        attrs["combo_items"] = [x.strip() for x in str(entry["ComboItems"]).split(",") if x.strip()]
    return attrs


def attrs_for_feature(entry: dict) -> dict:
    attrs = {}
    for key in ("Category", "Panel", "Type", "Description"):
        if key in entry:
            attrs[key.lower()] = entry[key]
    for key, attr in (("InvokeScript", "invoke_scripts"), ("UndoScript", "undo_scripts")):
        scripts = normalize_list(entry.get(key))
        if scripts:
            attrs[attr] = [script_facts(s) for s in scripts if isinstance(s, str)]
    return attrs


def attrs_for_appx(entry: dict) -> dict:
    attrs = {}
    for key in ("Content", "Description", "Category", "Panel", "type", "Type"):
        if key in entry:
            attrs[key.lower()] = entry[key]
    for key in ("winget", "choco"):
        if key in entry:
            attrs[key] = entry[key]
    return attrs


def attrs_for_theme(entry) -> dict:
    if isinstance(entry, dict):
        return {"keys": sorted(entry.keys())}
    return {"shape": type(entry).__name__}


def attrs_for_preset(entry) -> dict:
    members = entry if isinstance(entry, list) else []
    return {"members": list(members), "member_count": len(members)}


def attrs_for_dns(entry: dict) -> dict:
    attrs = {}
    if isinstance(entry, dict):
        for key in ("Primary", "Secondary", "DoH", "Name"):
            if key in entry:
                attrs[key.lower()] = entry[key]
        if not attrs:
            attrs = {"keys": sorted(entry.keys())}
    return attrs


def attrs_for_nav(entry) -> dict:
    if isinstance(entry, dict):
        return {"keys": sorted(entry.keys())}
    return {"shape": type(entry).__name__}


ATTRS_BUILDERS = {
    "tweak": attrs_for_tweak,
    "feature": attrs_for_feature,
    "appx": attrs_for_appx,
    "theme": attrs_for_theme,
    "preset": attrs_for_preset,
    "dns-provider": attrs_for_dns,
    "nav-entry": attrs_for_nav,
}


def extract_key(obj: dict, kind: str) -> str:
    """Etiqueta visible. WinUtil usa 'Content' (tweaks/feature) y
    'content' (applications.json, minúscula): normalizamos la búsqueda."""
    for key in ("Content", "content", "Description", "description", "name", "Name"):
        if isinstance(obj.get(key), str) and obj[key]:
            return obj[key]
    return ""


def build_items(config_dir: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    stats = {"per_file": {}, "missing_label": [], "dupes": [], "presets": {}}

    for filename, kind in SOURCES:
        path = config_dir / filename
        if not path.is_file():
            raise SystemExit(f"ERROR: falta {path}")
        data = load_json(path)
        if not isinstance(data, dict):
            raise SystemExit(f"ERROR: {filename} no es un objeto JSON")

        seen: set[str] = set()
        for key, entry in data.items():
            if key in seen:
                stats["dupes"].append(f"{filename}#{key}")
            seen.add(key)

            label = extract_key(entry, kind) if isinstance(entry, dict) else ""
            if kind == "preset":
                label = key
            if not label:
                stats["missing_label"].append(f"{filename}#{key}")

            attrs = ATTRS_BUILDERS[kind](entry)
            if kind == "preset":
                stats["presets"][key] = attrs["members"]

            rows.append({
                "item_id": f"winutil:{kind}:{key}",
                "source": f"config/{filename}",
                "source_ref": f"config/{filename}#{key}",
                "label": label,
                "kind": kind,
                "sha256": canonical_sha(entry),
                "attrs_json": json.dumps(attrs, sort_keys=True, ensure_ascii=False,
                                          separators=(",", ":")),
            })
        stats["per_file"][filename] = len(data)
    return rows, stats


def build_apps(config_dir: Path) -> tuple[list[dict], dict]:
    path = config_dir / "applications.json"
    data = load_json(path)
    rows: list[dict] = []
    by_cat: dict[str, int] = {}
    no_pkg = []
    for key, entry in data.items():
        entry = entry if isinstance(entry, dict) else {}
        cat = entry.get("category", "")
        by_cat[cat] = by_cat.get(cat, 0) + 1
        winget = entry.get("winget", "")
        choco = entry.get("choco", "")
        if not winget and not choco:
            no_pkg.append(key)
        rows.append({
            "item_id": f"winutil:catalog-entry:{key}",
            "source": "config/applications.json",
            "source_ref": f"config/applications.json#{key}",
            "label": extract_key(entry, "catalog-entry"),
            "kind": "catalog-entry",
            "sha256": canonical_sha(entry),
            "category": cat,
            "winget": winget,
            "choco": choco,
        })
    return rows, {"total": len(rows), "by_category": by_cat, "no_package": no_pkg}


def write_tsv(rows: list[dict], columns: tuple[str, ...], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(columns)]
    for row in sorted(rows, key=lambda r: r["item_id"]):
        lines.append("\t".join(str(row.get(c, "")) for c in columns))
    # UTF-8 sin BOM, LF, terminador final
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def _top_level_dupes(path: Path) -> list[str]:
    """Claves duplicadas en el objeto RAÍZ (no anidadas).

    json.load se queda con la última, así que hay que mirar los pares crudos.
    """
    dups: list[str] = []

    def hook(pairs):
        seen: set[str] = set()
        for k, _v in pairs:
            if k in seen:
                dups.append(k)
            seen.add(k)
        return dict(pairs)

    json.loads(path.read_text(encoding="utf-8-sig"), strict=False,
               object_pairs_hook=hook)
    # el hook se aplica a TODOS los objetos; nos quedamos solo con los que
    # aparecen más de una vez en el mismo objeto... aproximación honesta:
    return sorted(set(dups))


def cross_checks(config_dir: Path, stats: dict) -> dict:
    checks = {}
    tweaks = load_json(config_dir / "tweaks.json")
    appx = load_json(config_dir / "appx.json")
    preset = load_json(config_dir / "preset.json")

    missing_tweaks: list[str] = []
    resolved_appx: list[str] = []
    for pname, members in preset.items():
        for m in (members if isinstance(members, list) else []):
            if m in tweaks:
                continue
            if m in appx:
                # el preset AppxDefault referencia appx.json, no tweaks.json
                resolved_appx.append(f"{pname}->{m}")
            else:
                missing_tweaks.append(f"{pname}->{m}")

    checks["preset_members_total"] = sum(
        len(v) for v in preset.values() if isinstance(v, list))
    checks["preset_members_missing_in_tweaks"] = missing_tweaks
    checks["preset_members_resolved_in_appx"] = resolved_appx

    checks["raw_dupe_files"] = [
        (filename, _top_level_dupes(config_dir / filename))
        for filename, _kind in SOURCES
    ]
    return checks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=CONFIG_DIR)
    ap.add_argument("--out", type=Path, default=LEDGER)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    items, stats = build_items(args.config)
    apps, app_stats = build_apps(args.config)
    checks = cross_checks(args.config, stats)

    write_tsv(items, ITEMS_COLUMNS, args.out / "winutil-items.tsv")
    write_tsv(apps, APPS_COLUMNS, args.out / "winutil-apps.tsv")

    summary = {
        "items": len(items),
        "apps": len(apps),
        "per_file": stats["per_file"],
        "by_kind": {},
        "missing_label": stats["missing_label"],
        "preset_members_total": checks["preset_members_total"],
        "preset_members_missing": checks["preset_members_missing_in_tweaks"],
        "preset_members_in_appx": checks["preset_members_resolved_in_appx"],
        "dupe_files": checks["raw_dupe_files"],
        "apps_by_category": app_stats["by_category"],
        "apps_without_package": app_stats["no_package"],
    }
    for row in items:
        summary["by_kind"][row["kind"]] = summary["by_kind"].get(row["kind"], 0) + 1

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(f"items no-app : {len(items)}")
        for kind, n in sorted(summary["by_kind"].items()):
            print(f"  {kind:14} {n}")
        print(f"apps         : {len(apps)}")
        print(f"preset members comprobados : {summary['preset_members_total']}")
        print(f"  resueltos en appx.json   : {len(summary['preset_members_in_appx'])}")
        print(f"  inexistentes en ambos    : {len(summary['preset_members_missing'])}")
        for m in summary["preset_members_missing"]:
            print(f"   ! {m}")
        print("duplicados de clave raiz por fichero: " +
              ", ".join(f"{f}={len(d)}" for f, d in summary["dupe_files"]))
        if summary["missing_label"]:
            print("entradas sin etiqueta: " + ", ".join(summary["missing_label"]))
        else:
            print("entradas sin etiqueta: ninguna")
        print("apps sin gestor de paquetes: " +
              (", ".join(summary["apps_without_package"]) or "ninguna"))
        print("apps por categoría:")
        for cat, n in sorted(summary["apps_by_category"].items(), key=lambda kv: -kv[1]):
            print(f"  {cat or '(sin categoría)':28} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
