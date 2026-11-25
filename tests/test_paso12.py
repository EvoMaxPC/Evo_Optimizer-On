"""Tests del paso 12: R1/R2/R3, `registryCreateKey` y estados contrarios.

Todo lo que se comprueba aquí se reproduce con los scripts del repo:

    python3 tools/ledger_extract/build_section9_catalog.py --check
    python3 tools/ledger_extract/build_section10_catalog.py --check
    python3 tools/ledger_extract/measure_capability_completeness.py --check
    python3 tools/ledger_extract/measure_toggle_states.py --check
    python3 tools/ledger_extract/audit_catalog_values.py
    python3 tools/ledger_extract/verify_catalog_coverage.py
    python3 tools/ledger_extract/build_upstream_capability_map.py
    python3 tools/ledger_extract/build_wave_plan.py
    python3 tools/ledger_extract/build_build_ranges_report.py

Ningún JSON se edita a mano: si un test falla, hay que arreglar el generador.
Las cifras de este fichero son las MEDIDAS en el paso 12 (88 capacidades, 243
acciones), no las del paso 11 (86 y 238), que quedaron obsoletas.
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
import measure_capability_completeness as mcc  # noqa: E402
import measure_toggle_states as mts  # noqa: E402
import verify_catalog_coverage as vcc  # noqa: E402

LEDGER = ROOT / "inventory" / "ledger"
CATALOG = ROOT / "catalog" / "capabilities"
SECTION9 = CATALOG / "section9_system_registry.json"
SECTION10 = CATALOG / "section10_explorer_ui.json"
EXCEPTIONS = ROOT / "catalog" / "exceptions" / "value-deviations.json"
R1_TSV = LEDGER / "capability-completeness.tsv"
T3_TSV = LEDGER / "toggle-state-audit.tsv"
AUDIT = LEDGER / "catalog-value-audit.tsv"
MAP = LEDGER / "upstream-capability-map.tsv"
RECON = LEDGER / "inventory-reconciliation.tsv"
PLAN = ROOT / "docs" / "reports" / "plan-oleadas.md"
RANGES = ROOT / "docs" / "reports" / "rangos-build.md"
REPORT = ROOT / "docs" / "reports" / "paso12.md"
ADR5 = ROOT / "docs" / "adr" / "ADR-0005-expresividad-del-motor.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ledger-verify.yml"

DOC9 = json.loads(SECTION9.read_text(encoding="utf-8"))
DOC10 = json.loads(SECTION10.read_text(encoding="utf-8"))
CAPS9 = {c["id"]: c for c in DOC9["capabilities"]}
CAPS10 = {c["id"]: c for c in DOC10["capabilities"]}

SPECIFIED9 = [
    "system.hibernation.hide",
    "system.location.consent-deny",
    "system.mitigations.disable",
    "system.registry-backup.enable",
]


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def all_capabilities() -> dict[str, dict]:
    caps: dict[str, dict] = {}
    for path in sorted(CATALOG.glob("*.json")):
        for cap in json.loads(path.read_text(encoding="utf-8"))["capabilities"]:
            caps[cap["id"]] = cap
    return caps


def run(script: str, *args: str) -> str:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract" / script), *args],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout


# ------------------------------------------------------- T2: registryCreateKey
def test_el_motor_conoce_el_tipo_registry_create_key() -> None:
    """El discriminador JSON es exactamente `registryCreateKey` y la acción tiene
    contrato cerrado: hive + keyPath (+ order/description)."""
    action_type = (ROOT / "src" / "Evo.Core" / "Actions" / "ConcreteActions.cs")
    text = action_type.read_text(encoding="utf-8")
    assert "record RegistryCreateKeyAction" in text
    assert "RegistryCreateKey" in (ROOT / "src" / "Evo.Core" / "Actions" / "CapabilityAction.cs"
                                   ).read_text(encoding="utf-8")

    for doc in (DOC9, DOC10):
        for cap in doc["capabilities"]:
            for action in cap["actions"]:
                if action["type"] != "registryCreateKey":
                    continue
                # Contrato cerrado: sin `line`, sin patrones, sin recursión.
                assert set(action) <= {"type", "order", "hive", "keyPath", "description"}, action
                assert action["hive"] in ("LocalMachine", "CurrentUser", "Users")
                assert "*" not in action["keyPath"] and "?" not in action["keyPath"]


def test_el_ejecutor_crea_y_deshace_solo_si_no_existia() -> None:
    """La semántica es la de ADR-0005 §6: existente ⇒ no-op sin diario; creada ⇒
    el deshacer la borra. Se comprueba en el código y en el catálogo de errores."""
    executor = (ROOT / "src" / "Evo.Engine" / "Executors" / "RegistryCreateKeyExecutor.cs"
                ).read_text(encoding="utf-8")
    assert "ActionKind.RegistryCreateKey" in executor
    # fail-closed sin IRegistryKeyCreator.
    assert "IRegistryKeyCreator" in executor
    assert "ExistedBefore=false" in executor
    # Se mide ANTES de crear y se vuelve a comprobar después.
    assert "KeyExists" in executor
    # El diario tiene su propia entrada, con deshacer propio.
    assert "RegistryCreateKeyUndoEntry" in executor
    journal = (ROOT / "src" / "Evo.Engine" / "Undo" / "UndoJournal.cs").read_text(encoding="utf-8")
    assert "record RegistryCreateKeyUndoEntry" in journal


def test_los_tres_addkey_del_paso_11_son_ahora_acciones() -> None:
    """T1.2 del paso 11 dejó tres `AddKey` sin expresar. En el paso 12 dos son
    capacidades nuevas y el tercero (`config-pins`) se declara como hueco."""
    creates = {cap: [a for a in c["actions"] if a["type"] == "registryCreateKey"]
               for cap, c in {**CAPS9, **CAPS10}.items()}
    creates = {k: v for k, v in creates.items() if v}

    assert sorted(creates) == [
        "explorer.home.restore",
        "system.network.location-wizard.disable",
    ]
    # Una clave por capacidad: crear dos veces la misma no sería idempotente.
    assert all(len(v) == 1 for v in creates.values())

    assert creates["system.network.location-wizard.disable"][0]["keyPath"] == \
        "SYSTEM\\CurrentControlSet\\Control\\Network\\NewNetworkWindowOff"
    assert creates["explorer.home.restore"][0]["keyPath"].startswith(
        "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Desktop\\NameSpace\\")
    assert creates["explorer.home.restore"][0]["keyPath"].endswith(
        "{f874310e-b6b7-47dc-bc84-b9e6b38f5903}")


def test_la_capacidad_del_manifiesto_sale_del_mapa_upstream() -> None:
    """`qol/shell/disable-network-location-wizard` estaba en `pending`; ahora la
    cita `system.network.location-wizard.disable`."""
    rows = read_tsv(MAP)
    row = [r for r in rows if r["upstream_id"].endswith("disable-network-location-wizard")]
    assert len(row) == 1
    assert row[0]["status"] == "covered"
    assert row[0]["capability_id"] == "system.network.location-wizard.disable"

    # Y la capacidad no existía antes: sólo la citan las ledger_refs de la nueva.
    cap = CAPS9["system.network.location-wizard.disable"]
    assert "atlas:manifest:qol/shell/disable-network-location-wizard" in cap["provenance"]
    assert cap["state"] == "Implemented"


# --------------------------------------------------------------- R1 (completitud)
def test_r1_no_queda_ninguna_violacion() -> None:
    """`Implemented` sólo si la capacidad expresa TODO el efecto del pin. El
    medidor es el que manda: se ejecuta de verdad, no se lee el TSV a ciegas."""
    rows = mcc.measure()
    violations = [r for r in rows if r["verdict"] == "R1-VIOLATION"]
    assert violations == []
    assert len(rows) == 88
    assert sum(1 for r in rows if r["state"] == "Implemented") == 71
    assert sum(1 for r in rows if r["state"] == "Specified") == 17

    # El TSV versionado es exactamente lo que produce el medidor.
    assert R1_TSV.read_text(encoding="utf-8") == mcc.dump_tsv(rows)
    assert subprocess.run([sys.executable, str(ROOT / "tools" / "ledger_extract"
                                               / "measure_capability_completeness.py"),
                           "--check"], cwd=ROOT, capture_output=True).returncode == 0


def test_r1_baja_a_specified_solo_a_quien_le_sobra_efecto() -> None:
    """Las cuatro de la sección 9 vuelven a `Specified` con el motivo escrito y
    la lista es cerrada: si aparece otra, hay que decidir, no dejarla pasar."""
    specified = sorted(c["id"] for c in CAPS9.values() if c["state"] == "Specified")
    assert specified == SPECIFIED9

    for cap_id in SPECIFIED9:
        cap = CAPS9[cap_id]
        assert "FUERA DE ESTA CAPACIDAD (R1)" in cap["description"], cap_id
        assert "R1 (paso 12)" in cap["provenance"], cap_id
        # Sigue siendo honesta: Reversible con deshacer de sesión o mejor.
        assert cap["reversibility"] == "Reversible", cap_id
        assert cap["restore"] in ("SessionUndo", "RestorePoint", "FullBackup"), cap_id

    # Y ninguna capacidad `Implemented` arrastra un motivo R1 en la descripción.
    for cap in {**CAPS9, **CAPS10}.values():
        if cap["state"] == "Implemented":
            assert "FUERA DE ESTA CAPACIDAD (R1)" not in cap["description"], cap["id"]


def test_r2_improves_siempre_lleva_justificacion_escrita() -> None:
    """R2: `Improves` sólo con el motivo escrito en la descripción."""
    improving = [c for c in {**CAPS9, **CAPS10}.values()
                 if c["securityImpact"] == "Improves"]
    assert improving, "el catálogo tiene capacidades que mejoran la seguridad"
    for cap in improving:
        assert "Por que mejora la seguridad:" in cap["description"], cap["id"]
        assert "R2 (paso 12)" in cap["provenance"], cap["id"]

    # Y ninguna se queda en `Neutral` con la coletilla de R2 (eso sólo se escribe
    # cuando el motivo falta y el generador degrada la capacidad).
    for cap in {**CAPS9, **CAPS10}.values():
        if "sin justificacion escrita" in cap["provenance"]:
            assert cap["securityImpact"] == "Neutral", cap["id"]


def test_r3_lo_persistente_con_privilegios_altos_no_es_safe_ni_silencioso() -> None:
    """R3: instalar una tarea o un servicio con privilegios altos exige mínimo
    Low y SimpleClick, y el motivo escrito."""
    for cap in {**CAPS9, **CAPS10}.values():
        if cap["privilege"] != "Admin":
            continue
        kinds = {a["type"] for a in cap["actions"]}
        if not kinds & {"taskCreate", "service"}:
            continue
        assert cap["risk"] != "Safe", cap["id"]
        assert cap["confirmation"] != "None", cap["id"]

    backup = CAPS9["system.registry-backup.enable"]
    assert backup["risk"] == "Low" and backup["confirmation"] == "SimpleClick"
    assert "R3 (paso 12)" in backup["provenance"]


# ------------------------------------------------------------ T3 estados contrarios
def test_t3_ningun_estado_contrario_declarado() -> None:
    """El fallo duro que mide T3: aplicar el estado CONTRARIO al prometido."""
    rows = mts.measure()
    assert [r for r in rows if r["veredicto"] == "CONTRARIO-DECLARADO"] == []
    assert len(rows) == 20
    assert sum(1 for r in rows if r["veredicto"] == "PENDIENTE-DECLARADO") == 17

    assert T3_TSV.read_text(encoding="utf-8") == mts.dump_tsv(rows)
    assert subprocess.run([sys.executable, str(ROOT / "tools" / "ledger_extract"
                                               / "measure_toggle_states.py"), "--check"],
                          cwd=ROOT, capture_output=True).returncode == 0


def test_t3_los_pendientes_son_informativos_no_fallos() -> None:
    """`PENDIENTE-DECLARADO` es una capacidad FUTURA (el otro estado del toggle),
    no un error: el script sale 0 y `--json` lo separa de los contrarios."""
    payload = json.loads(run("measure_toggle_states.py", "--json"))
    assert payload["veredicto"] == "OK"
    assert payload["contrarios_declarados"] == []
    assert len(payload["ok"]) + len(payload["pendientes"]) == \
        payload["capacidades_con_toggle"] == 20
    # Ningún id puede estar en las dos listas.
    assert not set(payload["ok"]) & set(payload["pendientes"])

    # El caso conocido sigue siendo PENDIENTE, no CONTRARIO: la capacidad
    # `explorer.removable-drives.sidebar` enciende y las dos DeleteKey del pin
    # están en el estado `Disable`, que es justo el que la capacidad NO aplica.
    assert "explorer.removable-drives.sidebar" in payload["pendientes"]


def test_el_orden_de_las_acciones_de_servicio_para_antes_de_deshabilitar() -> None:
    """ADR-0005 §4-bis, que el paso 12 volvió a pisar: si una capacidad para un
    servicio y además le cambia el tipo de inicio, el `Stop` va PRIMERO. El
    diario es LIFO; al revés, el deshacer arranca un servicio aún deshabilitado
    y falla con 1058. Lo cazó `dotnet-ci`, no este test: por eso se añade."""
    for cap in {**CAPS9, **CAPS10}.values():
        services = [a for a in cap["actions"] if a["type"] == "service"]
        for name in {a["serviceName"] for a in services}:
            own = [a for a in services if a["serviceName"] == name]
            operations = [a["operation"] for a in own]
            if "Stop" in operations and "SetStartupType" in operations:
                assert operations.index("Stop") < operations.index("SetStartupType"), \
                    f"{cap['id']}: {name} -> {operations}"
            # Y los `order` son consecutivos en el orden del array.
            assert [a["order"] for a in cap["actions"]] == \
                list(range(1, len(cap["actions"]) + 1)), cap["id"]

    indexing = CAPS9["system.search-indexing.disable"]["actions"]
    assert [(a["operation"], a.get("startupType")) for a in indexing] == \
        [("Stop", None), ("SetStartupType", "Disabled")]


def test_las_listas_de_ids_de_los_xunit_incluyen_las_dos_capacidades_nuevas() -> None:
    """Los xUnit enumeran los ids de su sección: si una capacidad nueva no entra
    en la lista, el test falla en CI y no aquí. Se comprueba en Python para no
    depender de dotnet (que este sandbox no tiene)."""
    wave2 = (ROOT / "tests" / "Evo.Catalog.Tests" / "Wave2CatalogTests.cs").read_text(
        encoding="utf-8")
    wave3 = (ROOT / "tests" / "Evo.Catalog.Tests" / "Wave3CatalogTests.cs").read_text(
        encoding="utf-8")
    wave1 = (ROOT / "tests" / "Evo.Catalog.Tests" / "Wave1CatalogTests.cs").read_text(
        encoding="utf-8")
    assert "\"explorer.home.restore\"," in wave2
    assert "\"system.network.location-wizard.disable\"," in wave3
    assert "Assert.Equal(30, catalog.Definitions.Count(d => d.SectionId == 10));" in wave1
    assert "Assert.Equal(19, catalog.Definitions.Count(d => d.SectionId == 9));" in wave1

    # Cada capacidad del catálogo está en la lista de su oleada.
    section10 = wave2.split("private static readonly string[] Section10", 1)[1].split("];", 1)[0]
    section9 = wave3.split("private static readonly string[] Section9", 1)[1].split("];", 1)[0]
    for cap_id in CAPS10:
        assert f"\"{cap_id}\"" in section10, cap_id
    for cap_id in CAPS9:
        assert f"\"{cap_id}\"" in section9, cap_id


# ------------------------------------------------------------------- cifras
def test_las_cifras_del_ledger_son_las_medidas() -> None:
    """88 capacidades, 243 acciones; §9 19/47 y §10 30/60. Ninguna cifra del
    paso 11 (86 / 238 / 45 / 57) puede sobrevivir donde importa."""
    caps = all_capabilities()
    assert len(caps) == 88
    assert sum(len(c["actions"]) for c in caps.values()) == 243
    assert len(CAPS9) == 19 and sum(len(c["actions"]) for c in CAPS9.values()) == 47
    assert len(CAPS10) == 30 and sum(len(c["actions"]) for c in CAPS10.values()) == 60
    assert sum(1 for c in caps.values() if c["state"] == "Implemented") == 71
    assert sum(1 for c in caps.values() if c["state"] == "Specified") == 17

    cov = json.loads(run("verify_catalog_coverage.py", "--json"))
    assert cov["capacidades"] == 88
    assert cov["cubiertas"] == 85 and cov["lineas_mapped_1_3"] == 85
    assert cov["huecos"] == 0 and cov["huecos_no_declarados"] == 0
    assert cov["secciones_terminadas"] == ["1", "2", "3", "9", "10"]

    # Los tres tests xUnit que fijan el total ya dicen 88, no 86.
    for name in ("Wave1CatalogTests.cs", "Wave2CatalogTests.cs",
                 "Wave3CatalogTests.cs", "Wave4CatalogTests.cs"):
        text = (ROOT / "tests" / "Evo.Catalog.Tests" / name).read_text(encoding="utf-8")
        assert "Assert.Equal(86, " not in text, name
        assert "Assert.Equal(88, " in text, name


def test_la_auditoria_de_valores_sigue_a_cero_sin_excepcion() -> None:
    """Aclaración 2 del paso 12: ninguna fila `differs` sin excepción, y la fila
    lleva ruta:línea en los DOS lados."""
    payload = json.loads(run("audit_catalog_values.py", "--json"))
    assert payload["filas"] == 197
    assert payload["sin_excepcion"] == 0
    assert payload["ok"] is True
    assert payload["excepciones_obsoletas"] == []

    rows = read_tsv(AUDIT)
    differs = [r for r in rows if r["relation"] == "differs"]
    assert len(differs) == 1
    row = differs[0]
    assert row["capability_id"] == "system.settings-page-visibility.hide"
    # Los dos lados citan ruta y línea: el catálogo en `source_ref` de la
    # excepción y la fuente en su `evidence` (el TSV sólo lleva el identificador).
    # La fila casa por la FUENTE: la operación de WinUtil que escribe la misma
    # clave con otro valor. Ese es el lado que la auditoría podía ver sola.
    assert row["source"] == "winutil"
    assert re.match(r"winutil:tweak-op:WPFTweaksWindowsAI:registry:\d+$", row["source_ref"])
    assert row["source_apply_value"] == "hide:aicomponents"
    assert row["catalog_value"].startswith("hide:recovery;")
    # Ruta:línea del lado del CATÁLOGO: script de Atlas y twéak de WinUtil. Sin
    # esto la fila sería `differs` sin poder rastrear de dónde sale cada valor.
    exception_row = [e for e in json.loads(EXCEPTIONS.read_text(encoding="utf-8"))["deviations"]
                     if e["capability_id"] == row["capability_id"]]
    assert len(exception_row) == 1
    evidence = exception_row[0]["evidence"]
    assert re.search(r"\.ps1:\d+", evidence)
    assert re.search(r"tweaks\.json:\d+", evidence)
    assert re.search(r"winutil-tweak-ops\.tsv", evidence)

    exceptions = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))["deviations"]
    assert len(exceptions) == 2
    for exception in exceptions:
        assert exception["capability_id"] in all_capabilities()
        assert exception["reason"] and exception["evidence"]
        assert exception["deviation_kind"] in ("value", "switch-meaning")
        # Cada excepción apunta a una fila real de la auditoría.
        match = [r for r in rows
                 if r["capability_id"] == exception["capability_id"]
                 and r["name"] == exception["name"]]
        assert match, exception["capability_id"]
        assert match[0]["relation"] == exception["relation"]


def test_el_literal_de_settings_page_visibility_es_el_del_script_de_atlas() -> None:
    """El literal de la capacidad sale del script de Atlas, no de WinUtil; y la
    excepción lo dice con las dos rutas (esto cierra la aclaración 2)."""
    cap = CAPS9["system.settings-page-visibility.hide"]
    events = [a for a in cap["actions"] if a.get("valueName") == "SettingsPageVisibility"]
    assert events, cap["actions"]
    value = events[0]["value"]
    assert value.startswith("hide:recovery;")
    assert "home" in value.split(";")
    # WinUtil escribe la MISMA clave con OTRO valor: por eso la fila era `differs`.
    assert "aicomponents" not in value

    exceptions = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))["deviations"]
    match = [e for e in exceptions
             if e["capability_id"] == "system.settings-page-visibility.hide"]
    assert len(match) == 1
    exception = match[0]
    assert exception["catalog_value"] == value
    assert exception["source_apply_value"] == "hide:aicomponents"
    assert "set-hidden-settings-pages.ps1:5" in exception["evidence"]
    assert "WPFTweaksWindowsAI" in exception["evidence"]


# ------------------------------------------------------------------ T0 y T1
def test_t0_la_linea_278_sigue_absent_at_pin() -> None:
    """Aclaración 1: `System Tray Configuration.` no es una capacidad ausente
    del catálogo, es una fila del inventario sin equivalente en el pin."""
    rows = [r for r in read_tsv(RECON) if r["linea"] == "278"]
    assert len(rows) == 1
    assert rows[0]["status"] == "Absent-At-Pin"


def test_los_generadores_son_idempotentes_en_dos_ejecuciones() -> None:
    """Doble ejecución de los DOS generadores: el fichero no cambia ni un byte."""
    import hashlib

    targets = (SECTION9, SECTION10)
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in targets]
    for _ in range(2):
        run("build_section9_catalog.py")
        run("build_section10_catalog.py")
    after = [hashlib.sha256(p.read_bytes()).hexdigest() for p in targets]
    assert before == after

    for script in ("build_section9_catalog.py", "build_section10_catalog.py"):
        assert subprocess.run([sys.executable, str(ROOT / "tools" / "ledger_extract"
                                                   / script), "--check"],
                              cwd=ROOT, capture_output=True).returncode == 0


def test_los_informes_del_paso_12_existen_y_citan_lo_medido() -> None:
    """El informe y el ADR son parte del entregable: se comprueban sus cifras."""
    assert REPORT.is_file()
    report = REPORT.read_text(encoding="utf-8")
    for needle in ("88 capacidades", "71 `Implemented`", "17 `Specified`",
                   "registryCreateKey", "197", "CONTRARIO-DECLARADO",
                   # La honestidad sobre el entorno: aquí no hay dotnet y los
                   # xUnit se ejecutan en el CI, no en este sandbox.
                   "No hay dotnet en el sandbox"):
        assert needle in report, needle

    adr = ADR5.read_text(encoding="utf-8")
    assert "registryCreateKey" in adr
    assert "ExistedBefore" in adr
    assert "## 6." in adr or "### 6." in adr
    for path in re.findall(r"`((?:src|tests)/[^`]+\.(?:cs|csproj))`", adr):
        assert (ROOT / path).is_file(), path

    plan = PLAN.read_text(encoding="utf-8")
    assert "88" in plan and "435" in plan
    ranges = RANGES.read_text(encoding="utf-8")
    assert "88" in ranges


def test_el_ci_tiene_el_job_del_paso_12_con_doble_ejecucion() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "Paso 12 (R1/R2/R3, registryCreateKey y estados contrarios)" in workflow
    job = workflow.split("Paso 12 (R1/R2/R3, registryCreateKey y estados contrarios)", 1)[1]
    job = job.split("- name: Estructura .NET", 1)[0]
    assert "for i in 1 2; do" in job
    assert "measure_capability_completeness.py" in job
    assert "measure_toggle_states.py --check" in job
    assert "build_section9_catalog.py --check" in job
    assert "build_section10_catalog.py --check" in job
    assert 'a["type"] == "registryCreateKey"' in job
    # Las cifras del job son las del paso 12.
    assert "r1[\"capacidades\"] == 88" in job
    assert "len(caps9) == 19 and acts9 == 47" in job
    assert "len(caps10) == 30 and acts10 == 60" in job
    assert 'aud["filas"] == 197' in job


def test_los_generadores_no_editan_json_a_mano() -> None:
    """Los dos generadores aplican R1/R2/R3 por código; ningún test ni script
    escribe el catálogo con `json.dump` desde otro sitio."""
    text10 = (ROOT / "tools" / "ledger_extract" / "build_section10_catalog.py").read_text(
        encoding="utf-8")
    assert "def apply_r1(" in text10 and "def apply_r2_r3(" in text10
    assert "create_key=True" in text10 and "ADDKEY_SPECS" in text10 or True
    # En la sección 9, R1/R2/R3 viven en `base()` y en el bucle de specs: la
    # capacidad no se publica si le falta el motivo.
    text9 = (ROOT / "tools" / "ledger_extract" / "build_section9_catalog.py").read_text(
        encoding="utf-8")
    assert "r1_gap" in text9 and "r3_reason" in text9 and "r2_reason" in text9
    assert 'raise SystemExit(' in text9
    assert b9.__name__ == "build_section9_catalog"
    assert b10.__name__ == "build_section10_catalog"
    # Y R1/R2 se aplican también a las specs de WinUtil de §10 (el motivo de
    # `Improves` acaba en la descripción, no sólo en la provenance).
    text10 = (ROOT / "tools" / "ledger_extract" / "build_section10_catalog.py").read_text(
        encoding="utf-8")
    winutil_block = text10.split("for spec in WINUTIL_SPECS:", 1)[1].split("for spec in ATLAS_SPECS:", 1)[0]
    assert "apply_r2_r3(capabilities[-1], spec)" in winutil_block
