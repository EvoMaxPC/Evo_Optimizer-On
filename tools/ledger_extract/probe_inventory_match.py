#!/usr/bin/env python3
"""Sonda de coincidencia entre el inventario del usuario y los extractores.

**SOLO MIDE.** No decide mapeos, no marca nada como `Mapped` y no modifica el
inventario. Sirve para saber cuánto ruido hay entre cómo el usuario nombra las
cosas y cómo las nombran los ficheros de upstream.

Toma las líneas de los cubos `winutil` y `atlas` del inventario con la misma
clasificación que `count_inventory.py` (sin cabeceras de modo ni notas), las
normaliza y las cruza con las etiquetas del ledger:

    winutil -> label de inventory/ledger/winutil-items.tsv
    atlas   -> label de inventory/ledger/atlas-toggles.tsv

Normalización: minúsculas, `html.unescape`, se corta en " — ", se quitan los
caracteres no alfanuméricos.

Tipos de coincidencia:
    exacta      la cadena normalizada es igual
    contencion  una contiene a la otra (en cualquier sentido)
    ninguna     sin relación

Uso:
    python3 tools/ledger_extract/probe_inventory_match.py [--out TSV]
"""
from __future__ import annotations

import argparse
import csv
import html
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

import count_inventory as ci  # noqa: E402

INVENTORY = ROOT / "docs" / "requirements" / "INVENTARIO_USUARIO.md"
WINUTIL_ITEMS = ROOT / "inventory" / "ledger" / "winutil-items.tsv"
ATLAS_TOGGLES = ROOT / "inventory" / "ledger" / "atlas-toggles.tsv"
OUT = ROOT / "docs" / "reports" / "probe-coincidencia-inventario.tsv"

COLUMNS = ("seccion", "fuente", "linea", "tipo_coincidencia", "item_id_candidato")

DASH_CUT = " — "


def norm(text: str) -> str:
    s = html.unescape(text)
    # Cortar ANTES de tocar los guiones: el separador es el guión largo " — ".
    for sep in (DASH_CUT, " - ", "\u2014", "\u2013"):
        if sep in s:
            s = s.split(sep)[0]
            break
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def inventory_lines(md: Path, style: str = "bullet") -> list[dict]:
    """Líneas de los cubos winutil y atlas, con su sección.

    Reimplementa el recorrido de `count_inventory.parse` pero guardando la línea
    además de contarla; la clasificación (regla (d), regla (e), cambios de modo)
    es exactamente la misma.
    """
    pattern = ci.HEADING_STYLES[style]
    lines = md.read_text(encoding="utf-8").splitlines()
    body_start = 0
    if lines and lines[0].startswith("# INVENTARIO_USUARIO"):
        body_start = 2 if (len(lines) > 1 and lines[1].strip() == "") else 1

    out: list[dict] = []
    current: dict | None = None
    bucket = "general"
    for idx, raw in enumerate(lines[body_start:], start=body_start + 1):
        if pattern.match(raw):
            current = {"numero": len(out) * 0 + (current["numero"] + 1 if current else 1),
                       "titulo": ci.heading_title(raw, style)}
            bucket = "general"
            continue
        if current is None or not raw.strip():
            continue
        if current["titulo"] == ci.NO_MODE_SECTION_TITLE:
            continue
        if ci.is_note(raw):
            continue
        new_bucket = ci.bucket_of(raw)
        if new_bucket:
            bucket = new_bucket
        # El encabezado de modo ("WinUtil", "AtlasOS") lo cuenta el cubo, pero
        # no es una línea de contenido: sí se lee aquí, como pide el encargo.
        if ci.normalize(raw).strip() in ("WinUtil", "AtlasOS"):
            out.append({
                "seccion": current["numero"],
                "fuente": bucket,
                "linea": ci.normalize(raw).strip(),
            })
            continue
        if bucket in ("winutil", "atlas"):
            out.append({
                "seccion": current["numero"],
                "fuente": bucket,
                # heading_title recorta la viñeta; para LEER la línea hay que
                # quitar el sangrado y los dos espacios finales de Markdown.
                "linea": ci.normalize(raw).rstrip(),
            })
    return out


def load_labels(path: Path, col: str = "label") -> list[tuple[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return [(r["item_id"], r[col]) for r in csv.DictReader(fh, delimiter="\t")
                if r.get(col)]


def match(line: str, labels: list[tuple[str, str]]) -> tuple[str, str]:
    n = norm(line)
    if not n:
        return "ninguna", ""
    for item_id, label in labels:
        if norm(label) == n:
            return "exacta", item_id
    for item_id, label in labels:
        ln = norm(label)
        if ln and (ln in n or n in ln):
            return "contencion", item_id
    return "ninguna", ""


def probe(md: Path, winutil_tsv: Path, atlas_tsv: Path) -> list[dict]:
    win_labels = load_labels(winutil_tsv)
    atl_labels = load_labels(atlas_tsv)
    rows = []
    for item in inventory_lines(md):
        labels = win_labels if item["fuente"] == "winutil" else atl_labels
        kind, cand = match(item["linea"], labels)
        rows.append({"seccion": item["seccion"], "fuente": item["fuente"],
                     "linea": item["linea"], "tipo_coincidencia": kind,
                     "item_id_candidato": cand})
    return rows


def write_tsv(path: Path, rows: list[dict]) -> None:
    lines = ["\t".join(COLUMNS)]
    for r in rows:
        lines.append("\t".join(str(r[c]).replace("\t", " ") for c in COLUMNS))
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inventory", type=Path, default=INVENTORY)
    ap.add_argument("--winutil", type=Path, default=WINUTIL_ITEMS)
    ap.add_argument("--atlas", type=Path, default=ATLAS_TOGGLES)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    for p in (args.inventory, args.winutil, args.atlas):
        if not p.is_file():
            print(f"ERROR: falta {p}", file=sys.stderr)
            return 2

    rows = probe(args.inventory, args.winutil, args.atlas)
    write_tsv(args.out, rows)

    from collections import Counter
    print(f"lineas medidas        : {len(rows)}")
    for fuente in ("winutil", "atlas"):
        sub = [r for r in rows if r["fuente"] == fuente]
        c = Counter(r["tipo_coincidencia"] for r in sub)
        print(f"  {fuente:8s} total={len(sub):3d}  exacta={c['exacta']:3d}  "
              f"contencion={c['contencion']:3d}  ninguna={c['ninguna']:3d}")
    print(f"escrito: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
