#!/usr/bin/env python3
"""Sonda de palabras clave por PATRÓN sobre los clones de upstream (REQ-002/REQ-005).

Salidas:
  docs/inventory-recon/keyword-probe.tsv
      termino  patron  winutil_ficheros  atlas_ficheros
  docs/inventory-recon/keyword-probe-examples.tsv
      termino  repo  ruta            (hasta 3 rutas por término y repo)

Complemento (T3, secciones 16/17 del inventario):
  docs/inventory-recon/seccion16-17-probe.tsv
      item  fuente_inventario  patron  winutil_ficheros  atlas_ficheros  ejemplos

Diseño:
  * Un único recorrido por repo; se compilan los regex una vez.
  * Se ignoran ficheros > MAX_SCAN_BYTES (binarios grandes: .cab, .exe) para no
    leer 68 MB de basura; se declara en el informe.
  * Los patrones viven en keyword_patterns.py y NO se ajustan tras ver resultados.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from keyword_patterns import KEYWORD_PATTERNS, SECTION_PROBES  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEST = Path("/tmp/upstream")
RECON = ROOT / "docs" / "inventory-recon"

MAX_SCAN_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_EXAMPLES = 3
REPOS = ("winutil", "atlas")


def iter_files(repo: Path):
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo)
        if ".git" in rel.parts:
            continue
        yield rel.as_posix(), path


def scan(repo: Path, patterns: list[re.Pattern]) -> list[list[str]]:
    """Devuelve, por patrón, la lista de rutas que lo contienen."""
    hits: list[list[str]] = [[] for _ in patterns]
    for rel, path in iter_files(repo):
        try:
            if path.stat().st_size > MAX_SCAN_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, pat in enumerate(patterns):
            if pat.search(text):
                hits[i].append(rel)
    return hits


def compile_all(raw: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in raw]


def write_keyword_tsv(rows, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["termino\tpatron\twinutil_ficheros\tatlas_ficheros"]
    for term, pat, w, a in rows:
        lines.append(f"{term}\t{pat}\t{w}\t{a}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_examples_tsv(per_repo: dict[str, list[list[str]]], terms, out: Path) -> None:
    lines = ["termino\trepo\truta"]
    for i, (term, _pat) in enumerate(terms):
        for repo in REPOS:
            for rel in per_repo[repo][i][:MAX_EXAMPLES]:
                lines.append(f"{term}\t{repo}\t{rel}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_section_tsv(per_repo: dict[str, list[list[str]]], out: Path) -> None:
    lines = ["item\tfuente_inventario\tpatron\twinutil_ficheros\tatlas_ficheros\tejemplos"]
    offset = len(KEYWORD_PATTERNS)
    for j, (item, fuente, pat, dudoso) in enumerate(SECTION_PROBES):
        i = offset + j
        w = per_repo["winutil"][i]
        a = per_repo["atlas"][i]
        ex = []
        for rel in (w[:2] + a[2:])[:MAX_EXAMPLES]:
            ex.append(rel)
        label = pat + (" [patron dudoso]" if dudoso else "")
        lines.append(f"{item}\t{fuente}\t{label}\t{len(w)}\t{len(a)}\t{'; '.join(ex)}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(dest: Path, recon: Path) -> dict:
    terms = KEYWORD_PATTERNS
    probes = SECTION_PROBES
    all_raw = [p for _t, p in terms] + [p for _i, _f, p, _d in probes]
    patterns = compile_all(all_raw)

    per_repo = {}
    for repo in REPOS:
        base = dest / repo
        if not base.is_dir():
            raise SystemExit(f"ERROR: falta el clon {base}; ejecuta fetch_upstream.py")
        per_repo[repo] = scan(base, patterns)
        print(f"[{repo}] escaneado con {len(patterns)} patrones")

    rows = []
    for i, (term, pat) in enumerate(terms):
        rows.append((term, pat, len(per_repo["winutil"][i]), len(per_repo["atlas"][i])))
    write_keyword_tsv(rows, recon / "keyword-probe.tsv")
    write_examples_tsv(per_repo, terms, recon / "keyword-probe-examples.tsv")
    write_section_tsv(per_repo, recon / "seccion16-17-probe.tsv")

    zero_both = [t for t, _p, w, a in rows if w == 0 and a == 0]
    zero_winutil = [t for t, _p, w, a in rows if w == 0 and a > 0]
    zero_atlas = [t for t, _p, w, a in rows if a == 0 and w > 0]
    return {
        "terms": len(rows), "rows": rows,
        "zero_both": zero_both, "zero_winutil": zero_winutil, "zero_atlas": zero_atlas,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    ap.add_argument("--recon", type=Path, default=RECON)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    result = run(args.dest, args.recon)
    for name in ("keyword-probe.tsv", "keyword-probe-examples.tsv", "seccion16-17-probe.tsv"):
        print(f"escrito: {args.recon / name}")

    if args.json:
        print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, ensure_ascii=False))
    else:
        print(f"\ntérminos: {result['terms']}")
        print(f"0 en ambos       : {result['zero_both'] or 'ninguno'}")
        print(f"0 SOLO en winutil: {result['zero_winutil'] or 'ninguno'}")
        print(f"0 SOLO en atlas  : {result['zero_atlas'] or 'ninguno'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
