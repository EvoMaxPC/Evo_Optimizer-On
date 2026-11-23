#!/usr/bin/env python3
"""Cobertura de extract de WinUtil (criterio de ADR-0001).

Cada fichero con tratamiento `extract` debe producir al menos un item del
ledger (config) o de funciones/scripts. Los que no, se listan explícitamente
como "extract sin items" con su motivo: nada se ignora en silencio (REQ-005).

Uso:
    python3 tools/ledger_extract/coverage_check.py [--json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "inventory" / "partition" / "results" / "winutil.tsv"
ITEMS = ROOT / "inventory" / "ledger" / "winutil-items.tsv"
APPS = ROOT / "inventory" / "ledger" / "winutil-apps.tsv"
FUNCS = ROOT / "inventory" / "ledger" / "winutil-functions.tsv"

# Motivos explícitos para los ficheros extract que no producen item de ledger.
REASONS = {
    ".gitignore": "sin items (excluido por partición; no llega aquí)",
    "xaml/inputXML.xaml": "UI declarativa: se consume vía items de tweak/feature; no genera items propios",
    "lint/PSScriptAnalyser.ps1": "configuración de linter: no define funciones; cubre una capacidad de proceso (lint)",
    "windev.ps1": "lanzador de desarrollo: ejecuta Compile.ps1 y abre la app; sin función propia",
    "Compile.ps1": "implementation-detail (ADR-0001): empaquetado; mapeado a la capacidad de build reproducible",
    "sign.bat": "firma de artefactos del pipeline de release: paso de build, sin items propios (implementation-detail)",
    "pester/fixtures/legacy-config.json": "fixture de test Pester (datos de entrada), no comportamiento de producto",
}


def read_tsv(p: Path) -> list[dict]:
    with p.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    for p in (RESULTS, ITEMS, APPS, FUNCS):
        if not p.is_file():
            print(f"ERROR: falta {p}", file=sys.stderr)
            return 2

    extracts = [r["path"] for r in read_tsv(RESULTS) if r["treatment"] == "extract"]

    covered: set[str] = set()
    source_files = {r["source"] for r in read_tsv(ITEMS)} | {r["source"] for r in read_tsv(APPS)}
    for src in source_files:
        covered.add(src)
    # config/*.json cubiertos -> el fichero TSV de partición usa la misma ruta
    for r in read_tsv(FUNCS):
        if int(r["n_functions"]) > 0:
            covered.add(r["path"])

    with_items = [p for p in extracts if p in covered]
    without = [p for p in extracts if p not in covered]
    orphans = []
    for p in without:
        reason = REASONS.get(p)
        if reason is None:
            if p.startswith("pester/") or p.endswith(".Tests.ps1"):
                reason = "test Pester (it/describe sin `function`): cubre comportamiento existente, no define API"
            else:
                reason = "NO VERIFICADO: extract sin items y sin motivo declarado"
        orphans.append({"path": p, "reason": reason})

    result = {
        "extract_files": len(extracts),
        "with_items": len(with_items),
        "without_items": len(orphans),
        "unexplained": [o["path"] for o in orphans if o["reason"].startswith("NO VERIFICADO")],
        "orphans": orphans,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"ficheros extract      : {len(extracts)}")
        print(f"con al menos un item  : {len(with_items)}")
        print(f"extract sin items     : {len(orphans)}")
        print(f"sin motivo declarado  : {len(result['unexplained'])}")
        print("\nextract sin items (path -> motivo):")
        for o in orphans:
            print(f"  - {o['path']}: {o['reason']}")
    return 0 if not result["unexplained"] else 1


if __name__ == "__main__":
    sys.exit(main())
