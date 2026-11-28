#!/usr/bin/env python3
"""Entradas del manifiesto de tweaks de Atlas (`tweaks.manifest.psd1`).

No hay PowerShell en el sandbox: se parsea el fichero a mano. Su estructura la
declara el propio Atlas en dos sitios, que se usan como contrato:

    …/Atlas.Tweaks/Domain/Manifest.ps1:10-13
        $script:AtlasTweakCategoryKeys   = @('Name', 'ParentModes', 'Tweaks')
        $script:AtlasTweakStandaloneKeys = @('Slug', 'ParentModes')
        $script:AtlasTweakDisabledKeys   = @('Slug', 'Reason')
        $script:AtlasTweakParentModes    = @('Fresh', 'Upgrade')

    …/Manifest.ps1:181  la ruta se compone como
        Join-Path $TweaksRoot (($Slug -replace '/','\\') + '.psd1')

Formas de entrada en el manifiesto:

1. `Categories = @( @{ Name = 'x'; ParentModes = @(...); Tweaks = @( 'slug', ... ) } ... )`
   Los slugs de `Tweaks` son relativos a la categoria -> id = `<Name>/<slug>`.
2. `Standalone = @( @{ Slug = 'a/b'; ParentModes = @('Fresh') } ... )`
   Ya llevan la ruta completa -> id = `Slug`.
3. `Disabled = @( @{ Slug = 'a/b'; Reason = '...' } ... )`

Salida: `inventory/ledger/atlas-manifest.tsv`
    item_id  id  psd1_path  enabled  category  parent_modes  reason  section

- `psd1_path` vacio si el slug no resuelve a un fichero del pin.
- `attrs_json` queda como columna con los campos escalares restantes, para no
  perder informacion sin inventar columnas. **Sin cuerpos de scripts**: el
  manifiesto solo tiene slugs y modos.

Uso:
    python3 tools/ledger_extract/extract_atlas_manifest.py [--json]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = Path("/tmp/upstream/atlas")
LEDGER = ROOT / "inventory" / "ledger"
TWEAKS_DIR = "package/Executables/AtlasModules/Scripts/Tweaks"
MANIFEST = f"{TWEAKS_DIR}/tweaks.manifest.psd1"

COLUMNS = ("item_id", "id", "psd1_path", "enabled", "category",
           "parent_modes", "reason", "section", "attrs_json")


# --------------------------------------------------------------- utilidades
def strip_comments(text: str) -> str:
    """Quita comentarios `#` de PowerShell respetando las comillas."""
    out = []
    for line in text.splitlines():
        res, quote, i = [], "", 0
        while i < len(line):
            c = line[i]
            if quote:
                res.append(c)
                if c == quote and not (i + 1 < len(line) and line[i + 1] == quote):
                    quote = ""
                i += 1
                continue
            if c in ("'", '"'):
                quote = c
                res.append(c)
                i += 1
                continue
            if c == "#":
                break
            res.append(c)
            i += 1
        out.append("".join(res))
    return "\n".join(out)


def block(text: str, key: str) -> str | None:
    """Contenido de `key = @( ... )` con llaves y parentesis equilibrados."""
    m = re.search(rf"^\s*{key}\s*=\s*@\(", text, re.MULTILINE)
    if not m:
        return None
    i = text.index("(", m.end() - 1)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[i + 1:j]
    return None


def hashtables(block_text: str) -> list[str]:
    """Cuerpos de las hashtables `@{ ... }` de un bloque."""
    out, i = [], 0
    while True:
        m = re.compile(r"@\{").search(block_text, i)
        if not m:
            return out
        depth, j = 0, m.end() - 1
        for k in range(j, len(block_text)):
            if block_text[k] == "{":
                depth += 1
            elif block_text[k] == "}":
                depth -= 1
                if depth == 0:
                    out.append(block_text[m.end():k])
                    i = k + 1
                    break
        else:
            return out


def field(body: str, name: str) -> str | None:
    m = re.search(rf"\b{name}\s*=\s*'((?:[^']|'')*)'", body)
    return m.group(1).replace("''", "'") if m else None


def modes(body: str) -> str:
    m = re.search(r"\bParentModes\s*=\s*@\(([^)]*)\)", body)
    if not m:
        return ""
    return "|".join(re.findall(r"'([^']+)'", m.group(1)))


def quoted_list(body: str) -> list[str]:
    return [s.replace("''", "'") for s in re.findall(r"'((?:[^']|'')*)'", body)]


# ------------------------------------------------------------------ parseo
def parse(text: str) -> list[dict]:
    text = strip_comments(text)
    entries: list[dict] = []

    cats = block(text, "Categories") or ""
    for cat_body in hashtables(cats):
        cat = field(cat_body, "Name")
        if not cat:
            continue
        tm = re.search(r"\bTweaks\s*=\s*@\(([^)]*)\)", cat_body, re.DOTALL)
        slugs = quoted_list(tm.group(1)) if tm else []
        for slug in slugs:
            entries.append({
                "id": f"{cat}/{slug}",
                "enabled": "true",
                "category": cat,
                "parent_modes": modes(cat_body),
                "reason": "",
                "section": "Categories",
                "attrs_json": "",
            })

    for section in ("Standalone", "Disabled"):
        body = block(text, section) or ""
        for hb in hashtables(body):
            slug = field(hb, "Slug")
            if not slug:
                continue
            entries.append({
                "id": slug,
                "enabled": "true" if section == "Standalone" else "false",
                "category": slug.split("/")[0] if "/" in slug else "",
                "parent_modes": modes(hb),
                "reason": field(hb, "Reason") or "",
                "section": section,
                "attrs_json": json.dumps(
                    {"keys": sorted(set(re.findall(r"\b([A-Za-z]+)\s*=", hb)))},
                    sort_keys=True, separators=(",", ":")),
            })
    entries.sort(key=lambda e: e["id"])
    return entries


def resolve(entries: list[dict], root: Path) -> list[dict]:
    for e in entries:
        rel = f"{TWEAKS_DIR}/{e['id']}.psd1"
        e["psd1_path"] = rel if (root / rel).is_file() else ""
        e["item_id"] = f"atlas:manifest:{e['id']}"
    return entries


def build(root: Path = ATLAS) -> tuple[list[dict], dict]:
    path = root / MANIFEST
    text = path.read_text(encoding="utf-8-sig")
    entries = resolve(parse(text), root)
    dup = Counter(e["id"] for e in entries)
    meta = {
        "entradas": len(entries),
        "ids_distintos": len({e["id"] for e in entries}),
        "duplicados": sorted(k for k, v in dup.items() if v > 1),
        "enabled": sum(1 for e in entries if e["enabled"] == "true"),
        "disabled": sum(1 for e in entries if e["enabled"] == "false"),
        "por_seccion": dict(sorted(Counter(e["section"] for e in entries).items())),
        "sin_psd1": sorted(e["id"] for e in entries if not e["psd1_path"]),
        "parent_modes": dict(sorted(Counter(e["parent_modes"] for e in entries).items())),
    }
    return entries, meta


def write_tsv(path: Path, rows: list[dict]) -> None:
    lines = ["\t".join(COLUMNS)]
    for r in rows:
        lines.append("\t".join(str(r.get(c, "")) for c in COLUMNS))
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ATLAS)
    ap.add_argument("--out", type=Path, default=LEDGER)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows, meta = build(args.root)
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "atlas-manifest.tsv"
    write_tsv(out, rows)
    summary = {**meta,
               "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    print(f"entradas              : {meta['entradas']} (ids distintos {meta['ids_distintos']})")
    print(f"enabled / disabled    : {meta['enabled']} / {meta['disabled']}")
    print(f"por seccion           : {meta['por_seccion']}")
    print(f"parent_modes          : {meta['parent_modes']}")
    print(f"sin .psd1             : {len(meta['sin_psd1'])} {meta['sin_psd1']}")
    print(f"duplicados            : {meta['duplicados'] or 'ninguno'}")
    print(f"sha256                : {summary['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
