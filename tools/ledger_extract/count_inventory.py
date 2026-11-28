#!/usr/bin/env python3
r"""Cuenta el inventario del usuario por secciones y clasifica por upstream.

Genera docs/reports/inventario-usuario-conteo.tsv con EXACTAMENTE estas columnas:
    seccion, titulo, lineas_no_vacias, lineas_winutil, lineas_atlas, lineas_evo,
    lineas_general

Encabezado de seccion
---------------------
Por defecto `--heading-style bullet` porque el inventario real del responsable
usa `- TÍTULO EN MAYÚSCULAS` (17 secciones, ver docs/reports/paso1.md).

  bullet  : ^-\s+[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s,]+$      (formato del inventario real)
  numeric : ^[0-9]{1,2}\.\s+[A-ZÁÉÍÓÚÑ]            (regex pedido; da 0 con el
                                                    texto actual — se conserva
                                                    para inventarios numerados)

Clasificación (reiniciada a `general` en cada encabezado de sección)
--------------------------------------------------------------------
  línea exactamente "WinUtil"                                   -> winutil
  línea exactamente "AtlasOS"                                   -> atlas
  línea que empieza por "EVO CLEAN" o "Capacidad EVO a
      desarrollar:"                                             -> evo
  cualquier otra                                                -> general

Regla (d) — líneas de nota
--------------------------
Si una línea empieza (tras normalizar) por uno de los prefijos de NOTE_PREFIXES
("Importante:", "Observación:", "Estas últimas capacidades",
"WinUtil contiene además", "Atlas dispone de", "Fuentes de arquitectura",
"GitHub+1", "También hay funcionalidades") se cuenta como `general` y **no
cambia el modo**: la línea siguiente sigue en el modo anterior.

Regla (e) — sección 17
----------------------
En la última sección (CAPACIDADES ADICIONALES...) no hay cambios de modo:
TODAS sus líneas no vacías son `general`. Sus "WinUtil"/"AtlasOS" son cabeceras
de columna de una tabla aplanada, no sub-cabeceras.

Normalización
-------------
`html.unescape` y el quitar de la viñeta de título se aplican SOLO para
clasificar/contar y para emitir títulos. El fichero crudo del inventario nunca
se modifica (ERRATA-EVO-005).

Se ignoran la línea 1 (cabecera del fichero) y todo lo anterior al primer
encabezado.

Invariante comprobada en cada fila:
    lineas_winutil + lineas_atlas + lineas_evo + lineas_general == lineas_no_vacias

Uso:
    python3 tools/ledger_extract/count_inventory.py --strict
    python3 tools/ledger_extract/count_inventory.py --heading-style numeric --print
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MD = ROOT / "docs" / "requirements" / "INVENTARIO_USUARIO.md"
DEFAULT_TSV = ROOT / "docs" / "reports" / "inventario-usuario-conteo.tsv"

HEADING_STYLES = {
    # formato real del inventario: "- LIMPIEZA Y ELIMINACIÓN DE COMPONENTES"
    "bullet": re.compile(r"^-\s+[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s,]+$"),
    # regex de la especificación (inventarios numerados "1. Alcance")
    "numeric": re.compile(r"^[0-9]{1,2}\.\s+[A-ZÁÉÍÓÚÑ]"),
}

# Regla (d): prefijos de nota. Se comparan tras html.unescape + strip.
NOTE_PREFIXES = (
    "Importante:",
    "Observación:",
    "Estas últimas capacidades",
    "WinUtil contiene además",
    "Atlas dispone de",
    "Fuentes de arquitectura",
    "GitHub+1",
    "También hay funcionalidades",
)

# Regla (e): título (ya normalizado) de la sección sin cambios de modo.
NO_MODE_SECTION_TITLE = "CAPACIDADES ADICIONALES QUE NO DEBEMOS PERDER"

COLUMNS = (
    "seccion",
    "titulo",
    "lineas_no_vacias",
    "lineas_winutil",
    "lineas_atlas",
    "lineas_evo",
    "lineas_general",
)


def normalize(line: str) -> str:
    """Texto listo para clasificar: html.unescape + strip. NO toca el fichero."""
    return html.unescape(line).strip()


def heading_title(line: str, style: str) -> str:
    t = normalize(line)
    if style == "bullet":
        t = t[1:].strip()  # quita el "- " de la viñeta
    else:
        t = re.sub(r"^[0-9]{1,2}\.\s+", "", t)
    return t


def is_note(line: str) -> bool:
    """Regla (d): ¿es una línea de nota que no debe cambiar el modo?"""
    s = normalize(line)
    return s.startswith(NOTE_PREFIXES)


def bucket_of(line: str) -> str | None:
    """Devuelve el cubo si la línea CAMBIA la clasificación, si no None."""
    s = normalize(line)
    if s == "WinUtil":
        return "winutil"
    if s == "AtlasOS":
        return "atlas"
    if s.startswith("EVO CLEAN") or s.startswith("Capacidad EVO a desarrollar:"):
        return "evo"
    return None


def parse(md_path: Path, style: str = "bullet") -> tuple[list[dict], int]:
    pattern = HEADING_STYLES[style]
    lines = md_path.read_text(encoding="utf-8").splitlines()

    # Prefijo obligatorio: línea 1 cabecera, línea 2 en blanco -> cuerpo desde la 3.
    body_start = 0
    if lines and lines[0].startswith("# INVENTARIO_USUARIO"):
        body_start = 2 if (len(lines) > 1 and lines[1].strip() == "") else 1

    sections: list[dict] = []
    current: dict | None = None
    bucket = "general"

    for idx, raw in enumerate(lines[body_start:], start=body_start + 1):
        # OJO: se aplica el patrón a la línea SIN strip(), para que una viñeta
        # sangrada ("  - SANGRADO") no se confunda con un encabezado de sección.
        if pattern.match(raw):
            current = {
                "numero": len(sections) + 1,
                "titulo": heading_title(raw, style),
                "linea": idx,
                "winutil": 0,
                "atlas": 0,
                "evo": 0,
                "general": 0,
                "nonempty": 0,
            }
            sections.append(current)
            bucket = "general"  # reinicio en cada encabezado
            continue
        if current is None:
            continue  # antes del primer encabezado: ignorado

        if not raw.strip():
            continue  # las líneas vacías no cuentan ni cambian nada

        current["nonempty"] += 1

        # Regla (e): la sección de tabla no tiene cambios de modo.
        if current["titulo"] == NO_MODE_SECTION_TITLE:
            current["general"] += 1
            continue

        # Regla (d): una nota va a general y NO cambia el modo vigente.
        if is_note(raw):
            current["general"] += 1
            continue

        new_bucket = bucket_of(raw)
        if new_bucket:
            bucket = new_bucket

        current[bucket] += 1

    return sections, body_start


def invariant_ok(s: dict) -> bool:
    return (s["winutil"] + s["atlas"] + s["evo"] + s["general"]) == s["nonempty"]


def write_tsv(sections: list[dict], tsv_path: Path) -> None:
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["\t".join(COLUMNS)]
    for s in sections:
        rows.append(
            "\t".join(
                str(v)
                for v in (
                    f"{s['numero']:02d}",
                    s["titulo"],
                    s["nonempty"],
                    s["winutil"],
                    s["atlas"],
                    s["evo"],
                    s["general"],
                )
            )
        )
    tsv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--md", type=Path, default=DEFAULT_MD)
    ap.add_argument("--tsv", type=Path, default=DEFAULT_TSV)
    ap.add_argument("--heading-style", choices=sorted(HEADING_STYLES), default="bullet")
    ap.add_argument("--print", dest="do_print", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)

    if not args.md.is_file():
        print(f"ERROR: no existe {args.md}", file=sys.stderr)
        return 2

    sections, body_start = parse(args.md, args.heading_style)
    print(f"fichero   : {args.md}")
    print(f"estilo    : {args.heading_style}  ({HEADING_STYLES[args.heading_style].pattern})")
    print(f"cuerpo    : desde la línea {body_start + 1}")
    print(f"secciones : {len(sections)}")

    nums = [s["numero"] for s in sections]
    expected = list(range(1, 18))
    missing = [n for n in expected if n not in nums]
    extra = [s["titulo"] for s in sections if s["numero"] not in expected]
    print(f"faltantes : {missing if missing else 'ninguna'}")
    print(f"sobrantes : {extra if extra else 'ninguna'}")

    print("\n#   título")
    for s in sections:
        print(f"{s['numero']:>2}  {s['titulo']}")

    bad = [s["numero"] for s in sections if not invariant_ok(s)]
    print(f"\ninvariante: {'OK en las ' + str(len(sections)) + ' filas' if not bad else 'FALLA en ' + str(bad)}")

    if not args.do_print:
        write_tsv(sections, args.tsv)
        print(f"TSV       : {args.tsv}")
        print(
            "totales   : "
            f"no_vacias={sum(s['nonempty'] for s in sections)} "
            f"winutil={sum(s['winutil'] for s in sections)} "
            f"atlas={sum(s['atlas'] for s in sections)} "
            f"evo={sum(s['evo'] for s in sections)} "
            f"general={sum(s['general'] for s in sections)}"
        )

    if bad:
        return 1
    if args.strict:
        if nums != expected:
            print("\nSTRICT: las secciones NO son exactamente 1..17 en orden", file=sys.stderr)
            return 1
        print("\nSTRICT: secciones 1..17 en orden")
    return 0


if __name__ == "__main__":
    sys.exit(main())
