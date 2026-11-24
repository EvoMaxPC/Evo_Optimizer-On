#!/usr/bin/env python3
"""Tests del paso 8c: interruptores, sección por categoría y plan de oleadas.

Todo se mide sobre los artefactos reales del repositorio. Lo .NET corre en
`dotnet-ci`; aquí se comprueba lo medible sin dotnet.
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "inventory" / "ledger"
PARTITION = ROOT / "inventory" / "partition"
CATALOG = ROOT / "catalog" / "capabilities"
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

import audit_catalog_values as acv  # noqa: E402
import build_category_section_map as csm  # noqa: E402
import build_upstream_capability_map as bucm  # noqa: E402
import build_wave_plan as bwp  # noqa: E402
import verify_catalog_coverage as vcc  # noqa: E402

MAP_TSV = LEDGER / "upstream-capability-map.tsv"
CAT_TSV = PARTITION / "category-section-map.tsv"
PLAN_MD = ROOT / "docs" / "reports" / "plan-oleadas.md"
OPS_TSV = LEDGER / "winutil-tweak-ops.tsv"
AUDIT_TSV = LEDGER / "catalog-value-audit.tsv"
EXCEPTIONS = ROOT / "catalog" / "exceptions" / "value-deviations.json"
MAX_CELL = 400


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def capabilities() -> list[dict]:
    out = []
    for path in sorted(CATALOG.glob("*.json")):
        out.extend(json.loads(path.read_text(encoding="utf-8"))["capabilities"])
    return out


# ------------------------------------------------------- T1: tweak_type / audit
def test_winutil_ops_lleva_tweak_type_y_solo_valores_conocidos() -> None:
    rows = read_tsv(OPS_TSV)
    assert "tweak_type" in rows[0], "falta la columna tweak_type"
    assert {r["tweak_type"] for r in rows} <= {"Toggle", "Button", "Combobox", "none"}
    kinds = {r["tweak_type"] for r in rows}
    # El pin tiene 24 Toggle, 3 Button y 2 Combobox (config/tweaks.json).
    assert "Toggle" in kinds and "none" in kinds


def test_el_extractor_de_winutil_es_determinista() -> None:
    before = OPS_TSV.read_bytes()
    assert subprocess.run([sys.executable,
                           str(ROOT / "tools" / "ledger_extract" / "extract_winutil_ops.py")],
                          capture_output=True, check=False).returncode == 0
    assert OPS_TSV.read_bytes() == before


def test_las_relaciones_del_audit_distinguen_encendido_y_apagado() -> None:
    rows = read_tsv(AUDIT_TSV)
    assert "source_tweak_type" in rows[0], "falta source_tweak_type"
    relations = {r["relation"] for r in rows}
    assert relations <= set(acv.RELATIONS)
    off = [r for r in rows if r["relation"] == "equals-off"]
    assert off, "debe haber al menos una fila que copie el estado APAGADO"
    for row in off:
        assert row["source_tweak_type"] == "Toggle", row["capability_id"]
    on = [r for r in rows if r["relation"] == "equals-on"]
    for row in on:
        assert row["source_tweak_type"] == "Toggle", row["capability_id"]


def test_toda_desviacion_declara_si_es_de_significado_de_interruptor() -> None:
    document = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    assert document["deviations"]
    for deviation in document["deviations"]:
        assert deviation["deviation_kind"] in ("value", "switch-meaning")
        assert deviation["reason"].strip()


def test_debloat_start_websearch_desactiva_bing_de_verdad() -> None:
    cap = next(c for c in capabilities() if c["id"] == "debloat.start.websearch")
    values = {a["valueName"]: a["value"] for a in cap["actions"] if a["type"] == "registry"}
    assert values.get("BingSearchEnabled") == "0", "el estado APAGADO del Toggle es 0"
    assert values.get("DisableSearchBoxSuggestions") == "1"
    assert "BingSearchEnabled" in cap["description"]


# ------------------------------------------------------- T2: catálogo y ADR
def test_windows_ai_se_parte_en_dos_capacidades_con_rangos_propios() -> None:
    caps = {c["id"]: c for c in capabilities()}
    recall = caps["debloat.windows.ai.recall"]
    copilot = caps["debloat.copilot.remove"]

    assert "debloat.windows.ai" not in caps, "el id viejo no debe sobrevivir"
    assert recall["supportedBuilds"] == [26100, 26200]
    assert copilot["supportedBuilds"] == [22631, 26100, 26200]
    assert recall["reversibility"] == "Reversible"
    assert copilot["reversibility"] == "Irreversible"

    def names(cap: dict) -> set[str]:
        return {a.get("valueName") for a in cap["actions"] if a["type"] == "registry"}

    assert "RemoveMicrosoftCopilotApp" in names(copilot)
    assert "RemoveMicrosoftCopilotApp" not in names(recall)


def test_el_adr_0003_tiene_el_anexo_de_las_13_irreversibles() -> None:
    adr = (ROOT / "docs" / "adr" / "ADR-0003-reversibilidad-y-restauracion.md").read_text(
        encoding="utf-8")
    irreversibles = [c for c in capabilities() if c["reversibility"] == "Irreversible"]
    assert len(irreversibles) == 13
    for cap in irreversibles:
        assert f"`{cap['id']}`" in adr, f"falta {cap['id']} en el anexo"
    assert "NO VERIFICADO" in adr


# ------------------------------------------------- T3: categoría -> sección
def test_el_mapa_de_categorias_es_determinista_y_sin_duplicados() -> None:
    before = CAT_TSV.read_bytes()
    assert csm.main([]) == 0
    assert CAT_TSV.read_bytes() == before
    rows = read_tsv(CAT_TSV)
    keys = [(r["source"], r["category_key"]) for r in rows]
    assert len(keys) == len(set(keys))


def test_el_mapa_de_categorias_tiene_las_columnas_y_la_seccion_valida() -> None:
    rows = read_tsv(CAT_TSV)
    assert list(rows[0].keys()) == list(csm.COLUMNS)
    valid = {str(n) for n in range(1, 18)} | {"mixed", "unassigned"}
    for row in rows:
        assert row["section"] in valid, row
        assert row["basis"].strip()
        assert row["reviewed"] == "no"
        assert int(row["items"]) >= 1
        assert len(row["basis"]) <= MAX_CELL


def test_toda_categoria_del_mapa_upstream_esta_en_el_mapa_de_categorias() -> None:
    declared = {(r["source"], r["category_key"]) for r in read_tsv(CAT_TSV)}
    sources = {"winutil-tweak", "winutil-feature", "winutil-appx", "winutil-dns",
               "winutil-preset", "winutil-theme", "atlas-toggle", "atlas-manifest"}
    used = {group for _item, group, _key in csm.item_categories()}
    assert used <= sources | {"winutil"}
    for _item, group, key in csm.item_categories():
        assert (group, key) in declared, f"categoría sin fila: {group}/{key}"


def test_el_mapa_upstream_conserva_435_filas_y_anade_section_basis() -> None:
    assert bucm.main([]) == 0
    rows = read_tsv(MAP_TSV)
    assert len(rows) == 435
    assert list(rows[0].keys()) == list(bucm.COLUMNS)
    # El paso 8d añade las bases por ítem (item-effect/item-name-rule/...).
    assert {r["section_basis"] for r in rows} <= {
        "category", "text-rule", "none",
        "item-effect", "item-name-rule", "item-manifest-path"}
    # La regla nueva debe haber reducido de verdad las filas sin sección.
    without = sum(1 for r in rows if not r["section_guess"])
    assert without < 361, "el paso 8b dejaba 361 filas sin sección"
    for row in rows:
        if row["section_basis"] == "category":
            assert row["section_guess"], row["upstream_id"]
        if row["section_basis"] == "none":
            assert not row["section_guess"], row["upstream_id"]
        if row["section_basis"].startswith("item-"):
            assert row["section_guess"], row["upstream_id"]


def test_ninguna_celda_de_los_tsv_nuevos_supera_400_caracteres() -> None:
    for path in (MAP_TSV, CAT_TSV, AUDIT_TSV, OPS_TSV):
        for row in read_tsv(path):
            for column, value in row.items():
                assert len(value) <= MAX_CELL, (path.name, column, len(value))


# ------------------------------------------------------------- T4: plan
def test_el_plan_de_oleadas_es_reproducible_y_cubre_las_17_secciones() -> None:
    assert bwp.main(["--check"]) == 0
    text = PLAN_MD.read_text(encoding="utf-8")
    for section in range(1, 18):
        assert re.search(rf"^\| {section} \|", text, re.MULTILINE), section
    assert "| **Σ** | **17 secciones** | **588** |" in text


def test_el_plan_marca_lo_medido_y_lo_propuesto() -> None:
    text = PLAN_MD.read_text(encoding="utf-8")
    assert "MEDIDO:" in text
    assert "PROPUESTA (no medida)" in text
    assert len(re.findall(r"^\| W\d+ \|", text, re.MULTILINE)) == 17


# ------------------------------------------------------------- varios
def test_la_cobertura_1_3_sigue_siendo_26_de_26() -> None:
    assert vcc.main([]) == 0
    report = json.loads(subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract" / "verify_catalog_coverage.py"),
         "--json"], capture_output=True, text=True, check=False).stdout)
    assert report["lineas_mapped_1_3"] == 26
    assert report["cubiertas"] == 26
    assert report["huecos"] == 0
    assert len(report["por_seccion_17"]) == 17


def test_la_licencia_esta_confirmada_en_los_tres_ficheros() -> None:
    for relative in ("README.md", "docs/legal/upstream-licenses.md",
                     "docs/adr/ADR-0002-datos-de-atlas-y-gpl.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "confirmad" in text.lower(), relative
    for relative in ("README.md", "docs/legal/upstream-licenses.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "pendiente de confirmación" not in text.lower(), relative


def test_los_ficheros_nuevos_son_lf_y_sin_bom() -> None:
    for path in (MAP_TSV, CAT_TSV, AUDIT_TSV, OPS_TSV, PLAN_MD):
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), path.name
        assert b"\r\n" not in raw, path.name
