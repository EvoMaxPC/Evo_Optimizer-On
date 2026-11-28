"""Tests del Paso 3: extractor determinista de WinUtil.

Fixtures JSON sintéticos: utf-8-sig, comas finales, clave duplicada, preset con
miembro inexistente, determinismo, orden estable, un tweak con
registro+servicio+script, una app, y comprobaciones cruzadas.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = PKG.parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, PKG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ex = load("extract_winutil_config")
fn = load("extract_winutil_functions")
cov = load("coverage_check")


# --- fixtures ---------------------------------------------------------------

TWEAK = {
    "category": "Essential Tweaks",
    "panel": "1",
    "Content": "Telemetry - Disable",
    "Description": "desactiva telemetria",
    "registry": [{"Path": "HKCU:\\Software\\X", "Name": "Enabled", "Value": "0", "Type": "DWord"}],
    "service": [{"Name": "DiagTrack", "StartupType": "Disabled"}],
    "InvokeScript": ["Set-Service -Name DiagTrack -Status Stopped\nWrite-WinUtilLog 'x'\n"],
}


def make_config(tmp_path: Path, *, bom=True, trailing_comma=False, extra=None) -> Path:
    cfg = tmp_path / "config"
    cfg.mkdir(parents=True, exist_ok=True)

    def dump(name, obj):
        text = json.dumps(obj, indent=2, ensure_ascii=False)
        if trailing_comma:
            text = text.replace("\n}", ",\n}")
        data = text.encode("utf-8")
        if bom:
            data = b"\xef\xbb\xbf" + data
        (cfg / name).write_bytes(data)

    dump("tweaks.json", {"WPFTweaksTelemetry": TWEAK, **(extra or {})})
    dump("feature.json", {"WPFFeaturesdotnet": {"Content": "dotnet", "Category": "Features"}})
    dump("appx.json", {"WPFAppxTeams": {"Content": "Teams", "category": "Microsoft Apps"}})
    dump("preset.json", {"Standard": ["WPFTweaksTelemetry"], "Roto": ["WPFTweaksNOEXISTE"]})
    dump("dns.json", {"Google": {"Primary": "8.8.8.8"}})
    dump("themes.json", {"Light": {"keys": "x"}})
    dump("appnavigation.json", {"WPFInstall": {"Target": "Install"}})
    dump("applications.json", {"1password": {
        "category": "Utilities", "content": "1Password",
        "winget": "AgileBits.1Password", "choco": "1password"}})
    return cfg


# --- carga tolerante --------------------------------------------------------

def test_utf8_sig_se_carga(tmp_path):
    cfg = make_config(tmp_path, bom=True)
    data = ex.load_json(cfg / "tweaks.json")
    assert "WPFTweaksTelemetry" in data


def test_coma_final_tolerada_por_strict_false(tmp_path):
    """strict=False permite caracteres de control; las comas finales NO."""
    cfg = make_config(tmp_path, trailing_comma=True)
    with pytest.raises(json.JSONDecodeError):
        ex.load_json(cfg / "tweaks.json")


# --- extracción -------------------------------------------------------------

def test_items_no_app_y_kinds(tmp_path):
    cfg = make_config(tmp_path)
    items, stats = ex.build_items(cfg)
    kinds = {i["kind"] for i in items}
    assert kinds == {"tweak", "feature", "appx", "preset", "dns-provider", "theme", "nav-entry"}
    assert len(items) == 8  # 1 tweak + 1 feature + 1 appx + 2 preset + 1 dns + 1 theme + 1 nav


def test_item_id_es_determinista_y_prefijado(tmp_path):
    cfg = make_config(tmp_path)
    items, _ = ex.build_items(cfg)
    ids = [i["item_id"] for i in items]
    assert "winutil:tweak:WPFTweaksTelemetry" in ids
    assert all(i.startswith("winutil:") for i in ids)


def test_sha256_es_del_json_canonico(tmp_path):
    cfg = make_config(tmp_path)
    items, _ = ex.build_items(cfg)
    tweak = next(i for i in items if i["kind"] == "tweak")
    expected = ex.canonical_sha(TWEAK)
    assert tweak["sha256"] == expected
    # independiente del orden de claves
    reordered = dict(reversed(list(TWEAK.items())))
    assert ex.canonical_sha(reordered) == expected


def test_tweak_con_registro_servicio_y_script(tmp_path):
    cfg = make_config(tmp_path)
    items, _ = ex.build_items(cfg)
    tweak = next(i for i in items if i["kind"] == "tweak")
    attrs = json.loads(tweak["attrs_json"])
    assert attrs["registry"][0]["name"] == "Enabled"
    assert attrs["registry"][0]["type"] == "DWord"
    assert attrs["services"][0]["name"] == "DiagTrack"
    assert attrs["services"][0]["startuptype"] == "Disabled"
    script = attrs["invoke_scripts"][0]
    assert script["lines"] == 2
    assert len(script["sha256"]) == 64
    assert script["own_cmdlets"] == ["Write-WinUtilLog"]


def test_script_no_se_copia_solo_hechos(tmp_path):
    """El cuerpo del script NO debe aparecer en attrs_json."""
    cfg = make_config(tmp_path)
    items, _ = ex.build_items(cfg)
    tweak = next(i for i in items if i["kind"] == "tweak")
    assert "Set-Service -Name DiagTrack" not in tweak["attrs_json"]


def test_apps_aparte_con_label_y_paquetes(tmp_path):
    cfg = make_config(tmp_path)
    apps, stats = ex.build_apps(cfg)
    assert len(apps) == 1
    a = apps[0]
    assert a["item_id"] == "winutil:catalog-entry:1password"
    assert a["label"] == "1Password"           # viene de 'content' en minúscula
    assert a["winget"] == "AgileBits.1Password"
    assert a["choco"] == "1password"
    assert stats["by_category"] == {"Utilities": 1}


# --- comprobaciones cruzadas ------------------------------------------------

def test_preset_con_miembro_inexistente(tmp_path):
    cfg = make_config(tmp_path)
    _, stats = ex.build_items(cfg)
    checks = ex.cross_checks(cfg, stats)
    assert checks["preset_members_missing_in_tweaks"] == ["Roto->WPFTweaksNOEXISTE"]


def test_clave_duplicada_en_texto_crudo(tmp_path):
    cfg = make_config(tmp_path)
    raw = '{"A": 1, "A": 2}'
    (cfg / "tweaks.json").write_text(raw, encoding="utf-8")
    dups = ex._top_level_dupes(cfg / "tweaks.json")
    assert "A" in dups


def test_determinismo_byte_a_byte(tmp_path):
    cfg = make_config(tmp_path)
    items, _ = ex.build_items(cfg)
    apps, _ = ex.build_apps(cfg)
    out1, out2 = tmp_path / "a.tsv", tmp_path / "b.tsv"
    ex.write_tsv(items, ex.ITEMS_COLUMNS, out1)
    ex.write_tsv(list(reversed(items)), ex.ITEMS_COLUMNS, out2)
    assert out1.read_bytes() == out2.read_bytes()   # orden estable por item_id


def test_sin_bom_y_lf(tmp_path):
    cfg = make_config(tmp_path)
    items, _ = ex.build_items(cfg)
    out = tmp_path / "x.tsv"
    ex.write_tsv(items, ex.ITEMS_COLUMNS, out)
    data = out.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in data
    assert data.endswith(b"\n")


# --- funciones y cobertura --------------------------------------------------

def test_funciones_regex_y_scope():
    text = "function Invoke-Thing {\n}\n  Function Get-Other {\n}\n$var = 1\n"
    names = sorted(set(fn.FUNC_RE.findall(text)))
    assert names == ["Get-Other", "Invoke-Thing"]
    assert fn.scope_of("functions/public/a.ps1") == "public"
    assert fn.scope_of("functions/private/b.ps1") == "private"
    assert fn.scope_of("scripts/main.ps1") == "scripts"
    assert fn.scope_of("pester/x.Tests.ps1") == "other"


def test_cobertura_marca_huerfano_sin_motivo(tmp_path, monkeypatch):
    """Un extract sin item y sin motivo debe salir como NO VERIFICADO."""
    results = tmp_path / "r.tsv"
    results.write_text("path\ttreatment\nraro.ps1\textract\n", encoding="utf-8")
    items = tmp_path / "i.tsv"
    items.write_text("item_id\tsource\n", encoding="utf-8")
    apps = tmp_path / "a.tsv"
    apps.write_text("item_id\tsource\n", encoding="utf-8")
    funcs = tmp_path / "f.tsv"
    funcs.write_text("path\tn_functions\n", encoding="utf-8")
    monkeypatch.setattr(cov, "RESULTS", results)
    monkeypatch.setattr(cov, "ITEMS", items)
    monkeypatch.setattr(cov, "APPS", apps)
    monkeypatch.setattr(cov, "FUNCS", funcs)
    rc = cov.main([])
    assert rc == 1        # huérfano sin motivo declarado


# --- integridad de los artefactos reales ------------------------------------

def test_ledger_real_tiene_162_y_239():
    items = REPO / "inventory" / "ledger" / "winutil-items.tsv"
    apps = REPO / "inventory" / "ledger" / "winutil-apps.tsv"
    if not items.is_file() or not apps.is_file():
        pytest.skip("ledger no generado")
    n_items = len(items.read_text(encoding="utf-8").splitlines()) - 1
    n_apps = len(apps.read_text(encoding="utf-8").splitlines()) - 1
    assert n_items == 162
    assert n_apps == 239


def test_dns_son_ip_literales_no_inventadas():
    """El campo Primary de dns.json debe ser una IP, no una URL inventada."""
    import re as _re
    dns = Path("/tmp/upstream/winutil/config/dns.json")
    if not dns.is_file():
        pytest.skip("clon no disponible")
    data = ex.load_json(dns)
    ip = _re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
    for name, entry in data.items():
        for key in ("Primary", "Secondary"):
            if key in entry:
                assert ip.match(str(entry[key])), f"{name}.{key}={entry[key]!r} no es IPv4"
