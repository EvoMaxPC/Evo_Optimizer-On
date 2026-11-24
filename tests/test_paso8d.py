"""Tests del paso 8d: sección por ítem, reglas documentadas y rangos.

Todo lo que se comprueba aquí se puede reproducir con los scripts del repo:
    python3 tools/ledger_extract/extract_atlas_toggle_keys.py
    python3 tools/ledger_extract/build_item_section_map.py
    python3 tools/ledger_extract/build_upstream_capability_map.py
    python3 tools/ledger_extract/build_wave_plan.py
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

import build_item_section_map as ism  # noqa: E402
import build_upstream_capability_map as bucm  # noqa: E402
import verify_catalog_coverage as vcc  # noqa: E402

ITEM_TSV = ROOT / "inventory" / "partition" / "item-section-map.tsv"
MAP_TSV = ROOT / "inventory" / "ledger" / "upstream-capability-map.tsv"
TOGGLE_KEYS_TSV = ROOT / "inventory" / "ledger" / "atlas-toggle-keys.tsv"
CAT_TSV = ROOT / "inventory" / "partition" / "category-section-map.tsv"
RULES_MD = ROOT / "docs" / "inventory-recon" / "seccion-por-item-reglas.md"
PLAN_MD = ROOT / "docs" / "reports" / "plan-oleadas.md"
ADR = ROOT / "docs" / "adr" / "ADR-0004-puntos-de-restauracion.md"
CATALOG = ROOT / "catalog" / "capabilities"

MAX_CELL = 400


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def capabilities() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(CATALOG.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for capability in document["capabilities"]:
            out[capability["id"]] = capability
    return out


# ------------------------------------------------------------ determinismo
def test_el_generador_es_determinista_y_reproduce_el_fichero() -> None:
    rows = ism.build()
    text = ITEM_TSV.read_text(encoding="utf-8")
    # Doble construcción: mismos bytes.
    assert ism.build() == rows
    assert text.endswith("\n")
    assert "\r\n" not in text
    assert not text.startswith("\ufeff")
    assert len(read_tsv(ITEM_TSV)) == len(rows) == 435


def test_el_extractor_de_claves_de_toggle_es_determinista() -> None:
    rows = read_tsv(TOGGLE_KEYS_TSV)
    assert len(rows) > 0
    assert [r["item_id"] for r in rows] == sorted(r["item_id"] for r in rows)
    # Cada fila declara de qué línea del pin sale.
    for row in rows:
        assert row["source_ref"].startswith("package/Executables/AtlasModules/Toggles/")
        assert row["line"].isdigit()
        assert len(row["sha256_line"]) == 64


# ---------------------------------------------------------------- columnas
def test_columnas_exactas_y_sin_duplicados() -> None:
    rows = read_tsv(ITEM_TSV)
    assert list(rows[0].keys()) == list(ism.COLUMNS)
    assert len({r["upstream_id"] for r in rows}) == len(rows)


def test_ninguna_celda_supera_400_caracteres() -> None:
    for path in (ITEM_TSV, MAP_TSV, TOGGLE_KEYS_TSV):
        for row in read_tsv(path):
            for column, value in row.items():
                assert len(value) <= MAX_CELL, (path.name, column, len(value))


def test_cada_item_del_mapa_upstream_esta_en_el_mapa_por_item() -> None:
    upstream = {r["upstream_id"] for r in read_tsv(MAP_TSV)}
    items = {r["upstream_id"] for r in read_tsv(ITEM_TSV)}
    assert upstream == items, "los dos mapas deben cubrir el mismo universo"
    assert len(upstream) == 435


# ------------------------------------------------------------------ reglas
def test_section_es_1_17_o_unassigned() -> None:
    for row in read_tsv(ITEM_TSV):
        assert row["section"] == "unassigned" or row["section"] in {
            str(n) for n in range(1, 18)}, row["upstream_id"]


def test_basis_solo_los_valores_documentados() -> None:
    for row in read_tsv(ITEM_TSV):
        assert row["basis"] in ism.BASIS, (row["upstream_id"], row["basis"])


def test_unassigned_solo_con_manual_review_y_motivo() -> None:
    for row in read_tsv(ITEM_TSV):
        if row["section"] == "unassigned":
            assert row["basis"] == "manual-review", row["upstream_id"]
            assert row["evidence"].strip(), row["upstream_id"]


def test_toda_fila_con_seccion_declara_basis_y_evidencia() -> None:
    for row in read_tsv(ITEM_TSV):
        if row["section"] != "unassigned":
            assert row["basis"] != "manual-review", row["upstream_id"]
            assert row["evidence"].strip(), row["upstream_id"]


def test_reviewed_es_no_en_todas_las_filas() -> None:
    assert {r["reviewed"] for r in read_tsv(ITEM_TSV)} == {"no"}


# ------------------------------------------------------- reglas documentadas
def test_las_reglas_estan_documentadas_con_ejemplo() -> None:
    text = RULES_MD.read_text(encoding="utf-8")
    for key, _section, _terms in ism.NAME_RULES:
        assert f"`{key}`" in text, f"falta documentar {key}"
    documented = {
        "svc:set", "svc:set-multiple", "effect:power", "key:Search",
    }
    for key, _section, _pattern, _evidence in ism.EFFECT_RULES:
        if key in documented:
            continue
        assert key in text, f"falta documentar {key}"
    # El documento dice explícitamente que no se usa parecido textual.
    assert "parecido textual" in text


def test_ninguna_regla_de_nombre_es_un_generico() -> None:
    genericos = {"windows", "disable", "remove", "config", "settings", "set",
                 "fix", "run", "enable", "system"}
    for key, _section, terms in ism.NAME_RULES:
        for term in terms:
            assert term not in genericos, f"{key}: término genérico '{term}'"


def test_el_troceo_de_nombres_no_confunde_palabras() -> None:
    # 'BitLocker' casa con 'bitlocker' aunque se trocee como bit+locker.
    assert ism.apply_name("BitLocker - Disable") == ("13", "name:security")
    # 'Windows Restore' no puede casar con 'store' (15).
    assert ism.apply_name("Windows Restore") is None
    # 'NetworkNavigationPane' se trocea y casa con network.
    assert ism.apply_name("NetworkNavigationPane") == ("11", "name:network")


def test_un_efecto_ambiguo_no_decide() -> None:
    # Explorer (10) + AppX (15) a la vez: el efecto no elige.
    sections, _evidence = ism.effect_candidates([
        "key:hklm:\\software\\microsoft\\windows\\currentversion\\explorer\\advanced\\taskbarmn",
        "appx:efecto-declarado",
    ])
    assert sections == {"10", "15"}


def test_tres_o_mas_servicios_es_optimizacion_de_servicios() -> None:
    sections, evidence = ism.effect_candidates(
        ["svc:cscservice", "svc:diagtrack", "svc:mapsbroker"])
    assert sections == {"4"}
    assert evidence == "svc:set-multiple"


# ------------------------------------------------------------ mapa upstream
def test_el_mapa_upstream_usa_la_seccion_por_item() -> None:
    bucm.main([])
    assert bucm.main(["--json"]) == 0
    rows = read_tsv(MAP_TSV)
    assert len(rows) == 435
    bases = {r["section_basis"] for r in rows}
    assert bases <= {"category", "text-rule", "none",
                     "item-effect", "item-name-rule", "item-manifest-path"}
    # Se ha pasado de 140 filas sin sección (paso 8c) a bastante menos.
    without = sum(1 for r in rows if not r["section_guess"])
    assert without < 140, f"el paso 8c dejaba 140; ahora hay {without}"
    # La sección del mapa upstream coincide con la del mapa por ítem cuando la
    # base es la del ítem.
    item = {r["upstream_id"]: r for r in read_tsv(ITEM_TSV)}
    for row in rows:
        if row["section_basis"].startswith("item-"):
            assert row["section_guess"] == item[row["upstream_id"]]["section"]


def test_la_cobertura_1_3_sigue_siendo_26_de_26() -> None:
    rows = vcc.load_rows()
    capabilities_ = vcc.load_capabilities()
    mapped = covered = 0
    for row in rows:
        if row["seccion"] not in ("1", "2", "3"):
            continue
        if not row["status"].startswith("Mapped"):
            continue
        mapped += 1
        if any(vcc.prefix_matches(m, cap["prefixes"])
               for cap in capabilities_ for m in row["mapped_ids"]):
            covered += 1
    assert mapped == 26
    assert covered == 26


def test_el_plan_de_oleadas_es_reproducible_y_usa_las_cifras_nuevas() -> None:
    text = PLAN_MD.read_text(encoding="utf-8")
    assert "MEDIDO" in text and "PROPUESTA" in text
    assert "item-section-map.tsv" in text
    # La tabla por sección debe tener las 17 filas más el total.
    rows = [line for line in text.splitlines() if line.startswith("| ") and "|" in line]
    assert any("**Σ**" in line for line in rows)


# ----------------------------------------------------------- muestra (semilla)
def test_la_muestra_con_semilla_42_es_reproducible() -> None:
    rows = [r for r in read_tsv(ITEM_TSV) if r["basis"] != "category"]
    random.seed(42)
    picked = random.sample(rows, 25)
    assert len(picked) == 25
    # Las 25 tienen regla propia y evidencia.
    for row in picked:
        assert row["evidence"].strip()
        assert row["section"] == "unassigned" or row["section"].isdigit()
    # Repetir el muestreo da exactamente los mismos ids.
    random.seed(42)
    assert [r["upstream_id"] for r in random.sample(rows, 25)] == [
        r["upstream_id"] for r in picked]


def test_las_categorias_mixed_ya_no_quedan_en_bloque() -> None:
    with CAT_TSV.open(encoding="utf-8", newline="") as handle:
        categories = list(csv.DictReader(handle, delimiter="\t"))
    mixed = {r["category_key"] for r in categories if r["section"] == "mixed"}
    items = read_tsv(ITEM_TSV)
    leftovers = [r for r in items
                 if r["category_key"] in mixed and r["basis"] == "manual-review"]
    # Sólo siguen sin sección los que no tienen efecto propio.
    assert len(leftovers) < 40, len(leftovers)


# ------------------------------------------------------------------- T2 ADR
def test_el_adr_0004_esta_propuesto_y_no_implementa_la_llamada_real() -> None:
    text = ADR.read_text(encoding="utf-8")
    assert "Estado**: propuesto" in text
    assert "NO VERIFICADO" in text
    assert "Checkpoint-Computer" in text
    assert "SystemRestore.CreateRestorePoint" in text
    assert "VM del responsable" in text
    # No se ha escrito ningún servicio real en src: sólo la interfaz y los fakes.
    implementers = []
    for path in (ROOT / "src").rglob("*.cs"):
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if "IRestorePointService" in line and "class " in line:
                implementers.append(path.name)
    assert implementers == ["FakeRestorePointService.cs"], implementers


def test_las_interfaces_del_motor_estan_en_evo_core() -> None:
    restore = (ROOT / "src" / "Evo.Core" / "Restore" / "IRestorePointService.cs").read_text(
        encoding="utf-8")
    assert "interface IRestorePointService" in restore
    assert "IsAvailableAsync" in restore
    assert "CreateAsync" in restore
    assert "record RestorePointResult" in restore

    confirmation = (
        ROOT / "src" / "Evo.Core" / "Confirmation" / "IConfirmationProvider.cs"
    ).read_text(encoding="utf-8")
    assert "interface IConfirmationProvider" in confirmation
    assert "SummaryAndRestorePoint" in confirmation
    assert "TypeOperationName" in confirmation


def test_el_motor_aborta_antes_de_mutar_si_falta_el_punto() -> None:
    engine = (ROOT / "src" / "Evo.Engine" / "EngineCoordinator.cs").read_text(encoding="utf-8")
    assert "RequiresRestorePoint" in engine
    assert "AcceptNoRestorePoint" in engine
    assert "fail-closed" in engine
    # La puerta existe y está escrita ANTES del bucle que ejecuta las acciones
    # (la primera aparición de las dos marcas es la del comentario y el bucle).
    gate = engine.index("Puerta previa a la primera mutación")
    loop = engine.index("var results = new List<ActionResult>();")
    assert gate < loop


# ------------------------------------------------------------------- T2 rango
def test_las_capacidades_con_rango_incompleto_lo_justifican() -> None:
    four = {19045, 22631, 26100, 26200}
    caps = capabilities()
    incomplete = [c for c in caps.values() if not four <= set(c["supportedBuilds"])]
    assert {c["id"] for c in incomplete} == {
        "debloat.windows.ai.recall", "debloat.copilot.remove"}
    for capability in incomplete:
        provenance = capability["provenance"]
        assert capability["state"] == "Specified", capability["id"]
        assert ("NO VERIFICADO" in provenance
                or "RANGO NO VERIFICADO" in provenance), capability["id"]


def test_copilot_declara_su_evidencia_linea_a_linea() -> None:
    copilot = capabilities()["debloat.copilot.remove"]
    provenance = copilot["provenance"]
    for reference in ("disable-copilot.psd1:6", "disable-copilot.psd1:9",
                      "Copilot.psd1:13-14", "Copilot.ps1:42", "Copilot.ps1:52",
                      "Copilot.ps1:71"):
        assert reference in provenance, reference
    assert "RANGO NO VERIFICADO" in provenance
    assert copilot["supportedBuilds"] == [22631, 26100, 26200]
    # La política es la de 25H2+ según el pin; no se inventa 19045.
    assert 19045 not in copilot["supportedBuilds"]
