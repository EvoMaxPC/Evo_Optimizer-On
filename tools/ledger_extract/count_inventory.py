#!/usr/bin/env python3
"""Cuenta el inventario del usuario por secciones y clasifica por upstream.

Genera docs/reports/inventario-usuario-conteo.tsv con las columnas:
    seccion, lineas_no_vacias, lineas_winutil, lineas_atlas, lineas_evo

Reglas (literal de la especificación del responsable):
  * Encabezado de sección: línea que case ^[0-9]{1,2}\.\s+[A-ZÁÉÍÓÚÑ]
  * Cuerpo de la sección: desde el encabezado hasta el siguiente encabezado.
  * Se clasifica cada línea del cuerpo según el sub-encabezado vigente:
      - "WinUtil"                        -> winutil
      - "AtlasOS"                        -> atlas
      - "Capacidad EVO" / "EVO CLEAN" / "EVO" -> evo
      - cualquier otra línea             -> general
  * `lineas_no_vacias` = líneas del cuerpo no vacías (el encabezado no cuenta).
  * Columnas winutil/atlas/evo cuentan SOLO líneas no vacías de ese sub-bloque;
    el resto va a `general` (columna informativa añadida al final).

Uso:
    python3 tools/ledger_extract/count_inventory.py [--md RUTA] [--tsv RUTA]
    python3 tools/ledger_extract/count_inventory.py --print   # solo lista secciones
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MD = ROOT / "docs" / "requirements" / "INVENTARIO_USUARIO.md"
DEFAULT_TSV = ROOT / "docs" / "reports" / "inventario-usuario-conteo.tsv"

# Encabezado de sección: "1. Alcance", "17. Tabla...". Admite 1-2 dígitos.
SECTION_RE = re.compile(r"^(\d{1,2})\.\s+([A-ZÁÉÍÓÚÑ].*)$")

# Prefijos de sub-encabezado que abren un bloque de upstream.
SUBHEADERS = (
    ("WinUtil", "winutil"),
    ("AtlasOS", "atlas"),
    ("Capacidad EVO", "evo"),
    ("EVO CLEAN", "evo"),
    ("EVO", "evo"),
)

# Ruido markdown que puede preceder al sub-encabezado: "- **WinUtil**", "> ### EVO"
_LEAD = re.compile(r"^[\s>*_#`\-–—]*(?:\d+[.)]\s*)?")
_BOLD = re.compile(r"^[*_`]+|[*_`]+$")


def normalize(line: str) -> str:
    """Quita markdown decorativo del inicio para poder detectar el sub-encabezado."""
    s = _LEAD.sub("", line).strip()
    s = _BOLD.sub("", s).strip()
    return s


def classify_subheader(line: str) -> str | None:
    """Devuelve 'winutil' | 'atlas' | 'evo' si la línea ABRE un sub-bloque."""
    s = normalize(line)
    if not s:
        return None
    for prefix, key in SUBHEADERS:
        if s.startswith(prefix):
            return key
    return None


def parse(md_path: Path) -> tuple[list[dict], int]:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    # Prefijo obligatorio: línea 1 título, línea 2 en blanco. Cuerpo desde la 3.
    if lines and lines[0].startswith("# INVENTARIO_USUARIO"):
        body_start = 2 if (len(lines) > 1 and lines[1].strip() == "") else 1
    else:
        body_start = 0

    sections: list[dict] = []
    current = None
    bucket = "general"

    for idx, raw in enumerate(lines[body_start:], start=body_start + 1):
        m = SECTION_RE.match(raw)
        if m:
            number, title = int(m.group(1)), m.group(2).strip()
            current = {
                "seccion": f"{number:02d}",
                "numero": number,
                "titulo": title,
                "linea": idx,
                "winutil": 0,
                "atlas": 0,
                "evo": 0,
                "general": 0,
                "nonempty": 0,
            }
            sections.append(current)
            bucket = "general"
            continue
        if current is None:
            continue

        sub = classify_subheader(raw)
        if sub:
            bucket = sub

        if raw.strip():
            current["nonempty"] += 1
            current[bucket] += 1

    return sections, body_start


def write_tsv(sections: list[dict], tsv_path: Path) -> None:
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["seccion\tlineas_no_vacias\tlineas_winutil\tlineas_atlas\tlineas_evo"]
    for s in sections:
        rows.append(
            f"{s['seccion']}\t{s['nonempty']}\t{s['winutil']}\t{s['atlas']}\t{s['evo']}"
        )
    tsv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--md", type=Path, default=DEFAULT_MD)
    ap.add_argument("--tsv", type=Path, default=DEFAULT_TSV)
    ap.add_argument("--print", dest="do_print", action="store_true", help="solo imprime secciones")
    ap.add_argument("--strict", action="store_true", help="falla si no hay 17 secciones 1..17")
    args = ap.parse_args(argv)

    if not args.md.is_file():
        print(f"ERROR: no existe {args.md}", file=sys.stderr)
        return 2

    sections, body_start = parse(args.md)
    print(f"fichero   : {args.md}")
    print(f"cuerpo    : desde la línea {body_start + 1} (prefijo = {body_start} línea/s)")
    print(f"secciones : {len(sections)}")

    nums = [s["numero"] for s in sections]
    expected = list(range(1, 18))
    missing = [n for n in expected if n not in nums]
    extra = [n for n in nums if n not in expected]
    dupes = sorted({n for n in nums if nums.count(n) > 1})
    if missing:
        print(f"FALTAN    : {missing}")
    if extra:
        print(f"SOBRAN    : {extra} (fuera de 1..17)")
    if dupes:
        print(f"DUPLICADAS: {dupes}")

    print("\n#   título")
    for s in sections:
        print(f"{s['numero']:>2}  {s['titulo']}")

    if not args.do_print:
        write_tsv(sections, args.tsv)
        total = sum(s["nonempty"] for s in sections)
        print(f"\nTSV       : {args.tsv}")
        print(
            f"totales   : no_vacias={total} "
            f"winutil={sum(s['winutil'] for s in sections)} "
            f"atlas={sum(s['atlas'] for s in sections)} "
            f"evo={sum(s['evo'] for s in sections)} "
            f"general={sum(s['general'] for s in sections)}"
        )

    if args.strict:
        ok = nums == expected
        if not ok:
            print("\nSTRICT: la numeración NO es exactamente 1..17", file=sys.stderr)
            return 1
        print("\nSTRICT: numeración 1..17 completa y en orden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
