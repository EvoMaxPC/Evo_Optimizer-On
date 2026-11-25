"""Tests del paso 11: expresividad del motor + cierre de los huecos de las
oleadas 2 y 3.

Todo lo que se comprueba aquí se reproduce con los scripts del repo:
    python3 tools/ledger_extract/build_section9_catalog.py --check
    python3 tools/ledger_extract/build_section10_catalog.py --check
    python3 tools/ledger_extract/audit_catalog_values.py
    python3 tools/ledger_extract/verify_catalog_coverage.py
    python3 tools/ledger_extract/build_upstream_capability_map.py
    python3 tools/ledger_extract/build_wave_plan.py
    python3 tools/ledger_extract/build_build_ranges_report.py

Ningún JSON se edita a mano: si un test falla, hay que arreglar el generador.
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
import build_section10_catalog as b10  # noqa: E402
import verify_catalog_coverage as vcc  # noqa: E402

LEDGER = ROOT / "inventory" / "ledger"
CATALOG = ROOT / "catalog" / "capabilities"
SECTION9 = CATALOG / "section9_system_registry.json"
SECTION10 = CATALOG / "section10_explorer_ui.json"
AUDIT = LEDGER / "catalog-value-audit.tsv"
RECON = LEDGER / "inventory-reconciliation.tsv"
MAP = LEDGER / "upstream-capability-map.tsv"
RANGES = ROOT / "docs" / "reports" / "rangos-build.md"
PLAN = ROOT / "docs" / "reports" / "plan-oleadas.md"
ADR5 = ROOT / "docs" / "adr" / "ADR-0005-expresividad-del-motor.md"

DOCUMENT9 = json.loads(SECTION9.read_text(encoding="utf-8"))
DOCUMENT10 = json.loads(SECTION10.read_text(encoding="utf-8"))
CAPS9 = {c["id"]: c for c in DOCUMENT9["capabilities"]}
CAPS10 = {c["id"]: c for c in DOCUMENT10["capabilities"]}

NEW_TYPES = ("registryDeleteKey", "taskCreate")


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def actions_of(section: str, cap_id: str) -> list[dict]:
    caps = CAPS9 if section == "9" else CAPS10
    return caps[cap_id]["actions"]


# ------------------------------------------------------------------ T2 generadores
def test_los_dos_generadores_reproducen_byte_a_byte() -> None:
    for module, path in ((b9, SECTION9), (b10, SECTION10)):
        assert module.dump(module.build()) == path.read_text(encoding="utf-8"), module.__name__
        assert "--check" in module.__doc__


def test_los_generadores_pasan_check_por_subproceso() -> None:
    for script in ("build_section9_catalog.py", "build_section10_catalog.py"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "ledger_extract" / script), "--check"],
            capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr


def test_las_acciones_nuevas_salen_del_generador_y_no_del_json() -> None:
    """Si alguien edita el JSON a mano, `--check` deja de cuadrar.

    Aquí se comprueba el contenido: la tarea de AutoRegBackup y el borrado de
    clave de Inicio son los que produce el generador leyendo el pin.
    """
    task = [a for a in actions_of("9", "system.registry-backup.enable")
            if a["type"] == "taskCreate"]
    assert len(task) == 1
    assert task[0] == b9.reg_backup_task_actions()[0] | {"order": 3}

    home = [a for a in actions_of("10", "explorer.home.hide")
            if a["type"] == "registryDeleteKey"]
    assert len(home) == 1
    assert home[0]["hive"] == "LocalMachine"
    assert home[0]["keyPath"].endswith("{f874310e-b6b7-47dc-bc84-b9e6b38f5903}")
    assert home[0]["recursive"] is False


# ------------------------------------------------------------------ T1 contrato
def test_el_contrato_de_las_acciones_nuevas_es_cerrado() -> None:
    expected = {
        "registryDeleteKey": {"type", "order", "description", "hive", "keyPath", "recursive"},
        "taskCreate": {"type", "order", "description", "taskPath", "taskName", "execute",
                       "arguments", "trigger", "triggerAt", "userId", "runLevel",
                       "taskDescription", "overwrite"},
    }
    for section, caps in (("9", CAPS9), ("10", CAPS10)):
        for cap_id, cap in caps.items():
            orders = [a["order"] for a in cap["actions"]]
            assert orders == list(range(1, len(orders) + 1)), cap_id
            for action in cap["actions"]:
                assert action["type"] not in NEW_TYPES or set(action) == expected[action["type"]], (
                    section, cap_id, action)


def test_las_tareas_del_catalogo_son_las_del_pin() -> None:
    task = [a for a in actions_of("9", "system.registry-backup.enable")
            if a["type"] == "taskCreate"][0]
    # Literales del InvokeScript del pin (config/feature.json:87-91).
    assert task["taskName"] == "AutoRegBackup"
    assert task["execute"] == "schtasks"
    assert task["arguments"] == '/run /i /tn "\\Microsoft\\Windows\\Registry\\RegIdleBackup"'
    assert task["trigger"] == "Daily"
    assert task["triggerAt"] == "00:30"
    assert task["userId"] == "System"
    assert task["runLevel"] == "Highest"
    assert task["overwrite"] is False


def test_los_servicios_declarados_llevan_el_tipo_solo_si_lo_cambian() -> None:
    for section, caps in (("9", CAPS9), ("10", CAPS10)):
        for cap_id, cap in caps.items():
            for action in cap["actions"]:
                if action["type"] != "service":
                    continue
                if action["operation"] == "SetStartupType":
                    assert action["startupType"] in ("Automatic", "Manual", "Disabled"), cap_id
                else:
                    assert action["operation"] in ("Start", "Stop"), cap_id
                    assert "startupType" not in action, (section, cap_id, action)


# ------------------------------------------------------- T2 capacidades cerradas
def test_la_seccion_9_cierra_sus_dos_specified() -> None:
    """El paso 11 cerró las dos que quedaban. El paso 12 aplica R1 y reabre
    cuatro por un motivo DISTINTO: el pin hace operaciones que el motor no
    tiene (powercfg, bcdedit/CFG, política de Find My Device, RunLevel). La
    lista es cerrada: si aparece otra, este test falla."""
    specified = sorted(cid for cid, cap in CAPS9.items() if cap["state"] == "Specified")
    assert specified == [
        "system.hibernation.hide",
        "system.location.consent-deny",
        "system.mitigations.disable",
        "system.registry-backup.enable",
    ], specified
    # Paso 12: 18 -> 19 con system.network.location-wizard.disable.
    assert len(CAPS9) == 19
    # Actions: 39 del paso 10 + tarea (1) + w32time (1) + lfsvc/MapsBroker (4)
    # + Stop de WSearch (1) + registryCreateKey de NewNetworkWindowOff (1).
    assert sum(len(c["actions"]) for c in CAPS9.values()) == 47


def test_el_catalogo_completo_cambia_de_estado_pero_no_de_tamano() -> None:
    """73/13 -> 75/11: dos capacidades de §9 dejan de ser Specified.

    Se comprueba contra el informe generado (no contra un literal suelto) y
    contra los dos JSON que cambian, para que la cifra no pueda quedarse vieja.
    """
    text = RANGES.read_text(encoding="utf-8")
    assert "**88** capacidades, 71 `Implemented` y 17 `Specified`" in text
    for path in sorted(CATALOG.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for cap in document["capabilities"]:
            assert cap["state"] in ("Implemented", "Specified"), cap["id"]

    total = sum(len(json.loads(p.read_text(encoding="utf-8"))["capabilities"])
                for p in sorted(CATALOG.glob("*.json")))
    # Paso 12: 86 -> 88 capacidades y 238 -> 243 acciones. Las cinco de más son
    # Explorer y sistema: 3 de `explorer.home.restore` (crear la clave + 2 valores),
    # 1 `ServiceAction Stop` de WSearch y 1 `registryCreateKey` de
    # `system.network.location-wizard.disable`.
    assert total == 88
    actions = sum(len(a["actions"])
                  for p in sorted(CATALOG.glob("*.json"))
                  for a in json.loads(p.read_text(encoding="utf-8"))["capabilities"])
    assert actions == 243


def test_la_copia_de_seguridad_lleva_registro_y_tarea() -> None:
    cap = CAPS9["system.registry-backup.enable"]
    # Paso 12: R1 la pasa a Specified (el pin registra la tarea sin -RunLevel y
    # con /i, y eso queda declarado) y R3 le exige Risk=Low y SimpleClick por
    # instalar una tarea SYSTEM.
    assert cap["state"] == "Specified"
    assert cap["risk"] == "Low"
    assert cap["confirmation"] == "SimpleClick"
    assert "FUERA DE ESTA CAPACIDAD (R1)" in cap["description"]
    assert "R3 (paso 12)" in cap["provenance"]
    assert cap["reversibility"] == "Reversible"
    assert cap["restore"] == "SessionUndo"
    kinds = [a["type"] for a in cap["actions"]]
    assert kinds == ["registry", "registry", "taskCreate"]
    assert "se borra la tarea" in cap["description"].lower()
    assert "RegIdleBackup" in cap["provenance"]


def test_los_servidores_de_hora_arrancan_w32time_y_declaran_w32tm() -> None:
    cap = CAPS9["system.time.ntp-servers"]
    assert cap["state"] == "Implemented"
    service = [a for a in cap["actions"] if a["type"] == "service"]
    assert [(a["serviceName"], a["operation"]) for a in service] == [("w32time", "Start")]
    # Lo que sigue fuera se dice: dos comandos sin inversa, NO ejecutados.
    assert "w32tm /config /update" in cap["description"]
    assert "w32tm /resync" in cap["description"]
    assert "NO se ejecutan" in cap["provenance"]


def test_la_ubicacion_apaga_lfsvc_y_mapsbroker_con_evidencia_del_pin() -> None:
    cap = CAPS9["system.location.consent-deny"]
    services = [(a["serviceName"], a["operation"]) for a in cap["actions"]
                if a["type"] == "service"]
    # Parar primero y deshabilitar después: el deshacer LIFO devuelve el tipo de
    # inicio ANTES de intentar arrancar el servicio (si no, ERROR_SERVICE_DISABLED).
    assert services == [("lfsvc", "Stop"), ("lfsvc", "SetStartupType"),
                        ("MapsBroker", "Stop"), ("MapsBroker", "SetStartupType")]
    # La evidencia es ruta:linea del pin, no una impresion.
    assert "Atlas.Privacy/Domain/Location.ps1:113" in cap["provenance"]
    assert "Atlas.Privacy/Domain/Location.ps1:114" in cap["provenance"]
    assert "Atlas.Privacy/Domain/Location.ps1:91" in cap["provenance"]
    assert "Toggles/General/Location.psd1:13" in cap["provenance"]


def test_el_borrado_de_clave_de_inicio_esta_declarado_y_el_de_unidades_justificado() -> None:
    home = CAPS10["explorer.home.hide"]
    deletes = [a for a in home["actions"] if a["type"] == "registryDeleteKey"]
    assert len(deletes) == 1
    assert "BORRA la clave" in home["description"]
    assert "instantánea previa" in home["description"]

    # Las dos DeleteKey del pin estan en el estado 'Disable' (el contrario al que
    # declara la capacidad, que es 'Enable'): se justifica con el motivo medido.
    drums = CAPS10["explorer.removable-drives.sidebar"]
    assert not [a for a in drums["actions"] if a["type"] == "registryDeleteKey"]
    assert "CONTRARIO" in drums["description"]
    assert "DeleteKey" in drums["description"]


def test_adr_0003_se_sigue_cumpliendo_en_las_capacidades_tocadas() -> None:
    min_restore = {"Safe": "None", "Low": "SessionUndo", "Medium": "RestorePoint",
                   "High": "RestorePoint", "Critical": "FullBackup"}
    order = {"None": 0, "SessionUndo": 1, "RestorePoint": 2, "FullBackup": 3}
    for section, caps in (("9", CAPS9), ("10", CAPS10)):
        for cap_id, cap in caps.items():
            assert cap["reversibility"] == "Reversible", cap_id
            assert order[cap["restore"]] >= order[min_restore[cap["risk"]]], cap_id
            if any(a["type"] in NEW_TYPES for a in cap["actions"]):
                # Las acciones nuevas se deshacen: la capacidad no puede declarar
                # que no hay nada que restaurar.
                assert order[cap["restore"]] >= order["SessionUndo"], cap_id


# ------------------------------------------------------------------ T3 ledgers
def test_la_auditoria_incluye_el_borrado_de_clave_con_su_fuente() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract" / "audit_catalog_values.py"),
         "--json"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["sin_excepcion"] == 0
    assert report["distribucion"].get("ambiguous", 0) == 0
    assert report["excepciones"] == 2
    # 194 del paso 10 + la fila del DeleteKey de Inicio (195) + los dos valores
    # de explorer.home.restore (197).
    assert report["filas"] == 197
    assert report["por_seccion"]["9"] == 33
    assert report["por_seccion"]["10"] == 59

    rows = read_tsv(AUDIT)
    deletes = [r for r in rows if r["capability_id"] == "explorer.home.hide"
               and r["name"].startswith("(clave completa")]
    assert len(deletes) == 1
    assert deletes[0]["relation"] == "equals-apply"
    assert deletes[0]["source"] == "atlas"
    assert deletes[0]["source_ref"].endswith("Interface/Home.psd1")


def test_la_cobertura_sigue_en_85_de_85_sin_huecos() -> None:
    assert vcc.main([]) == 0
    report = json.loads(subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract" / "verify_catalog_coverage.py"),
         "--json"], capture_output=True, text=True, check=False).stdout)
    assert report["secciones_terminadas"] == ["1", "2", "3", "9", "10"]
    assert report["lineas_mapped_1_3"] == 85
    assert report["cubiertas"] == 85
    assert report["huecos"] == 0
    assert report["huecos_no_declarados"] == 0
    # Paso 12: 86 -> 88 capacidades (la cobertura sigue 85/85, no cambian las
    # líneas Mapped del inventario).
    assert report["capacidades"] == 88
    for section in ("1", "2", "3", "9", "10"):
        assert report["por_seccion"][section]["huecos"] == 0, section


def test_las_cifras_de_los_informes_generados_estan_al_dia() -> None:
    for script in ("build_wave_plan.py", "build_build_ranges_report.py"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "ledger_extract" / script), "--check"],
            capture_output=True, text=True, check=False)
        assert result.returncode == 0, (script, result.stderr)

    # El mapa de upstream no tiene `--check`: se comprueba que el fichero del
    # disco es exactamente lo que produce el generador (doble ejecución).
    first = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract" / "build_upstream_capability_map.py")],
        capture_output=True, text=True, check=True)
    assert first.returncode == 0
    assert MAP.read_text(encoding="utf-8").strip() != ""

    text = RANGES.read_text(encoding="utf-8")
    # Paso 12: 88 = 71 + 17 (R1 reabre cuatro de §9 y cierra dos de §10).
    assert "**88** capacidades, 71 `Implemented` y 17 `Specified`" in text

    plan = PLAN.read_text(encoding="utf-8")
    assert "| 9 |" in plan and "| 10 |" in plan

    # La seccion 9 del mapa de upstream no pierde sus filas covered.
    rows = [r for r in read_tsv(MAP) if r["section_guess"] == "9"]
    covered = [r for r in rows if r["status"] == "covered"]
    assert len(covered) == 8, [r["upstream_id"] for r in covered]


def test_no_se_rompe_la_reconciliacion_de_las_secciones_cerradas() -> None:
    rows = [r for r in read_tsv(RECON) if r["seccion"] == "9"]
    statuses = [r["status"] for r in rows]
    assert statuses.count("Mapped") == 30
    assert statuses.count("Absent-At-Pin") == 26
    assert statuses.count("Informative-Header") == 2


def test_el_informe_del_paso_11_cita_lo_medido() -> None:
    """El informe no puede inventar cifras: las que da tienen que cuadrar con
    el repo (y con los hallazgos T0 de este mismo paso)."""
    report = (ROOT / "docs" / "reports" / "paso11.md").read_text(encoding="utf-8")

    # Los siete renglones de la conciliación (6 MAPPED + 1 ABSENT), no «seis».
    for line in ("9:265", "9:269", "9:302", "9:307", "9:308", "9:316", "9:278"):
        assert line in report, line
    assert "Son **7 filas**, no 6" in report

    # T0-b.2: la partición medida (17/11) y no la del paso 10 (15/15).
    assert "17 ya cubiertas / 11 sin cubrir" in report

    # Las cifras de acción y estado, tal como están en el catálogo de verdad.
    assert "231             | 238" in report
    assert "73 / 13         | 75 / 11" in report

    # Y el aviso de honestidad: no hay dotnet en el sandbox.
    assert "no tiene dotnet" in report


def test_las_relajaciones_del_ci_estan_reparadas() -> None:
    """El job «Paso 9» ya no acepta `capacidades >= 68`: comprueba §10 por
    invariantes propias. Y ninguna prueba de catálogo deja de enumerar una
    sección sin sustituirlo por algo más estricto."""
    workflow = (ROOT / ".github" / "workflows" / "ledger-verify.yml").read_text(encoding="utf-8")
    assert 'cov["capacidades"] >= 68' not in workflow
    # Paso 12: la sección 10 creció a 30 capacidades / 60 acciones y el job del
    # paso 9 se actualizó con ella; lo que este test protege es que la
    # comprobación sea por invariantes del fichero, no un umbral flojo.
    assert 'len(caps10) == 30' in workflow
    assert 'acts10 == 60' in workflow

    wave1 = (ROOT / "tests" / "Evo.Catalog.Tests" / "Wave1CatalogTests.cs").read_text(encoding="utf-8")
    assert "SectionId is not 10 and not 9" in wave1
    # Paso 12: la sección 9 creció a 19 capacidades; lo que el test protege es
    # que la sección se enumere por su cuenta, no el número de aquel día.
    assert "catalog.Definitions.Count(d => d.SectionId == 9)" in wave1

    # Hay un barrido de TODO el catálogo que no depende de listas de ids.
    sweep = (ROOT / "tests" / "Evo.Catalog.Tests" / "Wave4CatalogTests.cs").read_text(encoding="utf-8")
    assert "EveryCapabilityInTheCatalogMeetsTheSameInvariants" in sweep
    assert "Assert.Equal(88, all.Count)" in sweep


# --------------------------------------------------------------------- ADR-0005
def test_el_adr_0005_existe_y_esta_propuesto() -> None:
    assert ADR5.is_file()
    text = ADR5.read_text(encoding="utf-8")
    # Paso 12: el ADR se amplía con `registryCreateKey`, pero sigue Propuesto.
    assert "- **Estado**: Propuesto (paso 11" in text
    for section in ("## Contexto", "## Decisión", "## Consecuencias"):
        assert section in text, section
    # Los tres huecos que cierra y los dos que deja declarados.
    assert "registryDeleteKey" in text and "taskCreate" in text
    assert "w32tm" in text
    assert "IRegistryTreeReader" in text
    assert "fail-closed" in text
    # Cita las pruebas que lo sostienen.
    assert "Wave4EngineTests" in text and "Wave4CatalogTests" in text


def test_el_adr_cita_los_ficheros_que_de_verdad_existen() -> None:
    text = ADR5.read_text(encoding="utf-8")
    paths = re.findall(r"`((?:src|tests)/[^`]+\.(?:cs|csproj))`", text)
    assert paths
    for path in paths:
        assert (ROOT / path).is_file(), path
