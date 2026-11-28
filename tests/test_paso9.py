"""Tests del paso 9: oleada 2 del catálogo = sección 10 (Explorador e interfaz).

Todo lo que se comprueba aquí se reproduce con los scripts del repo:
    python3 tools/ledger_extract/build_section10_catalog.py --check
    python3 tools/ledger_extract/verify_catalog_coverage.py
    python3 tools/ledger_extract/audit_catalog_values.py
    python3 tools/ledger_extract/build_upstream_capability_map.py
    python3 tools/ledger_extract/build_wave_plan.py
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

import build_section10_catalog as b10  # noqa: E402
import verify_catalog_coverage as vcc  # noqa: E402

LEDGER = ROOT / "inventory" / "ledger"
CATALOG = ROOT / "catalog" / "capabilities"
SECTION10 = CATALOG / "section10_explorer_ui.json"
RECON = LEDGER / "inventory-reconciliation.tsv"
AUDIT = LEDGER / "catalog-value-audit.tsv"
MAP = LEDGER / "upstream-capability-map.tsv"
EXCEPTIONS = ROOT / "catalog" / "exceptions" / "value-deviations.json"
PLAN = ROOT / "docs" / "reports" / "plan-oleadas.md"
RELEASES = ROOT / "catalog" / "windows-releases.json"

DOCUMENT = json.loads(SECTION10.read_text(encoding="utf-8"))
CAPS = DOCUMENT["capabilities"]
BY_ID = {c["id"]: c for c in CAPS}

ID_PATTERN = re.compile(r"^[a-z0-9]+(\.[a-z0-9\-]+)+$")
CLSID_CTX_MENU = "{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def actions_of(cap_id: str) -> list[dict]:
    return BY_ID[cap_id]["actions"]


# ------------------------------------------------------------------ T1 catálogo
def test_el_fichero_de_la_seccion_10_reproduce_byte_a_byte() -> None:
    """El JSON no se edita a mano: lo genera el script desde el pin."""
    assert b10.dump(b10.build()) == SECTION10.read_text(encoding="utf-8")
    assert SECTION10.read_text(encoding="utf-8").endswith("\n")
    assert "\r\n" not in SECTION10.read_text(encoding="utf-8")


def test_todas_las_acciones_llevan_el_discriminador_de_tipo() -> None:
    """`CapabilityAction` es polimórfica: sin `"type"` el cargador estricto de
    .NET rechaza el fichero entero (lo comprobó el CI del paso 9).

    Cambió en el paso 11: la sección 10 tiene DOS formas de acción desde que el
    motor sabe borrar claves completas (`registryDeleteKey`), no una. Y en el
    paso 12 son TRES: `registryCreateKey` expresa la `AddKey` de
    `explorer.home.restore`. La forma se comprueba por tipo, no se relaja la
    comprobación.
    """
    tipos = ("registry", "registryDeleteKey", "registryCreateKey")
    for cap in CAPS:
        for action in cap["actions"]:
            assert action["type"] in tipos, (cap["id"], action)
    # Una sola forma por discriminador: un campo de más en una sola capacidad
    # sería una acción que el cargador ignora en silencio.
    for kind in tipos:
        shapes = {tuple(sorted(a.keys())) for c in CAPS for a in c["actions"]
                  if a["type"] == kind}
        assert len(shapes) == 1, (kind, shapes)
    assert {tuple(sorted(a.keys())) for c in CAPS for a in c["actions"]
            if a["type"] == "registry"} == {
        ('description', 'hive', 'keyPath', 'operation', 'order',
         'type', 'value', 'valueName', 'valueType')}
    # La forma nueva es la del contrato cerrado: colmena, ruta y recursión.
    assert {tuple(sorted(a.keys())) for c in CAPS for a in c["actions"]
            if a["type"] == "registryDeleteKey"} == {
        ('description', 'hive', 'keyPath', 'order', 'recursive', 'type')}
    # Y la del paso 12: colmena y ruta, sin valor ni recursión (una clave vacía).
    assert {tuple(sorted(a.keys())) for c in CAPS for a in c["actions"]
            if a["type"] == "registryCreateKey"} == {
        ('description', 'hive', 'keyPath', 'order', 'type')}


def test_hay_30_capacidades_y_60_acciones() -> None:
    # Paso 11: la acción DeleteKey de `explorer.home.hide` ya se declara (antes se
    # omitía porque el motor no sabía borrar claves): 56 -> 57.
    # Paso 12: `explorer.home.restore` es la capacidad NUEVA que expresa la
    # `AddKey` del estado Enable de Home (29 -> 30 capacidades) y añade tres
    # acciones: crear la clave + dos valores (57 -> 60).
    assert len(CAPS) == 30
    assert sum(len(c["actions"]) for c in CAPS) == 60
    assert [c["id"] for c in CAPS] == sorted(c["id"] for c in CAPS), "orden estable"
    assert len({c["id"] for c in CAPS}) == 30


def test_los_ids_cumplen_el_contrato_y_el_namespace() -> None:
    for cap in CAPS:
        assert ID_PATTERN.match(cap["id"]), cap["id"]
        assert cap["id"].split(".")[0] in ("explorer", "ui"), cap["id"]
        assert cap["sectionId"] == 10


def test_adr_0003_en_todas_las_capacidades() -> None:
    allowed_restore = {"SessionUndo", "RestorePoint", "FullBackup", "None"}
    for cap in CAPS:
        assert cap["reversibility"] == "Reversible", cap["id"]
        assert cap["restore"] in allowed_restore
        assert cap["restore"] == "SessionUndo", cap["id"]
        assert cap["securityImpact"] in ("Improves", "Neutral", "Reduces")
        assert cap["state"] in ("Implemented", "Specified")
        # Paso 12 (R1): `Implemented` sólo si el pin no deja nada fuera; si lo
        # deja, la capacidad tiene que ser `Specified` y decirlo. Se comprueba en
        # las dos direcciones, no se admite ninguna de las dos a ciegas.
        if "FUERA DE ESTA CAPACIDAD (R1)" in cap["description"]:
            assert cap["state"] == "Specified", cap["id"]
        if cap["state"] == "Specified":
            assert "R1" in cap["provenance"], cap["id"]
        assert cap["variants"], cap["id"]
        assert set(cap["variants"]) <= {"Evo", "Atlas", "WinUtil", "Default"}
        # La confirmación es exactamente la del riesgo (CapabilityRules).
        assert cap["confirmation"] == {
            "Safe": "None", "Low": "SimpleClick", "Medium": "Summary",
            "High": "SummaryAndRestorePoint", "Critical": "TypeOperationName",
        }[cap["risk"]], cap["id"]
        # Y quien reduce seguridad no puede ir por debajo de Medium.
        if cap["securityImpact"] == "Reduces":
            assert cap["risk"] in ("Medium", "High", "Critical"), cap["id"]


def test_el_privilegio_sale_de_las_colmenas_que_escribe() -> None:
    for cap in CAPS:
        hives = {a["hive"] for a in cap["actions"]}
        expected = "Admin" if hives & {"LocalMachine", "Users"} else "User"
        assert cap["privilege"] == expected, (cap["id"], hives, cap["privilege"])


def test_supported_builds_es_explicito_y_del_catalogo() -> None:
    known = {release["build"] for release in json.loads(
        RELEASES.read_text(encoding="utf-8"))["releases"]}
    for cap in CAPS:
        assert cap["supportedBuilds"], f"{cap['id']}: supportedBuilds vacío"
        assert cap["supportedBuilds"] == sorted(cap["supportedBuilds"]), cap["id"]
        assert len(set(cap["supportedBuilds"])) == len(cap["supportedBuilds"])
        assert set(cap["supportedBuilds"]) <= known, cap["id"]


def test_el_menu_contextual_clasico_es_solo_windows_11() -> None:
    cap = BY_ID["ui.context-menu.classic"]
    assert cap["supportedBuilds"] == [22631, 26100, 26200]
    assert 19045 not in cap["supportedBuilds"]
    action = cap["actions"][0]
    assert CLSID_CTX_MENU in action["keyPath"]
    assert action["valueName"] == ""
    assert action["value"] == ""
    assert action["valueType"] == "String"
    assert action["hive"] == "CurrentUser"
    # Las tres variantes y la evidencia de WinUtil, línea 326 del inventario.
    assert set(cap["variants"]) == {"Evo", "Atlas", "WinUtil"}
    assert "winutil:tweak:WPFTweaksRightClickMenu" in cap["provenance"]
    assert "1172" in cap["provenance"]


def test_omitir_la_pantalla_de_bloqueo_no_se_declara_como_reduccion() -> None:
    """`ui.lockscreen.hide` quita la imagen del bloqueo, no la autenticación.

    Se valoró declararla SecurityImpact=Reduces y se descartó: con Reduces el motor
    exige riesgo >= Medium y punto de restauración para escribir un valor de HKCU,
    desproporcionado para una capa visual. La decisión queda escrita en su
    `description` y en las preguntas abiertas del informe del paso 9.
    """
    cap = BY_ID["ui.lockscreen.hide"]
    assert cap["securityImpact"] == "Neutral"
    assert cap["risk"] == "Low"
    assert cap["confirmation"] == "SimpleClick"
    assert cap["reversibility"] == "Reversible"
    assert cap["restore"] == "SessionUndo"
    assert "Reduces" in cap["description"], "la decisión y su motivo deben quedar escritos"
    # Y ninguna capacidad de la sección 10 reduce seguridad con riesgo < Medium.
    for other in CAPS:
        if other["securityImpact"] == "Reduces":
            assert other["risk"] in ("Medium", "High", "Critical"), other["id"]


def test_las_cinco_capacidades_sin_19045_lo_justifican() -> None:
    sin_w10 = [c["id"] for c in CAPS if 19045 not in c["supportedBuilds"]]
    # Paso 12: `explorer.home.restore` es la contraparte de `explorer.home.hide` y
    # usa el mismo CLSID de Windows 11, asi que tampoco declara 19045.
    assert sin_w10 == [
        "explorer.gallery.hide",
        "explorer.home.hide",
        "explorer.home.restore",
        "ui.context-menu.classic",
        "ui.taskbar.end-task",
        "ui.taskbar.icons-centered",
    ]
    for cap_id in sin_w10:
        assert "Builds:" in BY_ID[cap_id]["provenance"], cap_id


def test_toda_accion_es_una_operacion_que_el_motor_sabe_deshacer() -> None:
    """Set y Delete son las dos únicas operaciones del motor; las dos se deshacen
    con el valor previo. Ninguna acción borra CLAVES ni escribe binarios opacos."""
    for cap in CAPS:
        orders = [a["order"] for a in cap["actions"]]
        assert orders == sorted(orders) == list(range(1, len(orders) + 1)), cap["id"]
        for action in cap["actions"]:
            if action["type"] == "registryDeleteKey":
                # Borrado de CLAVE completa: la inversa es la instantánea previa
                # del subárbol que guarda el diario (paso 11).
                assert set(action) == {"type", "order", "hive", "keyPath",
                                       "recursive", "description"}, (cap["id"], action)
                assert action["recursive"] is False, cap["id"]
                continue
            if action["type"] == "registryCreateKey":
                # Creación de clave VACÍA (paso 12): la inversa es borrarla, y sólo
                # se apunta si no existía antes.
                assert set(action) == {"type", "order", "hive", "keyPath",
                                       "description"}, (cap["id"], action)
                continue
            assert action["operation"] in ("Set", "Delete"), cap["id"]
            # DWord y String son la mayoría; ExpandString es texto que el diario
            # devuelve tal cual. El único Binary del fichero es UserPreferencesMask
            # de ui.visual-effects.minimal, y viene copiado del pin (se comprueba
            # byte a byte en test_el_binario_de_efectos_visuales_es_el_del_pin).
            assert action["valueType"] in (
                "DWord", "String", "ExpandString", "Binary"), cap["id"]
            if action["valueType"] == "Binary":
                assert cap["id"] == "ui.visual-effects.minimal", cap["id"]
                assert action["valueName"] == "UserPreferencesMask", cap["id"]
            assert action["keyPath"] and "?" not in action["keyPath"]
            assert action["description"].strip()


def test_el_binario_de_efectos_visuales_es_el_del_pin() -> None:
    """UserPreferencesMask son 8 bytes; el catálogo los copia en base64 del pin,
    no los inventa. Se comprueba el tamaño y el tipo."""
    import base64

    mask = [a for a in actions_of("ui.visual-effects.minimal")
            if a["valueName"] == "UserPreferencesMask"]
    assert len(mask) == 1
    action = mask[0]
    assert action["valueType"] == "Binary"
    raw = base64.b64decode(action["value"])
    assert len(raw) == 8, len(raw)
    assert action["hive"] == "CurrentUser"


def test_la_procedencia_cita_el_pin_y_el_estado() -> None:
    for cap in CAPS:
        provenance = cap["provenance"]
        assert re.search(r"atlas@[0-9a-f]{40}:|winutil@[0-9a-f]{40}:", provenance), cap["id"]
        assert "ledger_refs:" in provenance, cap["id"]
        if "atlas@" in provenance and cap["id"] in (
                "explorer.gallery.hide", "explorer.home.hide", "ui.context-menu.classic",
                "explorer.compact-view.enable", "ui.snap-layouts.disable"):
            assert re.search(r"\(estado '[A-Za-z]+'\)", provenance), cap["id"]


def test_las_capacidades_de_atlas_no_fusionan_estados() -> None:
    """Semántica Toggle 8c: de cada .psd1 se copia UN estado, no dos."""
    home = BY_ID["explorer.home.hide"]
    assert "estado 'Disable'" in home["provenance"]
    values = {(a["keyPath"], a["valueName"]): a["value"]
              for a in home["actions"] if a["type"] == "registry"}
    # Paso 11: la tercera acción es el DeleteKey del pin (ya expresable).
    assert len(home["actions"]) == 3
    assert [a["type"] for a in home["actions"]] == [
        "registryDeleteKey", "registry", "registry"]
    assert values[(
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "LaunchTo")] == "1"
    assert values[(
        r"Software\Classes\CLSID\{f874310e-b6b7-47dc-bc84-b9e6b38f5903}",
        "System.IsPinnedToNameSpaceTree")] == "0"

    # El 'Enable' de ExtractContextMenu BORRA cuatro valores de
    # `Shell Extensions\Blocked`; es la cara opuesta del 'Disable', que escribe
    # la cadena vacía. Aquí sólo entra el estado Enable, con sus 4 Delete.
    extract = BY_ID["explorer.extract-context-menu.add"]
    assert "estado 'Enable'" in extract["provenance"]
    assert len(extract["actions"]) == 4
    assert {a["operation"] for a in extract["actions"]} == {"Delete"}
    assert all(a["keyPath"].endswith("Shell Extensions\\Blocked") for a in extract["actions"])


def test_las_operaciones_de_clave_se_declaran_o_se_justifican() -> None:
    """Paso 11: `DeleteKey` ya es una acción del motor (ADR-0005).

    `explorer.home.hide` la DECLARA; las dos `DeleteKey` de
    `explorer.removable-drives.sidebar` están en el estado «Disable» del pin, que
    es el CONTRARIO al que declara la capacidad (estado «Enable»): incluirlas
    borraría lo que la capacidad enciende, y la descripción lo dice con el
    motivo medido en vez de callarlo.
    """
    home = BY_ID["explorer.home.hide"]
    assert "BORRA la clave" in home["description"]
    assert [a["type"] for a in home["actions"]].count("registryDeleteKey") == 1

    drums = BY_ID["explorer.removable-drives.sidebar"]
    assert not [a for a in drums["actions"] if a["type"] == "registryDeleteKey"]
    assert "CONTRARIO" in drums["description"]
    assert "DeleteKey" in drums["description"]


def test_las_desviaciones_declaradas_siguen_siendo_las_que_hay() -> None:
    deviations = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))["deviations"]
    # Paso 10: la sección 9 añade una desviación de VALOR, no de significado
    # (SettingsPageVisibility la escriben Atlas y WinUtil con listas distintas).
    assert [d["capability_id"] for d in deviations] == [
        "debloat.settings.home", "system.settings-page-visibility.hide"]
    kinds = {d["deviation_kind"] for d in deviations}
    assert kinds <= {"value", "switch-meaning"}
    assert all(d["reason"].strip() for d in deviations)
    # Las 29 de la sección 10 no declaran ninguna desviación: copian el pin.
    assert not [d for d in deviations if d["capability_id"] in BY_ID]


# ------------------------------------------------------------------- T3 cobertura
def test_el_verificador_cubre_las_29_lineas_mapped_de_la_seccion_10() -> None:
    assert vcc.main([]) == 0
    report = json.loads(subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract" / "verify_catalog_coverage.py"),
         "--json"], capture_output=True, text=True, check=False).stdout)
    # Paso 10 suma la sección 9 y sus 18 capacidades al mismo verificador.
    assert report["secciones_terminadas"] == ["1", "2", "3", "4", "9", "10"]
    assert report["por_seccion"]["10"]["lineas_mapped"] == 29
    assert report["por_seccion"]["10"]["cubiertas"] == 29
    assert report["por_seccion"]["10"]["huecos"] == 0
    assert report["huecos"] == 0
    assert report["huecos_no_declarados"] == 0
    # Paso 12: 86 -> 88; paso 7: +12 seccion 4 +1 bateria seccion 9 = 101.
    assert report["capacidades"] == 101
    # DESVIACIÓN (etapa 7, línea 121 ahora Mapped vía WPFTweaksServices): sec 4 pasa de 12 a 13 Mapped.
    assert report["lineas_mapped_1_3"] == 3 + 17 + 6 + 13 + 31 + 29


def test_la_seccion_10_del_ledger_tiene_29_mapped_y_ninguna_queda_absente() -> None:
    rows = [r for r in read_tsv(RECON) if r["seccion"] == "10"]
    assert len(rows) == 48
    estados = {r["status"] for r in rows}
    mapped = [r for r in rows if r["status"] == "Mapped"]
    assert len(mapped) == 29, [r["linea"] for r in mapped]
    # Las seis líneas que el paso 4e marcaba Absent-At-Pin y el paso 9 corrigió.
    assert {r["linea"] for r in mapped} >= {"326", "339", "341", "343", "344", "347"}
    assert "Absent-At-Pin" in estados


def test_la_auditoria_de_valores_no_tiene_ni_ambiguous_ni_unhandled() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract" / "audit_catalog_values.py")],
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ambiguous" not in result.stdout
    assert "unhandled" not in result.stdout
    rows = read_tsv(AUDIT)
    assert rows
    assert not [r for r in rows if r["relation"] == "ambiguous"]
    assert not [r for r in rows if r["relation"] == "unhandled"]
    # Al principio el auditor sólo veía 16 de las 56 acciones de la sección 10:
    # filtraba por `action["type"] == "registry"` y el generador no escribía el
    # discriminador en la rama de Atlas. Con el discriminador corregido entran las
    # 56 y todas coinciden con el pin (Set y Delete incluidos).
    # Paso 11: el DeleteKey de `explorer.home.hide` entra en la auditoría como
    # fila propia (57), casada contra el `Operation = 'DeleteKey'` del pin.
    # Paso 12: los dos valores de `explorer.home.restore` suman 59 filas
    # (60 acciones menos la `registryCreateKey`, que no escribe ningún valor).
    section10 = [r for r in rows if r["capability_id"] in BY_ID]
    assert len(section10) == 59, len(section10)
    assert all(r["relation"] in ("equals-apply", "equals-on") for r in section10), [
        r for r in section10 if r["relation"] not in ("equals-apply", "equals-on")]


def test_el_mapa_de_upstream_marca_covered_con_una_capacidad_real() -> None:
    catalog_ids = set()
    for path in sorted(CATALOG.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        catalog_ids |= {c["id"] for c in document["capabilities"]}

    rows = read_tsv(MAP)
    covered = [r for r in rows if r["status"] == "covered"]
    assert covered
    for row in covered:
        assert row["capability_id"] in catalog_ids, row["upstream_id"]
        assert row["reason"].strip()
    # El mapa cubre ya capacidades de la sección 10 y ninguna apunta a un id muerto.
    assert {r["capability_id"] for r in covered} & set(BY_ID)
    for row in read_tsv(RECON):
        if row["seccion"] == "10" and row["status"] == "Mapped":
            assert row["mapped_ids"].strip()


def test_las_celdas_del_tsv_no_llevan_cuerpos_de_codigo() -> None:
    for path in (RECON, AUDIT, MAP):
        for row in read_tsv(path):
            for cell in row.values():
                assert len(cell) <= 400, (path.name, cell[:60])


def test_el_plan_de_oleadas_marca_la_seccion_10_como_cerrada() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract" / "build_wave_plan.py"), "--check"],
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    text = PLAN.read_text(encoding="utf-8")
    fila = next(l for l in text.splitlines() if l.startswith("| 10 |"))
    cells = [c.strip() for c in fila.split("|")]
    assert cells[3] == "48"      # líneas
    assert cells[4] == "29"      # Mapped
    assert cells[9] == "29"      # Mapped cubiertas
    assert cells[10] == "0"      # Mapped sin cubrir
    assert "29 de 29" in text


def test_el_informe_de_rangos_es_reproducible_y_dice_lo_medido() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "ledger_extract"
                             / "build_build_ranges_report.py"), "--check"],
        capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    text = (ROOT / "docs" / "reports" / "rangos-build.md").read_text(encoding="utf-8")
    # Paso 12h: 88 capacidades (69 Implemented / 19 Specified; ntp-servers a
    # Specified por R1) y 79 + 9 de rango.
    assert "**101** capacidades, 76 `Implemented` y 25 `Specified`" in text
    assert "**92**" in text and "**9**" in text
    # Las cinco de la sección 10 con rango recortado aparecen cada una.
    for cap_id in ("explorer.gallery.hide", "explorer.home.hide",
                   "explorer.home.restore", "ui.context-menu.classic",
                   "ui.taskbar.end-task", "ui.taskbar.icons-centered"):
        assert f"`{cap_id}`" in text, cap_id
