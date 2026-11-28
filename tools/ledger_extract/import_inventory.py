#!/usr/bin/env python3
"""Importa el bloque ===INICIO===/===FIN=== del responsable al inventario.

Garantiza el contrato del fichero:
    línea 1: "# INVENTARIO_USUARIO (fuente: mensaje original del responsable, sin editar)"
    línea 2: en blanco
    línea 3+: el texto literal del bloque, SIN las líneas de marcador.

No reformatea, no completa, no traduce: solo recorta los marcadores y comprueba
que el resultado es plausible (>= 300 líneas y sin el marcador `<<<PEGA`).

Uso:
    pbpaste | python3 tools/ledger_extract/import_inventory.py          # desde stdin
    python3 tools/ledger_extract/import_inventory.py --in bloque.txt    # desde fichero
    python3 tools/ledger_extract/import_inventory.py --in bloque.txt --force

Salidas: exit 0 si escribió, 1 si se negó (no escribe nada).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "docs" / "requirements" / "INVENTARIO_USUARIO.md"
HEADER = "# INVENTARIO_USUARIO (fuente: mensaje original del responsable, sin editar)"
START = "===INICIO==="
END = "===FIN==="
MIN_LINES = 300


def extract(text: str) -> tuple[str, list[str]]:
    """Devuelve (cuerpo, problemas). cuerpo='' si no se puede extraer."""
    problems: list[str] = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    starts = [i for i, l in enumerate(lines) if l.strip() == START]
    ends = [i for i, l in enumerate(lines) if l.strip() == END]
    if not starts:
        problems.append(f"no encuentro la línea {START}")
    if not ends:
        problems.append(f"no encuentro la línea {END}")
    if problems:
        return "", problems
    if len(starts) > 1 or len(ends) > 1:
        problems.append(f"marcadores repetidos (INICIO={len(starts)}, FIN={len(ends)})")
        return "", problems

    s, e = starts[0], ends[0]
    if e <= s:
        problems.append(f"{END} aparece antes que {START}")
        return "", problems

    body = "\n".join(lines[s + 1 : e])
    if not body.strip():
        problems.append("el bloque está vacío")
    if "<<<PEGA" in body:
        problems.append("el bloque contiene el marcador <<<PEGA (texto no pegado)")
    n = len(body.splitlines())
    if n < MIN_LINES:
        problems.append(f"el bloque tiene {n} líneas no vacías < {MIN_LINES} exigidas")
    return body, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", type=Path, help="fichero con el bloque (defecto: stdin)")
    ap.add_argument("--out", type=Path, default=TARGET)
    ap.add_argument("--force", action="store_true", help="escribe aunque falten comprobaciones")
    ap.add_argument("--dry-run", action="store_true", help="no escribe, solo valida")
    args = ap.parse_args(argv)

    if args.src:
        text = args.src.read_text(encoding="utf-8")
    elif sys.stdin.isatty():
        print("ERROR: no hay stdin ni --in; pega el bloque o pasa un fichero.", file=sys.stderr)
        return 2
    else:
        text = sys.stdin.read()

    body, problems = extract(text)
    if problems:
        print("RECHAZADO — no se escribe nada:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        if not args.force:
            return 1

    content = f"{HEADER}\n\n{body}\n"
    if args.dry_run:
        print("DRY-RUN válido:", file=sys.stderr)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(content, encoding="utf-8")
        print(f"escrito: {args.out}", file=sys.stderr)

    raw = content.encode("utf-8")
    print(f"líneas     : {content.count(chr(10))}")
    print(f"caracteres : {len(content)} (bytes: {len(raw)})")
    print(f"sha256     : {hashlib.sha256(raw).hexdigest()}")
    print(f"primera    : {content.splitlines()[0]}")
    print(f"última     : {content.rstrip(chr(10)).splitlines()[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
