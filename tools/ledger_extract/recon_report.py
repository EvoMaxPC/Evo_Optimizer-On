#!/usr/bin/env python3
"""Genera docs/inventory-recon/{winutil,atlas}.md desde los TSV de list_files.py.

Cada cifra del documento se acompaña del comando que la produjo, para que sea
reproducible (REQ-002/REQ-006). También imprime por stdout el contraste con el
reconocimiento previo del responsable.

Uso:
    python3 tools/ledger_extract/recon_report.py
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INV = ROOT / "inventory" / "upstream"
OUT = ROOT / "docs" / "inventory-recon"
UPSTREAM = Path("/tmp/upstream")

# Cifras del reconocimiento previo del responsable (sesión anterior).
# Se contrastan, NO se ajustan.
PRIOR = {
    "winutil": {
        "ps1_total": 197,
        "ps1_functions_public": 35,
        "ps1_functions_private": 90,
        "config_keys": {
            "applications.json": 239,
            "tweaks.json": 69,
            "feature.json": 33,
            "appx.json": 34,
            "themes.json": 3,
            "preset.json": 4,
            "appnavigation.json": 11,
            "dns.json": 8,
        },
    },
    "atlas": {
        "ps1": 372,
        "cmd": 188,
        "reg": 11,
        "yml": 24,
        "yaml": 6,
        "tests_pester_ps1": 109,
    },
}


def read_tsv(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        rows.append(dict(zip(header, line.split("\t"))))
    return rows


def count_by(rows: list[dict], key: str) -> Counter:
    return Counter(r[key] or "(sin extensión)" for r in rows)


def load_json_tolerant(path: Path):
    """utf-8-sig + strict=False (control chars) como pidió el responsable."""
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(raw, strict=False)


def to_md_table(counter: Counter, total: int, label: str) -> list[str]:
    out = [f"| {label} | ficheros | % |", "|---|---:|---:|"]
    for k, v in counter.most_common():
        out.append(f"| `{k}` | {v} | {100.0 * v / total:.1f}% |")
    out.append(f"| **total** | **{total}** | 100% |")
    return out


def winutil_doc(rows: list[dict]) -> tuple[list[str], list[tuple]]:
    total = len(rows)
    exts = count_by(rows, "ext")
    tops = count_by(rows, "top_dir")
    md = [
        "# Reconocimiento: WinUtil",
        "",
        f"Fuente: `inventory/upstream/winutil.files.tsv` (SHA fijado "
        f"`70c23c80641d7370532af2f619b2842658600842`).",
        "",
        f"**{total} ficheros** en el árbol. Comando:",
        "```bash",
        "git -C /tmp/upstream/winutil ls-tree -r -l --full-tree HEAD | wc -l",
        "tail -n +2 inventory/upstream/winutil.files.tsv | wc -l",
        "```",
        "",
        "## Ficheros por extensión",
        "",
        "Comando: `cut -f4 inventory/upstream/winutil.files.tsv | tail -n +2 | sort | uniq -c | sort -rn`",
        "",
        *to_md_table(exts, total, "ext"),
        "",
        "## Ficheros por directorio de primer nivel",
        "",
        "Comando: `cut -f5 inventory/upstream/winutil.files.tsv | tail -n +2 | sort | uniq -c | sort -rn`",
        "",
        *to_md_table(tops, total, "top_dir"),
        "",
    ]

    # conteo de .ps1 en functions/
    pub = sum(1 for r in rows if r["path"].startswith("functions/public/") and r["ext"] == "ps1")
    priv = sum(1 for r in rows if r["path"].startswith("functions/private/") and r["ext"] == "ps1")
    ps1_total = exts.get("ps1", 0)
    md += [
        "## Scripts PowerShell",
        "",
        "Comando: `awk -F'\\t' '$4==\"ps1\"' inventory/upstream/winutil.files.tsv | wc -l`",
        "",
        f"- `.ps1` totales: **{ps1_total}**",
        f"- `functions/public/*.ps1`: **{pub}**",
        f"- `functions/private/*.ps1`: **{priv}**",
        f"- otros `.ps1` (raíz, scripts/, tools/, pester/): **{ps1_total - pub - priv}**",
        "",
        "## Claves de `config/*.json`",
        "",
        "Carga tolerante: `encoding='utf-8-sig'` y `json.loads(..., strict=False)`.",
        "Comando: `python3 -c \"import json;print(len(json.loads(open('config/tweaks.json',encoding='utf-8-sig').read(),strict=False)))\"`",
        "",
        "| fichero | claves primer nivel |",
        "|---|---:|",
    ]
    found = {}
    cfgdir = UPSTREAM / "winutil" / "config"
    if cfgdir.is_dir():
        for f in sorted(cfgdir.glob("*.json")):
            try:
                data = load_json_tolerant(f)
                n = len(data) if isinstance(data, (dict, list)) else 0
            except Exception as exc:  # noqa: BLE001
                n = f"ERROR: {exc}"
            found[f.name] = n
            md.append(f"| `{f.name}` | {n} |")
    else:
        md.append("| _(clon no disponible; sin datos)_ | - |")

    # contraste
    diffs = []
    for fname, prior in PRIOR["winutil"]["config_keys"].items():
        real = found.get(fname)
        diffs.append((fname, prior, real, real == prior if isinstance(real, int) else False))
    diffs.append(("ps1 total", PRIOR["winutil"]["ps1_total"], ps1_total, ps1_total == PRIOR["winutil"]["ps1_total"]))
    diffs.append(("functions/public ps1", PRIOR["winutil"]["ps1_functions_public"], pub, pub == PRIOR["winutil"]["ps1_functions_public"]))
    diffs.append(("functions/private ps1", PRIOR["winutil"]["ps1_functions_private"], priv, priv == PRIOR["winutil"]["ps1_functions_private"]))

    md += ["", "## Contraste con el reconocimiento previo", "",
           "| magnitud | previo | medido | coincide |", "|---|---:|---:|:---:|"]
    for name, prior, real, same in diffs:
        md.append(f"| `{name}` | {prior} | {real} | {'sí' if same else '**NO**'} |")
    md.append("")
    return md, diffs


def atlas_doc(rows: list[dict]) -> tuple[list[str], list[tuple]]:
    total = len(rows)
    exts = count_by(rows, "ext")
    tops = count_by(rows, "top_dir")
    md = [
        "# Reconocimiento: AtlasOS",
        "",
        f"Fuente: `inventory/upstream/atlas.files.tsv` (SHA fijado "
        f"`ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`).",
        "",
        f"**{total} ficheros** en el árbol. Comando:",
        "```bash",
        "git -C /tmp/upstream/atlas ls-tree -r -l --full-tree HEAD | wc -l",
        "tail -n +2 inventory/upstream/atlas.files.tsv | wc -l",
        "```",
        "",
        "## Ficheros por extensión",
        "",
        "Comando: `cut -f4 inventory/upstream/atlas.files.tsv | tail -n +2 | sort | uniq -c | sort -rn`",
        "",
        *to_md_table(exts, total, "ext"),
        "",
        "## Ficheros por directorio de primer nivel",
        "",
        "Comando: `cut -f5 inventory/upstream/atlas.files.tsv | tail -n +2 | sort | uniq -c | sort -rn`",
        "",
        *to_md_table(tops, total, "top_dir"),
        "",
    ]
    tests_ps1 = sum(1 for r in rows if r["path"].startswith("tests/") and r["ext"] == "ps1")
    md += [
        "## Tests Pester",
        "",
        "Comando: `awk -F'\\t' '$1 ~ /^tests\\// && $4==\"ps1\"' inventory/upstream/atlas.files.tsv | wc -l`",
        "",
        f"- `.ps1` bajo `tests/`: **{tests_ps1}**",
        "",
    ]
    diffs = []
    for label, key in (("ps1", "ps1"), ("cmd", "cmd"), ("reg", "reg"),
                       ("yml", "yml"), ("yaml", "yaml")):
        prior = PRIOR["atlas"][key]
        real = exts.get(key, 0)
        diffs.append((f".{key}", prior, real, real == prior))
    diffs.append(("tests/*.ps1 (Pester)", PRIOR["atlas"]["tests_pester_ps1"], tests_ps1,
                  tests_ps1 == PRIOR["atlas"]["tests_pester_ps1"]))
    md += ["## Contraste con el reconocimiento previo", "",
           "| magnitud | previo | medido | coincide |", "|---|---:|---:|:---:|"]
    for name, prior, real, same in diffs:
        md.append(f"| `{name}` | {prior} | {real} | {'sí' if same else '**NO**'} |")
    md.append("")
    return md, diffs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inv", type=Path, default=INV)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    rc = 0
    for name, fn in (("winutil", winutil_doc), ("atlas", atlas_doc)):
        tsv = args.inv / f"{name}.files.tsv"
        if not tsv.is_file():
            print(f"ERROR: falta {tsv}; ejecuta list_files.py", file=sys.stderr)
            return 2
        rows = read_tsv(tsv)
        md, diffs = fn(rows)
        target = args.out / f"{name}.md"
        target.write_text("\n".join(md) + "\n", encoding="utf-8")
        print(f"[{name}] {len(rows)} ficheros -> {target}")
        for nm, prior, real, same in diffs:
            flag = "OK " if same else "DIFF"
            print(f"  {flag} {nm:<28} previo={prior!s:<6} medido={real!s:<6}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
