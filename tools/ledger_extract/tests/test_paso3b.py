#!/usr/bin/env python3
"""Tests del paso 3b/4a: extractor y cobertura de Atlas."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "tools" / "ledger_extract" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


ex = _load("extract_atlas_files")


def _write(p: Path, data: bytes | str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        p.write_text(data, encoding="utf-8")
    else:
        p.write_bytes(data)
    return p


def _part(tmp: Path, paths: list[str], all_extract: bool = False) -> Path:
    tsv = tmp / "part.tsv"
    with tsv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["path", "treatment", "rule_index", "rule_glob"])
        for i, p in enumerate(paths):
            treat = "extract" if (all_extract or i % 2 == 0) else "reference"
            w.writerow([p, treat, i, "*"])
    return tsv


def test_reg_utf16_le_con_bom(tmp_path):
    reg = _write(tmp_path / "u16.reg",
                 b"\xff\xfe" + (
                     "Windows Registry Editor Version 5.00\r\n\r\n"
                     "[HKEY_LOCAL_MACHINE\\SOFTWARE\\Test]\r\n"
                     '"Dword"=dword:00000001\r\n'
                     '"Text"="x"\r\n').encode("utf-16-le"))
    rows, entries = ex.build_rows(tmp_path, _part(tmp_path, ["u16.reg"]))
    assert len(rows) == 1
    assert rows[0]["reg_keys"] == 1
    assert rows[0]["reg_values"] == 2
    types = {e["name"]: e["type"] for e in entries}
    assert types == {"Dword": "dword", "Text": "sz"}


def test_reg_borrado_y_default(tmp_path):
    _write(tmp_path / "del.reg",
           "Windows Registry Editor Version 5.00\n\n"
           "[HKEY_CURRENT_USER\\A]\n"
           "@=hex(2):25,00\n"
           '"Kill"=-\n')
    rows, entries = ex.build_rows(tmp_path, _part(tmp_path, ["del.reg"]))
    assert rows[0]["reg_keys"] == 1
    got = {e["name"]: e["type"] for e in entries}
    assert got == {"@": "default", "Kill": "delete"}


def test_reg_no_copia_el_dato(tmp_path):
    _write(tmp_path / "s.reg",
           "Windows Registry Editor Version 5.00\n\n"
           "[HKEY_CURRENT_USER\\A]\n"
           '"Secreto"="VALOR-SENSIBLE-1234"\n')
    _, entries = ex.build_rows(tmp_path, _part(tmp_path, ["s.reg"]))
    assert len(entries) == 1
    e = entries[0]
    assert set(e) == {"item_id", "file", "key", "name", "type", "value_sha256"}
    assert "VALOR-SENSIBLE" not in json.dumps(e, ensure_ascii=False)
    assert len(e["value_sha256"]) == 64


def test_reg_item_id_con_clave_y_nombre(tmp_path):
    _write(tmp_path / "i.reg",
           "Windows Registry Editor Version 5.00\n\n"
           "[HKEY_CURRENT_USER\\Soft]\n\"N\"=dword:00000001\n")
    _, entries = ex.build_rows(tmp_path, _part(tmp_path, ["i.reg"]))
    assert entries[0]["item_id"] == "atlas:reg-entry:i.reg#HKEY_CURRENT_USER\\Soft|N"


def test_ps1_funciones_y_conteo(tmp_path):
    _write(tmp_path / "a.ps1",
           "function Get-One { 1 }\n"
           "Function Set-Two { 2 }\n"
           "  function Hel-Third { 3 }\n"
           "Write-Host 'no soy funcion'\n")
    rows, _ = ex.build_rows(tmp_path, _part(tmp_path, ["a.ps1"]))
    fns = json.loads(rows[0]["functions_json"])
    assert fns == ["Get-One", "Hel-Third", "Set-Two"]
    assert rows[0]["kind"] == "script"


def test_ps1_pester_sin_function_deja_nota(tmp_path):
    _write(tmp_path / "b.Tests.ps1", "Describe 'x' { It 'y' { 1 | Should -Be 1 } }\n")
    rows, _ = ex.build_rows(tmp_path, _part(tmp_path, ["b.Tests.ps1"]))
    assert rows[0]["functions_json"] == ""
    assert "pester:Describe1" in rows[0]["notes"]


def test_rust_tipos_publicos(tmp_path):
    _write(tmp_path / "m.rs",
           "pub struct A;\npub(crate) enum B { X }\nfn privada() {}\n"
           "pub fn visible() {}\n")
    rows, _ = ex.build_rows(tmp_path, _part(tmp_path, ["m.rs"]))
    got = json.loads(rows[0]["functions_json"])
    assert got == ["enum B", "fn visible", "struct A"]


def test_kind_clasificacion(tmp_path):
    for name in ("tests/x.Tests.ps1", "t.cmd", "r.reg", "a.rs", "app/i18n/en/a.ftl",
                 "p.cab", "c.json", "x.weird"):
        _write(tmp_path / name, "x\n")
    paths = ["tests/x.Tests.ps1", "t.cmd", "r.reg", "a.rs", "app/i18n/en/a.ftl",
             "p.cab", "c.json", "x.weird"]
    rows, _ = ex.build_rows(tmp_path, _part(tmp_path, paths, all_extract=True))
    kinds = {r["source_ref"]: r["kind"] for r in rows}
    assert kinds["tests/x.Tests.ps1"] == "test"
    assert kinds["t.cmd"] == "cmd"
    assert kinds["r.reg"] == "reg"
    assert kinds["a.rs"] == "rust"
    assert kinds["app/i18n/en/a.ftl"] == "i18n"
    assert kinds["p.cab"] == "package-binary"
    assert kinds["c.json"] == "config"
    assert kinds["x.weird"] == "other"


def test_binario_sin_lineas_y_solo_hash(tmp_path):
    _write(tmp_path / "b.cab", b"\x00\x01\x02")
    rows, _ = ex.build_rows(tmp_path, _part(tmp_path, ["b.cab"]))
    assert rows[0]["lines"] == 0
    assert rows[0]["sha256"] == hashlib.sha256(b"\x00\x01\x02").hexdigest()
    assert "binario" in rows[0]["notes"]


def test_orden_estable_por_item_id(tmp_path):
    _write(tmp_path / "z.ps1", "function A {}\n")
    _write(tmp_path / "a.ps1", "function B {}\n")
    rows, _ = ex.build_rows(tmp_path, _part(tmp_path, ["z.ps1", "a.ps1"]))
    ids = [r["item_id"] for r in rows]
    assert ids == sorted(ids)


def test_determinismo_dos_ejecuciones(tmp_path):
    _write(tmp_path / "a.ps1", "function A {}\n")
    _write(tmp_path / "r.reg", "Windows Registry Editor Version 5.00\n\n"
                               "[HKEY_CURRENT_USER\\A]\n\"V\"=\"1\"\n")
    part = _part(tmp_path, ["a.ps1", "r.reg"])
    out1 = tmp_path / "o1"
    out2 = tmp_path / "o2"
    ex.main(["--root", str(tmp_path), "--part", str(part), "--out", str(out1)])
    ex.main(["--root", str(tmp_path), "--part", str(part), "--out", str(out2)])
    for name in ("atlas-files.tsv", "atlas-reg-entries.tsv"):
        a = (out1 / name).read_bytes()
        b = (out2 / name).read_bytes()
        assert a == b, name
        assert not a.startswith(b"\xef\xbb\xbf")   # sin BOM
        assert b"\r\n" not in a                   # LF


def test_tsv_columnas_exactas(tmp_path):
    _write(tmp_path / "a.ps1", "function A {}\n")
    out = tmp_path / "o"
    ex.main(["--root", str(tmp_path), "--part", str(_part(tmp_path, ["a.ps1"])),
             "--out", str(out)])
    header = (out / "atlas-files.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert header.split("\t") == list(ex.FILES_COLUMNS)
    header2 = (out / "atlas-reg-entries.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert header2.split("\t") == list(ex.REG_COLUMNS)


def _coverage(tmp_path, files_rows, part_paths, reg_rows=()):
    """Devuelve (exit_code, salida) de coverage_check_atlas sobre datos sintéticos."""
    cov = _load("coverage_check_atlas")
    part = _part(tmp_path, part_paths)
    ledger = tmp_path / "ledger"
    ledger.mkdir(exist_ok=True)
    with (ledger / "atlas-files.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ex.FILES_COLUMNS, delimiter="\t",
                           lineterminator="\n")
        w.writeheader()
        for r in files_rows:
            w.writerow({c: r.get(c, "") for c in ex.FILES_COLUMNS})
    with (ledger / "atlas-reg-entries.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(ex.REG_COLUMNS)
        for r in reg_rows:
            w.writerow([r.get(c, "") for c in ex.REG_COLUMNS])

    cov.RESULTS = part
    cov.FILES = ledger / "atlas-files.tsv"
    cov.REG = ledger / "atlas-reg-entries.tsv"
    rc = cov.main([])
    return rc, cov


def test_cobertura_todo_con_hechos(tmp_path):
    row = {"item_id": "atlas:script:a.ps1", "source_ref": "a.ps1", "kind": "script",
           "lines": "3", "sha256": "x", "functions_json": '["A"]',
           "reg_keys": "", "reg_values": "", "notes": ""}
    rc, _ = _coverage(tmp_path, [row], ["a.ps1"])
    assert rc == 0


def test_cobertura_sin_motivo_falla(tmp_path):
    row = {"item_id": "atlas:other:x.weird", "source_ref": "x.weird",
           "kind": "other", "lines": "0", "sha256": "x", "functions_json": "",
           "reg_keys": "", "reg_values": "", "notes": ""}
    rc, _ = _coverage(tmp_path, [row], ["x.weird"])
    assert rc == 1


def test_cobertura_binario_con_motivo_ok(tmp_path):
    row = {"item_id": "atlas:package-binary:p.cab", "source_ref": "p.cab",
           "kind": "package-binary", "lines": "0", "sha256": "x",
           "functions_json": "", "reg_keys": "", "reg_values": "",
           "notes": "binario"}
    rc, _ = _coverage(tmp_path, [row], ["p.cab"])
    assert rc == 0


def test_cobertura_falta_en_ledger_falla(tmp_path):
    rc, _ = _coverage(tmp_path, [], ["faltante.ps1"])
    assert rc == 1
