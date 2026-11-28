#!/usr/bin/env python3
"""Valida la partición de ficheros upstream (inventory/partition/*.yml).

Comprueba, por repo:
  1. **0 ficheros sin clasificar**: todo path del TSV casa al menos una regla.
  2. **0 reglas muertas**: toda regla casa al menos un fichero.
  3. **exclude prohibido**: ninguna regla `exclude` toca una ruta de
     comportamiento (extensiones y directorios protegidos de abajo).
  4. Gana la primera regla que casa (glob propio: `*` no cruza '/', `**` sí;
     sin distinguir mayúsculas).

Escribe inventory/partition/results/<repo>.tsv con
    path    treatment    rule_index    rule_glob

Salida: resumen por tratamiento, lista completa de excluidos y exit != 0 si
alguna comprobación falla.

Uso:
    python3 tools/ledger_extract/partition_check.py
    python3 tools/ledger_extract/partition_check.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
INV = ROOT / "inventory"
PART = INV / "partition"
RESULTS = PART / "results"

TREATMENTS = ("extract", "reference", "exclude")

# --- rutas de comportamiento: NUNCA pueden ser exclude ----------------------
BEHAVIOUR_EXTS = {".ps1", ".psm1", ".psd1", ".cmd", ".bat", ".reg", ".json",
                  ".rs", ".toml", ".cab"}
BEHAVIOUR_DIRS = ("config/", "functions/", "scripts/", "package/", "app/src/")


class PartitionError(RuntimeError):
    pass


def read_tsv(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, l.split("\t"))) for l in lines[1:] if l.strip()]


def load_rules(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise PartitionError(f"{path}: schema != 1")
    rules = data.get("rules") or []
    if not rules:
        raise PartitionError(f"{path}: sin reglas")
    for i, r in enumerate(rules):
        for key in ("glob", "treatment", "reason"):
            if not r.get(key):
                raise PartitionError(f"{path}: regla {i} sin '{key}'")
        if r["treatment"] not in TREATMENTS:
            raise PartitionError(f"{path}: regla {i} treatment inválido: {r['treatment']}")
    return data


def is_behaviour_path(path: str) -> bool:
    low = path.lower()
    if Path(low).suffix in BEHAVIOUR_EXTS:
        return True
    return any(low.startswith(d) or f"/{d}" in low for d in BEHAVIOUR_DIRS)


_GLOB_CACHE: dict[str, re.Pattern] = {}


def compile_glob(glob: str) -> re.Pattern:
    """Glob con `*` (no cruza '/'), `**` (cruza '/') y `?` (un carácter).

    Necesario porque `fnmatch` traduce `*` a `.*` (cruza '/') y `**/` a `.*/`,
    lo que rompía reglas como `package/**/*.cmd` y `tools/**/*.yml`.
    """
    key = glob.lower()
    if key in _GLOB_CACHE:
        return _GLOB_CACHE[key]
    g = key
    out, i = [], 0
    while i < len(g):
        if g.startswith("**/", i):
            out.append("(?:.*/)?")   # cero o más segmentos
            i += 3
        elif g.startswith("**", i):
            out.append(".*")
            i += 2
        elif g[i] == "*":
            out.append("[^/]*")
            i += 1
        elif g[i] == "?":
            out.append(".")
            i += 1
        else:
            out.append(re.escape(g[i]))
            i += 1
    # IGNORECASE: el glob se guarda en minúsculas, pero así también casa
    # si alguien llama a compile_glob() con la ruta original.
    pat = re.compile("^" + "".join(out) + "$", re.IGNORECASE)
    _GLOB_CACHE[key] = pat
    return pat


def first_match(rules: list[dict], path: str) -> tuple[int, dict] | None:
    low = path.lower()
    for i, rule in enumerate(rules):
        if compile_glob(rule["glob"]).match(low):
            return i, rule
    return None


def check_repo(name: str, part_path: Path, tsv_path: Path, out_dir: Path) -> dict:
    data = load_rules(part_path)
    rules = data["rules"]
    rows = read_tsv(tsv_path)

    assigned: list[dict] = []
    unclassified: list[str] = []
    used: set[int] = set()
    for row in rows:
        path = row["path"]
        hit = first_match(rules, path)
        if hit is None:
            unclassified.append(path)
            continue
        idx, rule = hit
        used.add(idx)
        assigned.append({
            "path": path,
            "treatment": rule["treatment"],
            "rule_index": idx + 1,
            "rule_glob": rule["glob"],
        })

    dead = [
        {"index": i + 1, "glob": r["glob"], "treatment": r["treatment"]}
        for i, r in enumerate(rules) if i not in used
    ]

    violations = [
        {"index": i + 1, "glob": r["glob"], "path": a["path"]}
        for i, r in enumerate(rules) if r["treatment"] == "exclude"
        for a in assigned
        if a["rule_index"] == i + 1 and is_behaviour_path(a["path"])
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name}.tsv"
    lines = ["path\ttreatment\trule_index\trule_glob"]
    lines += [f"{a['path']}\t{a['treatment']}\t{a['rule_index']}\t{a['rule_glob']}" for a in assigned]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    counts = Counter(a["treatment"] for a in assigned)
    excluded = [a["path"] for a in assigned if a["treatment"] == "exclude"]
    return {
        "repo": name,
        "files": len(rows),
        "assigned": len(assigned),
        "unclassified": unclassified,
        "dead_rules": dead,
        "exclude_violations": violations,
        "counts": {t: counts.get(t, 0) for t in TREATMENTS},
        "excluded": excluded,
        "results_tsv": str(out),
        "ok": not unclassified and not dead and not violations,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inv", type=Path, default=INV)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    reports = []
    for name in ("winutil", "atlas"):
        part = PART / f"{name}.yml"
        tsv = args.inv / "upstream" / f"{name}.files.tsv"
        if not part.is_file():
            print(f"ERROR: falta {part}", file=sys.stderr)
            return 2
        if not tsv.is_file():
            print(f"ERROR: falta {tsv}; ejecuta list_files.py", file=sys.stderr)
            return 2
        reports.append(check_repo(name, part, tsv, RESULTS))

    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
    else:
        for r in reports:
            print(f"\n=== {r['repo']} ===")
            print(f"ficheros      : {r['files']}  (asignados {r['assigned']})")
            print(f"sin clasificar: {len(r['unclassified'])}")
            for p in r["unclassified"][:10]:
                print(f"   - {p}")
            print(f"reglas muertas: {len(r['dead_rules'])}")
            for d in r["dead_rules"]:
                print(f"   - #{d['index']} {d['glob']} ({d['treatment']})")
            print(f"exclude sobre comportamiento: {len(r['exclude_violations'])}")
            for v in r["exclude_violations"]:
                print(f"   - regla #{v['index']} {v['glob']} toca {v['path']}")
            print("tratamientos : " + "  ".join(f"{k}={v}" for k, v in r["counts"].items()))
            print(f"resultados   : {r['results_tsv']}")
            print(f"EXCLUIDOS ({len(r['excluded'])}):")
            for p in sorted(r["excluded"]):
                print(f"   x {p}")
            print(f"VEREDICTO    : {'OK' if r['ok'] else 'FALLA'}")

    return 0 if all(r["ok"] for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
