#!/usr/bin/env python3
"""Mapa upstream -> capacidad EVO (paso 8b).

La cifra que gobierna la cobertura real no es el inventario del responsable
(588 lineas) sino el **universo upstream**: cada item de WinUtil y cada entrada
de Atlas en el pin. Este script pone una fila por item y dice si alguna
capacidad del catalogo lo cita.

Universo (ADR-0001: las 239 apps de WinUtil se mantienen aparte):
    162 filas de inventory/ledger/winutil-items.tsv
     91 filas de inventory/ledger/atlas-toggles.tsv
    182 filas de inventory/ledger/atlas-manifest.tsv
    ---
    435 filas

Columnas:
    upstream_id     id del item en el ledger (winutil:*/atlas:toggle:*/atlas:manifest:*)
    source          winutil | atlas-toggle | atlas-manifest
    label           etiqueta legible del item
    section_guess   1-17 o vacio si no hay evidencia
    section_basis   category | item-effect | item-name-rule | item-manifest-path |
                    text-rule | none (de donde sale section_guess)
    capability_id   id de la capacidad del catalogo que lo cubre (vacio si no hay)
    status          covered | pending | variant-of | not-a-capability
    reason          por que tiene ese estado

Orden de `section_guess` (paso 8d):
    1. categoria del item segun inventory/partition/category-section-map.tsv, si
       esa categoria tiene una seccion 1-17 (no vale si es mixed/unassigned);
    2. si no, la seccion del item en inventory/partition/item-section-map.tsv
       (regla `item-effect`, `item-name-rule` o `item-manifest-path`);
    3. si no, la capacidad que lo cubre o la seccion ya medida en
       inventory-reconciliation.tsv (regla `text-rule`);
    4. si no hay nada, vacio (`none`).

`covered`  algun `ledger_refs:` de una capacidad del catalogo cita el item.
`pending`  ningun item del catalogo lo cita.
`variant-of` el item es una variante/duplicado de otro item ya cubierto (misma
           clave y mismo valor). Nunca se usa para "es dificil".
`not-a-capability` SOLO con motivo escrito: entradas de navegacion de UI,
           cabeceras o ficheros sin efecto declarado. Nunca por ser avanzado o
           arriesgado.

Sin cuerpos de codigo. Celdas <= 400 caracteres. Determinista: orden estable
por (source, upstream_id), LF, UTF-8 sin BOM.

Uso:
    python3 tools/ledger_extract/build_upstream_capability_map.py
    python3 tools/ledger_extract/build_upstream_capability_map.py --json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_catalog_coverage as vcc  # noqa: E402
import build_category_section_map as csm  # noqa: E402
import build_item_section_map as ism  # noqa: E402
LEDGER = ROOT / "inventory" / "ledger"
CATALOG_DIR = ROOT / "catalog" / "capabilities"
OUT = LEDGER / "upstream-capability-map.tsv"

COLUMNS = ("upstream_id", "source", "label", "section_guess", "section_basis",
           "capability_id", "status", "reason")
STATUSES = ("covered", "pending", "variant-of", "not-a-capability")
MAX_CELL = 400

LEDGER_REF = re.compile(r"\b(?:winutil|atlas):[A-Za-z0-9_.:\-/*{}]+")
SECTION_OF_ID = {"1": 1, "2": 2, "3": 3, "4": 4}

# Motivos escritos para not-a-capability. Solo UI/navegacion, nunca "avanzado".
NOT_A_CAPABILITY = {
    "nav-entry": "entrada de navegacion de la UI de WinUtil (pestana/menu): no tiene efecto propio",
    "nav": "entrada de navegacion de la UI de WinUtil (pestana/menu): no tiene efecto propio",
    "header": "cabecera o separador del manifiesto: no declara ninguna operacion",
}


def section_from_reconciliation() -> dict[tuple[str, str], str]:
    """(item_id del ledger, seccion) medido en inventory-reconciliation.tsv.

    Es la evidencia disponible para `section_guess`: la conciliacion ya decidio
    en que seccion del inventario cae cada item que aparece en una linea Mapped.
    No se inventa por parecido de texto (regla R2 del paso 4e).
    """
    index: dict[tuple[str, str], str] = {}
    for row in vcc.load_rows():
        for item in row.get("mapped_ids", []):
            index.setdefault((item, row["seccion"]), row["seccion"])
    return index


RECONCILED = section_from_reconciliation()


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def load_catalog_refs() -> tuple[dict[str, str], dict[str, int]]:
    """item_id del ledger -> capability_id, y capability_id -> seccion."""
    refs: dict[str, str] = {}
    sections: dict[str, int] = {}
    for path in sorted(CATALOG_DIR.glob("*.json"), key=lambda p: p.name):
        document = json.loads(path.read_text(encoding="utf-8"))
        for capability in document.get("capabilities", []):
            sections[capability["id"]] = int(capability["sectionId"])
            for item in LEDGER_REF.findall(capability.get("provenance", "")):
                refs.setdefault(item, capability["id"])
    return refs, sections


def ref_matches(item_id: str, ref: str) -> bool:
    """Casamiento por prefijo en ambos sentidos, igual que en la cobertura."""
    return item_id == ref or item_id.startswith(ref) or ref.startswith(item_id)


# Nombres de item de WinUtil que aparecen en las provenances (WPFTweaks*,
# WPFAppx*, WPF<Feature>). Se usan como segunda via de casamiento: una capacidad
# que cita `winutil:tweak-op:WPFTweaksTelemetry:registry:1` cubre el item
# `winutil:tweak:WPFTweaksTelemetry`, que es el mismo item upstream.
WINUTIL_NAME = re.compile(r"\b(WPF[A-Za-z0-9_]+)")
# Slug de un .psd1 de Atlas: 'Tweaks/privacy/telemetry/disallow-data-collection.psd1'
# -> 'privacy/telemetry/disallow-data-collection', que es el id del manifiesto.
ATLAS_SLUG = re.compile(r"Tweaks/([A-Za-z0-9_\-/]+?)\.psd1")


def load_secondary_index() -> tuple[dict[str, str], dict[str, str]]:
    winutil_names: dict[str, str] = {}
    atlas_slugs: dict[str, str] = {}
    for path in sorted(CATALOG_DIR.glob("*.json"), key=lambda p: p.name):
        document = json.loads(path.read_text(encoding="utf-8"))
        for capability in document.get("capabilities", []):
            provenance = capability.get("provenance", "")
            for name in WINUTIL_NAME.findall(provenance):
                winutil_names.setdefault(name, capability["id"])
            for slug in ATLAS_SLUG.findall(provenance):
                atlas_slugs.setdefault(slug, capability["id"])
    return winutil_names, atlas_slugs


WINUTIL_NAMES, ATLAS_SLUGS = load_secondary_index()


def find_capability(item_id: str, refs: dict[str, str]) -> str | None:
    for ref, capability in refs.items():
        if ref_matches(item_id, ref):
            return capability
    if item_id.startswith("winutil:"):
        for name in WINUTIL_NAME.findall(item_id):
            if name in WINUTIL_NAMES:
                return WINUTIL_NAMES[name]
    if item_id.startswith("atlas:manifest:"):
        slug = item_id[len("atlas:manifest:"):]
        if slug in ATLAS_SLUGS:
            return ATLAS_SLUGS[slug]
    return None


def guess_section(capability: str | None, sections: dict[str, int], label: str,
                  source: str) -> str:
    _ = source
    """Seccion: la de la capacidad que lo cubre; si no hay, se deja vacia.

    Reglas de docs/inventory-recon/conciliacion-reglas.md: la seccion sale de la
    evidencia del ledger, no del nombre del item. Inventarla por parecido de
    texto seria exactamente el error que la regla R2 evita, asi que sin
    capacidad asociada la columna queda vacia.
    """
    if capability and capability in sections:
        return str(sections[capability])
    # Sin capacidad: se usa la seccion que el ledger ya midio para ese item.
    guesses = {section for (item, section) in RECONCILED if ref_matches(item, label)}
    if len(guesses) == 1:
        return guesses.pop()
    return ""


# upstream_id -> (seccion propuesta por categoria, categoria). Se calcula una vez.
CATEGORY_SECTION = csm.index()

# upstream_id -> (seccion, basis) del mapa por item (paso 8d). Se calcula una
# vez; cubre las categorias mixed y los items sin categoria.
ITEM_SECTION = {row["upstream_id"]: (row["section"], row["basis"])
                for row in ism.build()}


def section_from_category(item_id: str) -> str:
    """Seccion propuesta por la categoria del item, si no es mixed/unassigned."""
    section, _category = CATEGORY_SECTION.get(item_id, ("", ""))
    return section if section.isdigit() else ""


def load_rows() -> list[dict]:
    rows: list[dict] = []

    path = LEDGER / "winutil-items.tsv"
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            rows.append({"upstream_id": row["item_id"], "source": "winutil",
                         "label": norm(row.get("label", "")), "kind": row.get("kind", "")})

    path = LEDGER / "atlas-toggles.tsv"
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            rows.append({"upstream_id": row["item_id"], "source": "atlas-toggle",
                         "label": norm(row.get("label", "")), "kind": "toggle"})

    path = LEDGER / "atlas-manifest.tsv"
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            rows.append({"upstream_id": row["item_id"], "source": "atlas-manifest",
                         "label": norm(row.get("id", "")), "kind": "manifest"})
    return rows


def build() -> list[dict]:
    refs, sections = load_catalog_refs()
    rows = load_rows()

    # variant-of: mismo label ya cubierto por otra fila del mismo source.
    covered_by_label: dict[tuple[str, str], str] = {}
    out: list[dict] = []

    for row in sorted(rows, key=lambda r: (r["source"], r["upstream_id"])):
        capability = find_capability(row["upstream_id"], refs)
        status: str
        reason: str

        if capability:
            status = "covered"
            reason = f"cubierta por {capability} (ledger_refs de su provenance)"
            covered_by_label.setdefault((row["source"], row["label"].lower()), capability)
        elif row["kind"] in ("nav-entry", "nav", "header"):
            status = "not-a-capability"
            reason = NOT_A_CAPABILITY[row["kind"]]
        elif (row["source"], row["label"].lower()) in covered_by_label:
            status = "variant-of"
            reason = (f"misma etiqueta que {covered_by_label[(row['source'], row['label'].lower())]}, "
                      "que ya la cubre")
        else:
            status = "pending"
            reason = "ninguna capacidad del catalogo la cita todavia"

        # 1) categoria; 2) mapa por item del paso 8d; 3) reglas de siempre
        # (capacidad / conciliacion); 4) vacio.
        by_category = section_from_category(row["upstream_id"])
        item_section, item_basis = ITEM_SECTION.get(row["upstream_id"], ("", "manual-review"))
        if by_category:
            section_guess, section_basis = by_category, "category"
        elif item_section.isdigit():
            section_guess, section_basis = item_section, f"item-{item_basis}"
        else:
            section_guess = guess_section(capability, sections, row["upstream_id"],
                                          row["source"])
            section_basis = "text-rule" if section_guess else "none"

        out.append({
            "upstream_id": row["upstream_id"],
            "source": row["source"],
            "label": row["label"][:MAX_CELL],
            "section_guess": section_guess,
            "section_basis": section_basis,
            "capability_id": capability or "",
            "status": status,
            "reason": reason[:MAX_CELL],
        })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    rows = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (v[:MAX_CELL] if isinstance(v, str) else v)
                             for k, v in row.items()})

    by_source = Counter(r["source"] for r in rows)
    cross = defaultdict(int)
    for row in rows:
        cross[(row["source"], row["status"])] += 1

    pending_by_section = Counter(
        (r["section_guess"] or "(sin seccion)") for r in rows if r["status"] == "pending")
    source_x_section = Counter(
        (r["source"], r["section_guess"] or "(sin seccion)") for r in rows)
    pending_by_basis = Counter(
        r["section_basis"] for r in rows if r["status"] == "pending")
    by_basis = Counter(r["section_basis"] for r in rows)

    summary = {
        "filas": len(rows),
        "por_source": dict(sorted(by_source.items())),
        "source_x_status": {f"{s}|{st}": cross[(s, st)]
                            for s in sorted(by_source) for st in STATUSES},
        "pending_por_seccion": dict(sorted(pending_by_section.items())),
        "por_basis": dict(sorted(by_basis.items())),
        "pending_por_basis": dict(sorted(pending_by_basis.items())),
        "source_x_section": {f"{s}|{sec}": n for (s, sec), n in sorted(source_x_section.items())},
        "cobertura": {
            "covered": sum(1 for r in rows if r["status"] == "covered"),
            "total": len(rows),
        },
    }
    summary["cobertura"]["porcentaje"] = round(
        100.0 * summary["cobertura"]["covered"] / max(len(rows), 1), 1)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"filas del mapa upstream : {len(rows)}")
    for source, count in sorted(by_source.items()):
        print(f"  {source:15s} {count}")
    print("\nsource x status:")
    for source in sorted(by_source):
        cells = " ".join(f"{st}={cross[(source, st)]}" for st in STATUSES)
        print(f"  {source:15s} {cells}")
    print("\nsection_basis (todas las filas):")
    for basis, count in sorted(by_basis.items()):
        print(f"  {basis:10s} {count}")
    print("\npending por section_guess:")
    for section, count in sorted(pending_by_section.items()):
        print(f"  {section:14s} {count}")
    print(f"\ncobertura real: {summary['cobertura']['covered']}/{len(rows)} "
          f"({summary['cobertura']['porcentaje']} %)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
