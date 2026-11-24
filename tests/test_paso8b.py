#!/usr/bin/env python3
"""Tests del paso 8b: auditoría de valores, reversibilidad, huecos y mapa upstream.

Todo se mide sobre los artefactos reales del repositorio. La lógica C# corre en
`dotnet-ci` sobre Windows; aquí se comprueba lo medible sin dotnet.
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
CATALOG = ROOT / "catalog" / "capabilities"
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

import audit_catalog_values as acv  # noqa: E402
import build_upstream_capability_map as bucm  # noqa: E402
import coverage_gate as gate  # noqa: E402
import verify_catalog_coverage as vcc  # noqa: E402

AUDIT_TSV = LEDGER / "catalog-value-audit.tsv"
MAP_TSV = LEDGER / "upstream-capability-map.tsv"
EXCEPTIONS = ROOT / "catalog" / "exceptions" / "value-deviations.json"
MAX_CELL = 400


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def catalog_capabilities() -> list[dict]:
    caps = []
    for path in sorted(CATALOG.glob("*.json")):
        caps.extend(json.loads(path.read_text(encoding="utf-8"))["capabilities"])
    return caps


# ------------------------------------------------------------------ T1: auditoría
def test_la_auditoria_pasa_sin_filas_inseguras() -> None:
    assert acv.main([]) == 0


def test_el_tsv_de_auditoria_tiene_las_columnas_y_relaciones_esperadas() -> None:
    rows = read_tsv(AUDIT_TSV)
    assert list(rows[0].keys()) == list(acv.COLUMNS)
    assert rows, "la auditoría no escribió filas"
    assert {row["relation"] for row in rows} <= set(acv.RELATIONS)


def test_ninguna_celda_supera_400_caracteres() -> None:
    for row in read_tsv(AUDIT_TSV):
        for column, value in row.items():
            assert len(value) <= MAX_CELL, (row["capability_id"], column, len(value))


def test_no_hay_duplicados_en_la_auditoria() -> None:
    keys = [(r["capability_id"], r["hive"], r["key"], r["name"]) for r in read_tsv(AUDIT_TSV)]
    assert len(keys) == len(set(keys))


def test_toda_fila_equals_original_o_differs_tiene_excepcion() -> None:
    document = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    declared = {
        (d["capability_id"], d["hive"], acv.norm_key(d["key"]), d["name"])
        for d in document["deviations"]
    }
    for row in read_tsv(AUDIT_TSV):
        if row["relation"] in ("equals-original", "differs"):
            key = (row["capability_id"], row["hive"], row["key"], row["name"])
            assert key in declared, f"desviación sin excepción: {key}"


def test_cada_excepcion_tiene_motivo_y_evidencia_con_ruta_del_pin() -> None:
    document = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    assert document["deviations"], "la oleada 1b introdujo una desviación real"
    for deviation in document["deviations"]:
        assert deviation["reason"].strip()
        assert deviation["evidence"].strip()
        assert re.search(r"winutil@[0-9a-f]{40}:|atlas@[0-9a-f]{8}:|inventory/ledger/",
                         deviation["evidence"]), deviation["evidence"]


def test_el_caso_bingsearch_no_se_copia_porque_activa_bing() -> None:
    """BingSearchEnabled: catálogo no lo escribe; la política de Atlas sí."""
    caps = catalog_capabilities()
    assert not any(
        action.get("valueName") == "BingSearchEnabled"
        for cap in caps
        for action in cap["actions"]
        if action.get("type") == "registry"
    ), "el catálogo no debe escribir BingSearchEnabled (en el pin aplica 1 = activar)"


def test_EnableActivityFeed_del_catalogo_es_0_y_la_fuente_discrepa() -> None:
    rows = [r for r in read_tsv(AUDIT_TSV) if r["name"] == "EnableActivityFeed"]
    assert rows
    for row in rows:
        assert row["catalog_value"] == "0"
        # WinUtil aplica 1 (activa el feed) y Atlas aplica 0: discrepancia real.
        assert row["relation"] in ("ambiguous", "equals-apply")


def test_AllowTelemetry_del_catalogo_coincide_con_las_fuentes() -> None:
    rows = [r for r in read_tsv(AUDIT_TSV) if r["name"] == "AllowTelemetry"]
    assert rows
    assert {r["catalog_value"] for r in rows} == {"0"}
    assert {r["relation"] for r in rows} == {"equals-apply"}


# -------------------------------------------------------- T2: reversibilidad JSON
def test_toda_capacidad_declara_reversibilidad_valida() -> None:
    for cap in catalog_capabilities():
        assert cap["reversibility"] in ("Reversible", "NothingToRestore", "Irreversible"), cap["id"]


def test_las_ramas_de_reversibilidad_cumplen_la_adr_0003() -> None:
    restore = ["None", "SessionUndo", "RestorePoint", "FullBackup"]
    confirmation = ["None", "SimpleClick", "Summary", "SummaryAndRestorePoint",
                    "TypeOperationName"]
    minimum_restore = {"Safe": 0, "Low": 1, "Medium": 2, "High": 2, "Critical": 3}
    minimum_confirmation = {"Safe": 0, "Low": 1, "Medium": 2, "High": 3, "Critical": 4}

    for cap in catalog_capabilities():
        risk = cap["risk"]
        rest = restore.index(cap["restore"])
        conf = confirmation.index(cap["confirmation"])

        assert conf >= minimum_confirmation[risk], f"{cap['id']}: confirmación por debajo del mínimo"

        if cap["reversibility"] == "Reversible":
            assert rest >= 1, f"{cap['id']}: Reversible exige >= SessionUndo"
            assert rest >= minimum_restore[risk], f"{cap['id']}: mínimo por riesgo"
        elif cap["reversibility"] == "NothingToRestore":
            assert rest == 0, f"{cap['id']}: NothingToRestore exige None"
            assert risk in ("Safe", "Low", "Medium"), f"{cap['id']}: riesgo > Medium"
        else:  # Irreversible
            assert rest == 0, f"{cap['id']}: Irreversible exige None"
            assert risk in ("High", "Critical"), f"{cap['id']}: Irreversible exige High+"
            assert conf >= 2, f"{cap['id']}: Irreversible exige fila >= Summary"


def test_la_regla_vieja_ya_no_esta_en_el_validador() -> None:
    source = (ROOT / "src" / "Evo.Catalog" / "CatalogValidator.cs").read_text(encoding="utf-8")
    rules = (ROOT / "src" / "Evo.Core" / "Models" / "CapabilityRules.cs").read_text(encoding="utf-8")
    assert "RestoreLevel.None es incompatible" not in rules
    assert "ValidateReversibility" in rules
    assert "R-RISK" in source and "Reversibility" in source


def test_hay_al_menos_ocho_tests_xunit_de_reversibilidad() -> None:
    text = (ROOT / "tests" / "Evo.Core.Tests" / "ReversibilityTests.cs").read_text(encoding="utf-8")
    assert len(re.findall(r"\[Fact\]", text)) >= 8
    for branch in ("NothingToRestore", "Irreversible", "Reversible"):
        assert branch in text


# ---------------------------------------------------------------- T3: huecos
def test_la_cobertura_del_inventario_es_26_de_26() -> None:
    assert vcc.main([]) == 0
    assert vcc.DECLARED_GAPS == {}, "no quedan huecos declarados en las secciones 1-3"


def test_verify_catalog_coverage_json_dice_26_cubiertas() -> None:
    capabilities = vcc.load_capabilities()
    rows = vcc.load_rows()
    mapped = [r for r in rows if r["seccion"] in vcc.SECTIONS and r["status"].startswith("Mapped")]
    cubiertas = [
        row for row in mapped
        if any(
            vcc.prefix_matches(m, cap["prefixes"])
            for cap in capabilities for m in row["mapped_ids"]
        )
    ]
    assert len(mapped) == 26
    assert len(cubiertas) == 26


def test_implemented_solo_si_el_motor_la_ejecuta_y_la_fuente_esta_verificada() -> None:
    caps = {c["id"]: c for c in catalog_capabilities()}
    # dmwappush: única fuente no verificada como tweak -> Specified.
    assert caps["privacy.telemetry.dmwappush"]["state"] == "Specified"
    assert "NO VERIFICADO" in caps["privacy.telemetry.dmwappush"]["provenance"]
    # Las que solo existen como script en el pin -> Specified.
    for capability_id in ("cleanup.winsxs.resetbase", "debloat.edge.remove",
                          "debloat.store.search", "debloat.explorer.auto-folder-discovery",
                          "debloat.drivers.razer", "debloat.drivers.logitech",
                          "debloat.network.adobe-blocklist", "debloat.start.layout"):
        assert caps[capability_id]["state"] == "Specified", capability_id

    implemented = [c for c in caps.values() if c["state"] == "Implemented"]
    specified = [c for c in caps.values() if c["state"] == "Specified"]
    assert len(implemented) + len(specified) == len(caps) == 38


def test_winsxs_resetbase_es_irreversible_y_conflicta_con_la_variante_sin_resetbase() -> None:
    caps = {c["id"]: c for c in catalog_capabilities()}
    reset = caps["cleanup.winsxs.resetbase"]
    assert reset["reversibility"] == "Irreversible"
    assert reset["risk"] == "High"
    assert reset["restore"] == "None"
    assert reset["confirmation"] in ("SummaryAndRestorePoint", "TypeOperationName")
    assert "cleanup.winsxs.component" in reset["conflictsWith"]
    assert "cleanup.winsxs.resetbase" in caps["cleanup.winsxs.component"]["conflictsWith"]
    assert any("/ResetBase" in a.get("arguments", []) for a in reset["actions"] if a["type"] == "command")


# ---------------------------------------------------------------- T4: mapa
def test_el_mapa_tiene_435_filas_y_las_columnas_pedidas() -> None:
    assert bucm.main([]) == 0
    rows = read_tsv(MAP_TSV)
    assert len(rows) == 435, "162 winutil + 91 atlas-toggle + 182 atlas-manifest"
    assert list(rows[0].keys()) == list(bucm.COLUMNS)
    sources = {}
    for row in rows:
        sources[row["source"]] = sources.get(row["source"], 0) + 1
    assert sources == {"winutil": 162, "atlas-toggle": 91, "atlas-manifest": 182}


def test_el_mapa_no_tiene_duplicados_ni_estados_invalidos() -> None:
    rows = read_tsv(MAP_TSV)
    ids = [r["upstream_id"] for r in rows]
    assert len(ids) == len(set(ids))
    assert {r["status"] for r in rows} <= set(bucm.STATUSES)
    for row in rows:
        assert len(row["reason"]) <= MAX_CELL
        if row["status"] == "covered":
            assert row["capability_id"], row["upstream_id"]
        if row["status"] == "not-a-capability":
            assert row["reason"].strip(), row["upstream_id"]
        if row["section_guess"]:
            assert 1 <= int(row["section_guess"]) <= 17


def test_el_mapa_es_determinista() -> None:
    assert bucm.main([]) == 0
    first = MAP_TSV.read_bytes()
    assert bucm.main([]) == 0
    assert MAP_TSV.read_bytes() == first


# ---------------------------------------------------------------- T4: gate
def test_coverage_gate_phase0_sale_cero() -> None:
    assert gate.main(["--gate", "phase0"]) == 0


def test_coverage_gate_beta_falla_con_pending_y_no_bloquea_en_modo_informativo() -> None:
    rows = read_tsv(MAP_TSV)
    pending = sum(1 for r in rows if r["status"] == "pending")
    assert pending > 0, "si ya no hay pending, el gate beta debe pasar a bloqueante"
    assert gate.main(["--gate", "beta"]) == 1
    assert gate.main(["--gate", "beta", "--informational"]) == 0


# ---------------------------------------------------------------- T5: varios
def test_los_ficheros_nuevos_son_lf_y_sin_bom() -> None:
    for path in (AUDIT_TSV, MAP_TSV, EXCEPTIONS,
                 *sorted(CATALOG.glob("*.json"))):
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), path.name
        assert b"\r\n" not in raw, path.name


def test_los_scripts_nuevos_compilan() -> None:
    for script in ("audit_catalog_values.py", "build_upstream_capability_map.py",
                   "coverage_gate.py", "verify_catalog_coverage.py"):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(ROOT / "tools" / "ledger_extract" / script)],
            capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
