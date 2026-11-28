#!/usr/bin/env python3
"""Tests del paso 4b: toggles de Atlas, .psd1 de tweaks y sonda de coincidencia."""
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


tg = _load("extract_atlas_toggles")
pm = _load("probe_inventory_match")


CATALOG = {
    "schemaVersion": 1,
    "toggles": [
        {
            "name": "Alpha",
            "group": "General",
            "description": "d" * 40,
            "elevation": "Admin",
            "noStateRecord": False,
            "menu": True,
            "launcher": "3. General\\Alpha\\Enable Alpha.cmd",
            "warning": None,
            "states": [
                {"name": "Enable", "stateValue": 1,
                 "launcher": "3. General\\Alpha\\Enable Alpha.cmd",
                 "reboot": "None",
                 "work": {"registry": 2, "services": 1, "scheduledTasks": 0,
                          "machineAction": "Enable-AtlasAlpha",
                          "userAction": None, "action": None, "user": False}},
                {"name": "Disable", "stateValue": 0,
                 "launcher": None, "reboot": "Recommend",
                 "work": {"registry": 1, "services": 0, "scheduledTasks": 1,
                          "machineAction": None, "userAction": "Disable-AtlasAlpha",
                          "action": None, "user": True}},
            ],
        },
        {
            "name": "Beta",
            "group": "Services",
            "description": "e" * 30,
            "elevation": "TrustedInstaller",
            "noStateRecord": True,
            "menu": False,
            "launcher": None,
            "warning": "careful",
            "states": [
                {"name": "Run", "stateValue": None,
                 "launcher": "9. Troubleshooting\\Beta\\Run Beta.cmd",
                 "reboot": "Prompt",
                 "work": {"registry": 0, "services": 0, "scheduledTasks": 0,
                          "machineAction": None, "userAction": None,
                          "action": "Invoke-AtlasBeta", "user": False}},
            ],
        },
    ],
}


def _tree(tmp: Path, catalog: dict | None = None,
          launchers: tuple[str, ...] = (
              "3. General/Alpha/Enable Alpha.cmd",
              "9. Troubleshooting/Beta/Run Beta.cmd",
          )) -> Path:
    d = tmp / "package" / "Executables" / "AtlasModules" / "Toggles"
    d.mkdir(parents=True, exist_ok=True)
    (d / "catalog.json").write_text(
        json.dumps(catalog or CATALOG, indent=2), encoding="utf-8")
    for rel in launchers:
        p = tmp / "package" / "Executables" / "AtlasDesktop" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n", encoding="utf-8")
    return tmp


def _part(tmp: Path, psd1: dict[str, str] | None = None) -> Path:
    psd1 = psd1 or {}
    paths = []
    for rel in sorted(psd1):
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(psd1[rel], encoding="utf-8")
        paths.append(rel)
    tsv = tmp / "part.tsv"
    with tsv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["path", "treatment", "rule_index", "rule_glob"])
        for i, p in enumerate(paths):
            w.writerow([p, "extract", i, "*"])
    return tsv


TWDIR = "package/Executables/AtlasModules/Scripts/Tweaks/"


# --- toggles ---------------------------------------------------------------

def test_toggles_cuenta_y_columnas(tmp_path):
    _tree(tmp_path)
    rows, _, _ = tg.build_toggles(tmp_path)
    assert len(rows) == 2
    assert set(rows[0]) == set(tg.TOGGLE_COLUMNS)
    assert rows[0]["item_id"] == "atlas:toggle:Alpha"
    assert rows[0]["kind"] == "toggle"
    assert rows[0]["category"] == "General"


