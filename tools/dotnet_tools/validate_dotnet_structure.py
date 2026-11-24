#!/usr/bin/env python3
"""Validador local de la estructura .NET de EVO CLEAN (paso 6).

Se ejecuta en Linux (sandbox del agente y CI de Python) y **no** compila nada:
comprueba la coherencia de los ficheros versionados.

Comprobaciones:

1. `Evo.sln` referencia **todos** los `.csproj` del repo y ninguno inexistente.
2. Cada `.csproj` es XML válido, usa `Microsoft.NET.Sdk`, y **no** redeclara
   `TargetFramework` / `Nullable` / `ImplicitUsings` (vienen de
   `Directory.Build.props`, que sí debe declararlos).
3. `catalog/windows-releases.json` valida contra el esquema estricto inline:
   builds únicos y no solapados, `installationType == "Client"`, rangos
   coherentes, `policy.maxSupportedBuild`, etc.
4. Coherencia de proyectos: `Evo.Detection` referencia `Evo.Core`; los tests
   referencian su proyecto de producto y declaran `IsTestProject`.

Exit 0 si todo pasa; exit 1 con el detalle de los fallos.

Uso:
    python3 tools/dotnet_tools/validate_dotnet_structure.py
    python3 tools/dotnet_tools/validate_dotnet_structure.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOLUTION = ROOT / "Evo.sln"
PROPS = ROOT / "Directory.Build.props"
CATALOG = ROOT / "catalog" / "windows-releases.json"

REQUIRED_PROPS = {
    "TargetFramework": "net10.0-windows",
    "Nullable": "enable",
    "ImplicitUsings": "enable",
    "TreatWarningsAsErrors": "true",
    "AnalysisLevel": "latest",
    "Company": "EvoMaxPC",
    "Product": "EVO CLEAN",
}

INHERITED = ("TargetFramework", "Nullable", "ImplicitUsings",
             "TreatWarningsAsErrors", "AnalysisLevel", "Company", "Product",
             "Copyright")

MIN_RELEASES = 5


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def find_csprojs() -> list[Path]:
    skip = {"bin", "obj", ".git", "node_modules"}
    out = []
    for path in ROOT.rglob("*.csproj"):
        if any(part in skip for part in path.parts):
            continue
        out.append(path)
    return sorted(out, key=rel)


def csproj_property(path: Path, name: str) -> str | None:
    tree = ET.parse(path)
    root = tree.getroot()
    for group in root.findall("PropertyGroup"):
        node = group.find(name)
        if node is not None and node.text:
            return node.text.strip()
    return None


def check_props(errors: list[str]) -> None:
    if not PROPS.is_file():
        errors.append("falta Directory.Build.props en la raiz")
        return
    try:
        root = ET.parse(PROPS).getroot()
    except ET.ParseError as exc:
        errors.append(f"Directory.Build.props: XML invalido ({exc})")
        return
    values: dict[str, str] = {}
    for group in root.findall("PropertyGroup"):
        for node in group:
            if node.text and node.text.strip():
                values.setdefault(node.tag, node.text.strip())
    for name, expected in REQUIRED_PROPS.items():
        actual = values.get(name)
        if actual is None:
            errors.append(f"Directory.Build.props: falta <{name}>")
        elif actual != expected:
            errors.append(
                f"Directory.Build.props: <{name}> = '{actual}' (esperado '{expected}')")
    copyright_value = values.get("Copyright", "")
    if "EvoMaxPC" not in copyright_value or "GPL-3.0-only" not in copyright_value:
        errors.append(
            "Directory.Build.props: <Copyright> debe citar EvoMaxPC y GPL-3.0-only")


def parse_solution(errors: list[str]) -> list[str]:
    """Devuelve las rutas de .csproj referenciadas por Evo.sln."""
    if not SOLUTION.is_file():
        errors.append("falta Evo.sln")
        return []
    text = SOLUTION.read_text(encoding="utf-8-sig")
    if "Microsoft Visual Studio Solution File" not in text:
        errors.append("Evo.sln: cabecera de solucion invalida")
    refs = re.findall(r'Project\("\{[^}]+\}"\)\s*=\s*"[^"]*",\s*"([^"]+\.csproj)"',
                      text)
    if not refs:
        errors.append("Evo.sln: no referencia ningun .csproj")
    guids = re.findall(r'Project\("\{[^}]+\}"\)\s*=\s*"[^"]*",\s*"[^"]*",\s*"(\{[^}]+\})"',
                       text)
    if len(set(g.lower() for g in guids)) != len(guids):
        errors.append("Evo.sln: GUID de proyecto duplicado")
    if "GlobalSection(ProjectConfigurationPlatforms)" not in text:
        errors.append("Evo.sln: falta ProjectConfigurationPlatforms")
    return [r.replace("\\", "/") for r in refs]


def check_solution_membership(errors: list[str]) -> None:
    refs = parse_solution(errors)
    ref_paths = set(refs)
    for ref in refs:
        if not (ROOT / ref).is_file():
            errors.append(f"Evo.sln: referencia un .csproj inexistente ({ref})")
    for path in find_csprojs():
        if rel(path) not in ref_paths:
            errors.append(f"Evo.sln: falta el proyecto {rel(path)}")


def check_csprojs(errors: list[str]) -> None:
    for path in find_csprojs():
        name = rel(path)
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            errors.append(f"{name}: XML invalido ({exc})")
            continue

        sdk = root.get("Sdk")
        if sdk != "Microsoft.NET.Sdk":
            errors.append(f"{name}: Sdk debe ser 'Microsoft.NET.Sdk' (es '{sdk}')")

        # Los tests pueden rebajar TreatWarningsAsErrors (analizadores de xUnit);
        # el resto de propiedades heredadas no se redeclaran NUNCA.
        overridable = {"TreatWarningsAsErrors"} if csproj_property(
            path, "IsTestProject") == "true" else set()
        for inherited in INHERITED:
            if inherited in overridable:
                continue
            value = csproj_property(path, inherited)
            if value is not None:
                errors.append(
                    f"{name}: redeclara <{inherited}> ('{value}'); viene de "
                    "Directory.Build.props")

        is_test = "Tests" in path.name
        is_leaf = path.parent.name == "Evo.Core"
        if not is_test and not is_leaf and root.find("ItemGroup/ProjectReference") is None:
            errors.append(f"{name}: un proyecto de producto que no es Evo.Core debe "
                          "declarar ProjectReference")

        if "Tests" in path.name:
            if csproj_property(path, "IsTestProject") != "true":
                errors.append(f"{name}: los tests deben declarar "
                              "<IsTestProject>true</IsTestProject>")
            packages = {node.get("Include") for node in root.iter("PackageReference")}
            for required in ("xunit", "Microsoft.NET.Test.Sdk"):
                if required not in packages:
                    errors.append(f"{name}: falta PackageReference '{required}'")
            references = {node.get("Include", "").replace("\\", "/")
                          for node in root.iter("ProjectReference")}
            if not any("Evo." in r and "Tests" not in r for r in references):
                errors.append(f"{name}: no referencia el proyecto bajo prueba")

    detection = ROOT / "src" / "Evo.Detection" / "Evo.Detection.csproj"
    if detection.is_file():
        refs = {node.get("Include", "").replace("\\", "/")
                for node in ET.parse(detection).getroot().iter("ProjectReference")}
        if not any(r.endswith("Evo.Core/Evo.Core.csproj") for r in refs):
            errors.append("src/Evo.Detection/Evo.Detection.csproj: debe referenciar "
                          "Evo.Core")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def check_catalog(errors: list[str]) -> dict | None:
    if not CATALOG.is_file():
        errors.append("falta catalog/windows-releases.json")
        return None
    raw = CATALOG.read_text(encoding="utf-8")
    if raw.startswith("\ufeff"):
        errors.append("catalog/windows-releases.json: no debe tener BOM")
    if "\r\n" in raw:
        errors.append("catalog/windows-releases.json: debe usar LF")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        errors.append(f"catalog/windows-releases.json: JSON invalido ({exc})")
        return None

    if not isinstance(data, dict):
        errors.append("catalog: la raiz debe ser un objeto")
        return None

    if data.get("schemaVersion") != 1:
        errors.append("catalog: schemaVersion debe ser 1")
    if data.get("catalog") != "windows-releases":
        errors.append("catalog: 'catalog' debe ser 'windows-releases'")

    types = data.get("supportedInstallationTypes")
    if not isinstance(types, list) or "Client" not in types:
        errors.append("catalog: supportedInstallationTypes debe incluir 'Client'")

    policy = data.get("policy")
    max_build = 0
    if not isinstance(policy, dict):
        errors.append("catalog: falta 'policy'")
    else:
        if policy.get("unknownBuild") != "reject":
            errors.append("catalog.policy: unknownBuild debe ser 'reject'")
        if policy.get("nonClientInstallationType") != "reject":
            errors.append("catalog.policy: nonClientInstallationType debe ser 'reject'")
        max_build = policy.get("maxSupportedBuild", 0)
        if not _is_int(max_build) or max_build <= 0:
            errors.append("catalog.policy: maxSupportedBuild debe ser un entero > 0")

    releases = data.get("releases")
    if not isinstance(releases, list):
        errors.append("catalog: 'releases' debe ser una lista")
        return data
    if len(releases) < MIN_RELEASES:
        errors.append(f"catalog: se esperaban >= {MIN_RELEASES} releases "
                      f"(hay {len(releases)})")

    ids: set[str] = set()
    ranges: list[tuple[str, int, int]] = []
    for index, release in enumerate(releases):
        tag = f"catalog.releases[{index}]"
        if not isinstance(release, dict):
            errors.append(f"{tag}: debe ser un objeto")
            continue
        rid = release.get("id")
        if not isinstance(rid, str) or not rid:
            errors.append(f"{tag}: falta 'id'")
            rid = f"[{index}]"
        else:
            tag = f"release '{rid}'"
            if rid in ids:
                errors.append(f"{tag}: id duplicado")
            ids.add(rid)

        for field in ("displayName", "installationType"):
            if not isinstance(release.get(field), str) or not release.get(field):
                errors.append(f"{tag}: falta '{field}'")

        if release.get("installationType") != "Client":
            errors.append(f"{tag}: installationType debe ser 'Client' "
                          f"(es '{release.get('installationType')}')")

        for field in ("build", "buildMin"):
            if not _is_int(release.get(field)) or release.get(field, 0) <= 0:
                errors.append(f"{tag}: '{field}' debe ser un entero > 0")

        build = release.get("build", 0)
        build_min = release.get("buildMin", 0)
        build_max = release.get("buildMax")
        open_ended = release.get("openEnded", False)

        if _is_int(build) and _is_int(build_min) and build < build_min:
            errors.append(f"{tag}: build {build} < buildMin {build_min}")

        if build_max is not None and not _is_int(build_max):
            errors.append(f"{tag}: 'buildMax' debe ser entero o null")
            build_max = None

        if _is_int(build_max) and _is_int(build_min) and build_max < build_min:
            errors.append(f"{tag}: buildMax {build_max} < buildMin {build_min}")

        if not isinstance(open_ended, bool):
            errors.append(f"{tag}: 'openEnded' debe ser booleano")
        elif open_ended != (build_max is None):
            errors.append(f"{tag}: 'openEnded' incoherente con 'buildMax'")

        if _is_int(build_max) and max_build and build_max > max_build:
            errors.append(f"{tag}: buildMax {build_max} excede "
                          f"policy.maxSupportedBuild {max_build}")
        if _is_int(build_min) and max_build and build_min > max_build:
            errors.append(f"{tag}: buildMin {build_min} excede "
                          f"policy.maxSupportedBuild {max_build}")

        architectures = release.get("architectures")
        if not isinstance(architectures, list) or not architectures:
            errors.append(f"{tag}: 'architectures' no puede estar vacio")
        else:
            for architecture in architectures:
                if architecture not in ("x64", "arm64", "x86"):
                    errors.append(f"{tag}: arquitectura no soportada '{architecture}'")

        for flag in ("esuRequired", "requiresEsuNotice"):
            if not isinstance(release.get(flag), bool):
                errors.append(f"{tag}: '{flag}' debe ser booleano")

        if not isinstance(release.get("supportStatus"), str) or not release.get("supportStatus"):
            errors.append(f"{tag}: falta 'supportStatus'")

        if not isinstance(release.get("provenance"), str) or not release.get("provenance"):
            errors.append(f"{tag}: falta 'provenance' (REQ-002/REQ-006)")

        if _is_int(release.get("buildMin")):
            upper = build_max if _is_int(build_max) else (max_build or 10**9)
            ranges.append((rid, release["buildMin"], upper))

    for i, (id_a, min_a, max_a) in enumerate(ranges):
        for id_b, min_b, max_b in ranges[i + 1:]:
            if min_a <= max_b and min_b <= max_a:
                errors.append(f"catalog: rangos solapados {id_a} y {id_b}")

    for required in ("win10-22h2", "win11-23h2", "win11-24h2", "win11-25h2",
                     "win11-26h2"):
        if required not in ids:
            errors.append(f"catalog: falta la version obligatoria '{required}'")

    return data


def check_notices(errors: list[str]) -> None:
    notices = ROOT / "THIRD_PARTY_NOTICES.md"
    if not notices.is_file():
        errors.append("falta THIRD_PARTY_NOTICES.md")
        return
    text = notices.read_text(encoding="utf-8")
    for pin in ("70c23c80641d7370532af2f619b2842658600842",
                "ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f"):
        if pin not in text:
            errors.append(f"THIRD_PARTY_NOTICES.md: falta el pin {pin[:9]}")
    for license_name in ("MIT", "GPL-3.0"):
        if license_name not in text:
            errors.append(f"THIRD_PARTY_NOTICES.md: falta la licencia {license_name}")
    lowered = text.lower()
    for tool in ("shutup10", "process explorer", "nvcleanstall"):
        if tool not in lowered:
            errors.append(f"THIRD_PARTY_NOTICES.md: falta la herramienta '{tool}'")
    if "no redistribuid" not in lowered and "no se redistribuye" not in lowered:
        errors.append("THIRD_PARTY_NOTICES.md: falta la declaracion de no redistribucion")


def validate() -> list[str]:
    errors: list[str] = []
    check_props(errors)
    check_solution_membership(errors)
    check_csprojs(errors)
    check_catalog(errors)
    check_notices(errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    errors = validate()
    projects = [rel(p) for p in find_csprojs()]
    data = None
    if CATALOG.is_file():
        try:
            data = json.loads(CATALOG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None

    resumen = {
        "ok": not errors,
        "proyectos": projects,
        "ca_proyectos": len(projects),
        "releases": len(data.get("releases", [])) if isinstance(data, dict) else 0,
        "errores": errors,
    }

    if args.json:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
    else:
        print(f"proyectos : {len(projects)}")
        for project in projects:
            print(f"  - {project}")
        print(f"releases  : {resumen['releases']}")
        if errors:
            print("FALLOS:", file=sys.stderr)
            for error in errors[:40]:
                print(f"  - {error}", file=sys.stderr)
        else:
            print("estructura .NET: OK")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
