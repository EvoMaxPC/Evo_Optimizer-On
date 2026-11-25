"""Tests del paso 10: oleada 3 del catálogo = sección 9 (Registro y sistema).

Todo lo que se comprueba aquí se reproduce con los scripts del repo:
    python3 tools/ledger_extract/build_section9_catalog.py --check
    python3 tools/ledger_extract/verify_catalog_coverage.py
    python3 tools/ledger_extract/audit_catalog_values.py
    python3 tools/ledger_extract/build_upstream_capability_map.py
    python3 tools/ledger_extract/build_wave_plan.py
    python3 tools/ledger_extract/build_build_ranges_report.py
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

import build_section9_catalog as b9  # noqa: E402
import verify_catalog_coverage as vcc  # noqa: E402

LEDGER = ROOT / "inventory" / "ledger"
CATALOG = ROOT / "catalog" / "capabilities"
SECTION9 = CATALOG / "section9_system_registry.json"
RECON = LEDGER / "inventory-reconciliation.tsv"
AUDIT = LEDGER / "catalog-value-audit.tsv"
MAP = LEDGER / "upstream-capability-map.tsv"
EXCEPTIONS = ROOT / "catalog" / "exceptions" / "value-deviations.json"
PLAN = ROOT / "docs" / "reports" / "plan-oleadas.md"
RANGES = ROOT / "docs" / "reports" / "rangos-build.md"

DOCUMENT = json.loads(SECTION9.read_text(encoding="utf-8"))
CAPS = DOCUMENT["capabilities"]
BY_ID = {c["id"]: c for c in CAPS}

ID_PATTERN = re.compile(r"^[a-z0-9]+(\.[a-z0-9\-]+)+$")
RISK_ORDER = {"Safe": 0, "Low": 1, "Medium": 2, "High": 3, "Critical": 4}
RESTORE_ORDER = {"None": 0, "SessionUndo": 1, "RestorePoint": 2, "FullBackup": 3}
CONFIRM_ORDER = {"None": 0, "SimpleClick": 1, "Summary": 2,
                 "SummaryAndRestorePoint": 3, "TypeOperationName": 4}
MIN_RESTORE = {"Safe": "None", "Low": "SessionUndo", "Medium": "RestorePoint",
               "High": "RestorePoint", "Critical": "FullBackup"}
MIN_CONFIRM = {"Safe": "None", "Low": "SimpleClick", "Medium": "Summary",
               "High": "SummaryAndRestorePoint", "Critical": "TypeOperationName"}


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def section9_rows() -> list[dict]:
    return [r for r in read_tsv(RECON) if r["seccion"] == "9"]


def coverage_json() -> dict:
    return json.loads(subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract"
                             / "verify_catalog_coverage.py"), "--json"],
        capture_output=True, text=True, check=False).stdout)


# ------------------------------------------------------------------ T1 catálogo
def test_el_fichero_de_la_seccion_9_reproduce_byte_a_byte() -> None:
    """El JSON no se edita a mano: lo genera el script desde el pin."""
    assert b9.dump(b9.build()) == SECTION9.read_text(encoding="utf-8")
    text = SECTION9.read_text(encoding="utf-8")
    assert text.endswith("\n") and "\r\n" not in text


def test_la_seccion_9_declara_18_capacidades_con_ids_validos_y_unicos() -> None:
    assert len(CAPS) == 18
    ids = [c["id"] for c in CAPS]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids), "el generador ordena por id"
    for cap_id in ids:
        assert ID_PATTERN.match(cap_id), cap_id
        assert cap_id.split(".")[0] in ("system", "registry"), cap_id
        assert BY_ID[cap_id]["sectionId"] == 9


def test_todas_las_acciones_llevan_discriminador_y_una_sola_forma_por_tipo() -> None:
    """`CapabilityAction` es polimórfica: sin `"type"` el cargador estricto de
    .NET rechaza el fichero entero (lección del paso 9).

    Cambió en el paso 11: el motor sabe crear tareas (`taskCreate`), así que la
    sección 9 tiene tres formas de acción. Se añade la comprobación de la nueva;
    no se relaja ninguna de las dos anteriores.
    """
    shapes: dict[str, set] = {}
    for cap in CAPS:
        for action in cap["actions"]:
            assert action["type"] in ("registry", "service", "taskCreate"), (cap["id"], action)
            shapes.setdefault(action["type"], set()).add(tuple(sorted(action)))
    assert shapes["registry"] == {("description", "hive", "keyPath", "operation",
                                   "order", "type", "value", "valueName", "valueType")}
    # El pin tiene dos clases de operación de servicio y el contrato es cerrado:
    # `SetStartupType` lleva `startupType` y `Start`/`Stop` no lo llevan (paso 11
    # añade el arranque de w32time y las paradas de lfsvc/MapsBroker). Son dos
    # formas, no campos sueltos: un campo de más en una sola acción se vería aquí.
    assert shapes["service"] == {
        ("description", "operation", "order", "serviceName", "startupType", "type"),
        ("description", "operation", "order", "serviceName", "type")}
    # La forma de la tarea es la del contrato cerrado `TaskCreateAction`; el
    # `startupType` no aparece y `triggerAt` sí (Daily a las 00:30 del pin).
    assert shapes["taskCreate"] == {
        ("arguments", "description", "execute", "order", "overwrite", "runLevel",
         "taskDescription", "taskName", "taskPath", "trigger", "triggerAt", "type",
         "userId")}


def test_adr_0003_riesgo_restauracion_confirmacion_y_seguridad_coherentes() -> None:
    """Las mismas reglas que `CatalogValidator` y `CapabilityRules`."""
    for cap in CAPS:
        risk = RISK_ORDER[cap["risk"]]
        assert (CONFIRM_ORDER[cap["confirmation"]] >=
                CONFIRM_ORDER[MIN_CONFIRM[cap["risk"]]]), cap["id"]
        assert cap["reversibility"] == "Reversible", cap["id"]
        assert (RESTORE_ORDER[cap["restore"]] >=
                RESTORE_ORDER[MIN_RESTORE[cap["risk"]]]), (cap["id"], cap["restore"])
        assert RESTORE_ORDER[cap["restore"]] >= RESTORE_ORDER["SessionUndo"], cap["id"]
        if cap["securityImpact"] == "Reduces":
            assert risk >= RISK_ORDER["Medium"], cap["id"]
        assert cap["variants"] and cap["supportedBuilds"], cap["id"]
        assert cap["supportedBuilds"] == sorted(set(cap["supportedBuilds"])), cap["id"]
        orders = [a["order"] for a in cap["actions"]]
        assert orders == list(range(1, len(orders) + 1)), (cap["id"], orders)


def test_implemented_solo_con_acciones_y_specified_sin_perder_los_valores() -> None:
    for cap in CAPS:
        if cap["state"] == "Implemented":
            assert cap["actions"], cap["id"]
        else:
            assert cap["state"] == "Specified", cap["id"]
            # Una capacidad Specified de esta sección sigue declarando los valores
            # del registro que sí se pueden aplicar, y dice en la provenance qué
            # parte del pin no se declara.
            assert cap["actions"], cap["id"]
            assert "Specified" in cap["provenance"], cap["id"]
    # Paso 11: las dos que quedaban en Specified cierran su hueco con las
    # acciones nuevas (tarea AutoRegBackup y arranque de w32time) y pasan a
    # Implemented. No queda ninguna Specified en la sección 9.
    specified = sorted(c["id"] for c in CAPS if c["state"] == "Specified")
    assert specified == []


def test_las_tres_capacidades_que_reducen_seguridad_lo_dicen_sin_taparlo() -> None:
    reduces = sorted(c["id"] for c in CAPS if c["securityImpact"] == "Reduces")
    assert reduces == ["system.error-reporting.crash-control", "system.mitigations.disable"]
    # mitigaciones: riesgo alto y confirmación reforzada, no Safe.
    mitig = BY_ID["system.mitigations.disable"]
    assert mitig["risk"] == "High"
    assert mitig["confirmation"] == "SummaryAndRestorePoint"
    assert "REDUCE" in mitig["description"].upper()
    # crash-control: se dice que ya no habrá volcado completo.
    crash = BY_ID["system.error-reporting.crash-control"]
    assert crash["risk"] == "Medium"
    assert "volcado completo" in crash["description"]


def test_privilegio_derivado_de_la_colmena_y_de_los_servicios() -> None:
    for cap in CAPS:
        needs_admin = any(a.get("hive") in ("LocalMachine", "Users") or
                          a["type"] == "service" for a in cap["actions"])
        assert cap["privilege"] == ("Admin" if needs_admin else "User"), cap["id"]
    # Los dos de servicios exigen elevación aunque no escriban registro.
    for cap_id in ("system.services.manual-profile", "system.search-indexing.disable"):
        assert BY_ID[cap_id]["privilege"] == "Admin", cap_id


def test_la_provenance_cita_el_pin_y_los_ledger_refs() -> None:
    for cap in CAPS:
        prov = cap["provenance"]
        assert "winutil@70c23c80641d7370532af2f619b2842658600842" in prov or \
               "atlas@ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f" in prov, cap["id"]
        assert "ledger_refs:" in prov, cap["id"]
        assert "Reversibilidad (ADR-0003)" in prov, cap["id"]


# ------------------------------------------------------- T2 valores y cobertura
def test_los_valores_del_pin_estan_copiados_literalmente() -> None:
    """Cada valor del catálogo existe en el pin (los literales se leen, no se
    escriben). Se comprueba contra `build()` recalculado desde `/tmp/upstream`
    y contra tres literales medidos a mano en el paso 10."""
    rebuilt = {c["id"]: c for c in b9.build()["capabilities"]}
    assert rebuilt == BY_ID
    mouse = [a["value"] for a in BY_ID["system.mouse-acceleration.enable"]["actions"]]
    assert mouse == ["1", "6", "10"]           # Value de WPFToggleMouseAcceleration
    game = [a["valueName"] for a in BY_ID["system.game-mode.enable"]["actions"]]
    assert game == ["AllowAutoGameMode", "AutoGameModeEnabled"]
    utc = BY_ID["system.time.utc-rtc"]["actions"][0]
    assert (utc["valueName"], utc["valueType"], utc["value"]) == \
        ("RealTimeIsUniversal", "QWord", "1")


def test_la_auditoria_de_valores_no_tiene_ninguna_fila_ambigua() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract"
                             / "audit_catalog_values.py"), "--json"],
        capture_output=True, text=True, check=False)
    report = json.loads(result.stdout)
    assert result.returncode == 0
    assert report["sin_excepcion"] == 0
    assert report["distribucion"].get("ambiguous", 0) == 0
    assert report["distribucion"].get("differs", 0) == 1   # declarada con excepción
    rows = [r for r in read_tsv(AUDIT) if r["capability_id"].startswith("system.")]
    assert len(rows) == 33
    assert {r["relation"] for r in rows} <= {
        "equals-apply", "equals-on", "equals-off", "differs", "no-source"}


def test_la_desviacion_de_settings_page_visibility_esta_declarada() -> None:
    deviations = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))["deviations"]
    by_cap = {d["capability_id"]: d for d in deviations}
    assert set(by_cap) == {"debloat.settings.home", "system.settings-page-visibility.hide"}
    dev = by_cap["system.settings-page-visibility.hide"]
    assert dev["relation"] == "differs"
    assert dev["deviation_kind"] == "value"
    assert dev["evidence"].strip() and dev["reason"].strip()
    # El valor declarado es el literal completo del script del pin.
    assert dev["catalog_value"] == BY_ID["system.settings-page-visibility.hide"][
        "actions"][0]["value"]
    assert dev["source_apply_value"] == "hide:aicomponents"


def test_el_verificador_cubre_las_27_lineas_mapped_de_la_seccion_9() -> None:
    assert vcc.main([]) == 0
    report = coverage_json()
    assert "9" in report["secciones_terminadas"]
    assert report["por_seccion"]["9"] == {"lineas_mapped": 30, "cubiertas": 30,
                                         "huecos": 0}
    assert report["huecos"] == 0
    assert report["huecos_no_declarados"] == 0
    assert report["capacidades"] == 86


def test_las_correcciones_medidas_del_paso_10_estan_en_el_ledger() -> None:
    rows = {r["linea"]: r for r in section9_rows()}
    # 265 y 308 y 316 pasan de un mapeo equivocado a un mapeo medido.
    assert rows["265"]["status"] == "Mapped"
    assert rows["265"]["mapped_ids"] == "winutil:tweak:WPFTweaksServices"
    assert rows["308"]["mapped_ids"] == "atlas:toggle:KeyboardShortcuts"
    assert rows["316"]["mapped_ids"] == "atlas:manifest:qol/set-hidden-settings-pages"
    # Tres falsos negativos del paso 4e que el pin sí implementa.
    assert rows["269"]["mapped_ids"] == "atlas:manifest:qol/system/disable-wpbt"
    assert rows["302"]["mapped_ids"] == "atlas:manifest:misc/config-oem-information"
    assert rows["307"]["mapped_ids"] == "atlas:toggle:KeyboardShortcuts"
    # 278 sale de Mapped: el pin no tiene esa función (medido, con motivo).
    assert rows["278"]["status"] == "Absent-At-Pin"
    assert "System Tray Configuration" in rows["278"]["texto"]
    assert "bandeja" in rows["278"]["rationale"]
    mapped = [r for r in section9_rows() if r["status"] == "Mapped"]
    assert len(mapped) == 30
    assert len(section9_rows()) == 58


def test_el_mapa_upstream_marca_cubiertos_los_items_de_la_seccion_9() -> None:
    subprocess.run([sys.executable, str(ROOT / "tools" / "ledger_extract"
                                   / "build_upstream_capability_map.py")],
                   capture_output=True, text=True, check=True)
    rows = [r for r in read_tsv(MAP) if r["section_guess"] == "9"]
    assert len(rows) == 11
    covered = {r["upstream_id"] for r in rows if r["status"] == "covered"}
    assert covered == {
        "atlas:manifest:misc/config-oem-information",
        "atlas:manifest:misc/config-time",
        "atlas:manifest:qol/set-keyboard-switching",
        "atlas:manifest:qol/system/crash-control-qol",
        "atlas:manifest:qol/system/disable-wpbt",
        "winutil:feature:WPFFeatureRegBackup",
        "winutil:tweak:WPFTweaksDisableSearchIndexing",
        "winutil:tweak:WPFTweaksUTC",
    }
    pending = {r["upstream_id"] for r in rows if r["status"] == "pending"}
    assert pending == {"atlas:toggle:Indexing", "atlas:toggle:Workplace",
                       "winutil:feature:WPFPanelTimedate"}


def test_los_informes_derivados_son_reproducibles_y_reflejan_la_oleada_3() -> None:
    for script in ("build_section9_catalog.py", "build_wave_plan.py",
                   "build_build_ranges_report.py"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "ledger_extract" / script), "--check"],
            capture_output=True, text=True, check=False)
        assert result.returncode == 0, (script, result.stderr)
    plan = PLAN.read_text(encoding="utf-8")
    assert "oleada 3, cerrada en el catálogo (30 de 30" in plan
    assert "| 30 | 0 | 0 | 26 | 2 | 30 | 0 | 26 | 3 |" in plan   # fila de §9
    ranges = RANGES.read_text(encoding="utf-8")
    assert "**86** capacidades" in ranges
    assert "`system.hibernation.hide`" in ranges


def test_la_doble_ejecucion_del_generador_da_los_mismos_bytes(tmp_path) -> None:
    """Determinismo: dos procesos distintos, mismo sha256 (lo mismo hace el CI)."""
    first = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract"
                             / "build_section9_catalog.py")],
        capture_output=True, text=True, check=True)
    first_bytes = SECTION9.read_bytes()
    second = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract"
                             / "build_section9_catalog.py")],
        capture_output=True, text=True, check=True)
    assert first.stdout == second.stdout
    assert SECTION9.read_bytes() == first_bytes
    assert first_bytes.startswith(b"{\n")
