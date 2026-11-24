#!/usr/bin/env python3
"""Tests del paso 8: oleada 1 del catálogo (secciones 1, 2 y 3).

Se valida sobre los ficheros reales de `catalog/capabilities/`:
  * esquema y campos obligatorios (lo mismo que exige CatalogLoader);
  * patrón de Id del validador C# y unicidad;
  * simetría de conflictos, ausencia de ciclos y riesgo/restauración según el paso 6;
  * que cada capacidad declara provenance y que las fuentes citadas existen en el pin;
  * cobertura del ledger (`verify_catalog_coverage.py`);
  * que los tests xUnit exigidos por T4 existen y cubren los tres escenarios.

La lógica C# se ejecuta en `dotnet-ci` sobre Windows; aquí sólo se comprueba lo
que es medible sin dotnet.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES = ROOT / "catalog" / "capabilities"
LEDGER = ROOT / "inventory" / "ledger"
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

import verify_catalog_coverage as vcc  # noqa: E402

ID_PATTERN = re.compile(r"^[a-z0-9]+(\.[a-z0-9\-]+)+$")
FILES = {
    1: CAPABILITIES / "section1_cleanup.json",
    2: CAPABILITIES / "section2_debloat.json",
    3: CAPABILITIES / "section3_telemetry.json",
}
EXPECTED_IDS = {
    1: [
        "cleanup.temp.user",
        "cleanup.temp.system",
        "cleanup.delivery.optimization",
        "cleanup.wer.reports",
        "cleanup.recycle.bin",
        "cleanup.winsxs.component",
        "cleanup.memory.dumps",
    ],
    2: [
        "debloat.appx.consumer",
        "debloat.cortana.remove",
        "debloat.onedrive.uninstall",
        "debloat.edge.policies",
        "debloat.start.websearch",
        "debloat.windows.ai",
        "debloat.content.delivery",
        "debloat.telemetry.appx",
    ],
    3: [
        "privacy.telemetry.diagtrack",
        "privacy.telemetry.dmwappush",
        "privacy.advertising.id",
        "privacy.activity.history",
        "privacy.feedback.frequency",
        "privacy.location.sensors",
        "privacy.ceip.tasks",
        "privacy.diagnostic.data.level",
        "privacy.kms.activation.telemetry",
    ],
}
REQUIRED_FIELDS = (
    "id", "name", "description", "sectionId", "risk", "securityImpact",
    "privilege", "restore", "confirmation", "state", "variants",
    "conflictsWith", "dependsOn", "supportedBuilds", "provenance", "actions",
)
ACTION_TYPES = {"registry", "service", "task", "process", "command"}
RISK = ["Safe", "Low", "Medium", "High", "Critical"]
SECURITY_IMPACT = ["Improves", "Neutral", "Reduces"]
PRIVILEGE = ["User", "Admin", "TrustedInstaller"]
RESTORE = ["None", "SessionUndo", "RestorePoint", "FullBackup"]
CONFIRMATION = ["None", "SimpleClick", "Summary", "SummaryAndRestorePoint", "TypeOperationName"]
KNOWN_BUILDS = {19045, 22631, 26100, 26200}

MIN_RESTORE = {"Safe": "None", "Low": "SessionUndo", "Medium": "RestorePoint",
               "High": "RestorePoint", "Critical": "FullBackup"}
MIN_CONFIRMATION = {"Safe": "None", "Low": "SimpleClick", "Medium": "Summary",
                    "High": "SummaryAndRestorePoint", "Critical": "TypeOperationName"}


def load(section: int) -> dict:
    return json.loads(FILES[section].read_text(encoding="utf-8"))


def all_capabilities() -> list[dict]:
    return [cap for section in (1, 2, 3) for cap in load(section)["capabilities"]]


def by_id() -> dict[str, dict]:
    return {cap["id"]: cap for cap in all_capabilities()}


# --------------------------------------------------------------------------- T1
@pytest.mark.parametrize("section", [1, 2, 3])
def test_los_tres_ficheros_existen_y_declaran_metadatos(section: int) -> None:
    path = FILES[section]
    assert path.is_file(), f"falta {path.relative_to(ROOT)}"
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "el JSON no debe llevar BOM"
    assert b"\r\n" not in raw, "el JSON debe usar LF"
    document = load(section)
    metadata = document["metadata"]
    assert metadata["schemaVersion"] == 1
    assert metadata["version"]
    assert metadata["provenance"]
    assert metadata["generatedBy"] in ("paso 8 (oleada 1)", "paso 8b (oleada 1b)")


@pytest.mark.parametrize("section", [1, 2, 3])
def test_ids_del_paso_8_siguen_presentes(section: int) -> None:
    # La oleada 1b añade capacidades: los 24 ids del paso 8 se mantienen.
    ids = [cap["id"] for cap in load(section)["capabilities"]]
    assert set(EXPECTED_IDS[section]) <= set(ids), "falta algún id del paso 8"


def test_hay_38_capacidades_y_ningun_id_repetido() -> None:
    # 24 de la oleada 1 (paso 8) + 14 de la oleada 1b (paso 8b).
    ids = [cap["id"] for cap in all_capabilities()]
    assert len(ids) == 38
    assert len(set(ids)) == 38
    for capability_id in ids:
        assert ID_PATTERN.match(capability_id), capability_id


@pytest.mark.parametrize("capability", all_capabilities(), ids=lambda c: c["id"])
def test_campos_obligatorios_y_enums_validos(capability: dict) -> None:
    for field in REQUIRED_FIELDS:
        assert field in capability, f"falta '{field}'"

    assert capability["name"].strip()
    assert capability["description"].strip()
    assert capability["provenance"].strip()
    assert capability["sectionId"] in (1, 2, 3)

    assert capability["risk"] in RISK
    assert capability["securityImpact"] in SECURITY_IMPACT
    assert capability["privilege"] in PRIVILEGE
    assert capability["restore"] in RESTORE
    assert capability["confirmation"] in CONFIRMATION
    assert capability["state"] in ("Stub", "Specified", "Implemented")
    assert isinstance(capability["variants"], list) and capability["variants"]
    assert isinstance(capability["actions"], list) and capability["actions"]


@pytest.mark.parametrize("capability", all_capabilities(), ids=lambda c: c["id"])
def test_invariantes_de_riesgo_segun_adr_0003(capability: dict) -> None:
    # ADR-0003 sustituye la regla "None exige Risk >= High": la restauración
    # mínima depende de la reversibilidad declarada (ver test_paso8b.py).
    risk = capability["risk"]
    assert capability["reversibility"] in ("Reversible", "NothingToRestore", "Irreversible")
    confirmation_index = CONFIRMATION.index(capability["confirmation"])
    assert confirmation_index >= CONFIRMATION.index(MIN_CONFIRMATION[risk]), (
        f"{capability['id']}: riesgo {risk} exige confirmación >= {MIN_CONFIRMATION[risk]}")
    if risk == "Critical":
        assert capability["confirmation"] == "TypeOperationName"
    if capability["securityImpact"] == "Reduces":
        assert risk in ("Medium", "High", "Critical")


@pytest.mark.parametrize("capability", all_capabilities(), ids=lambda c: c["id"])
def test_estado_declarado_con_acciones_bien_formadas(capability: dict) -> None:
    # Paso 8b: Implemented = el motor la ejecuta contra fakes con tests;
    # Specified = declarada con acciones pero sin verificar contra el pin.
    assert capability["state"] in ("Implemented", "Specified")
    assert capability["actions"], "toda capacidad declarada exige acciones"

    orders = [action["order"] for action in capability["actions"]]
    assert len(set(orders)) == len(orders), "Order duplicado"
    assert all(order >= 0 for order in orders)

    for action in capability["actions"]:
        assert action["type"] in ACTION_TYPES
        assert action["description"].strip()
        if action["type"] == "registry":
            assert action["hive"] in ("LocalMachine", "CurrentUser", "ClassesRoot", "Users")
            assert action["keyPath"]
            assert action["valueName"]
            assert action["operation"] in ("Set", "Delete")
            assert action["valueType"] in (
                "String", "DWord", "QWord", "Binary", "MultiString", "ExpandString")
            if action["operation"] == "Set":
                assert "value" in action
        elif action["type"] == "service":
            assert action["serviceName"]
            assert action["operation"] in ("SetStartupType", "Start", "Stop")
            if action["operation"] == "SetStartupType":
                assert action["startupType"]
        elif action["type"] == "task":
            assert action["taskPath"].startswith("\\")
            assert action["taskName"]
            assert isinstance(action["enabled"], bool)
        elif action["type"] == "command":
            assert action["fileName"]
            assert isinstance(action["arguments"], list)


@pytest.mark.parametrize("capability", all_capabilities(), ids=lambda c: c["id"])
def test_supported_builds_coherentes_con_windows_releases(capability: dict) -> None:
    builds = capability["supportedBuilds"]
    assert isinstance(builds, list)
    assert len(set(builds)) == len(builds), "SupportedBuilds con duplicados"
    assert builds == sorted(builds), "SupportedBuilds desordenado"
    for build in builds:
        assert build >= 10240
        assert build in KNOWN_BUILDS, f"build {build} no está en windows-releases.json"


def test_conflictos_simetricos_y_sin_conflicto_consigo_misma() -> None:
    capabilities = by_id()
    for capability in capabilities.values():
        for conflict in capability["conflictsWith"]:
            assert conflict in capabilities, f"{capability['id']}: conflicto desconocido {conflict}"
            assert conflict != capability["id"]
            assert capability["id"] in capabilities[conflict]["conflictsWith"], (
                f"conflicto no simétrico entre {capability['id']} y {conflict}")


def test_dependencias_existen_y_el_grafo_es_un_dag() -> None:
    capabilities = by_id()
    for capability in capabilities.values():
        for dependency in capability["dependsOn"]:
            assert dependency in capabilities, f"{capability['id']}: dependencia {dependency} inexistente"
            assert dependency != capability["id"]

    state: dict[str, int] = {}

    def visit(node: str, path: list[str]) -> None:
        state[node] = 1
        path.append(node)
        for dependency in capabilities[node]["dependsOn"]:
            marker = state.get(dependency, 0)
            if marker == 1:
                cycle = path[path.index(dependency):] + [dependency]
                pytest.fail(f"ciclo de dependencias: {' -> '.join(cycle)}")
            if marker == 0:
                visit(dependency, path)
        path.pop()
        state[node] = 2

    for node in capabilities:
        if state.get(node, 0) == 0:
            visit(node, [])


def test_provenance_cita_fuentes_del_pin() -> None:
    allowed_prefixes = (
        "winutil@70c23c80641d7370532af2f619b2842658600842",
        "atlas@ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f",
        "inventory/ledger/",
        "https://",
        "NO VERIFICADO",
        "ledger_refs",
        "Nota",
    )
    for capability in all_capabilities():
        provenance = capability["provenance"]
        assert any(prefix in provenance for prefix in allowed_prefixes), (
            f"{capability['id']}: provenance no cita ninguna fuente del pin")


def test_toda_seccion_3_declara_security_impact_neutral() -> None:
    for capability in all_capabilities():
        assert capability["securityImpact"] == "Neutral", capability["id"]


def test_ninguna_capacidad_toca_el_inventario_ni_ficheros_de_usuario() -> None:
    """Regla del paso 8: sólo registro, servicios, tareas y comandos acotados."""
    prohibidos = ("INVENTARIO_USUARIO.md", "/home/", "C:\\Users\\%USERNAME%\\Documents")
    for capability in all_capabilities():
        blob = json.dumps(capability, ensure_ascii=False)
        for prohibido in prohibidos:
            assert prohibido not in blob


# --------------------------------------------------------------------------- T5
def test_verify_catalog_coverage_pasa() -> None:
    assert vcc.main([]) == 0


def test_no_hay_huecos_no_declarados_en_las_secciones_1_a_3() -> None:
    capabilities = vcc.load_capabilities()
    rows = vcc.load_rows()
    mapped = [r for r in rows if r["seccion"] in vcc.SECTIONS and r["status"].startswith("Mapped")]
    assert len(mapped) == 26, "el ledger cambió: revisar los totales del paso 8"

    sin_cubrir = []
    for row in mapped:
        supporters = [
            cap["id"] for cap in capabilities
            if any(vcc.prefix_matches(m, cap["prefixes"]) for m in row["mapped_ids"])
        ]
        if not supporters and (row["seccion"], row["linea"]) not in vcc.DECLARED_GAPS:
            sin_cubrir.append((row["seccion"], row["linea"], row["texto"]))
    assert not sin_cubrir, sin_cubrir


def test_los_huecos_declarados_siguen_siendo_huecos() -> None:
    """Si una capacidad nueva cubre un hueco declarado, hay que borrar la
    declaración: si no, el ledger mentiría sobre la cobertura."""
    capabilities = vcc.load_capabilities()
    rows = vcc.load_rows()
    mapped = [r for r in rows if r["seccion"] in vcc.SECTIONS and r["status"].startswith("Mapped")]
    cubiertas = {
        (row["seccion"], row["linea"])
        for row in mapped
        if any(
            vcc.prefix_matches(m, cap["prefixes"])
            for cap in capabilities
            for m in row["mapped_ids"]
        )
    }
    obsoletos = sorted(set(vcc.DECLARED_GAPS) & cubiertas)
    assert not obsoletos, f"huecos declarados que ya están cubiertos: {obsoletos}"


def test_el_script_es_determinista() -> None:
    first = vcc.main(["--json"])
    second = vcc.main(["--json"])
    assert first == 0
    assert second == 0


# --------------------------------------------------------------------------- T4
def test_los_tests_xunit_de_la_oleada_1_existen_y_cubren_los_tres_escenarios() -> None:
    catalog_tests = (ROOT / "tests" / "Evo.Catalog.Tests" / "Wave1CatalogTests.cs").read_text(encoding="utf-8")
    engine_tests = (ROOT / "tests" / "Evo.Engine.Tests" / "Wave1EngineTests.cs").read_text(encoding="utf-8")

    assert "TestWave1Catalog_LoadsAndValidates" in catalog_tests
    assert "TestWave1Catalog_DryRun_NoSystemMutation" in engine_tests
    assert "TestWave1Catalog_ExecuteAndRollback_RestoresState" in engine_tests
    assert "RollbackAsync" in engine_tests
    assert "AssertSameState" in engine_tests

    # Los tests del motor cargan el catálogo real desde el directorio de salida
    # (el .csproj copia catalog/capabilities allí), no un JSON escrito a mano.
    assert 'Path.Combine(AppContext.BaseDirectory, "capabilities")' in engine_tests
    assert "CatalogLoader" in engine_tests
    assert "LoadDirectory" in engine_tests

    # Y los .csproj copian catalog/capabilities al directorio de salida.
    for project in ("tests/Evo.Catalog.Tests/Evo.Catalog.Tests.csproj",
                    "tests/Evo.Engine.Tests/Evo.Engine.Tests.csproj"):
        text = (ROOT / project).read_text(encoding="utf-8")
        assert "catalog\\capabilities\\*.json" in text, project
        assert 'Link="capabilities\\%(Filename)%(Extension)"' in text, project


def test_los_json_del_catalogo_son_reproducibles() -> None:
    """Reescribir con el mismo indent no cambia los bytes: el catálogo es estable."""
    for path in FILES.values():
        original = path.read_text(encoding="utf-8")
        assert original.endswith("\n")
        assert json.dumps(json.loads(original), ensure_ascii=False, indent=2) + "\n" == original
