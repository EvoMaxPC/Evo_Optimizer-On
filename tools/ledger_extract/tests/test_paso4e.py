#!/usr/bin/env python3
"""Tests del paso 4e: manifiesto de Atlas, verificacion de WinUtil y conciliacion."""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

LEDGER = ROOT / "inventory" / "ledger"
WINUTIL = Path("/tmp/upstream/winutil")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "tools" / "ledger_extract" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


am = _load("extract_atlas_manifest")
bc = _load("build_conciliacion")


def _tsv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


NEW_TSVS = ("atlas-manifest.tsv", "conciliacion-borrador.tsv")


# ------------------------------------------------------------------ formato
@pytest.mark.parametrize("name", NEW_TSVS)
def test_formato_determinista(name):
    raw = (LEDGER / name).read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")


def test_atlas_manifest_columnas_y_sin_duplicados():
    header, rows = _tsv(LEDGER / "atlas-manifest.tsv")
    assert header == list(am.COLUMNS)
    ids = [r["item_id"] for r in rows]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_atlas_manifest_cifras():
    _, rows = _tsv(LEDGER / "atlas-manifest.tsv")
    assert len(rows) == 182
    assert sum(1 for r in rows if r["enabled"] == "true") == 177
    assert sum(1 for r in rows if r["enabled"] == "false") == 5
    assert {r["section"] for r in rows} == {"Categories", "Standalone", "Disabled"}
    # ningun id sin fichero, y ningun cuerpo de script
    assert all(r["psd1_path"].endswith(".psd1") for r in rows)
    for r in rows:
        for k, v in r.items():
            assert len(v or "") <= 400, f"celda {k} de {len(v)} caracteres"


def test_atlas_manifest_resuelve_todos():
    _, rows = _tsv(LEDGER / "atlas-manifest.tsv")
    for r in rows:
        assert (Path("/tmp/upstream/atlas") / r["psd1_path"]).is_file(), r["id"]


def test_manifest_parse_no_corta_en_parentmodes():
    """El fallo del 4d: `Tweaks = @( ... )` cortado en el `)` de ParentModes.

    `networking` y `performance` tienen ParentModes dentro del bloque; con el
    parser malo solo salian 4 y 10 slugs.
    """
    text = (Path("/tmp/upstream/atlas") /
            "package/Executables/AtlasModules/Scripts/Tweaks/tweaks.manifest.psd1"
            ).read_text(encoding="utf-8-sig")
    entries = am.parse(text)
    cats = {}
    for e in entries:
        if e["section"] == "Categories":
            cats[e["category"]] = cats.get(e["category"], 0) + 1
    # solo habilitados en categoria; los deshabilitados van por `Disabled`
    assert cats["networking"] == 4
    assert cats["performance"] == 10
    assert len(entries) == 182


def test_manifest_slugs_coincide_con_el_extractor():
    """`extract_atlas_toggle_effects.manifest_slugs` delega en el mismo parser."""
    fx = _load("extract_atlas_toggle_effects")
    text = (Path("/tmp/upstream/atlas") /
            "package/Executables/AtlasModules/Scripts/Tweaks/tweaks.manifest.psd1"
            ).read_text(encoding="utf-8-sig")
    en, dis = fx.manifest_slugs(text)
    assert len(en) == 177 and len(dis) == 5


# ----------------------------------------------------- WinUtil vs JSON bruto
def _raw_tweaks() -> dict:
    return json.loads((WINUTIL / "config" / "tweaks.json")
                      .read_text(encoding="utf-8-sig"), strict=False)


def test_winutil_registry_y_service_contra_el_json():
    data = _raw_tweaks()
    reg = sum(len(v.get("registry") or []) for v in data.values())
    svc = sum(len(v.get("service") or []) for v in data.values())
    inv = sum(1 for v in data.values() if v.get("InvokeScript"))
    und = sum(1 for v in data.values() if v.get("UndoScript"))
    _, rows = _tsv(LEDGER / "winutil-tweak-ops.tsv")
    got = {k: sum(1 for r in rows if r["kind"] == k)
           for k in ("registry", "service", "script")}
    und = sum(1 for r in rows if r["direction"] == "undo")
    assert got["registry"] == reg == 121
    assert got["service"] == svc == 9
    # `kind` distingue script vs estructura; la direccion va en `direction`
    assert got["script"] == inv + und == 49
    assert und == 22
    # claves de nivel 2 reales: no hay ScheduledTask ni appx en tweaks.json
    keys = {k for v in data.values() for k in v}
    assert "ScheduledTask" not in keys and "scheduledtask" not in keys
    assert "appx" not in keys


