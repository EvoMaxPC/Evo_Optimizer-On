#!/usr/bin/env python3
"""Tests del paso 4d: efectos de Atlas, grafo de llamadas y operaciones de WinUtil."""
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


fx = _load("extract_atlas_effects")
te = _load("extract_atlas_toggle_effects")
wo = _load("extract_winutil_ops")


def _tsv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


NEW_TSVS = ("atlas-effects.tsv", "atlas-toggle-effects.tsv", "atlas-psd1-refs.tsv",
            "winutil-tweak-ops.tsv", "winutil-feature-ops.tsv", "winutil-appx-ops.tsv")


# ------------------------------------------------------------ ficheros base
@pytest.mark.parametrize("name", NEW_TSVS)
def test_formato_y_determinismo(name):
    p = LEDGER / name
    assert p.is_file(), f"falta {name}"
    raw = p.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM prohibido"
    assert b"\r\n" not in raw, "LF obligatorio"
    assert raw.endswith(b"\n"), "salto final"


@pytest.mark.parametrize("name", NEW_TSVS)
def test_item_id_ordenado_y_sin_duplicados(name):
    header, rows = _tsv(LEDGER / name)
    col = "item_id" if "item_id" in header else header[0]
    if name == "atlas-toggle-effects.tsv":
        # esta tabla no tiene item_id: su clave natural es (toggle, estado, funcion)
        keys = [(r["toggle_id"], r["state"], r["function_name"]) for r in rows]
        assert keys == sorted(keys)
        assert len(keys) == len(set(keys))
        return
    ids = [r[col] for r in rows]
    assert ids == sorted(ids), f"{name}: no ordenado por {col}"
    assert len(ids) == len(set(ids)), f"{name}: {col} duplicados"


@pytest.mark.parametrize("name", NEW_TSVS)
def test_sin_cuerpos_de_codigo(name):
    """Ninguna celda puede contener un cuerpo de funcion: > 400 caracteres."""
    _, rows = _tsv(LEDGER / name)
    for r in rows:
        for k, v in r.items():
            assert len(v or "") <= 400, f"{name}: celda {k} de {len(v)} caracteres"


# ---------------------------------------------------------------- efectos
def test_detect_registry_y_target_literal():
    got = fx.detect("Set-ItemProperty -Path 'HKLM:\\Software\\X' -Name 'Y' -Value 1")
    assert ("registry", "Set-ItemProperty") in {(e[0], e[1]) for e in got}
    reg = [e for e in got if e[0] == "registry"][0]
    assert reg[3] == "literal"
    assert reg[4].startswith("HKLM")


def test_detect_variable_y_unresolved():
    # New-Item solo cuenta como registro si la ruta es una clave HK*/REGISTRY;
    # con una variable no se afirma que sea registro (evita falsos positivos).
    assert [e for e in fx.detect("New-Item -Path $state -Force")
            if e[0] == "registry"] == []
    var = fx.detect("Set-ItemProperty -Path $hive -Name 'X' -Value 1")
    assert var and var[0][3] == "variable"
    unres = fx.detect("Stop-Process -Name $p -ErrorAction SilentlyContinue")
    assert unres and unres[0][3] in ("variable", "unresolved")


def test_detect_no_cuenta_comandos_dentro_de_cadenas():
    """`throw "reg.exe import failed"` no es una operacion de registro."""
    assert [e for e in fx.detect('throw "reg.exe import failed"')
            if e[0] == "registry"] == []


def test_detect_other_exe_lista_lo_no_clasificado():
    got = fx.detect('& "C:\\tools\\mi-herramienta.exe" /silent')
    exes = [e for e in got if e[0] == "other-exe"]
    assert exes and exes[0][1].lower() == "mi-herramienta.exe"


def test_detect_otros_tipos():
    casos = {
        "sc.exe config DiagTrack start= disabled": "service",
        "schtasks /TN '\\Microsoft\\X' /Disable": "scheduled-task",
        "bcdedit /set {default} nx OptIn": "boot",
        "powercfg /hibernate off": "power",
        "Disable-WindowsOptionalFeature -FeatureName Foo": "dism",
        "Set-MpPreference -DisableRealtimeMonitoring $true": "defender",
        "icacls C:\\Windows /grant Administrators:F": "ownership",
        "fsutil behavior set disablelastaccess 1": "filesystem-config",
    }
    for line, esperado in casos.items():
        tipos = {e[0] for e in fx.detect(line)}
        assert esperado in tipos, f"{line} -> {tipos}"