def test_toggle_attrs_no_copia_texto(tmp_path):
    _tree(tmp_path)
    rows, _, _ = tg.build_toggles(tmp_path)
    blob = json.dumps(rows, ensure_ascii=False)
    assert "d" * 40 not in blob          # descripción no transcrita
    assert "careful" not in blob         # warning no transcrito
    attrs = json.loads(rows[0]["attrs_json"])
    assert attrs["desc_len"] == 40
    assert len(attrs["desc_sha256"]) == 16
    assert "warning_sha256" not in attrs   # Alpha no tiene warning
    beta = json.loads(next(r for r in rows if r["label"] == "Beta")["attrs_json"])
    assert beta["warning_len"] == 7 and len(beta["warning_sha256"]) == 16


def test_toggle_attrs_operaciones(tmp_path):
    _tree(tmp_path)
    rows, _, _ = tg.build_toggles(tmp_path)
    a = {r["label"]: json.loads(r["attrs_json"]) for r in rows}
    assert a["Alpha"]["ops"] == {"registry": 3, "services": 1,
                                 "scheduled_tasks": 1}
    assert a["Alpha"]["user_scope"] == 1
    assert a["Alpha"]["states"] == 2
    assert a["Beta"]["elevation"] == "TrustedInstaller"


def test_ids_duplicados_detectados(tmp_path):
    cat = json.loads(json.dumps(CATALOG))
    cat["toggles"][1]["name"] = "Alpha"
    _tree(tmp_path, catalog=cat)
    rows, _, data = tg.build_toggles(tmp_path)
    cross = tg.cross_checks(tmp_path, rows, [], data)
    assert cross["duplicate_ids"] == ["Alpha"]
    assert cross["prediction_ok"] is False


def test_referencias_rotas(tmp_path):
    _tree(tmp_path, launchers=("3. General/Alpha/Enable Alpha.cmd",))
    rows, broken, _ = tg.build_toggles(tmp_path)
    assert len(broken) == 1
    assert "Beta" in broken[0].split(":")[0]
    attrs = {r["label"]: json.loads(r["attrs_json"]) for r in rows}
    assert attrs["Beta"]["refs"] == {"total": 1, "broken": 1}


def test_toggle_sin_etiqueta(tmp_path):
    cat = json.loads(json.dumps(CATALOG))
    cat["toggles"][0]["name"] = ""
    _tree(tmp_path, catalog=cat)
    rows, _, data = tg.build_toggles(tmp_path)
    cross = tg.cross_checks(tmp_path, rows, [], data)
    assert cross["unnamed"] == ["atlas:toggle:"]


# --- .psd1 de tweaks -------------------------------------------------------

def test_tweak_files_claves_y_menciones(tmp_path):
    txt = ("@{\n"
           "    Name = 'x'\n"
           "    Description = 'y'\n"
           "    Registry = @(\n"
           "        @{ Path = 'HKLM:\\Software\\X'; Value = 'a' }\n"
           "    )\n"
           "    Script = { bcdedit /set x y }\n"
           "    Services = @()\n"
           "    Run = { netsh int ip reset }\n"
           "}\n")
    part = _part(tmp_path, {TWDIR + "qol/x.psd1": txt})
    rows = tg.build_tweak_files(tmp_path, part)
    assert len(rows) == 1
    r = rows[0]
    assert r["item_id"] == f"atlas:tweak-file:{TWDIR}qol/x.psd1"
    assert json.loads(r["keys_json"]) == [
        "Description", "Name", "Registry", "Run", "Script", "Services"]
    assert (r["hklm"], r["hkcu"], r["set_service"], r["schtasks"],
            r["bcdedit"], r["netsh"]) == (1, 0, 0, 0, 1, 1)
    assert r["lines"] == 10


def test_solo_psd1_de_tweaks(tmp_path):
    part = _part(tmp_path, {
        TWDIR + "a.psd1": "Name = 'a'\n",
        "package/Executables/AtlasModules/Scripts/Modules/X/X.psd1": "Name = 'b'\n",
    })
    rows = tg.build_tweak_files(tmp_path, part)
    assert len(rows) == 1
    assert "Tweaks/" in rows[0]["source_ref"]


# --- determinismo y orden --------------------------------------------------

