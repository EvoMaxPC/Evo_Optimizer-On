#!/usr/bin/env python3
"""Revisión de la partición (T4 del paso 2b). Solo informa: no cambia reglas.

Genera docs/reports/paso2b.md con:
  (a) tabla tratamiento x top_dir por repo
  (b) ficheros de comportamiento en `reference`, por dir de 1er y 2º nivel
  (c) tools/ y services/ de atlas agrupado por subdirectorio con tratamiento
  (d) tools/ y scripts/ y docs/ de winutil con su tratamiento
  + marcas "A REVISAR" (comportamiento en reference fuera de
    tests/, .github/, docs/, tools/, services/)

Uso:
    python3 tools/ledger_extract/partition_review.py
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "inventory" / "partition" / "results"
UPSTREAM = ROOT / "inventory" / "upstream"

BEHAVIOUR_EXTS = {"ps1", "psm1", "psd1", "cmd", "bat", "reg", "json", "rs", "toml", "cab"}
ALLOWED_REFERENCE_DIRS = ("tests/", ".github/", "docs/", "tools/", "services/")


def read_tsv(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, l.split("\t"))) for l in lines[1:] if l.strip()]


def load(repo: str) -> list[dict]:
    rows = read_tsv(RESULTS / f"{repo}.tsv")
    sizes = {r["path"]: r for r in read_tsv(UPSTREAM / f"{repo}.files.tsv")}
    for r in rows:
        meta = sizes.get(r["path"], {})
        r["size"] = int(meta.get("size", 0))
        r["ext"] = meta.get("ext", "")
        r["top_dir"] = meta.get("top_dir", ".")
        parts = r["path"].split("/")
        r["lvl2"] = f"{parts[0]}/{parts[1]}" if len(parts) > 1 else "."
    return rows


def table_treatment_by_top(rows: list[dict]) -> list[str]:
    grid: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        grid[r["top_dir"]][r["treatment"]] += 1
    out = ["| top_dir | extract | reference | exclude | total |", "|---|---:|---:|---:|---:|"]
    for top in sorted(grid, key=lambda k: -sum(grid[k].values())):
        c = grid[top]
        out.append(f"| `{top}` | {c['extract']} | {c['reference']} | {c['exclude']} | {sum(c.values())} |")
    tot = Counter(r["treatment"] for r in rows)
    out.append(f"| **TOTAL** | **{tot['extract']}** | **{tot['reference']}** | **{tot['exclude']}** | **{len(rows)}** |")
    return out


def behaviour_in_reference(rows: list[dict]) -> tuple[list[str], list[str], list[str]]:
    sel = [r for r in rows if r["treatment"] == "reference" and r["ext"] in BEHAVIOUR_EXTS]
    by1 = Counter(r["top_dir"] for r in sel)
    by2 = Counter(r["lvl2"] for r in sel)
    review = [
        r for r in sel
        if not any(r["path"].startswith(d) for d in ALLOWED_REFERENCE_DIRS)
    ]
    md = [
        f"Ficheros con extensión de comportamiento en `reference`: **{len(sel)}**",
        "",
        "| directorio de 1er nivel | ficheros |",
        "|---|---:|",
    ]
    for k, v in by1.most_common():
        md.append(f"| `{k}` | {v} |")
    md += ["", "| directorio de 2º nivel | ficheros |", "|---|---:|"]
    for k, v in by2.most_common(15):
        md.append(f"| `{k}` | {v} |")
    md += ["", f"**A REVISAR** (comportamiento en reference fuera de "
               f"`tests/`, `.github/`, `docs/`, `tools/`, `services/`): **{len(review)}**"]
    if review:
        md += ["", "| ruta | ext | bytes |", "|---|---|---:|"]
        for r in sorted(review, key=lambda x: x["path"]):
            md.append(f"| `{r['path']}` | {r['ext']} | {r['size']} |")
    else:
        md.append("")
        md.append("_Ninguno._")
    return md, [r["path"] for r in review], [r["path"] for r in sel]


def subtree(rows: list[dict], prefix: str) -> list[str]:
    sel = [r for r in rows if r["path"].startswith(prefix)]
    if not sel:
        return [f"_Sin ficheros bajo `{prefix}`_"]
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in sel:
        rest = r["path"][len(prefix):]
        sub = rest.split("/")[0] + "/" if "/" in rest else "(raíz)"
        groups[sub].append(r)
    md = [f"`{prefix}` — **{len(sel)} ficheros**:", "",
          "| subdirectorio | ficheros | tratamientos | bytes |", "|---|---:|---|---:|"]
    for sub in sorted(groups):
        g = groups[sub]
        tr = Counter(r["treatment"] for r in g)
        trs = ", ".join(f"{k}={v}" for k, v in tr.items())
        md.append(f"| `{sub}` | {len(g)} | {trs} | {sum(r['size'] for r in g)} |")
    return md


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "reports" / "paso2b.md")
    ap.add_argument("--print", dest="do_print", action="store_true")
    args = ap.parse_args(argv)

    md = ["# Paso 2b — Revisión de la partición y sonda con patrones", "",
          "Generado por `tools/ledger_extract/partition_review.py`. Solo informa: "
          "no se modificó ninguna regla de partición.", ""]
    review_all = {}
    for repo in ("winutil", "atlas"):
        rows = load(repo)
        md += [f"## {repo} — tratamiento x directorio de primer nivel", "",
               *table_treatment_by_top(rows), "",
               f"## {repo} — comportamiento en `reference`", ""]
        bmd, review, sel = behaviour_in_reference(rows)
        md += bmd + [""]
        review_all[repo] = {"review": review, "sel": sel}

    atlas = load("atlas")
    md += ["## atlas — `tools/` y `services/` por subdirectorio", "",
           *subtree(atlas, "tools/"), "", *subtree(atlas, "services/"), ""]

    win = load("winutil")
    md += ["## winutil — `tools/`, `scripts/`, `docs/`", "",
           *subtree(win, "tools/"), "", *subtree(win, "scripts/"), "",
           *subtree(win, "docs/"), ""]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"escrito: {args.out}")
    for repo, d in review_all.items():
        print(f"[{repo}] reference con extensión de comportamiento: {len(d['sel'])}, A REVISAR: {len(d['review'])}")
        for p in d["review"]:
            print(f"   ! {p}")
    if args.do_print:
        print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