def test_effects_tsv_columnas_y_cifras():
    header, rows = _tsv(LEDGER / "atlas-effects.tsv")
    assert header == list(fx.COLUMNS)
    assert len(rows) == 986, "cifra del paso 4d; si cambia, actualizar el informe"
    assert {r["target_kind"] for r in rows} <= {"literal", "variable", "unresolved"}
    assert len({r["effect_type"] for r in rows}) >= 10
    assert all(re.fullmatch(r"[0-9a-f]{64}", r["sha256_line"]) for r in rows)
    assert all(len(r["value"]) <= 120 for r in rows)


def test_effects_containers_son_funciones_o_marcadores():
    _, fns = _tsv(LEDGER / "atlas-functions.tsv")
    nombres = {r["name"] for r in fns}
    _, rows = _tsv(LEDGER / "atlas-effects.tsv")
    for r in rows:
        if r["container"] in ("<top>", "<script>"):
            continue
        assert r["container"] in nombres, f"contenedor desconocido {r['container']}"


# ------------------------------------------------------- toggles / grafo
def test_toggle_effects_columnas_y_funciones_existentes():
    header, rows = _tsv(LEDGER / "atlas-toggle-effects.tsv")
    assert header == list(te.COLUMNS)
    _, fns = _tsv(LEDGER / "atlas-functions.tsv")
    nombres = {r["name"] for r in fns}
    for r in rows:
        assert r["function_name"] in nombres, r["function_name"]


def test_toggle_effects_cifras():
    _, rows = _tsv(LEDGER / "atlas-toggle-effects.tsv")
    assert len(rows) == 92
    assert len({r["toggle_id"] for r in rows}) == 52
    assert sum(1 for r in rows if int(r["transitive_effects"]) == 0) == 39
    assert sum(1 for r in rows if r["has_cycle"] == "true") == 21
    for r in rows:
        assert int(r["transitive_effects"]) >= int(r["direct_effects"])
        assert int(r["depth_max"]) <= te.MAX_DEPTH


def test_reach_detecta_ciclo_con_camino():
    calls = {"A": {"B"}, "B": {"A"}}
    tipos, prof, ciclo, camino = te.reach(calls, {}, "A")
    assert ciclo and camino[0] == camino[-1] and len(camino) >= 3
    assert prof == 1


def test_psd1_refs_columnas_y_manifest():
    header, rows = _tsv(LEDGER / "atlas-psd1-refs.tsv")
    assert header == list(te.REF_COLUMNS)
    assert len(rows) == 183
    # el manifiesto declara 108 slugs: 103 habilitados + 5 en `Disabled`
    assert sum(int(r["referenced_by_manifest"]) for r in rows) == 108
    estados = {r["manifest_state"] for r in rows}
    assert estados == {"enabled", "disabled", ""}
    assert sum(1 for r in rows if r["manifest_state"] == "enabled") == 103
    assert sum(1 for r in rows if r["manifest_state"] == "disabled") == 5


# --------------------------------------------------------------- winutil
def test_winutil_ops_columnas_y_tweak_ids():
    header, rows = _tsv(LEDGER / "winutil-tweak-ops.tsv")
    assert header == list(wo.COLUMNS)
    _, items = _tsv(LEDGER / "winutil-items.tsv")
    validos = {r["source_ref"].split("#")[1] for r in items if r["kind"] == "tweak"}
    for r in rows:
        assert r["tweak_id"] in validos, r["tweak_id"]


def test_winutil_ops_cifras():
    _, rows = _tsv(LEDGER / "winutil-tweak-ops.tsv")
    assert len(rows) == 179
    assert len({r["tweak_id"] for r in rows}) == 65
    assert sum(1 for r in rows if r["kind"] == "registry") == 121
    assert sum(1 for r in rows if r["direction"] == "undo") == 22
    assert {r["direction"] for r in rows} == {"apply", "undo"}


def test_winutil_scripts_sin_cuerpo():
    _, rows = _tsv(LEDGER / "winutil-tweak-ops.tsv")
    for r in rows:
        if r["kind"].startswith("script"):
            assert r["value"].isdigit(), "solo el conteo de lineas"
            assert re.fullmatch(r"[0-9a-f]{64}", r["sha256"])


def test_winutil_feature_y_appx():
    _, feat = _tsv(LEDGER / "winutil-feature-ops.tsv")
    _, appx = _tsv(LEDGER / "winutil-appx-ops.tsv")
    assert len(feat) == 31
    assert sum(1 for r in feat if r["kind"] == "feature") == 13
    assert len(appx) == 34
    assert {r["kind"] for r in appx} == {"appx-package"}
