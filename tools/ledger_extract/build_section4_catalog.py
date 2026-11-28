#!/usr/bin/env python3
"""Genera `catalog/capabilities/section4_services.json` (ETAPA 7, sección 4).

Los VALORES de cada acción no se escriben a mano: se leen del pin fijado
(WinUtil `70c23c8…` en `config/tweaks.json`; Atlas `ec3c4058…` en
`package/Executables/AtlasModules/Toggles/Services/*.psd1`) y la provenance
cita fichero, línea del pin Y línea del inventario de la sección 4 que cubre.
Si el pin no está en `/tmp/upstream`, el script falla con un mensaje claro:
no se inventa ningún literal.

Alcance de la sección 4 (OPTIMIZACIÓN DE SERVICIOS) del inventario
(docs/requirements/INVENTARIO_USUARIO.md, líneas 119-145):

WinUtil
  DiagTrack      línea 122  -> winutil:tweak-op:WPFTweaksServices:service:1
  MapsBroker     línea 123  -> winutil:tweak-op:WPFTweaksServices:service:2
  StorSvc        línea 124  -> winutil:tweak-op:WPFTweaksServices:service:3
  SharedAccess   línea 125  -> winutil:tweak-op:WPFTweaksServices:service:4
  CscService     línea 126  -> winutil:tweak-op:WPFTweaksServices:service:0

AtlasOS (toggles de Toggles/Services/ del pin, estado 'Disable')
  Bluetooth          línea 130  -> atlas:toggle:Bluetooth
  Lanman Workstation línea 131  -> atlas:toggle:LanmanWorkstation
  Network Discovery  línea 132  -> atlas:toggle:NetworkDiscovery

Las demás líneas de la sección 4 (Service Host Splitting, Set-WinUtilService,
NVIDIA Display Container, Printing, SuperFetch/SysMain, Windows Update,
Game Bar, indexación, localización, compartición de archivos, predeterminados,
Backup Services, Restore Atlas Service Defaults, Reset Services) quedan fuera
de esta oleada: o el pin no las implementa como valor de registro o servicio
expresable (Service Host Splitting, Set-WinUtilService), o su efecto vive en
un MachineAction de script .ps1 (NVIDIA Display Container, Printing,
SuperFetch) y no cabe en las acciones del motor sin una regla R1 escrita.
Cada una se documenta como gap en su descripción/provenance.

Salida determinista: orden por id, LF, UTF-8 sin BOM, 3 espacios de sangría.

Uso:
    python3 tools/ledger_extract/build_section4_catalog.py
    python3 tools/ledger_extract/build_section4_catalog.py --check
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "catalog" / "capabilities" / "section4_services.json"
UPSTREAM = Path("/tmp/upstream")
WINUTIL_TWEAKS = UPSTREAM / "winutil" / "config" / "tweaks.json"
ATLAS_TOGGLES = UPSTREAM / "atlas" / "package" / "Executables" / "AtlasModules" / "Toggles"

WINUTIL_PIN = "winutil@70c23c80641d7370532af2f619b2842658600842"
ATLAS_PIN = "atlas@ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f"
DEFAULT_BUILDS = [19045, 22631, 26100, 26200]

W_TWEAKS: dict = (
    json.loads(WINUTIL_TWEAKS.read_text(encoding="utf-8"), strict=False)
    if WINUTIL_TWEAKS.is_file() else {}
)

CONFIRM = {"Safe": "None", "Low": "SimpleClick", "Medium": "Summary",
           "High": "SummaryAndRestorePoint", "Critical": "TypeOperationName"}
RESTORE = {"Safe": "SessionUndo", "Low": "SessionUndo",
           "Medium": "RestorePoint", "High": "RestorePoint",
           "Critical": "FullBackup"}
HIVES = {"HKLM": "LocalMachine", "HKCU": "CurrentUser",
         "HKCR": "ClassesRoot", "HKU": "Users"}

# ----------------------------------------------------------------- especificación
# Cada entrada de WinUtil: id, nombre del servicio en el pin, línea del
# inventario de la sección 4, riesgo, seguridad y notas de construcción.
WINUTIL_SPECS = [
    dict(id="services.winutil.diagtrack", service="DiagTrack",
         name="Deshabilitar DiagTrack (telemetría de WinUtil)",
         inventario_linea=122,
         desc="Pone el servicio Connected User Experiences and Telemetry (DiagTrack) "
              "en arranque Deshabilitado, como WinUtil (WPFTweaksServices). Se detiene "
              "si estaba corriendo y el tipo de inicio previo se guarda para deshacer.",
         risk="Low", security="Improves",
         r2_reason=(
             "MEJORA la privacidad: DiagTrack envía datos de uso y diagnóstico a "
             "Microsoft. Deshabilitarlo corta esa telemetría. El coste (menos datos de "
             "diagnóstico) se declara en la descripción y no reduce ninguna protección."),
         build_note="DiagTrack existe en 19045 y en Windows 11"),
    dict(id="services.winutil.mapsbroker", service="MapsBroker",
         name="Pasar MapsBroker a inicio Manual",
         inventario_linea=123,
         desc="Pone el servicio MapsBroker en arranque Manual (no se inicia solo). "
              "WinUtil lo deja en Manual desde su tipo predeterminado Automatic. "
              "Reversible: el motor guarda el tipo previo.",
         risk="Low", security="Neutral",
         build_note="MapsBroker existe en 19045 y en Windows 11"),
    dict(id="services.winutil.storsvc", service="StorSvc",
         name="Pasar StorSvc a inicio Manual",
         inventario_linea=124,
         desc="Pone el servicio Almacenamiento (StorSvc) en arranque Manual, como "
              "WinUtil. Reversible: el motor guarda el tipo previo.",
         risk="Low", security="Neutral",
         build_note="StorSvc existe en 19045 y en Windows 11"),
    dict(id="services.winutil.sharedaccess", service="SharedAccess",
         name="Deshabilitar SharedAccess (compartición de conexión)",
         inventario_linea=125,
         desc="Pone el servicio SharedAccess (Compartición de conexión a Internet) "
              "en arranque Deshabilitado, como WinUtil. Puede impedir compartir la "
              "conexión a Internet por el equipo; el coste se declara en la descripción.",
         risk="Low", security="Neutral",
         build_note="SharedAccess existe en 19045 y en Windows 11"),
    dict(id="services.winutil.cscservice", service="CscService",
         name="Deshabilitar CscService (archivos sin conexión)",
         inventario_linea=126,
         desc="Pone el servicio CscService (Cliente de archivos sin conexión) en "
              "arranque Deshabilitado, como WinUtil. Quita la sincronización de archivos "
              "de red sin conexión; el coste se declara en la descripción.",
         risk="Low", security="Neutral",
         build_note="CscService existe en 19045 y en Windows 11"),
]

# Cada entrada de Atlas: (fichero de toggle, estado), líneas del inventario
# que cubre, riesgo, seguridad, notas y gap R1 (si el pin hace algo más).
ATLAS_SERVICE_SPECS = [
    dict(atlas_toggle=("Services/Bluetooth.psd1", "Disable"),
         id="services.atlas.bluetooth",
         name="Desactivar Bluetooth (toggle de Atlas)",
         inventario_lineas=[130],
         desc="Desactiva Bluetooth: pone AllowBluetooth=0 en la directiva de "
              "conectividad y pasa los servicios de Bluetooth (bthserv, BTHUSB, "
              "BluetoothUserService y los demás) a Deshabilitado, como el estado "
              "'Disable' del toggle Bluetooth de Atlas. Reversible.",
         risk="Low", security="Neutral",
         build_note="ConsentStore y servicios de Bluetooth presentes en 19045 y Windows 11"),
    dict(atlas_toggle=("Services/LanmanWorkstation.psd1", "Disable"),
         id="services.atlas.lanmanworkstation",
         name="Desactivar el servicio de Estación de trabajo (LanmanWorkstation)",
         inventario_lineas=[131],
         desc="Pasa LanmanWorkstation y los servicios de red relacionados "
              "(LanmanServer, mrxsmb, mrxsmb20, rdbss, srv2, KSecPkg) a Deshabilitado, "
              "como el estado 'Disable' del toggle Lanman Workstation de Atlas. "
              "Desactivar LanmanWorkstation puede romper el acceso a recursos de red; "
              "el coste se declara en la descripción.",
         risk="Medium", security="Neutral",
         r1_gap=(
             "el pin declara además MachineAction Set-AtlasLanmanWorkstationState "
             "que ejecuta el script LanmanWorkstation.ps1 con efectos que no son valor "
             "de registro ni tipo de servicio expresables (por ejemplo reglas de firewall "
             "o dependencias de red). Esos efectos no se declaran aquí; por eso State=Specified."),
         build_note="las claves de servicio de LanmanWorkstation existen en 19045 y Windows 11"),
    dict(atlas_toggle=("Services/NetworkDiscovery.psd1", "Disable"),
         id="services.atlas.networkdiscovery",
         name="Desactivar el descubrimiento de red (Network Discovery)",
         inventario_lineas=[132],
         desc="Pasa fdPHost, FDResPub, lmhosts y SSDPSRV a Deshabilitado, como el "
              "estado 'Disable' del toggle Network Discovery de Atlas. El equipo deja de "
              "ser visible en la red y de descubrir otros equipos. Reversible.",
         risk="Low", security="Neutral",
         r1_gap=(
             "el pin declara además MachineAction Set-AtlasNetworkDiscoveryState que "
             "ejecuta NetworkDiscovery.ps1 con efectos de directiva de red y perfil que "
             "no son valores de registro ni tipo de servicio expresables. Esos efectos "
             "no se declaran aquí; por eso State=Specified."),
         build_note="los servicios de descubrimiento de red existen en 19045 y Windows 11"),
]


# ---------------------------------------------------------------- utilidades
def rel_line(path: Path, needle: str) -> int:
    """Línea (1-based) de la primera aparición de `needle` en el fichero."""
    text = path.read_text(encoding="utf-8", errors="replace")
    index = text.find(needle)
    if index < 0:
        return 0
    return text.count("\n", 0, index) + 1


def split_path(path: str) -> tuple[str, str]:
    """'HKCU:\\X' o 'HKCU\\X' -> ('HKCU', 'X'). El pin usa las dos formas."""
    if ":" in path:
        hive, key = path.split(":", 1)
    else:
        hive, key = path.split("\\", 1)
    return hive.strip().upper(), key.lstrip("\\")


def winutil_service_actions(tweak: str) -> list[dict]:
    """Acciones de servicio de un tweak de `config/tweaks.json` (WinUtil)."""
    entry = W_TWEAKS.get(tweak)
    if entry is None:
        raise SystemExit(f"el tweak {tweak} no existe en el pin de WinUtil")
    actions = []
    for order, item in enumerate(entry.get("service") or [], start=1):
        actions.append({
            "type": "service",
            "order": order,
            "description": f"{item['Name']} -> {item['StartupType']}",
            "serviceName": item["Name"],
            "operation": "SetStartupType",
            "startupType": item["StartupType"],
        })
    if not actions:
        raise SystemExit(f"el tweak {tweak} no declara servicios en el pin")
    return actions


def service_stop_action(service_name: str, order: int) -> dict:
    return {
        "type": "service",
        "order": order,
        "description": f"{service_name}: detener",
        "serviceName": service_name,
        "operation": "Stop",
    }


def _balanced_spans(block: str) -> list[str]:
    """Trocea `@{ … }` de primer nivel, respetando comillas y `@( … )`.

    Mismo contrato que `entry_spans` de `build_section10_catalog`: `{` y `(`\
    abren, `}` cierra cuando `depth` llega a 0, y `)` decrementa `depth` (para\
    los `)` de cierre de `Registry = @( … )` y `Services = @( … )` anidados).
    """
    spans: list[str] = []
    index = 0
    while index < len(block):
        start = block.find("@{", index)
        if start < 0:
            return spans
        depth, cursor, in_quote = 0, start, False
        closed = False
        while cursor < len(block):
            char = block[cursor]
            if char == "'":
                in_quote = not in_quote
            elif not in_quote:
                if char in "{(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        spans.append(block[start:cursor + 1])
                        closed = True
                        break
            cursor += 1
        if not closed:
            return spans
        index = cursor + 1
    return spans


def _entry_spans(text: str) -> list[str]:
    """Trocea `@{ … }` de primer nivel de un texto (no anidan dentro de sí)."""
    spans: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("@{", index)
        if start < 0:
            return spans
        depth, cursor, in_quote = 0, start, False
        closed = False
        while cursor < len(text):
            char = text[cursor]
            if char == "'":
                in_quote = not in_quote
            elif not in_quote:
                if char in "{(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        spans.append(text[start:cursor + 1])
                        closed = True
                        break
            cursor += 1
        if not closed:
            return spans
        index = cursor + 1
    return spans


FIELD = {
    "path": re.compile(r"Path\s*='([^']*)'"),
    "name": re.compile(r"Name\s*=\s*'([^']*)'"),
    "type": re.compile(r"Type\s*='([^']*)'"),
    "data": re.compile(r"Data\s*=(@\([^)]*\)|'[^']*'|[^;{}\s,]+)"),
    "op": re.compile(r"Operation\s*='([^']*)'"),
    "startup": re.compile(r"StartupType\s*=\s*(\d+)"),
}


def parse_registry_entries(text: str) -> list[dict]:
    """Entradas del bloque `Registry = @( … )` de un trozo de texto."""
    entries = []
    for body in _entry_spans(text):
        path_match = FIELD["path"].search(body)
        if not path_match:
            continue
        name_match = FIELD["name"].search(body)
        operation = FIELD["op"].search(body)
        op = operation.group(1) if operation else "Set"
        if not name_match and op not in ("DeleteKey", "AddKey"):
            continue
        data_match = FIELD["data"].search(body)
        type_match = FIELD["type"].search(body)
        entries.append({
            "path": path_match.group(1),
            "name": name_match.group(1) if name_match else "",
            "type": type_match.group(1) if type_match else "",
            "op": op,
            "data": data_match.group(1) if data_match else "",
            "has_data": data_match is not None,
        })
    return entries


def atlas_service_entries(state_block: str) -> list[dict]:
    """Entradas del bloque `Services = @( … )` de un estado: Nombre + StartupType."""
    entries = []
    for body in _entry_spans(state_block):
        name_match = FIELD["name"].search(body)
        startup = FIELD["startup"].search(body)
        if not name_match:
            continue
        entries.append({
            "name": name_match.group(1),
            "startupType": int(startup.group(1)) if startup else None,
        })
    return entries


def startup_type_name(code: int | None) -> str:
    return {4: "Disabled", 3: "Manual", 2: "Automatic", 1: "System", 0: "Boot"}.get(
        code, f"{code}")


def atlas_state_block(text: str, state: str) -> str:
    """Devuelve el INTERIOR del estado `state` (sin su `@{ … }`) de un .psd1 de toggles."""
    text = re.sub(r"#[^\n]*", "", text)
    marker = text.find("States")
    if marker < 0:
        raise SystemExit("el .psd1 no tiene bloque States")
    paren = text.find("@(", marker)
    if paren < 0:
        raise SystemExit("el .psd1 no tiene `@(` tras States")
    depth, cursor, in_quote = 0, paren + 1, False
    while cursor < len(text):
        char = text[cursor]
        if char == "'":
            in_quote = not in_quote
        elif not in_quote:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
        cursor += 1
    block = text[paren + 2:cursor]

    for body in _balanced_spans(block):
        if "StateValue" not in body:
            continue
        name = re.search(r"Name\s*=\s*'([^']+)'", body)
        if name and name.group(1) == state:
            return body[2:-1]
    raise SystemExit(f"estado '{state}' no encontrado en el .psd1")


def atlas_actions_for_state(relative: str, state: str) -> tuple[list[dict], str]:
    """Acciones (registro + servicio) del estado `state` de un toggle de Atlas.

    Devuelve (acciones, ruta_relativa_del_pin). Las acciones de servicio se
    emiten como Stop (primero) + SetStartupType (después), igual que hace el
    pin, para que el deshacer LIFO del motor restaure el arranque antes de
    intentar arrancar el servicio.
    """
    path = ATLAS_TOGGLES / relative
    state_block = atlas_state_block(path.read_text(encoding="utf-8", errors="replace"), state)
    actions: list[dict] = []
    order = 1
    # --- Registro del estado ---
    for entry in parse_registry_entries(state_block):
        hive, key = split_path(entry["path"])
        if entry["op"] == "DeleteKey":
            actions.append({
                "type": "registryDeleteKey",
                "order": order,
                "hive": HIVES[hive],
                "keyPath": key,
                "recursive": False,
                "description": f"Borrar la clave {hive}\\{key}",
            })
            order += 1
            continue
        if entry["op"] == "AddKey":
            actions.append({
                "type": "registryCreateKey",
                "order": order,
                "hive": HIVES[hive],
                "keyPath": key,
                "description": f"Crear la clave {hive}\\{key}",
            })
            order += 1
            continue
        if not entry["has_data"]:
            raise SystemExit(
                f"{relative}: {entry['name'] or '(predeterminado)'} en "
                f"{entry['path']} sin Data ni Operation: no se inventa un literal")
        raw = entry["data"].strip()
        if raw.startswith("@(") and raw.endswith(")"):
            import base64
            numbers = [int(x, 16) if x.lower().startswith("0x") else int(x)
                       for x in re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", raw)]
            value = base64.b64encode(bytes(numbers)).decode("ascii")
        elif raw.startswith("'") and raw.endswith("'"):
            value = raw[1:-1]
        else:
            value = raw
        op = entry["op"]
        if op.lower() == "delete":
            op = "Delete"
        actions.append({
            "type": "registry",
            "order": order,
            "hive": HIVES[hive],
            "keyPath": key,
            "valueName": entry["name"],
            "value": value,
            "valueType": entry["type"] or "String",
            "operation": op,
            "description": f"{entry['name'] or '(predeterminado)'} en {hive}",
        })
        order += 1
    # --- Servicios del estado: Stop primero, SetStartupType después (LIFO). ---
    service_entries = atlas_service_entries(state_block)
    for se in service_entries:
        actions.append(service_stop_action(se["name"], order))
        order += 1
    for se in service_entries:
        stype = startup_type_name(se["startupType"]) if se["startupType"] is not None else "Disabled"
        actions.append({
            "type": "service",
            "order": order,
            "description": f"{se['name']} -> {stype}",
            "serviceName": se["name"],
            "operation": "SetStartupType",
            "startupType": stype,
        })
        order += 1
    return actions, str(path.relative_to(UPSTREAM / "atlas"))


def apply_r1(capability: dict, spec: dict) -> dict:
    gap = spec.get("r1_gap")
    if not gap:
        return capability
    capability["state"] = "Specified"
    capability["description"] = (
        capability["description"].rstrip()
        + " FUERA DE ESTA CAPACIDAD (R1): " + gap
    )
    capability["provenance"] = (
        capability["provenance"].rstrip()
        + " R1 (paso 12): el pin hace ADEMAS esto, que NO se declara como accion: "
        + gap
        + " Como el efecto del pin no queda expresado entero, State=Specified."
    )
    return capability


def base(cap_id: str, name: str, desc: str, section_id: int, risk: str,
         security: str, actions: list[dict], builds: list[int] | None,
         state: str, variants: list[str], provenance: str,
         r2_reason: str | None = None, r3_reason: str | None = None) -> dict:
    if security == "Improves":
        if not r2_reason:
            raise SystemExit(
                f"{cap_id}: SecurityImpact=Improves exige r2_reason (regla R2)")
        desc = desc.rstrip() + " Por que mejora la seguridad: " + r2_reason
        provenance = provenance.rstrip() + " R2 (paso 12): SecurityImpact=Improves por: " + r2_reason
    return {
        "id": cap_id,
        "name": name,
        "description": desc,
        "sectionId": section_id,
        "risk": risk,
        "securityImpact": security,
        "privilege": "Admin" if any(
            a["type"] == "service"
            or a.get("hive") in ("LocalMachine", "Users")
            for a in actions) else "User",
        "restore": RESTORE[risk],
        "reversibility": "Reversible",
        "confirmation": CONFIRM[risk],
        "state": state,
        "variants": variants,
        "conflictsWith": [],
        "dependsOn": [],
        "supportedBuilds": builds or DEFAULT_BUILDS,
        "provenance": provenance,
        "actions": actions,
    }


def build() -> dict:
    capabilities: list[dict] = []

    # --------------------------------------------------------------- WinUtil
    for spec in WINUTIL_SPECS:
        actions = winutil_service_actions("WPFTweaksServices")
        # Filtrar solo el servicio de esta especificación.
        actions = [a for a in actions if a["serviceName"] == spec["service"]]
        if not actions:
            raise SystemExit(f"WPFTweaksServices no declara {spec['service']} en el pin")
        # ORDEN (ADR-0005 4-bis): primero Stop, luego SetStartupType.
        ordered: list[dict] = []
        for index, action in enumerate(actions):
            ordered.append(service_stop_action(action["serviceName"], 2 * index + 1))
            ordered.append(dict(action, order=2 * index + 2))
        actions = ordered
        entry = W_TWEAKS["WPFTweaksServices"]
        original_type = next(i["OriginalType"] for i in entry["service"]
                             if i["Name"] == spec["service"])
        service_to_op = {"CscService": "0", "DiagTrack": "1", "MapsBroker": "2",
                         "StorSvc": "3", "SharedAccess": "4"}
        provenance = (
            f"{WINUTIL_PIN}:config/tweaks.json:WPFTweaksServices (service: {spec['service']} "
            f"StartupType={actions[1]['startupType']}, OriginalType={original_type}). "
            "Servicio y tipo de inicio tomados de la fuente: "
            + "; ".join(
                (f"{a['serviceName']}={a['startupType']}"
                 if a["operation"] == "SetStartupType" else f"{a['serviceName']}=Stop")
                for a in actions)
            + ". Semantica: `StartupType` es lo que WinUtil aplica y `OriginalType` lo "
              "que restaura su deshacer; el motor guarda el tipo previo. "
              "Reversibilidad (ADR-0003): Reversible - el motor registra el tipo de "
              "inicio anterior de cada servicio y lo devuelve al deshacer. "
            + f" Builds: {spec['build_note']}. "
            + f"ledger_refs: winutil:tweak:WPFTweaksServices, "
            f"winutil:tweak-op:WPFTweaksServices:service:{service_to_op[spec['service']]}"
            + f" Inventario sección 4: línea {spec['inventario_linea']} ({spec['service']})."
        )
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"], 4,
            spec["risk"], spec["security"], actions, None,
            "Implemented", ["Evo", "WinUtil"], provenance,
            r2_reason=spec.get("r2_reason")))

    # ------------------------------------------------------- Atlas (servicios)
    for spec in ATLAS_SERVICE_SPECS:
        relative, state = spec["atlas_toggle"]
        actions, source = atlas_actions_for_state(relative, state)
        for action in actions:
            action.pop("line", None) if "line" in action else None
        lineas_pin = [rel_line(ATLAS_TOGGLES / relative, "Registry")]
        lineas_pin = [l for l in lineas_pin if l] or \
            [rel_line(ATLAS_TOGGLES / relative, "Services")]
        refs = f"{source}:{lineas_pin[0]}"
        blocked = ""
        state_label = f" (estado '{state}')"
        def action_text(a: dict) -> str:
            if a["type"] == "registry":
                return f"{a['valueName'] or '(predeterminado)'}={a['value']}"
            if a["type"] == "registryDeleteKey":
                return f"BORRAR CLAVE {a['hive']}\\{a['keyPath']}"
            if a["type"] == "registryCreateKey":
                return f"CREAR CLAVE {a['hive']}\\{a['keyPath']}"
            st = a.get("startupType", "Stop")
            return f"{a['serviceName']}={st}"
        provenance = (
            f"{ATLAS_PIN}:{refs}{state_label}. Valores y servicios tomados del bloque "
            "Registry y Services del pin: "
            + "; ".join(action_text(a) for a in actions)
            + "." + blocked
            + f" Builds: {spec['build_note']}. "
            + f"ledger_refs: atlas:toggle:{Path(relative).stem}"
            + f" Inventario sección 4: líneas "
            + ", ".join(str(l) for l in spec["inventario_lineas"])
            + f" ({', '.join(str(l) for l in spec['inventario_lineas'])})."
        )
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"], 4,
            spec["risk"], spec["security"], actions, None,
            spec.get("state", "Specified"), ["Evo", "Atlas"], provenance,
            r2_reason=spec.get("r2_reason")))
        apply_r1(capabilities[-1], spec)

    capabilities.sort(key=lambda c: c["id"])
    return {
        "metadata": {
            "version": "1.0.0",
            "schemaVersion": 1,
            "provenance": (
                f"ETAPA 7, seccion 4 (oleada 1). Fuentes: {WINUTIL_PIN}, {ATLAS_PIN}. "
                "Los literales de valor se leen del pin con "
                "tools/ledger_extract/build_section4_catalog.py; ninguno se escribe a mano."
            ),
            "generatedBy": "etapa 7 (oleada 1)",
        },
        "capabilities": capabilities,
    }


def dump(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=3, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="no escribe: compara con el fichero y sale 1 si difiere")
    args = parser.parse_args(argv)

    if not WINUTIL_TWEAKS.is_file() or not ATLAS_TOGGLES.is_dir():
        print("falta el pin en /tmp/upstream (ejecuta tools/ledger_extract/fetch_upstream.py)",
              file=sys.stderr)
        return 1

    document = build()
    text = dump(document)
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != text:
            print("section4_services.json NO coincide con el pin", file=sys.stderr)
            return 1
        print(f"section4_services.json reproducible: OK "
              f"({len(document['capabilities'])} capacidades)")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    total = sum(len(c["actions"]) for c in document["capabilities"])
    print(f"capacidades: {len(document['capabilities'])} | acciones: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
