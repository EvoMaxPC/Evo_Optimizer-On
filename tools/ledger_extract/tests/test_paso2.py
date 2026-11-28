"""Tests del Paso 2: list_files, partition_check y carga de JSON tolerante.

Cubre:
  * list_files: extensión, top_dir, parseo de `git ls-tree -r -l`, verificación de SHA.
  * partition_check: sin clasificar, regla muerta, exclude prohibido, primera regla gana.
  * glob: `*` no cruza '/', `**` sí.
  * carga de JSON tolerante a utf-8-sig y strict=False.
  * integridad: las particiones reales del repo están limpias.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent            # tools/ledger_extract/tests
PKG = HERE.parent                                  # tools/ledger_extract
REPO = PKG.parents[1]                              # raíz del repo


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, PKG / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


lf = load("list_files")
pc = load("partition_check")


# --- list_files -------------------------------------------------------------

def test_extension_simple_y_sin_extension():
    assert lf.extension("config/tweaks.json") == "json"
    assert lf.extension("README.md") == "md"
    assert lf.extension(".gitignore") == ""          # dotfile sin extensión
    assert lf.extension("tools/uv.lock") == "lock"
    assert lf.extension("A.PS1") == "ps1"            # normaliza a minúsculas


def test_top_dir_raiz_y_anidado():
    assert lf.top_dir("package/Executables/x.cmd") == "package"
    assert lf.top_dir("README.md") == "."
    assert lf.top_dir(".github/workflows/x.yml") == ".github"


def test_parseo_de_ls_tree_linea_real():
    """Formato: <mode> SP <type> SP <object> SP+ <size> TAB <path>."""
    line = "100644 blob a4267d7b6a2ee0d0735e4ee5bc1733a27484ab4f     297\t.github/CODEOWNERS"
    meta, _, path = line.partition("\t")
    fields = meta.split()
    assert len(fields) == 4
    assert fields[2].startswith("a4267d7b")
    assert fields[3] == "297"
    assert path == ".github/CODEOWNERS"


def test_write_and_read_tsv_roundtrip(tmp_path):
    rows = [{"path": "a/b.ps1", "size": 10, "blob_sha": "abc", "ext": "ps1", "top_dir": "a"}]
    out = tmp_path / "x.files.tsv"
    lf.write_tsv(rows, out)
    text = out.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "path\tsize\tblob_sha\text\ttop_dir"
    assert text.splitlines()[1] == "a/b.ps1\t10\tabc\tps1\ta"


def test_list_tree_sobre_repo_git_real(tmp_path):
    """Un repo git mínimo: 2 ficheros, uno en subdirectorio."""
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@e.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a.ps1").write_text("x", encoding="utf-8")
    (repo / "d").mkdir()
    (repo / "d" / "b.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "c"], cwd=repo, check=True)

    rows = lf.list_tree(repo)
    by_path = {r["path"]: r for r in rows}
    assert set(by_path) == {"a.ps1", "d/b.json"}
    assert by_path["a.ps1"]["top_dir"] == "."
    assert by_path["d/b.json"]["top_dir"] == "d"
    assert by_path["d/b.json"]["ext"] == "json"
    assert all(len(r["blob_sha"]) == 40 for r in rows)


# --- glob -------------------------------------------------------------------

def test_glob_estrella_no_cruza_barra():
    assert pc.compile_glob("*.md").match("README.md")
    assert not pc.compile_glob("*.md").match("docs/a.md")


def test_glob_doble_estrella_cruza_barras():
    assert pc.compile_glob("package/**/*.cmd").match("package/A/B/x.cmd")
    assert pc.compile_glob("package/**/*.cmd").match("package/x.cmd")
    assert pc.compile_glob("tools/**").match("tools/dev/x.ps1")
    assert not pc.compile_glob("tools/**").match("other/tools/x.ps1")


def test_glob_case_insensitive():
    assert pc.compile_glob("package/**").match("Package/Executables/A.PS1")


# --- partition_check --------------------------------------------------------

def _setup(tmp_path, rules, files):
    part = tmp_path / "p.yml"
    part.write_text(yaml.safe_dump({"schema": 1, "repo": "t", "rules": rules}), encoding="utf-8")
    tsv = tmp_path / "t.files.tsv"
    lines = ["path\tsize\tblob_sha\text\ttop_dir"]
    lines += [f"{f}\t1\t{'a'*40}\t{f.rsplit('.',1)[-1]}\t{f.split('/')[0]}" for f in files]
    tsv.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return part, tsv


def test_sin_clasificar_falla(tmp_path):
    rules = [{"glob": "*.ps1", "treatment": "extract", "reason": "r"}]
    part, tsv = _setup(tmp_path, rules, ["a.ps1", "b.json"])
    rep = pc.check_repo("t", part, tsv, tmp_path / "out")
    assert rep["unclassified"] == ["b.json"]
    assert not rep["ok"]


def test_regla_muerta_falla(tmp_path):
    rules = [
        {"glob": "*.ps1", "treatment": "extract", "reason": "r"},
        {"glob": "*.cmd", "treatment": "extract", "reason": "r"},
    ]
    part, tsv = _setup(tmp_path, rules, ["a.ps1"])
    rep = pc.check_repo("t", part, tsv, tmp_path / "out")
    assert [d["glob"] for d in rep["dead_rules"]] == ["*.cmd"]
    assert not rep["ok"]


def test_exclude_prohibido_sobre_comportamiento(tmp_path):
    rules = [{"glob": "**", "treatment": "exclude", "reason": "r"}]
    part, tsv = _setup(tmp_path, rules, ["functions/public/a.ps1", "logo.png"])
    rep = pc.check_repo("t", part, tsv, tmp_path / "out")
    assert [v["path"] for v in rep["exclude_violations"]] == ["functions/public/a.ps1"]
    assert not rep["ok"]


def test_exclude_sobre_binario_es_legal(tmp_path):
    rules = [{"glob": "*.png", "treatment": "exclude", "reason": "binario"}]
    part, tsv = _setup(tmp_path, rules, ["a.png"])
    rep = pc.check_repo("t", part, tsv, tmp_path / "out")
    assert rep["exclude_violations"] == []
    assert rep["ok"]


def test_primera_regla_gana(tmp_path):
    rules = [
        {"glob": "config/*.json", "treatment": "extract", "reason": "primera"},
        {"glob": "**", "treatment": "reference", "reason": "segunda"},
    ]
    part, tsv = _setup(tmp_path, rules, ["config/tweaks.json"])
    rep = pc.check_repo("t", part, tsv, tmp_path / "out")
    text = (tmp_path / "out" / "t.tsv").read_text(encoding="utf-8").splitlines()
    assert text[1] == "config/tweaks.json\textract\t1\tconfig/*.json"


@pytest.mark.parametrize("path,expected", [
    ("package/Pkg/x.cab", True),
    ("package/x.cab", True),
    ("docs/index.mdx", False),
])
def test_glob_package_cab_casa_en_ambas_profundidades(path, expected):
    assert bool(pc.compile_glob("package/**/*.cab").match(path)) is expected


@pytest.mark.parametrize("path,expected", [
    ("functions/public/Invoke-WPFButton.ps1", True),
    ("config/preset.json", True),
    ("app/src/main.rs", True),
    ("package/x.reg", True),
    ("docs/index.mdx", False),
    ("assets/logo.png", False),
])
def test_is_behaviour_path_clasificacion(path, expected):
    assert pc.is_behaviour_path(path) is expected


# --- carga tolerante de JSON ------------------------------------------------

def test_json_utf8_sig_y_control_chars(tmp_path):
    """utf-8-sig (BOM) + control chars -> strict=False."""
    p = tmp_path / "dirty.json"
    payload = '{"a": "linea\x01con control", "b": 1}'
    p.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))
    raw = p.read_text(encoding="utf-8-sig")
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw)
    data = json.loads(raw, strict=False)
    assert data["b"] == 1
    assert "\x01" in data["a"]


def test_recon_report_usa_carga_tolerante(tmp_path):
    rr = load("recon_report")
    p = tmp_path / "tweaks.json"
    p.write_bytes(b"\xef\xbb\xbf" + b'{"k1": {"x": "\x02"}, "k2": {}}')
    data = rr.load_json_tolerant(p)
    assert len(data) == 2


# --- integridad de las particiones reales -----------------------------------

@pytest.mark.parametrize("repo_name", ["winutil", "atlas"])
def test_particiones_reales_limpias(repo_name):
    part = REPO / "inventory" / "partition" / f"{repo_name}.yml"
    tsv = REPO / "inventory" / "upstream" / f"{repo_name}.files.tsv"
    if not tsv.is_file():
        pytest.skip(f"falta {tsv}; ejecuta list_files.py")
    rep = pc.check_repo(repo_name, part, tsv, REPO / "inventory" / "partition" / "results")
    assert rep["unclassified"] == []
    assert rep["dead_rules"] == []
    assert rep["exclude_violations"] == []
    assert rep["ok"]


# --- sonda de palabras clave con patrones (paso 2b) -------------------------

kp = load("keyword_probe")


def _synthetic_repos(tmp_path):
    """Dos repos mínimos: el término vive SOLO en el primero."""
    a = tmp_path / "winutil"
    b = tmp_path / "atlas"
    (a / "sub").mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "sub" / "tweak.ps1").write_text("Set-Item ... TimerResolution 5000\n", encoding="utf-8")
    (a / "readme.md").write_text("nada relevante\n", encoding="utf-8")
    (b / "script.ps1").write_text("Write-Host 'hola'\n", encoding="utf-8")
    return a, b


def test_orientacion_sonda_no_se_invierte(tmp_path):
    """Término presente solo en el repo A debe dar (n,0), nunca (0,n)."""
    a, b = _synthetic_repos(tmp_path)
    pats = kp.compile_all([r"timer.?resolution|TimerResolution"])
    hits_a = kp.scan(a, pats)
    hits_b = kp.scan(b, pats)
    assert (len(hits_a[0]), len(hits_b[0])) == (1, 0), (hits_a, hits_b)


def test_orientacion_con_varias_columnas(tmp_path):
    """Con 3 patrones, cada columna conserva su repo."""
    a, b = _synthetic_repos(tmp_path)
    pats = kp.compile_all([r"TimerResolution", r"nada relevante", r"Write-Host"])
    ha, hb = kp.scan(a, pats), kp.scan(b, pats)
    assert [len(x) for x in ha] == [1, 1, 0]
    assert [len(x) for x in hb] == [0, 0, 1]


def test_patrones_incluyen_variantes_sin_espacio():
    """Win32 Priority debe casar 'Win32PrioritySeparation' (sin espacio)."""
    entry = dict(kp.KEYWORD_PATTERNS)
    rx = __import__("re").compile(entry["Win32 Priority"], __import__("re").IGNORECASE)
    assert rx.search("Win32PrioritySeparation")
    assert rx.search("Win32 Priority")
    rx_hags = __import__("re").compile(entry["HAGS"], __import__("re").IGNORECASE)
    assert rx_hags.search('HwSchMode')


def test_catalogo_patrones_completo_y_compilable():
    assert len(kp.KEYWORD_PATTERNS) >= 88
    for term, pat in kp.KEYWORD_PATTERNS:
        assert term and pat
        __import__("re").compile(pat, __import__("re").IGNORECASE)
    # sin términos duplicados
    terms = [t for t, _ in kp.KEYWORD_PATTERNS]
    assert len(terms) == len(set(terms))


def test_section_probes_tienen_fuente_y_marcas_dudosas():
    fuentes = {f for _i, f, _p, _d in kp.SECTION_PROBES}
    assert fuentes == {"sec16:Atlas", "sec16:WinUtil", "sec17"}
    assert any(d for *_x, d in kp.SECTION_PROBES)   # hay "patron dudoso"
    for item, fuente, pat, dudoso in kp.SECTION_PROBES:
        assert item and pat and isinstance(dudoso, bool)