def test_winutil_feature_y_appx_cifras_contra_json():
    feat = json.loads((WINUTIL / "config" / "feature.json")
                      .read_text(encoding="utf-8-sig"), strict=False)
    appx = json.loads((WINUTIL / "config" / "appx.json")
                      .read_text(encoding="utf-8-sig"), strict=False)
    n_feat = sum(len(v.get("feature") or []) for v in feat.values())
    n_inv = sum(1 for v in feat.values() if v.get("InvokeScript"))
    _, frows = _tsv(LEDGER / "winutil-feature-ops.tsv")
    assert len(frows) == n_feat + n_inv == 31
    _, arows = _tsv(LEDGER / "winutil-appx-ops.tsv")
    assert len(arows) == len(appx) == 34


# --------------------------------------------------------- conciliacion
def test_conciliacion_columnas_y_588_filas():
    header, rows = _tsv(LEDGER / "conciliacion-borrador.tsv")
    assert header == list(bc.COLUMNS)
    assert len(rows) == 588
    assert len({r["linea"] for r in rows}) == 588


def test_conciliacion_sin_mapped_y_texto_acotado():
    _, rows = _tsv(LEDGER / "conciliacion-borrador.tsv")
    for r in rows:
        assert r["estado_propuesto"] != "Mapped"
        assert r["estado_propuesto"] in {"propuesto-mapped", "propuesto-evo-propio",
                                         "sin-evidencia", "informativo"}
        assert r["confianza"] in {"alta", "media", "baja", "ninguna"}
        assert r["regla"] in {"R1", "R2", "R3", "R4"}
        assert len(r["texto"]) <= 200
        assert len(r["candidatos"]) <= 5 * 200


def test_conciliacion_candidatos_existen_en_su_tsv():
    """Cada candidato es un `item_id` real de alguno de los TSV fuente."""
    validos: set[str] = set()
    # las reglas R3 citan tambien operaciones de efectos/ops como evidencia
    for name in ("winutil-items.tsv", "winutil-apps.tsv", "atlas-toggles.tsv",
                 "atlas-tweak-files.tsv", "atlas-manifest.tsv",
                 "atlas-effects.tsv", "atlas-tweak-ops.tsv",
                 "winutil-tweak-ops.tsv"):
        _, rows = _tsv(LEDGER / name)
        validos |= {r["item_id"] for r in rows}
    _, rows = _tsv(LEDGER / "conciliacion-borrador.tsv")
    for r in rows:
        for c in filter(None, r["candidatos"].split("|")):
            assert c in validos, c


def test_conciliacion_invariante_confianza_estado():
    _, rows = _tsv(LEDGER / "conciliacion-borrador.tsv")
    for r in rows:
        if r["confianza"] == "ninguna":
            assert r["estado_propuesto"] == "sin-evidencia"
            assert r["regla"] == "R4"
        else:
            assert r["estado_propuesto"] == "propuesto-mapped"
            assert r["candidatos"]


def test_conciliacion_no_modifica_el_inventario():
    import hashlib
    p = ROOT / "docs" / "requirements" / "INVENTARIO_USUARIO.md"
    assert hashlib.sha256(p.read_bytes()).hexdigest() == \
        "0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709"


def test_reglas_r2_exige_contiguedad():
    """`Install Software.` no debe casar con `Razer Software Auto-Install`."""
    sources = bc.load_sources()
    df = bc.token_df(sources)
    hits = bc.r2("Install Software.", sources, df)
    ids = {i for _, i in hits}
    assert "winutil:tweak:WPFTweaksRazerBlock" not in ids


def test_reglas_r4_sin_candidatos():
    sources = bc.load_sources()
    targets = bc.effect_targets()
    df = bc.token_df(sources)
    regla, cands, conf, estado = bc.classify(
        "Fuentes de arquitectura y codigo: Atlas Architecture", sources, targets, df)
    assert regla == "R4" and cands == [] and conf == "ninguna"
    assert estado == "sin-evidencia"
