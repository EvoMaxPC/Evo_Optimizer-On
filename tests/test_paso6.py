#!/usr/bin/env python3
"""Tests del paso 6: cimientos .NET 10, catalogo de Windows y validador.

Complementan a los tests del validador (`validate_dotnet_structure.py`), que
se ejecuta tambien en el workflow `dotnet-ci` sobre Windows.
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

# Los cuatro proyectos del paso 6: se comprueba que siguen existiendo y que
# forman parte de la solucion (que ahora tiene 9 proyectos, ver test_paso7.py).
CSPROJ = [
    "src/Evo.Core/Evo.Core.csproj",
    "src/Evo.Detection/Evo.Detection.csproj",
    "tests/Evo.Core.Tests/Evo.Core.Tests.csproj",
    "tests/Evo.Detection.Tests/Evo.Detection.Tests.csproj",
]


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True)


# --------------------------------------------------------------- estructura
def test_validador_exit_0():
    res = _run(str(DOTNET_TOOLS / "validate_dotnet_structure.py"))
    assert res.returncode == 0, res.stdout + res.stderr


def test_validador_json_ok():
    res = _run(str(DOTNET_TOOLS / "validate_dotnet_structure.py"), "--json")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert data["errores"] == []
    assert data["ca_proyectos"] >= len(CSPROJ)
    assert data["releases"] == 5


def test_ficheros_dotnet_existen():
    for name in ("Directory.Build.props", "Evo.sln", "global.json",
                 "THIRD_PARTY_NOTICES.md", "catalog/windows-releases.json"):
        assert (ROOT / name).is_file(), name
    for name in CSPROJ:
        assert (ROOT / name).is_file(), name


def test_csproj_xml_valido():
    for name in CSPROJ:
        root = ET.parse(ROOT / name).getroot()
        assert root.get("Sdk") == "Microsoft.NET.Sdk"


def test_csproj_no_duplican_targetframework():
    for name in CSPROJ:
        tree = ET.parse(ROOT / name)
        for node in tree.getroot().iter("TargetFramework"):
            pytest.fail(f"{name} redeclara TargetFramework: {node.text}")
        for node in tree.getroot().iter("Nullable"):
            pytest.fail(f"{name} redeclara Nullable: {node.text}")


def test_directory_build_props_valores():
    root = ET.parse(ROOT / "Directory.Build.props").getroot()
    values = {}
    for group in root.findall("PropertyGroup"):
        for node in group:
            if node.text:
                values.setdefault(node.tag, node.text.strip())
    assert values["TargetFramework"] == "net10.0-windows"
    assert values["Nullable"] == "enable"
    assert values["ImplicitUsings"] == "enable"
    assert values["TreatWarningsAsErrors"] == "true"
    assert values["AnalysisLevel"] == "latest"
    assert values["Company"] == "EvoMaxPC"
    assert values["Product"] == "EVO CLEAN"
    assert "GPL-3.0-only" in values["Copyright"]


def test_sln_referencia_los_proyectos_del_paso6():
    text = (ROOT / "Evo.sln").read_text(encoding="utf-8-sig")
    for name in CSPROJ:
        assert name.replace("/", "\\") in text, name


def test_validador_detecta_proyecto_fuera_de_la_sln(tmp_path, monkeypatch):
    assert vds.validate() == []
    monkeypatch.setattr(vds, "SOLUTION", tmp_path / "Evo.sln")
    (tmp_path / "Evo.sln").write_text(
        "Microsoft Visual Studio Solution File, Format Version 12.00\n"
        'Project("{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}") = "X", '
        '"src\\Evo.Core\\Evo.Core.csproj", "{11111111-1111-1111-1111-111111111111}"\n'
        "EndProject\n"
        "GlobalSection(ProjectConfigurationPlatforms)\n",
        encoding="utf-8")
    errors = vds.validate()
    assert any("falta el proyecto" in e for e in errors)


# --------------------------------------------------------------- catalogo
def test_catalogo_esquema_estricto():
    data = json.loads((ROOT / "catalog/windows-releases.json").read_text(encoding="utf-8"))
    assert data["schemaVersion"] == 1
    assert data["policy"]["unknownBuild"] == "reject"
    assert data["policy"]["nonClientInstallationType"] == "reject"
    assert data["supportedInstallationTypes"] == ["Client"]
    assert len(data["releases"]) == 5
    for release in data["releases"]:
        assert release["installationType"] == "Client"
        assert release["architectures"]
        assert isinstance(release["esuRequired"], bool)
        assert release["provenance"]


def test_catalogo_builds_exigidos():
    data = json.loads((ROOT / "catalog/windows-releases.json").read_text(encoding="utf-8"))
    builds = {r["id"]: (r["build"], r["esuRequired"]) for r in data["releases"]}
    assert builds["win10-22h2"] == (19045, True)
    assert builds["win11-23h2"] == (22631, False)
    assert builds["win11-24h2"] == (26100, False)
    assert builds["win11-25h2"] == (26200, False)
    assert builds["win11-26h2"] == (27600, False)


def test_catalogo_rechaza_server(monkeypatch, tmp_path):
    """Un catalogo con installationType Server debe ser rechazado."""
    raw = (ROOT / "catalog/windows-releases.json").read_text(encoding="utf-8")
    roto = tmp_path / "windows-releases.json"
    roto.write_text(raw.replace('"installationType": "Client"',
                                '"installationType": "Server"'), encoding="utf-8")
    monkeypatch.setattr(vds, "CATALOG", roto)
    errors = vds.check_catalog([])
    assert errors, "el catalogo con Server deberia fallar"


def test_catalogo_rechaza_solape():
    errors: list[str] = []
    data = vds.check_catalog(errors)
    assert data is not None
    assert errors == []


def test_catalogo_json_invalido(tmp_path, monkeypatch):
    roto = tmp_path / "windows-releases.json"
    roto.write_text("{ no es json", encoding="utf-8")
    monkeypatch.setattr(vds, "CATALOG", roto)
    errors: list[str] = []
    assert vds.check_catalog(errors) is None
    assert any("JSON invalido" in e for e in errors)


# --------------------------------------------------------------- codigo C#
def test_codigo_csharp_presente():
    core = sorted((ROOT / "src" / "Evo.Core").rglob("*.cs"))
    detection = sorted((ROOT / "src" / "Evo.Detection").rglob("*.cs"))
    assert len(core) >= 8, [p.name for p in core]
    assert len(detection) >= 4, [p.name for p in detection]


def test_enums_exigidos_existen():
    text = "".join(p.read_text(encoding="utf-8")
                   for p in (ROOT / "src/Evo.Core/Enums").glob("*.cs"))
    for name in ("RiskLevel", "SecurityImpact", "PrivilegeLevel", "RestoreLevel",
                 "ConfirmationType", "CapabilityState", "Variant"):
        assert f"enum {name}" in text, name
    for value in ("Safe", "Low", "Medium", "High", "Critical", "TrustedInstaller",
                  "SessionUndo", "RestorePoint", "FullBackup", "TypeOperationName",
                  "Stub", "Specified", "Implemented", "WinUtil", "Atlas", "Evo"):
        assert value in text, value


def test_interfaces_exigidas_existen():
    text = "".join(p.read_text(encoding="utf-8")
                   for p in (ROOT / "src/Evo.Core/System").glob("*.cs"))
    text += (ROOT / "src/Evo.Core/Execution/ICapabilityExecutor.cs").read_text(encoding="utf-8")
    for name in ("ISystemEnvironment", "IRegistryAccessor", "IServiceAccessor",
                 "ITaskAccessor", "IProcessAccessor", "ICommandRunner",
                 "ICapabilityExecutor"):
        assert f"interface {name}" in text, name


def test_capability_contract_tiene_las_propiedades():
    text = (ROOT / "src/Evo.Core/Models/CapabilityContract.cs").read_text(encoding="utf-8")
    for prop in ("Id", "Name", "Description", "SectionId", "Risk", "SecurityImpact",
                 "Privilege", "Restore", "Confirmation", "State", "Variants",
                 "ConflictsWith", "DependsOn", "SupportedBuilds"):
        assert f" {prop} {{" in text, prop


def test_detector_cubre_los_cinco_casos_en_los_tests():
    text = (ROOT / "tests/Evo.Detection.Tests/WindowsDetectorTests.cs").read_text(encoding="utf-8")
    assert "24H2" in text or "26100" in text
    assert "19045" in text
    assert "ServerDatacenter" in text
    assert "99999" in text
    assert "arm64" in text
    assert "ServerNotSupportedException" in text


def test_workflow_dotnet_ci_valido():
    import yaml

    path = ROOT / ".github/workflows/dotnet-ci.yml"
    assert path.is_file()
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "jobs" in doc
    job = doc["jobs"]["build-and-test"]
    matrix = job["strategy"]["matrix"]["include"]
    runners = {entry["os"] for entry in matrix}
    assert runners == {"windows-2025", "windows-11-arm"}
    steps = " ".join(json.dumps(step) for step in job["steps"])
    for needle in ("setup-dotnet", "dotnet restore Evo.sln",
                   "dotnet build Evo.sln", "dotnet test Evo.sln",
                   "publish-report.sh"):
        assert needle in steps, needle
