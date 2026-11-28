#!/usr/bin/env python3
"""Tests del paso 5: conciliacion definitiva y matriz de cobertura maestra."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

LEDGER = ROOT / "inventory" / "ledger"
RECON = LEDGER / "inventory-reconciliation.tsv"
MATRIX = ROOT / "docs" / "reports" / "matriz-cobertura.md"
INFORME = ROOT / "docs" / "requirements" / "CONCILIACION_INVENTARIO.md"
STATUSES = ("Mapped", "Mapped-To-App", "EVO-Exclusive", "Absent-At-Pin",
            "Informative-Header")
COLUMNS = ["seccion", "linea", "fuente_declarada", "texto", "status",
           "mapped_ids", "confidence", "rationale"]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "tools" / "ledger_extract" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


bf = _load("build_final_reconciliation")
gm = _load("generate_coverage_matrix")
vr = _load("validate_reconciliation")


def _rows(path: Path = RECON) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


# ------------------------------------------------------------------ formato
def test_formato_determinista():
    raw = RECON.read_bytes()
    assert b"\r\n" not in raw, "LF obligatorio"
    assert not raw.startswith(b"\xef\xbb\xbf"), "sin BOM"
    raw.decode("utf-8")
    assert raw.endswith(b"\n")


def test_cabecera_exacta():
    header = RECON.read_text(encoding="utf-8").splitlines()[0].split("\t")
    assert header == COLUMNS


def test_588_filas():
    assert len(_rows()) == 588


def test_lineas_unicas_y_ordenadas():
    lineas = [int(r["linea"]) for r in _rows()]
    assert lineas == sorted(lineas)
    assert len(set(lineas)) == 588


# ------------------------------------------------------------------ estados
def test_cinco_estados_exactos():
    estados = Counter(r["status"] for r in _rows())
    assert set(estados) == set(STATUSES)
    assert sum(estados.values()) == 588
    assert not [r for r in _rows() if not r["status"].strip()]


def test_mapped_tiene_ids():
    for r in _rows():
        if r["status"] in ("Mapped", "Mapped-To-App"):
            assert r["mapped_ids"], f"linea {r['linea']} sin ids"


def test_mapped_to_app_solo_en_seccion_15():
    for r in _rows():
        if r["status"] == "Mapped-To-App":
            assert r["seccion"] == "15"
            assert all(m.startswith("winutil:catalog-entry:")
                       for m in r["mapped_ids"].split("|"))


def test_evo_exclusive_en_secciones_previstas():
    permitidas = {"1", "6", "7", "17"}
    for r in _rows():
        if r["status"] == "EVO-Exclusive":
            assert r["seccion"] in permitidas, (r["linea"], r["seccion"])


def test_confianza_valores_validos():
    for r in _rows():
        assert r["confidence"] in ("alta", "media", "baja", "ninguna")


def test_texto_y_celdas_acotados():
    for r in _rows():
        assert len(r["texto"]) <= 200
        for v in r.values():
            assert len(v) <= 400
            assert not any(ord(c) < 32 for c in v)


def test_fuente_declarada_valores_validos():
    for r in _rows():
        assert r["fuente_declarada"] in ("winutil", "atlas", "evo", "general")


def test_todas_las_secciones_presentes():
    assert {int(r["seccion"]) for r in _rows()} == set(range(1, 18))


# ------------------------------------------------------------------ matriz
def test_matriz_cruzada_suma_588():
    por_sec, totales, totales_sec = gm.build_matrix(_rows())
    assert sum(totales_sec.values()) == 588
    assert sum(totales.values()) == 588
    assert len(por_sec) == 17
    for sec, c in por_sec.items():
        assert sum(c.values()) == totales_sec[sec]


def test_matriz_md_generada():
    assert MATRIX.is_file()
    txt = MATRIX.read_text(encoding="utf-8")
    for s in STATUSES:
        assert s in txt
    assert txt.count("| **Total** |") >= 2
    sha = hashlib.sha256(RECON.read_bytes()).hexdigest()
    assert sha in txt


def test_matriz_es_reproducible(tmp_path):
    out = tmp_path / "m.md"
    res = subprocess.run(
        [sys.executable,
         str(ROOT / "tools" / "ledger_extract" / "generate_coverage_matrix.py"),
         "--report", str(out)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert out.read_text(encoding="utf-8") == MATRIX.read_text(encoding="utf-8")


def test_ids_mapeados_existen_en_los_ledgers():
    data = gm.load()
    cov = gm.coverage(data["recon"], data)
    assert cov["ids_otros"] == 0
    assert cov["atomicos"] == cov["winutil_items_hit"] + cov["winutil_apps_hit"] \
        + cov["winutil_ops_hit"] + cov["atlas_toggles_hit"] \
        + cov["atlas_effects_hit"] + cov["atlas_regs_hit"] \
        + cov["atlas_manifest_hit"]


def test_cobertura_cifras_base():
    data = gm.load()
    cov = gm.coverage(data["recon"], data)
    assert cov["winutil_items"] == 162
    assert cov["winutil_apps"] == 239
    assert cov["atlas_toggles"] == 91
    assert cov["atlas_manifest"] == 182
    assert cov["atlas_regs"] == 327


# ------------------------------------------------------------------ validador
def test_validador_exit_0():
    res = subprocess.run(
        [sys.executable,
         str(ROOT / "tools" / "ledger_extract" / "validate_reconciliation.py"),
         "--skip-determinism"], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr


def test_validador_detecta_errores():
    rows = _rows()
    ids = vr.source_ids()
    assert vr.check(rows, ids) == []
    roto = [dict(r) for r in rows]
    roto[0]["status"] = "Inventado"
    errores = vr.check(roto, ids)
    assert any("estados desconocidos" in e for e in errores)
    roto2 = [dict(r) for r in rows]
    roto2[3]["mapped_ids"] = "winutil:item:no-existe"
    roto2[3]["status"] = "Mapped"
    assert any("inexistente" in e for e in vr.check(roto2, ids))
    recortado = rows[:-1]
    assert any("588" in e for e in vr.check(recortado, ids))


def test_determinismo_doble_ejecucion():
    cmd = [sys.executable,
           str(ROOT / "tools" / "ledger_extract" / "build_final_reconciliation.py")]
    shas = []
    for _ in range(2):
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, res.stderr
        shas.append(hashlib.sha256(RECON.read_bytes()).hexdigest())
    assert shas[0] == shas[1]


# ------------------------------------------------------------------ informe
def test_informe_inventario_intacto():
    sha = hashlib.sha256(
        (ROOT / "docs" / "requirements" / "INVENTARIO_USUARIO.md").read_bytes()
    ).hexdigest()
    assert sha == "0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709"


def test_informe_conciliacion_incluye_tabla():
    assert INFORME.is_file()
    txt = INFORME.read_text(encoding="utf-8")
    assert "588" in txt
    for s in STATUSES:
        assert s in txt
