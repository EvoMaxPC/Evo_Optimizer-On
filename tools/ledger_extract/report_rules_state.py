#!/usr/bin/env python3
"""
Informe de reglas R1/R2/R3 sobre las 88 capacidades del catalogo.

Lee SOLO catalog/capabilities/*.json (de un ref de git dado o del HEAD del
repositorio) y, para cada capacidad, aplica:

  R1: Implemented solo si la capacidad expresa TODO lo que hace el pin para ese
      efecto. Si queda fuera algo (comando sin inversa, script, machine-action),
      pasa a Specified y lo omitido se declara en description/provenance.
      A este nivel el script detecta la violacion cuando una capacidad
      `Implemented` deja texto de omision en su description/provenance
      ("FUERA DE ESTA CAPACIDAD", "no se declara", "no se ejecutan", ...).
  R2: securityImpact == Improves exige justificacion escrita en la description
      ("Por que mejora" / "MEJORA"). Sin ella, Neutral.
  R3: aplica cuando privilege == Admin y las acciones incluyen taskCreate o
      service (tarea programada o servicio persistente con privilegios altos).
      R3 ok exige Risk == Low y Confirmation == SimpleClick.
      R3 NO se amplia a escrituras de registro con Admin.

Imprime una tabla y la guarda en docs/reports/reglas-r1-r3.md.
Con --check compara el TSV generado contra el ya presente en
inventory/ledger/reglas-r1-r3.tsv (o el que se indique) y devuelve 1 si difiere.

Solo stdlib. Determinista: orden por id, LF.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = ROOT / "catalog" / "capabilities"
OUT_TSV = ROOT / "inventory" / "ledger" / "reglas-r1-r3.tsv"
OUT_MD = ROOT / "docs" / "reports" / "reglas-r1-r3.md"

COLUMNS = (
    "id", "seccion", "state", "reversibility", "risk", "securityImpact",
    "privilege", "confirmation", "restore", "supportedBuilds", "actionTypes",
    "R1_ok", "R2_ok", "R3_aplica", "R3_ok",
)

# Marcadores de omision R1 en description/provenance de una capacidad Implemented.
R1_OMISSION_MARKERS = (
    "FUERA DE ESTA CAPACIDAD",
    "no se declara",
    "no se ejecutan",
    "no expresan",
    "queda fuera",
    "sin inversa",
)

# Justificacion R2 en la description.
R2_JUST_MARKERS = ("Por que mejora", "MEJORA")


def load_catalog(ref: str | None = None) -> list[dict]:
    """Lee las capacidades del catalogo (de un ref de git o del HEAD local)."""
    capabilities: list[dict] = []
    if ref is None:
        paths = sorted(CATALOG_DIR.glob("*.json"), key=lambda p: p.name)
        for path in paths:
            document = json.loads(path.read_text(encoding="utf-8"))
            for cap in document.get("capabilities", []):
                cap["_file"] = path.name
                capabilities.append(cap)
    else:
        # El arbol de catalogo en el ref: un JSON por seccion.
        tree = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", ref, "catalog/capabilities"],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        for rel in sorted(tree):
            raw = subprocess.run(
                ["git", "show", f"{ref}:{rel}"], capture_output=True, text=True,
                check=True,
            ).stdout
            document = json.loads(raw)
            for cap in document.get("capabilities", []):
                cap["_file"] = rel
                capabilities.append(cap)
    return capabilities


def action_types(cap: dict) -> str:
    kinds = sorted({a.get("type", "") for a in cap.get("actions", [])})
    return ",".join(kinds)


def builds(cap: dict) -> str:
    b = cap.get("supportedBuilds") or cap.get("builds") or []
    return ",".join(str(x) for x in b)


def r1_ok(cap: dict) -> str:
    """R1: para Implemented, exige que no haya omisiones declaradas."""
    text = (cap.get("description", "") + "\n" + cap.get("provenance", "")).lower()
    state = cap.get("state")
    if state == "Implemented":
        for marker in R1_OMISSION_MARKERS:
            if marker.lower() in text:
                return "no"  # deja algo fuera del pin -> deberia ser Specified
        return "si"
    if state == "Specified":
        return "si"  # Specified asume expresamente lo no expresado
    return "si"  # Stub / otro: no aplica


def r2_ok(cap: dict) -> str:
    """R2: Improves exige justificacion escrita en la description."""
    impact = cap.get("securityImpact", "")
    desc = cap.get("description", "")
    if impact == "Improves":
        return "si" if any(m in desc for m in R2_JUST_MARKERS) else "no"
    return "si"  # Neutral / Reduces no exigen justificacion de mejora


def r3_aplica(cap: dict) -> str:
    """R3 aplica a Admin + tarea programada (taskCreate) o servicio (service)."""
    if cap.get("privilege") == "Admin":
        kinds = {a.get("type", "") for a in cap.get("actions", [])}
        if "taskCreate" in kinds or "service" in kinds:
            return "si"
    return "no"


def r3_ok(cap: dict) -> str:
    if r3_aplica(cap) != "si":
        return "-"
    risk = cap.get("risk", "")
    conf = cap.get("confirmation", "")
    return "si" if (risk == "Low" and conf == "SimpleClick") else "no"


def evaluate(cap: dict) -> dict:
    return {
        "id": cap["id"],
        "seccion": str(cap.get("sectionId", "")),
        "state": cap.get("state", ""),
        "reversibility": cap.get("reversibility", ""),
        "risk": cap.get("risk", ""),
        "securityImpact": cap.get("securityImpact", ""),
        "privilege": cap.get("privilege", ""),
        "confirmation": cap.get("confirmation", ""),
        "restore": cap.get("restore", ""),
        "supportedBuilds": builds(cap),
        "actionTypes": action_types(cap),
        "R1_ok": r1_ok(cap),
        "R2_ok": r2_ok(cap),
        "R3_aplica": r3_aplica(cap),
        "R3_ok": r3_ok(cap),
        "description": cap.get("description", ""),
        "provenance": cap.get("provenance", ""),
    }


def dump_tsv(rows: list[dict]) -> str:
    lines = ["\t".join(COLUMNS)]
    for row in rows:
        lines.append("\t".join(str(row[c]) for c in COLUMNS))
    return "\n".join(lines) + "\n"


def md_table(rows: list[dict]) -> str:
    lines = [
        "## Reglas R1/R2/R3 sobre el catalogo de capacidades",
        "",
        "Generado por `tools/ledger_extract/report_rules_state.py` (solo lee el JSON del catalogo).",
        "",
        "Columnas: `id | seccion | state | reversibility | risk | securityImpact | privilege | confirmation | restore | supportedBuilds | actionTypes | R1_ok | R2_ok | R3_aplica | R3_ok`.",
        "",
        "```",
        "id | seccion | state | reversibility | risk | securityImpact | privilege | confirmation | restore | supportedBuilds | actionTypes | R1_ok | R2_ok | R3_aplica | R3_ok",
    ]
    for row in rows:
        lines.append(
            " | ".join(str(row[c]) for c in COLUMNS)
        )
    lines.append("```")
    lines.append("")
    lines.append("### Totales")
    implemented = sum(1 for r in rows if r["state"] == "Implemented")
    specified = sum(1 for r in rows if r["state"] == "Specified")
    stub = sum(1 for r in rows if r["state"] == "Stub")
    improves = sum(1 for r in rows if r["securityImpact"] == "Improves")
    r3 = sum(1 for r in rows if r["R3_aplica"] == "si")
    r3_ok = sum(1 for r in rows if r["R3_ok"] == "si")
    lines.append(f"- Capacidades totales: {len(rows)}  (Implemented={implemented}, Specified={specified}, Stub={stub})")
    lines.append(f"- securityImpact=Improves: {improves}")
    lines.append(f"- R3 aplica (Admin + tarea/servicio): {r3}, de las cuales R3_ok={r3_ok}")
    lines.append("")
    lines.append("### Capacidades `Specified` con motivo literal")
    for row in rows:
        if row["state"] != "Specified":
            continue
        text = (row["description"] + "\n" + row["provenance"])
        # Motivo: la frase que termina con "State=Specified" o la ultima oracion.
        match = re.search(r".*State=Specified\.", text)
        motivo = match.group(0).strip() if match else text.strip().splitlines()[-1]
        lines.append(f"- `{row['id']}`: {motivo}")
    lines.append("")
    lines.append("### Reglas aplicadas")
    lines.append("- R1: `Implemented` exige que la capacidad exprese TODO el efecto del pin; omisiones pasan a `Specified`.")
    lines.append("- R2: `securityImpact=Improves` exige justificacion escrita en la `description`; sin ella, `Neutral`.")
    lines.append("- R3: aplica a `Admin` con `taskCreate` o `service`; exige `Risk=Low` y `Confirmation=SimpleClick`. No se amplía a escrituras de registro con Admin.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default=None, help="ref de git del catalogo a evaluar (por defecto HEAD)")
    parser.add_argument("--check", action="store_true", help="compara el TSV generado con el existente")
    parser.add_argument("--out-tsv", default=str(OUT_TSV), help="ruta del TSV de salida")
    parser.add_argument("--out-md", default=str(OUT_MD), help="ruta del markdown de salida")
    parser.add_argument("--json", default=None, help="ruta del JSON de resumen de salida")
    args = parser.parse_args(argv)

    capabilities = load_catalog(args.ref)
    rows = [evaluate(c) for c in capabilities]
    rows.sort(key=lambda r: r["id"])
    tsv = dump_tsv(rows)
    md = md_table(rows)

    Path(args.out_tsv).parent.mkdir(parents=True, exist_ok=True)
    if args.check:
        current = Path(args.out_tsv).read_text(encoding="utf-8") if Path(args.out_tsv).is_file() else ""
        if current != tsv:
            print(
                f"el TSV de reglas no coincide con {args.out_tsv}: ejecuta el script sin --check",
                file=sys.stderr,
            )
            return 1
    else:
        Path(args.out_tsv).write_text(tsv, encoding="utf-8")
        Path(args.out_md).write_text(md, encoding="utf-8")

    implemented = sum(1 for r in rows if r["state"] == "Implemented")
    specified = sum(1 for r in rows if r["state"] == "Specified")
    stub = sum(1 for r in rows if r["state"] == "Stub")
    improves = sum(1 for r in rows if r["securityImpact"] == "Improves")
    r3 = sum(1 for r in rows if r["R3_aplica"] == "si")
    r3_ok = sum(1 for r in rows if r["R3_ok"] == "si")
    r1_fail = [r["id"] for r in rows if r["state"] == "Implemented" and r["R1_ok"] == "no"]
    r2_fail = [r["id"] for r in rows if r["securityImpact"] == "Improves" and r["R2_ok"] == "no"]
    r3_bad = [r["id"] for r in rows if r["R3_ok"] == "no"]

    print(f"capacidades evaluadas: {len(rows)}")
    print(f"  Implemented={implemented}  Specified={specified}  Stub={stub}  (suma {implemented+specified+stub})")
    print(f"  securityImpact=Improves: {improves}")
    print(f"  R3 aplica: {r3}, R3_ok: {r3_ok}")
    if r1_fail:
        print(f"  R1 sin cumplir (Implemented con omision): {r1_fail}")
    if r2_fail:
        print(f"  R2 sin cumplir (Improves sin justificacion): {r2_fail}")
    if r3_bad:
        print(f"  R3 sin cumplir: {r3_bad}")
    print(f"TSV: {args.out_tsv}")
    print(f"MD:  {args.out_md}")
    if args.json:
        summary = {
            "capacidades": len(rows),
            "implemented": implemented,
            "specified": specified,
            "stub": stub,
            "improves": improves,
            "r3_aplica": r3,
            "r3_ok": r3_ok,
            "r1_fail": r1_fail,
            "r2_fail": r2_fail,
            "r3_bad": r3_bad,
        }
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