def test_orden_estable_y_determinismo(tmp_path):
    _tree(tmp_path)
    part = _part(tmp_path, {TWDIR + "z.psd1": "Name='z'\n",
                            TWDIR + "a.psd1": "Name='a'\n"})
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    for out in (out1, out2):
        assert tg.main(["--root", str(tmp_path), "--part", str(part),
                        "--out", str(out)]) == 0
    for name in ("atlas-toggles.tsv", "atlas-tweak-files.tsv"):
        a = (out1 / name).read_bytes()
        b = (out2 / name).read_bytes()
        assert a == b, name
        assert not a.startswith(b"\xef\xbb\xbf")
        assert b"\r\n" not in a
        ids = [l.split("\t")[0] for l in a.decode().splitlines()[1:]]
        assert ids == sorted(ids)


def test_sha256_canonico_de_la_entrada(tmp_path):
    _tree(tmp_path)
    rows, _, data = tg.build_toggles(tmp_path)
    expected = hashlib.sha256(tg.canonical(data["toggles"][0])).hexdigest()
    assert rows[0]["sha256"] == expected


def test_orden_de_claves_no_altera_sha(tmp_path):
    cat = json.loads(json.dumps(CATALOG))
    reordered = [dict(reversed(list(e.items()))) for e in cat["toggles"]]
    cat2 = {"schemaVersion": 1, "toggles": reordered}
    _tree(tmp_path / "a")
    _tree(tmp_path / "b", catalog=cat2)
    r1, _, _ = tg.build_toggles(tmp_path / "a")
    r2, _, _ = tg.build_toggles(tmp_path / "b")
    assert [r["sha256"] for r in r1] == [r["sha256"] for r in r2]


# --- sonda de coincidencia -------------------------------------------------

def test_normalizacion():
    assert pm.norm("Widgets — eliminación.") == "widgets"
    assert pm.norm("Start Menu Recommendations.") == "startmenurecommendations"
    assert pm.norm("W&auml;hle — x") == "wahle"


def test_coincidencia_exacta_contencion_ninguna():
    labels = [("winutil:tweak:A", "Game Mode"), ("winutil:tweak:B", "Widgets")]
    assert pm.match("Game Mode.", labels) == ("exacta", "winutil:tweak:A")
    assert pm.match("Disable Widgets now", labels)[0] == "contencion"
    assert pm.match("Totally Unrelated", labels) == ("ninguna", "")


def test_sonda_totales(tmp_path):
    md = tmp_path / "INV.md"
    md.write_text(
        "# INVENTARIO_USUARIO (test)\n\n"
        "- SECCION UNO  \n"
        "WinUtil  \n"
        "Game Mode.  \n"
        "Ruido total.  \n"
        "AtlasOS  \n"
        "Remove Edge.  \n",
        encoding="utf-8")
    win = tmp_path / "w.tsv"
    win.write_text("item_id\tsource\tsource_ref\tlabel\tkind\tsha256\tattrs_json\n"
                   "winutil:tweak:A\tc\tc#A\tGame Mode\ttweak\th\t{}\n",
                   encoding="utf-8")
    atl = tmp_path / "a.tsv"
    atl.write_text(
        "item_id\tsource\tsource_ref\tlabel\tkind\tcategory\tsha256\tattrs_json\n"
        "atlas:toggle:RemoveEdge\ta\tc\tRemoveEdge\ttoggle\tGeneral\th\t{}\n",
        encoding="utf-8")
    out = tmp_path / "out.tsv"
    assert pm.main(["--inventory", str(md), "--winutil", str(win),
                    "--atlas", str(atl), "--out", str(out)]) == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8"), delimiter="\t"))
    kinds = {(r["fuente"], r["linea"]): r["tipo_coincidencia"] for r in rows}
    assert kinds[("winutil", "Game Mode.")] == "exacta"
    assert kinds[("winutil", "Ruido total.")] == "ninguna"
    assert kinds[("atlas", "Remove Edge.")] == "exacta"
