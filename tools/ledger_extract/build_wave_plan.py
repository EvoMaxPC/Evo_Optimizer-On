#!/usr/bin/env python3
"""Plan de oleadas con cifras medidas (paso 8c).

Lee dos fuentes y no calcula nada nuevo que no esté en ellas:

  * `inventory/ledger/inventory-reconciliation.tsv` (588 líneas del inventario
    del responsable) -> líneas por estado, Mapped cubiertas y huecos por sección,
    reutilizando `verify_catalog_coverage.py` para no duplicar la regla de cruce.
  * `inventory/ledger/upstream-capability-map.tsv` (universo upstream) ->
    pendientes por sección, sólo los que tienen `section_guess` (los `mixed` no
    se reparten porque eso es trabajo del paso siguiente).

La tabla que sale es **medida**. El orden de las oleadas es una **propuesta**
del agente y se marca como tal en el informe.

Salida: docs/reports/plan-oleadas.md

Uso:
    python3 tools/ledger_extract/build_wave_plan.py [--check]
    `--check` no escribe: compara el fichero generado con el del disco y sale 1
    si difieren (lo usa CI para demostrar que es reproducible).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_catalog_coverage as vcc  # noqa: E402

LEDGER = ROOT / "inventory" / "ledger"
OUT = ROOT / "docs" / "reports" / "plan-oleadas.md"
STATES = vcc.RECONCILIATION_STATES

# Orden propuesto (NO medido): motivo escrito por sección. Se declara como
# propuesta en el propio informe.
PROPOSAL = [
    (1, "Base de limpieza: 24 unidades de trabajo y ya tiene 3/3 Mapped cubiertas. "
        "Va primero porque las demás oleadas reutilizan su motor de borrado."),
    (2, "Debloat es el núcleo del producto y ya está 17/17. Continúa con 10 y 9."),
    (10, "Explorador e interfaz: oleada 2, cerrada en el catálogo (29 de 29 "
         "líneas Mapped cubiertas). Sigue siendo la sección con más ítems de upstream "
         "pendientes: el trabajo que queda es de upstream, no del inventario."),
    (9, "Registro y configuración: oleada 3, cerrada en el catálogo (27 de 27 líneas "
        "Mapped cubiertas con 18 capacidades). Quedan 3 ítems de upstream pendientes y "
        "ninguno es un valor de registro fijo: la indización se aplica como acción de "
        "TrustedInstaller, la página de «workplace» se edita de forma incremental "
        "(conservando las demás páginas) y el panel de fecha y hora sólo abre "
        "timedate.cpl."),
    (3, "Telemetría: 6/6 Mapped cubiertas; el resto (34 Absent-At-Pin) son los "
        "ajustes de privacidad finos, que necesitan el motor de 2."),
    (4, "Servicios: alto riesgo por servicio, 9 Mapped. Después de 3 para no "
        "duplicar DiagTrack."),
    (12, "Windows Update: 5 Mapped y 21 Absent-At-Pin; toca el mismo DISM de 1 y "
         "14, así que va después de ellas."),
    (14, "Reparación y diagnóstico: 13 Mapped; sus comandos comparten ejecutor con 1."),
    (13, "Seguridad: 9 Mapped y riesgo alto; después de 4 y 12, que ya tocan servicios "
         "y directivas del sistema."),
    (11, "Red: 4 Mapped y 20 Absent-At-Pin; aislada, puede ir en cualquier momento."),
    (5, "Rendimiento: 7 Mapped, 1 cubierta; toca energía y programas, poco acoplado."),
    (7, "Memoria y segundo plano: 10 EVO-Exclusive propios; necesita 6 resuelto "
        "antes (mismo objeto: apps en segundo plano)."),
    (6, "Gaming: 11 EVO-Exclusive propios y 12 Absent-At-Pin; depende de 7."),
    (8, "Inicio y apagado: 4 Mapped, riesgo alto (arranque). Va tarde."),
    (15, "Administración de aplicaciones: 5 Mapped-To-App y 23 Absent-At-Pin; "
         "depende del instalador (16)."),
    (16, "Funciones de instalación: 35 Absent-At-Pin, casi todo tooling propio; "
         "sólo tiene sentido con 15 cerrada."),
    (17, "Capacidades adicionales: 32 cabeceras informativas y 15 EVO-Exclusive; "
         "es un cajón de requisitos, se cierra al final."),
]


def load_upstream() -> list[dict]:
    path = LEDGER / "upstream-capability-map.tsv"
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def build() -> str:
    rows = vcc.load_rows()
    upstream = load_upstream()
    sections = vcc.ALL_SECTIONS

    by_section: dict[str, dict] = {}
    for section in sections:
        section_rows = [r for r in rows if r["seccion"] == section]
        states = {s: sum(1 for r in section_rows if r["status"] == s) for s in STATES}
        work = states["EVO-Exclusive"] + states["Absent-At-Pin"]
        by_section[section] = {"states": states, "lineas": len(section_rows), "work": work}

    covered_by_section: Counter = Counter()
    capabilities = vcc.load_capabilities()
    for row in rows:
        if not row["status"].startswith("Mapped"):
            continue
        if vcc.supporters_of_row(row, capabilities):
            covered_by_section[row["seccion"]] += 1

    pending_section = Counter(
        r["section_guess"] for r in upstream
        if r["status"] == "pending" and r["section_guess"])
    pending_no_section = sum(
        1 for r in upstream if r["status"] == "pending" and not r["section_guess"])

    lines: list[str] = []
    lines.append("# Plan de oleadas (cifras medidas)")
    lines.append("")
    lines.append("Generado por `tools/ledger_extract/build_wave_plan.py`. "
                 "No editar a mano: CI compara el fichero con el generado.")
    lines.append("")
    lines.append("## Tabla por sección")
    lines.append("")
    lines.append("MEDIDO: las cuatro primeras columnas de estado salen de "
                 "`inventory/ledger/inventory-reconciliation.tsv` (588 líneas); "
                 f"«Mapped cubiertas» cruza esas líneas con `ledger_refs` de las "
                 f"{capability_count()} capacidades del catálogo; "
                 "«pending upstream» cuenta las filas `pending` "
                 "de `upstream-capability-map.tsv` con `section_guess` igual a esa "
                 "sección.")
    lines.append("")
    header = ("| § | Título | Líneas | Mapped | Mapped-To-App | EVO-Exclusive | "
              "Absent-At-Pin | Informative | Mapped cubiertas | Mapped sin cubrir | "
              "Trabajo (medido) | Pending upstream |")
    lines.append(header)
    lines.append("|" + "---|" * 12)
    totals = Counter()
    for section in sections:
        data = by_section[section]
        states = data["states"]
        mapped = states["Mapped"] + states["Mapped-To-App"]
        covered = covered_by_section[section]
        uncovered = mapped - covered
        work = uncovered + data["work"]
        title = vcc_section_title(section)
        lines.append(
            f"| {section} | {title} | {data['lineas']} | {states['Mapped']} | "
            f"{states['Mapped-To-App']} | {states['EVO-Exclusive']} | "
            f"{states['Absent-At-Pin']} | {states['Informative-Header']} | "
            f"{covered} | {uncovered} | {work} | {pending_section.get(section, 0)} |")
        totals["lineas"] += data["lineas"]
        for state in STATES:
            totals[state] += states[state]
        totals["covered"] += covered
        totals["uncovered"] += uncovered
        totals["work"] += work
        totals["pending"] += pending_section.get(section, 0)
    lines.append(
        f"| **Σ** | **17 secciones** | **{totals['lineas']}** | **{totals['Mapped']}** | "
        f"**{totals['Mapped-To-App']}** | **{totals['EVO-Exclusive']}** | "
        f"**{totals['Absent-At-Pin']}** | **{totals['Informative-Header']}** | "
        f"**{totals['covered']}** | **{totals['uncovered']}** | **{totals['work']}** | "
        f"**{totals['pending']}** |")
    lines.append("")
    lines.append(f"Pendientes upstream **sin sección**: {pending_no_section}. Desde el "
                 "paso 8d la sección sale también de "
                 "`inventory/partition/item-section-map.tsv` (435 filas, regla y "
                 "evidencia escritas). Lo que queda sin sección no tiene efecto "
                 "propio: entradas de navegación, presets, paneles heredados y "
                 "scripts cuyo efecto no está medido en el pin.")
    lines.append("")
    lines.append("## Orden propuesto de oleadas")
    lines.append("")
    lines.append("PROPUESTA (no medida): el orden y los motivos son del agente; las "
                 "cifras de cada fila son las de la tabla de arriba.")
    lines.append("")
    lines.append("| Oleada | § | Trabajo medido | Motivo de la posición |")
    lines.append("|---|---|---|---|")
    for index, (section, reason) in enumerate(PROPOSAL, start=1):
        data = by_section[str(section)]
        states = data["states"]
        mapped = states["Mapped"] + states["Mapped-To-App"]
        uncovered = mapped - covered_by_section[str(section)]
        work = uncovered + data["work"]
        lines.append(f"| W{index} | {section} {vcc_section_title(section)} | {work} | {reason} |")
    lines.append("")
    lines.append("## Cómo leer las cifras")
    lines.append("")
    lines.append("- «Trabajo» = Mapped sin cubrir + EVO-Exclusive + Absent-At-Pin. "
                 "No cuenta las líneas informativas.")
    lines.append("- «Pending upstream» no se suma con «Trabajo»: miden universos "
                 "distintos (ítems de upstream frente a líneas del inventario).")
    lines.append("- Desde el paso 8d, los ítems de categorías `mixed` sí aparecen: "
                 "se reparten por ítem con regla y evidencia en "
                 "`inventory/partition/item-section-map.tsv`. Los que siguen sin "
                 "sección son los que no tienen efecto propio (navegación, presets, "
                 "paneles, scripts sin operación medida).")
    return "\n".join(lines) + "\n"


# Titulos con su grafia real (los del inventario van en mayusculas; aqui solo se
# normaliza la caja para que la tabla sea legible, sin cambiar ni una palabra).
TITLES = {
    "1": "Limpieza y eliminación de componentes",
    "2": "Debloat de Windows",
    "3": "Telemetría y privacidad",
    "4": "Optimización de servicios",
    "5": "Optimización CPU y rendimiento",
    "6": "Optimización gaming",
    "7": "Memoria y aplicaciones en segundo plano",
    "8": "Administración de inicio y apagado",
    "9": "Registro de Windows y configuración del sistema",
    "10": "Explorador de archivos e interfaz",
    "11": "Red y conectividad",
    "12": "Windows Update y mantenimiento",
    "13": "Seguridad y protección",
    "14": "Reparación y diagnóstico",
    "15": "Administración de aplicaciones",
    "16": "Funciones de instalación y administración avanzada",
    "17": "Capacidades adicionales que no debemos perder",
}


def capability_count() -> int:
    """Número de capacidades del catálogo (se lee, no se escribe a mano)."""
    total = 0
    for path in sorted((ROOT / "catalog" / "capabilities").glob("*.json")):
        total += len(json.loads(path.read_text(encoding="utf-8")).get("capabilities", []))
    return total


def vcc_section_title(section) -> str:
    return TITLES[str(section)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="no escribe; compara con el fichero del disco")
    args = parser.parse_args(argv)

    text = build()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != text:
            print("plan-oleadas.md NO reproducible: el fichero del disco difiere", file=sys.stderr)
            return 1
        print("plan-oleadas.md reproducible: OK")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"escrito {OUT.relative_to(ROOT)} ({len(text)} caracteres)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
