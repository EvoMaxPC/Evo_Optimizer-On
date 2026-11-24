#!/usr/bin/env python3
"""Puerta de cobertura upstream -> capacidad (paso 8b). SOLO INFORMATIVA.

Lee `inventory/ledger/upstream-capability-map.tsv` y decide si el catalogo
alcanza el umbral de la fase pedida.

    phase0   linea base: se informa y siempre sale 0 (no bloquea nada)
    beta     exige pending == 0
    release  exige pending == 0

El modo es informativo en el sentido de que hoy NO esta enganchado a ningun
workflow como paso bloqueante: se ejecuta en `ledger-verify` para publicar la
cifra. Cuando el responsable decida que beta/release bloquean, basta con dejar
de usar `--informational`.

Uso:
    python3 tools/ledger_extract/coverage_gate.py --gate phase0
    python3 tools/ledger_extract/coverage_gate.py --gate beta --informational
    python3 tools/ledger_extract/coverage_gate.py --gate release --json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "inventory" / "ledger" / "upstream-capability-map.tsv"
GATES = ("phase0", "beta", "release")


def load() -> list[dict]:
    if not MAP.is_file():
        raise SystemExit(f"FALTA el mapa {MAP}: ejecuta build_upstream_capability_map.py")
    with MAP.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", choices=GATES, required=True)
    parser.add_argument("--informational", action="store_true",
                        help="informa pero no falla aunque el umbral no se cumpla")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    rows = load()
    status = Counter(row["status"] for row in rows)
    total = len(rows)
    covered = status.get("covered", 0)
    pending = status.get("pending", 0)
    percentage = round(100.0 * covered / max(total, 1), 1)

    if args.gate == "phase0":
        ok = True
    else:
        ok = pending == 0

    if args.informational:
        ok = True

    report = {
        "gate": args.gate,
        "filas": total,
        "covered": covered,
        "pending": pending,
        "not_a_capability": status.get("not-a-capability", 0),
        "variant_of": status.get("variant-of", 0),
        "porcentaje": percentage,
        "informational": args.informational,
        "ok": ok,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if ok else 1

    print(f"gate {args.gate}: {covered}/{total} cubiertas ({percentage} %), "
          f"pending={pending}, not-a-capability={report['not_a_capability']}")
    if args.gate != "phase0" and pending:
        print(f"umbral {args.gate}: NO cumplido (pending debe ser 0)")
    print("veredicto:", "OK" if ok else "FALLA",
          "(modo informativo)" if args.informational else "")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
