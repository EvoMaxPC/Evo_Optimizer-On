#!/usr/bin/env python3
"""Cobertura del catálogo de capacidades frente al ledger de conciliación (paso 8).

Cruza los IDs de `catalog/capabilities/*.json` con
`inventory/ledger/inventory-reconciliation.tsv` y responde a una sola pregunta:

    ¿toda línea *Mapped* de las secciones ya construidas (1-3 desde la oleada 1,
    10 desde la oleada 2 del paso 9) tiene al menos una capacidad que la
    respalde?

El cruce se hace por `mapped_ids`: cada capacidad declara en `provenance` los
item_id del ledger de los que sale. Una línea del inventario queda cubierta si
alguna capacidad comparte **al menos un** item_id con su columna `mapped_ids`.

Solo stdlib. Determinista: se ordena todo antes de imprimir.

Uso:
    python3 tools/ledger_extract/verify_catalog_coverage.py
    python3 tools/ledger_extract/verify_catalog_coverage.py --json
    python3 tools/ledger_extract/verify_catalog_coverage.py --strict

Salida (exit code):
    0  toda línea Mapped de 1-3 está cubierta
    1  hay líneas Mapped sin capacidad (o --strict y hay huecos declarados)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = ROOT / "catalog" / "capabilities"
RECONCILIATION = ROOT / "inventory" / "ledger" / "inventory-reconciliation.tsv"

# Item_id del ledger: prefijo:clase:...:sufijo. Se extraen del texto de provenance.
LEDGER_ID = re.compile(r"\b(?:winutil|atlas):[A-Za-z0-9_.:\-/*{}]+")
SECTIONS = ("1", "2", "3")
# Secciones con catalogo construido y con el mismo criterio estricto (0 huecos).
# La 10 entra en el paso 9 (oleada 2). La 4 entra en el paso 7 (oleada 1).
# La 12 entra en la Etapa 8 Parte B (seccion Windows Update y Mantenimiento).
COMPLETED_SECTIONS = ("1", "2", "3", "4", "9", "10", "12")
# Las 17 secciones del inventario, para el plan de oleadas (paso 8c). El
# veredicto y los huecos siguen calculandose SOLO sobre SECTIONS, de modo que
# esta lista amplia el informe pero no cambia el comportamiento en 1-3.
ALL_SECTIONS = tuple(str(n) for n in range(1, 18))
RECONCILIATION_STATES = ("Mapped", "Mapped-To-App", "EVO-Exclusive",
                         "Absent-At-Pin", "Informative-Header")

# Huecos conocidos y aceptados: líneas Mapped del inventario que NO pueden
# apoyarse en ninguna de las 24 capacidades de la oleada 1 porque la línea no
# está entre las que el enunciado del paso 8 pide construir. Se declaran aquí,
# con su motivo, para que el hueco sea explícito y no silencioso. Si aparece un
# hueco nuevo, el script falla: hay que decidir si es capacidad nueva o hueco.
# Huecos aceptados. VACIO desde el paso 8b: las 26 lineas Mapped de las
# secciones 1-3 estan cubiertas por al menos una capacidad. La mecanica se
# mantiene porque una oleada futura puede necesitar declarar un hueco temporal
# con motivo; el script falla si aparece uno no declarado y tambien si una
# declaracion se queda obsoleta.
DECLARED_GAPS: dict[tuple[str, str], str] = {}

# Procedencia forzada: `mapped_ids` de la línea -> `ledger_refs` de la capacidad.
# Existe por un defecto MEDIDO del paso 4e: esas tres líneas del inventario citan
# una operación de OTRO tweak (`LoginBlur` para las notificaciones, `NumLock`
# para los atajos, `HideSettingsHome` para el reinicio del Explorador), así que
# el casamiento por prefijo no encuentra nunca a la capacidad correcta. La
# relación real se escribe aquí, una por una, con su motivo; no se relaja la
# regla para todas las líneas. Lo comprueba tests/test_paso9.py.
DECLARED_SOURCES: dict[tuple[str, str], str] = {
    # (seccion, linea) -> capacidad. Se indexa por línea y no por mapped_id
    # porque un mismo id puede aparecer en dos líneas con significados distintos
    # (WPFToggleLoginBlur:registry:0 está en la 333 y en la 334).
    ("10", "334"): "ui.notifications.center-hide",
    ("10", "347"): "ui.numlock.startup",
    # Etapa 8 Parte B: linea 405 (Registry Backup) se expresa como
    # system.registry-backup.enable (seccion 9); linea 406 (System Restore Point)
    # se expresa como ui.logon.acrylic-blur (seccion 10). No se crean
    # capacidades duplicadas en seccion 12.
    ("12", "405"): "system.registry-backup.enable",
    ("12", "406"): "ui.logon.acrylic-blur",
}


def load_capabilities() -> list[dict]:
    """Lee los JSON del catálogo y extrae (id, seccion, item_ids de provenance)."""
    capabilities = []
    for path in sorted(CATALOG_DIR.glob("*.json"), key=lambda p: p.name):
        document = json.loads(path.read_text(encoding="utf-8"))
        for definition in document.get("capabilities", []):
            item_ids = sorted(set(LEDGER_ID.findall(definition.get("provenance", ""))))
            capabilities.append(
                {
                    "id": definition["id"],
                    "file": path.name,
                    "section": str(definition.get("sectionId")),
                    "prefixes": item_ids,
                }
            )
    return capabilities


def load_rows() -> list[dict]:
    """Filas del ledger, con mapped_ids ya partidos."""
    lines = RECONCILIATION.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    rows = []
    for raw in lines[1:]:
        if not raw.strip():
            continue
        cells = raw.split("\t")
        row = dict(zip(header, cells))
        row["mapped_ids"] = [i for i in (row.get("mapped_ids") or "").split("|") if i]
        rows.append(row)
    return rows


def prefix_matches(mapped_id: str, prefixes: list[str]) -> bool:
    """True si algún item_id de la provenance casa con el mapped_id de la línea.

    Se admite casamiento por prefijo en ambos sentidos porque la provenance cita
    la entrada de catálogo (`winutil:tweak:WPFTweaksTelemetry`) mientras la línea
    puede citar una op concreta (`winutil:tweak-op:WPFTweaksTelemetry:registry:1`),
    y al revés.
    """
    for prefix in prefixes:
        if prefix == mapped_id or mapped_id.startswith(prefix) or prefix.startswith(mapped_id):
            return True
    return False


def supporters_of_row(row: dict, capabilities: list[dict]) -> list[str]:
    """Capacidades que cubren una línea `Mapped` del inventario.

    Es la ÚNICA definición de cobertura del repo: la usan el verificador (para
    decidir si hay hueco) y el plan de oleadas (para contar «Mapped cubiertas»).
    Si se separaran, el plan podría decir 27 y el verificador 29 sobre las
    mismas líneas.
    """
    forced = {cap for (sec, line), cap in DECLARED_SOURCES.items()
              if (sec, line) == (row["seccion"], row["linea"])}
    found = {
        cap["id"]
        for cap in capabilities
        if any(prefix_matches(m, cap["prefixes"]) for m in row["mapped_ids"])
    }
    return sorted(found | forced)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="salida JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="falla también si hay huecos declarados en DECLARED_GAPS",
    )
    args = parser.parse_args(argv)

    if not CATALOG_DIR.is_dir():
        print(f"FALTA el directorio {CATALOG_DIR}", file=sys.stderr)
        return 1
    if not RECONCILIATION.is_file():
        print(f"FALTA el ledger {RECONCILIATION}", file=sys.stderr)
        return 1

    capabilities = load_capabilities()
    rows = load_rows()

    mapped = [r for r in rows
              if r["seccion"] in COMPLETED_SECTIONS and r["status"].startswith("Mapped")]

    def supporters_of(row: dict) -> list[str]:
        return supporters_of_row(row, capabilities)

    covered: list[dict] = []
    gaps: list[dict] = []
    for row in mapped:
        supporters = supporters_of(row)
        entry = {
            "seccion": row["seccion"],
            "linea": row["linea"],
            "texto": row["texto"],
            "mapped_ids": row["mapped_ids"],
            "capabilities": sorted(supporters),
        }
        (covered if supporters else gaps).append(entry)

    # Un hueco es aceptado solo si está declarado Y sigue siendo un hueco de verdad.
    undeclared = [g for g in gaps if (g["seccion"], g["linea"]) not in DECLARED_GAPS]
    stale = [
        key
        for key in DECLARED_GAPS
        if not any((g["seccion"], g["linea"]) == key for g in gaps)
    ]

    # Capacidades que no respaldan ninguna línea Mapped. No es un fallo: buena
    # parte de la oleada 1 nace de líneas Absent-At-Pin del inventario (Atlas sobre
    # todo). Se informa para que la cifra quede a la vista y no se confunda con
    # cobertura.
    without_mapped_line = []
    for cap in capabilities:
        hits = [r for r in mapped if cap["id"] in supporters_of(r)]
        if not hits:
            without_mapped_line.append(cap["id"])

    # Informe por las 17 secciones: lineas por estado, Mapped cubiertas/huecos y
    # trabajo pendiente (Mapped sin cubrir + EVO-Exclusive + Absent-At-Pin).
    all_mapped = [r for r in rows if r["status"].startswith("Mapped")]
    per_all_section: dict[str, dict] = {}
    for section in ALL_SECTIONS:
        section_rows = [r for r in rows if r["seccion"] == section]
        states = {state: sum(1 for r in section_rows if r["status"] == state)
                  for state in RECONCILIATION_STATES}
        section_mapped = [r for r in section_rows if r["status"].startswith("Mapped")]
        covered_here = sum(1 for row in section_mapped if supporters_of(row))
        per_all_section[section] = {
            "estados": states,
            "lineas": len(section_rows),
            "mapped": len(section_mapped),
            "mapped_cubiertas": covered_here,
            "mapped_sin_cubrir": len(section_mapped) - covered_here,
            "trabajo": (len(section_mapped) - covered_here
                        + states["EVO-Exclusive"] + states["Absent-At-Pin"]),
        }
    _ = all_mapped

    per_section = {}
    for section in COMPLETED_SECTIONS:
        per_section[section] = {
            "lineas_mapped": sum(1 for r in mapped if r["seccion"] == section),
            "cubiertas": sum(1 for c in covered if c["seccion"] == section),
            "huecos": sum(1 for g in gaps if g["seccion"] == section),
        }

    report = {
        "capacidades": len(capabilities),
        # Nombre conservado por compatibilidad con los tests del paso 8; ahora
        # cuenta las secciones terminadas (1-3 y 10).
        "lineas_mapped_1_3": len(mapped),
        "secciones_terminadas": list(COMPLETED_SECTIONS),
        "cubiertas": len(covered),
        "huecos": len(gaps),
        "huecos_declarados": len(DECLARED_GAPS),
        "huecos_no_declarados": len(undeclared),
        "declaraciones_obsoletas": sorted(f"{s}:{l}" for s, l in stale),
        "capacidades_sin_linea_mapped": sorted(without_mapped_line),
        "por_seccion": per_section,
        "por_seccion_17": per_all_section,
        "detalle_huecos": sorted(
            ({"seccion": g["seccion"], "linea": g["linea"], "texto": g["texto"],
              "mapped_ids": g["mapped_ids"]} for g in undeclared),
            key=lambda d: (d["seccion"], int(d["linea"])),
        ),
    }

    ok = not undeclared and not stale
    if args.strict and gaps:
        ok = False

    if args.json:
        report["ok"] = ok
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if ok else 1

    print(f"capacidades del catalogo : {report['capacidades']}")
    print(f"lineas Mapped {'+'.join(COMPLETED_SECTIONS)}   : {report['lineas_mapped_1_3']}")
    print(f"  cubiertas             : {report['cubiertas']}")
    print(f"  huecos declarados     : {report['huecos']} (de {report['huecos_declarados']} declarados)")
    for section, data in per_section.items():
        print(
            f"  seccion {section}: {data['lineas_mapped']} Mapped, "
            f"{data['cubiertas']} cubiertas, {data['huecos']} huecos"
        )
    if undeclared:
        print("\nHUECOS NO DECLARADOS:")
        for gap in report["detalle_huecos"]:
            print(f"  linea {gap['linea']} ({gap['texto']}): {gap['mapped_ids']}")
    if stale:
        print("\nDECLARACIONES OBSOLETAS (ya no son hueco):")
        for key in report["declaraciones_obsoletas"]:
            print(f"  {key}")
    if without_mapped_line:
        print("\n(cifra informativa) capacidades que no respaldan ninguna linea Mapped:")
        for cap in report["capacidades_sin_linea_mapped"]:
            print(f"  {cap}")
    print("\nveredicto:", "OK" if ok else "FALLA")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
