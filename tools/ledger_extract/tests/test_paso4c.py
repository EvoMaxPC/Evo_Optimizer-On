#!/usr/bin/env python3
"""Tests del paso 4c: funciones, puente, ops del catálogo y ops de los .psd1."""
from __future__ import annotations

import csv
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

LEDGER = ROOT / "inventory" / "ledger"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "tools" / "ledger_extract" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


fn = _load("extract_atlas_functions")
br = _load("extract_atlas_bridge")
tg = _load("extract_atlas_toggle_ops")
tw = _load("extract_atlas_tweak_ops")
cx = _load("cross_atlas_ops")


def _tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


TSVS = ("atlas-functions.tsv", "atlas-toggle-bridge.tsv",
        "atlas-toggle-ops.tsv", "atlas-tweak-ops.tsv")


# ---------------------------------------------------------------- ficheros
@pytest.mark.parametrize("name", TSVS)
def test_tsv_existe_y_es_determinista(name):
    p = LEDGER / name
    assert p.is_file(), f"falta {name}"
    raw = p.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM prohibido"
    assert b"\r\n" not in raw, "LF obligatorio"
    assert raw.endswith(b"\n")


@pytest.mark.parametrize("name", [t for t in TSVS
                                 if t != "atlas-toggle-bridge.tsv"])
def test_orden_por_item_id(name):
    rows = _tsv(LEDGER / name)
    ids = [r["item_id"] for r in rows]
    assert ids == sorted(ids), f"{name} no está ordenado por item_id"
    assert len(ids) == len(set(ids)), f"{name} tiene item_id duplicados"


# --------------------------------------------------------------- funciones
def test_parser_funciones_cuenta_anidadas():
    src = "\n".join([
        "function Get-Alpha {",
        "    param($x)",
        "    return $x",
        "}",
        "function Get-Beta {",
        "    function Get-Inner { 'anidada' }",
        "    Get-Inner",
        "}",
    ])
    got = fn.find_functions(src)
    assert [g[0] for g in got] == ["Get-Alpha", "Get-Beta", "Get-Inner"]
    assert got[0][1:3] == (1, 4)
    assert got[2][1:3] == (6, 6)


def test_scope_class_clasifica():
    assert fn.scope_class("package/x.ps1") == "product"
    assert fn.scope_class("app/x.ps1") == "product"
    assert fn.scope_class("tests/x.ps1") == "test"
    assert fn.scope_class("tools/x.ps1") == "tooling"


def test_functions_tsv_cifras():
    rows = _tsv(LEDGER / "atlas-functions.tsv")
    # 4d corrigio el parser (calificador de ambito + comentario de bloque):
    # 1563 -> 1562 y product 1173 -> 1172. Ver docs/reports/paso4d.md.
    assert len(rows) == 1562
    assert len({r["path"] for r in rows}) == 254
    assert {r["scope"] for r in rows} == {"product", "test"}
    assert sum(r["scope"] == "test" for r in rows) == 390
    assert sum(r["scope"] == "product" for r in rows) == 1172
    assert all(re.fullmatch(r"[0-9a-f]{64}", r["sha256_body"]) for r in rows)


# ----------------------------------------------------------------- puente
def test_puente_cifras():
    rows = _tsv(LEDGER / "atlas-toggle-bridge.tsv")
    assert len(rows) == 92
    assert len({r["function_name"] for r in rows}) == 74
    assert {r["match_kind"] for r in rows} == {"function"}
    assert len({r["resolved_in"] for r in rows}) == 52


def test_puente_no_alcanza_ningun_psd1():
    rows = _tsv(LEDGER / "atlas-toggle-bridge.tsv")
    for r in rows:
        for p in r["resolved_in"].split(";"):
            assert not p.endswith(".psd1")


def test_psd1_names_extrae_nombres_declarados():
    names = br.psd1_names(Path("/tmp/upstream/atlas"))
    assert len(names) >= 182


# ---------------------------------------------------- ops del catalogo
def test_catalogo_declara_solo_contadores():
    rows = _tsv(LEDGER / "atlas-toggle-ops.tsv")
    assert len(rows) == 303
    assert all(r["action"] == "unresolved" for r in rows)
    assert all(not r["hive"] and not r["key"] for r in rows)
    assert len({(r["toggle_id"], r["state"]) for r in rows}) == 94


# ------------------------------------------------------------ ops .psd1
def test_registry_blocks_extrae_bloque():
    txt = "Registry = @(\n  @{ Path = 'HKLM:\\A\\B' }\n)\n"
    blocks = tw.registry_blocks(txt)
    assert len(blocks) == 1
    assert "HKLM" in blocks[0]


def test_iter_entries_no_corta_con_guids():
    block = " @{ Path = 'HKLM:\\CLSID\\{abc}\\x'; Operation = 'DeleteKey' } "
    entries = list(tw.iter_entries(block))
    assert len(entries) == 1
    assert "CLSID\\{abc}" in entries[0]


@pytest.mark.parametrize("raw,esperado", [
    ("HKCU\\Software\\X", ("HKCU", "Software\\X")),
    ("HKLM:\\SOFTWARE\\X", ("HKLM", "SOFTWARE\\X")),
    ("Registry::HKEY_LOCAL_MACHINE\\SOFTWARE\\X", ("HKLM", "SOFTWARE\\X")),
    ("HKCR\\CLSID", ("HKCR", "CLSID")),
    ("HKU\\S-1-5-18", ("HKU", "S-1-5-18")),
])
def test_split_hive_normaliza(raw, esperado):
    assert tw.split_hive(raw) == esperado


def test_tweak_ops_cifras():
    rows = _tsv(LEDGER / "atlas-tweak-ops.tsv")
    assert len(rows) == 408
    assert all(r["parse_status"] == "ok" for r in rows)
    assert {r["hive"] for r in rows} == {"HKCR", "HKCU", "HKLM", "HKU"}
    # 4 claves aparecen declaradas dos veces en los .psd1 -> 404 distintas
    assert len({(r["hive"], r["key"], r["value_name"]) for r in rows}) == 404
    assert all(re.fullmatch(r"[0-9a-f]{64}", r["value_sha256"]) for r in rows)


def test_tweak_ops_conserva_operaciones_sobre_clave():
    rows = _tsv(LEDGER / "atlas-tweak-ops.tsv")
    key_ops = [r for r in rows if r["unparsed_reason"].startswith("key-operation:")]
    assert len(key_ops) == 37
    assert all(r["value_name"] == "" for r in key_ops)


def test_tweak_ops_no_copian_datos_literales():
    with (LEDGER / "atlas-tweak-ops.tsv").open(encoding="utf-8") as fh:
        header = next(csv.reader(fh, delimiter="\t"))
    assert "data" not in {h.lower() for h in header}


def test_psd1_con_registry_son_154():
    rows = _tsv(LEDGER / "atlas-tweak-ops.tsv")
    assert len({r["path"] for r in rows}) == 154


# -------------------------------------------------------------- cruce
def test_cruce_no_comparable():
    tg_rows = _tsv(LEDGER / "atlas-toggle-ops.tsv")
    tw_rows = _tsv(LEDGER / "atlas-tweak-ops.tsv")
    tg_keys = {cx.key_of(r) for r in tg_rows if r["hive"] and r["key"]}
    assert tg_keys == set()
    # el cruce normaliza a minúsculas -> 403 claves distintas
    tw_keys = {cx.key_of(r) for r in tw_rows}
    assert len(tw_keys) == 403
    assert tg_keys & tw_keys == set()


def test_cruce_emitible():
    assert cx.main([]) == 0
