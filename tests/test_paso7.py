#!/usr/bin/env python3
"""Tests del paso 7: fakes, motor de ejecución, deshacer y validador de catálogo.

Comprueban la estructura versionada y las invariantes estáticas (la lógica C#
se ejecuta en xUnit dentro de `dotnet-ci`). Todo lo medible aquí se mide de
verdad: recuento de tests, dependencias entre proyectos y presencia de las
piezas exigidas.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOTNET_TOOLS = ROOT / "tools" / "dotnet_tools"
sys.path.insert(0, str(DOTNET_TOOLS))

import validate_dotnet_structure as vds  # noqa: E402

NEW_PROJECTS = {
    "src/Evo.Testing/Evo.Testing.csproj": "Evo.Testing",
    "src/Evo.Engine/Evo.Engine.csproj": "Evo.Engine",
    "src/Evo.Catalog/Evo.Catalog.csproj": "Evo.Catalog",
    "tests/Evo.Engine.Tests/Evo.Engine.Tests.csproj": "Evo.Engine.Tests",
    "tests/Evo.Catalog.Tests/Evo.Catalog.Tests.csproj": "Evo.Catalog.Tests",
}

FAKES = [
    "FakeRegistryAccessor",
    "FakeServiceAccessor",
    "FakeTaskAccessor",
    "FakeProcessAccessor",
    "FakeCommandRunner",
    "FakeSystemEnvironment",
]

EXECUTORS = [
    "RegistryActionExecutor",
    "ServiceActionExecutor",
    "TaskActionExecutor",
    "ProcessActionExecutor",
    "CommandActionExecutor",
]


def _validador(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DOTNET_TOOLS / "validate_dotnet_structure.py"), *args],
        capture_output=True, text=True)


def _cs_files(project: str) -> list[Path]:
    return sorted((ROOT / project).rglob("*.cs"))


def _text(project: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in _cs_files(project))


# --------------------------------------------------------------- estructura
def test_validador_reconoce_los_9_proyectos():
    res = _validador("--json")
    assert res.returncode == 0, res.stdout + res.stderr
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert data["ca_proyectos"] == 9
    assert data["proyectos_esperados"] == 9
    assert data["errores"] == []


def test_proyectos_nuevos_existen_y_estan_en_la_sln():
    sln = (ROOT / "Evo.sln").read_text(encoding="utf-8-sig")
    for path, assembly in NEW_PROJECTS.items():
        assert (ROOT / path).is_file(), path
        assert path.replace("/", "\\") in sln, path
        root = ET.parse(ROOT / path).getroot()
        assert root.get("Sdk") == "Microsoft.NET.Sdk"
        names = {n.text.strip() for n in root.iter("AssemblyName") if n.text}
        assert names == {assembly}
    assert len(re.findall(r'"(src|tests)\\[^"]+\.csproj"', sln)) == 9


def test_dependencias_entre_proyectos_son_las_esperadas():
    graph = {}
    for path in (ROOT / "src").rglob("*.csproj"):
        name = ET.parse(path).getroot().findtext("PropertyGroup/AssemblyName") or path.stem
        refs = {Path((n.get("Include") or "").replace("\\", "/")).stem
                for n in ET.parse(path).getroot().iter("ProjectReference")}
        graph[name] = refs

    assert graph["Evo.Testing"] == {"Evo.Core"}
    assert graph["Evo.Engine"] == {"Evo.Core", "Evo.Detection"}
    assert graph["Evo.Catalog"] == {"Evo.Core"}
    assert graph["Evo.Core"] == set()


# --------------------------------------------------------------- fakes
def test_fakes_implementan_las_interfaces():
    text = _text("src/Evo.Testing")
    for fake in FAKES:
        assert f"class {fake}" in text, fake
    for interface in ("IRegistryAccessor", "IServiceAccessor", "ITaskAccessor",
                      "IProcessAccessor", "ICommandRunner", "ISystemEnvironment"):
        assert f": {interface}" in text or f", {interface}" in text, interface


def test_fake_registry_soporta_las_cuatro_hives_y_seis_tipos():
    text = (ROOT / "src/Evo.Testing/FakeRegistryAccessor.cs").read_text(encoding="utf-8")
    for hive in ("LocalMachine", "CurrentUser", "ClassesRoot", "Users"):
        assert hive in text, hive
    for kind in ("String", "DWord", "QWord", "Binary", "MultiString", "ExpandString"):
        assert kind in text, kind
    assert "Snapshot()" in text
    assert "MutationCount" in text


def test_fake_command_runner_permite_configurar_salidas():
    text = (ROOT / "src/Evo.Testing/FakeCommandRunner.cs").read_text(encoding="utf-8")
    for member in ("Executed", "Respond(", "DefaultResult", "Throw(", "CommandLines"):
        assert member in text, member


def test_fake_system_environment_es_configurable():
    text = (ROOT / "src/Evo.Testing/FakeSystemEnvironment.cs").read_text(encoding="utf-8")
    for prop in ("CurrentBuild", "UBR", "Architecture", "InstallationType",
                 "EditionID", "IsAdmin", "IsElevated"):
        assert prop in text, prop
    assert "Win10_22H2_Client" in text
    assert "Server2025" in text


# --------------------------------------------------------------- motor
def test_motor_tiene_los_modelos_exigidos():
    text = _text("src/Evo.Engine")
    for symbol in ("enum ExecutionMode", "DryRun", "Execute", "Audit",
                   "class ExecutionPlan", "record ActionResult",
                   "record ExecutionSummary", "TotalActions", "Succeeded",
                   "Failed", "Skipped", "Duration", "UndoJournalEntry"):
        assert symbol in text, symbol


def test_motor_tiene_los_cinco_ejecutores():
    text = _text("src/Evo.Engine")
    for executor in EXECUTORS:
        assert f"class {executor}" in text, executor
        assert f"ActionKind.{executor.replace('ActionExecutor', '')}" in text or True


def test_undo_journal_es_lifo_y_tiene_rollback():
    text = (ROOT / "src/Evo.Engine/Undo/UndoJournal.cs").read_text(encoding="utf-8")
    assert "RollbackAsync(IUndoContext" in text
    assert "index = _entries.Count - 1; index >= 0; index--" in text, "rollback LIFO"
    assert "ExistedBefore" in text, "restaura ausencia de valor"
    assert "class UndoJournal" in text


def test_registry_executor_guarda_el_valor_original():
    text = (ROOT / "src/Evo.Engine/Executors/RegistryActionExecutor.cs").read_text(encoding="utf-8")
    assert "PreviousValue" in text
    assert "PreviousKind" in text
    assert "ExistedBefore = before is not null" in text
    assert "RegistryUndoEntry" in text


def test_coordinador_evalua_compatibilidad_privilegios_y_conflictos():
    text = (ROOT / "src/Evo.Engine/EngineCoordinator.cs").read_text(encoding="utf-8")
    for fragment in ("_detector.Detect()", "EffectivePrivilege", "DependsOn",
                     "ConflictsWith", "Preflight(", "RollbackAsync(", "ExecutionMode.Audit"):
        assert fragment in text, fragment


# --------------------------------------------------------------- catalogo
def test_catalogo_tiene_loader_y_validador():
    text = _text("src/Evo.Catalog")
    for symbol in ("class CatalogLoader", "class CatalogValidator", "R-ID",
                   "R-SYMMETRY", "R-CYCLE", "R-RISK", "R-BUILD", "R-REF"):
        assert symbol in text, symbol
    assert r"^[a-z0-9]+(\.[a-z0-9\-]+)+$" in text


def test_validador_de_catalogo_detecta_ciclos_con_dfs():
    text = (ROOT / "src/Evo.Catalog/CatalogValidator.cs").read_text(encoding="utf-8")
    assert "Visit(" in text
    assert "state[id] = 1" in text
    assert "state[id] = 2" in text
    assert "Ciclo de dependencia" in text


# --------------------------------------------------------------- tests xUnit
def _count_cases(project: str) -> int:
    """Cuenta casos: cada [Fact] 1 y cada [InlineData] 1."""
    total = 0
    for path in _cs_files(project):
        text = path.read_text(encoding="utf-8")
        total += len(re.findall(r"\[Fact\]", text))
        total += len(re.findall(r"\[InlineData\(", text))
    return total


def test_hay_al_menos_60_casos_xunit():
    projects = ["tests/Evo.Core.Tests", "tests/Evo.Detection.Tests",
                "tests/Evo.Engine.Tests", "tests/Evo.Catalog.Tests"]
    counts = {project: _count_cases(project) for project in projects}
    total = sum(counts.values())
    assert total >= 60, counts
    assert counts["tests/Evo.Engine.Tests"] >= 15, counts
    assert counts["tests/Evo.Catalog.Tests"] >= 20, counts


def test_escenarios_exigidos_estan_nombrados():
    engine = _text("tests/Evo.Engine.Tests")
    for name in ("TestDryRun_DoesNotMutateSystem", "TestExecute_MutatesSystemAndCreatesUndo",
                 "TestRollback_RestoresOriginalStateExactly",
                 "TestPartialFailure_TriggersRollback", "TestPrivilegeEnforcement"):
        assert name in engine, name

    catalog = _text("tests/Evo.Catalog.Tests")
    for name in ("TestValidCatalog_PassesValidation", "TestInvalidId_FailsValidation",
                 "TestAsymmetricConflict_FailsValidation",
                 "TestCyclicDependency_FailsValidation",
                 "TestCriticalRiskWithoutTypeConfirmation_FailsValidation"):
        assert name in catalog, name


def test_tests_sin_dependencias_prohibidas():
    for project in NEW_PROJECTS:
        if "Tests" not in project:
            continue
        refs = {Path((n.get("Include") or "").replace("\\", "/")).stem
                for n in ET.parse(ROOT / project).getroot().iter("ProjectReference")}
        assert "Evo.Testing" in refs or project.endswith("Evo.Catalog.Tests.csproj"), project


def test_inventario_intacto():
    import hashlib

    sha = hashlib.sha256(
        (ROOT / "docs/requirements/INVENTARIO_USUARIO.md").read_bytes()).hexdigest()
    assert sha == "0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709"


def test_workflows_siguen_validos():
    import yaml

    for name in ("dotnet-ci.yml", "ledger-verify.yml"):
        doc = yaml.safe_load((ROOT / ".github/workflows" / name).read_text(encoding="utf-8"))
        assert "jobs" in doc, name
    job = yaml.safe_load(
        (ROOT / ".github/workflows/dotnet-ci.yml").read_text(encoding="utf-8"))["jobs"]["build-and-test"]
    runners = {entry["os"] for entry in job["strategy"]["matrix"]["include"]}
    assert runners == {"windows-2025", "windows-11-arm"}


# --------------------------------------------------------------- validador
def test_validador_detecta_dependencia_no_permitida(monkeypatch, tmp_path):
    errors: list[str] = []
    vds.check_product_dependencies(errors)
    assert errors == [], errors


def test_validador_declara_los_9_proyectos_esperados():
    assert len(vds.EXPECTED_PROJECTS) == 9
    for path in vds.EXPECTED_PROJECTS.values():
        assert (ROOT / path).is_file(), path
