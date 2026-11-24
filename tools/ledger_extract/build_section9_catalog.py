#!/usr/bin/env python3
"""Genera `catalog/capabilities/section9_system_registry.json` (paso 10, oleada 3).

Los VALORES de cada acción no se escriben a mano: se leen del pin fijado
(WinUtil `70c23c8…` en `config/tweaks.json` y `config/feature.json`; Atlas
`ec3c4058…` en `package/Executables/AtlasModules/Toggles/` y `Scripts/Tweaks/`)
y la provenance cita fichero y línea. Si el pin no está en `/tmp/upstream`, el
script falla con un mensaje claro: no se inventa ningún literal.

Alcance de la sección 9 (REGISTRO DE WINDOWS Y CONFIGURACIÓN DEL SISTEMA):

- Las líneas del inventario conciliado que ninguna capacidad cubría todavía y
  que el pin SÍ implementa (hibernación, ubicación, servicios, modo de juego,
  aceleración del ratón, S0/S3, mitigaciones, atajos de teclado, visibilidad de
  páginas de Configuración).
- Los ítems de upstream que `item-section-map.tsv` asigna a la sección 9 y que
  son de registro (control de fallos, WPBT, retardo de menús, servidores NTP,
  información OEM, copia de seguridad del registro, UTC, indexación).
- Cuando el pin hace además algo que NO es de registro (servicios, scripts,
  tareas programadas), no se calla: se dice en la descripción, se anota en la
  provenance y, si el efecto completo no cabe en el motor, la capacidad queda en
  `State=Specified`.

Salida determinista: orden por id, LF, UTF-8 sin BOM, 3 espacios de sangría.

Uso:
    python3 tools/ledger_extract/build_section9_catalog.py
    python3 tools/ledger_extract/build_section9_catalog.py --check
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Se reutiliza el parseo ya probado de la oleada 2 (mismo pin, mismas reglas):
# troceo de `@{ … }`, estados de los .psd1 de Toggles, normalización de literales
# y de rutas.
import build_section10_catalog as b10  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "catalog" / "capabilities" / "section9_system_registry.json"
UPSTREAM = b10.UPSTREAM
WINUTIL_TWEAKS = b10.WINUTIL_TWEAKS
WINUTIL_FEATURES = UPSTREAM / "winutil" / "config" / "feature.json"
ATLAS_TOGGLES = b10.ATLAS_TOGGLES
ATLAS_TWEAKS = b10.ATLAS_TWEAKS

WINUTIL_PIN = b10.WINUTIL_PIN
ATLAS_PIN = b10.ATLAS_PIN
DEFAULT_BUILDS = b10.DEFAULT_BUILDS
W_TWEAKS: dict = b10.W_TWEAKS
W_FEATURES: dict = (
    json.loads(WINUTIL_FEATURES.read_text(encoding="utf-8"), strict=False)
    if WINUTIL_FEATURES.is_file() else {}
)

CONFIRM = {"Safe": "None", "Low": "SimpleClick", "Medium": "Summary",
           "High": "SummaryAndRestorePoint", "Critical": "TypeOperationName"}
# ADR-0003: con Reversibility=Reversible el mínimo de restauración depende del
# riesgo (Low -> SessionUndo, Medium/High -> RestorePoint). Las capacidades de
# esta sección que tocan estado de máquina (HKLM) y piden Medium/High van con
# RestorePoint: el motor crea el punto antes de escribir y además guarda el valor
# previo. Las de HKCU van con SessionUndo.
RESTORE = {"Safe": "SessionUndo", "Low": "SessionUndo",
           "Medium": "RestorePoint", "High": "RestorePoint",
           "Critical": "FullBackup"}

HIVES = {"HKLM": "LocalMachine", "HKCU": "CurrentUser",
         "HKCR": "ClassesRoot", "HKU": "Users"}

# --------------------------------------------------------------- especificación
# Cada entrada:
#   id, name, desc, risk, security, build_note
#   winutil     tweak de `config/tweaks.json` (se toma `Value`, que es el valor
#               que WinUtil escribe)
#   services    True si el tweak declara `service` (se emiten ServiceActions)
#   feature     entrada de `config/feature.json` cuyos literales están en el
#               `InvokeScript` (se leen con `script_props`)
#   atlas_toggle (ruta dentro de Toggles, estado) del pin
#   atlas_tweak ruta dentro de Scripts/Tweaks (con .psd1)
#   static_key/static_value_variable  script del pin con clave y valor literales
#   omit        lo que el pin hace y NO se declara (se escribe, no se calla)
#   state       "Implemented" por defecto
WINUTIL_SPECS = [
    dict(id="system.game-mode.enable", winutil="WPFToggleGameMode",
         name="Activar el modo de juego de Windows",
         desc="Pone AllowAutoGameMode=1 y AutoGameModeEnabled=1 en HKCU\\Software\\"
              "Microsoft\\GameBar. El modo de juego evita que Windows reparta recursos "
              "de CPU y GPU entre segundo plano y juego mientras uno está en primer "
              "plano. Es una preferencia por usuario y ya suele estar activa.",
         risk="Safe", security="Neutral",
         build_note="claves de HKCU presentes en 19045 y en las tres builds de Windows 11"),
    dict(id="system.mouse-acceleration.enable", winutil="WPFToggleMouseAcceleration",
         name="Activar la aceleración del puntero del ratón",
         desc="Pone MouseSpeed='1' y MouseThreshold1='6' / MouseThreshold2='10' en "
              "HKCU\\Control Panel\\Mouse. La casilla encendida del pin ACTIVA la "
              "aceleración (es el valor por defecto de Windows); el catálogo declara el "
              "efecto tal y como está medido en la fuente, sin invertir su significado. "
              "Sólo escribe valores de la sesión del usuario.",
         risk="Safe", security="Neutral",
         build_note="claves de HKCU/Control Panel estables desde Windows 10 1507"),
    dict(id="system.sleep.s0-network-keep", winutil="WPFToggleStandbyFix",
         name="Mantener la red durante el reposo moderno (S0)",
         desc="Pone ACSettingIndex=1 en la directiva de energía del adaptador de red "
              "(HKCU\\SOFTWARE\\Policies\\Microsoft\\Power\\PowerSettings\\f15576e8-…). "
              "Evita que la conexión se caiga al entrar en reposo moderno (S0). No "
              "cambia el modelo de reposo del equipo.",
         risk="Safe", security="Neutral",
         build_note="la directiva por GUID existe en 19045 y en las tres de Windows 11"),
    dict(id="system.sleep.s3-enable", winutil="WPFToggleS3Sleep",
         name="Usar el reposo S3 clásico",
         desc="Pone PlatformAoAcOverride=0 en HKLM\\SYSTEM\\CurrentControlSet\\Control\\"
              "Power. Fuerza el modelo de reposo clásico (S3) en equipos que soportan "
              "reposo moderno (S0). Cambia cómo duerme el equipo y puede afectar a la "
              "reanudación en portátiles modernos, por eso el riesgo no es Safe.",
         risk="Medium", security="Neutral",
         build_note="el valor existe en 19045 y en las tres de Windows 11 a partir de 2004"),
    dict(id="system.time.utc-rtc", winutil="WPFTweaksUTC",
         name="Guardar el reloj del hardware en UTC",
         desc="Pone RealTimeIsUniversal=1 (QWord) en HKLM\\SYSTEM\\CurrentControlSet\\"
              "Control\\TimeZoneInformation. Windows pasa a interpretar el reloj de la "
              "placa como UTC, que es lo que esperan Linux y otros sistemas en un equipo "
              "con arranque dual. En un equipo de un solo sistema no hace falta.",
         risk="Low", security="Neutral",
         build_note="valor documentado y presente en 19045 y en Windows 11"),
    dict(id="system.registry-backup.enable", winutil="WPFFeatureRegBackup",
         feature=True, state="Specified",
         name="Reactivar la copia de seguridad diaria del registro",
         desc="Pone EnablePeriodicBackup=1 y BackupCount=2 en HKLM\\SYSTEM\\"
              "CurrentControlSet\\Control\\Session Manager\\Configuration Manager, que es "
              "lo que Microsoft desactivó por defecto en Windows 10 1803. El pin además "
              "registra la tarea programada AutoRegBackup (schtasks /run /i /tn "
              "\\Microsoft\\Windows\\Registry\\RegIdleBackup, diaria a las 00:30): una "
              "tarea que no EXISTE todavía no se puede habilitar con el motor, sólo "
              "crearla, así que la capacidad queda en Specified y los valores del "
              "registro son los que se declaran.",
         risk="Safe", security="Improves",
         build_note="los valores son los mismos desde 1803; la tarea existe en todas"),
    dict(id="system.services.manual-profile", winutil="WPFTweaksServices", services=True,
         name="Pasar a manual o desactivar los servicios del perfil de WinUtil",
         desc="Ajusta el tipo de inicio de cinco servicios: CscService (Desactivado), "
              "DiagTrack (Desactivado), MapsBroker (Manual), StorSvc (Manual) y "
              "SharedAccess (Manual). Desactivar DiagTrack reduce la telemetría; "
              "desactivar CscService quita el cliente de archivos sin conexión y "
              "SharedAccess en Manual puede impedir compartir la conexión a Internet. Se "
              "puede deshacer porque el motor guarda el tipo de inicio previo.",
         risk="Low", security="Improves",
         build_note="los cinco servicios existen en 19045 y en Windows 11"),
    dict(id="system.search-indexing.disable", winutil="WPFTweaksDisableSearchIndexing",
         services=True,
         name="Desactivar la indización de búsqueda de Windows",
         desc="Pone el servicio WSearch en Desactivado y lo detiene si estaba corriendo. "
              "La búsqueda del Explorador y del menú Inicio deja de usar el índice y "
              "pasa a recorrer las carpetas: menos actividad de disco en reposo y "
              "resultados más lentos en bibliotecas grandes.",
         risk="Low", security="Neutral",
         build_note="WSearch existe en 19045 y en Windows 11"),
]

ATLAS_TOGGLE_SPECS = [
    dict(id="system.hibernation.hide", atlas_toggle=("General/Hibernation.psd1", "Disable"),
         name="Ocultar la opción Hibernar del menú de energía",
         desc="Pone ShowHibernateOption=0 en HKLM\\SOFTWARE\\Microsoft\\Windows\\"
              "CurrentVersion\\Explorer\\FlyoutMenuSettings: la entrada «Hibernar» deja "
              "de aparecer en el menú de energía. El pin ejecuta además "
              "Disable-AtlasHibernation, que apaga la hibernación de verdad con powercfg; "
              "esa acción de máquina no es de registro y aquí no se declara.",
         risk="Low", security="Neutral",
         builds=[22631, 26100, 26200],
         build_note="la clave FlyoutMenuSettings (menú de energía de Windows 11) existe "
                    "desde 22631; en 19045 Windows no la lee y la entrada del menú no "
                    "cambia, por eso NO se declara 19045"),
    dict(id="system.location.consent-deny", atlas_toggle=("General/Location.psd1", "Disable"),
         name="Denegar el acceso a la ubicación",
         desc="Pone Value='Deny' en el ConsentStore de ubicación (HKLM) y "
              "ShowGlobalPrompts=0 en el mismo ConsentStore del usuario. Quita el "
              "permiso global de ubicación: las aplicaciones dejan de poder pedirla. "
              "El pin ejecuta además Disable-AtlasLocation, que apaga lfsvc y MapsBroker; "
              "esos servicios no se declaran aquí.",
         risk="Low", security="Improves",
         build_note="ConsentStore de ubicación presente en 19045 y en Windows 11"),
    dict(id="system.mitigations.disable", atlas_toggle=("Security/Mitigations.psd1", "Disable"),
         name="Desactivar las mitigaciones del kernel",
         desc="Escribe FeatureSettingsOverride=3, FeatureSettingsOverrideMask=3, "
              "DisableExceptionChainValidation=1 y ProtectionMode=0 bajo HKLM\\SYSTEM: "
              "desactiva mitigaciones del kernel (SEHOP, validación del árbol de "
              "excepciones) para ganar rendimiento. REDUCE de forma real la protección "
              "frente a exploits y exige reinicio; por eso el riesgo es High y la "
              "confirmación pide resumen y punto de restauración.",
         risk="High", security="Reduces",
         build_note="los cuatro valores existen en 19045 y en Windows 11"),
    dict(id="system.keyboard-shortcuts.disable", atlas_toggle=("Interface/KeyboardShortcuts.psd1",
                                                              "Disable"),
         name="Desactivar los atajos de cambio de idioma del teclado",
         desc="Pone Hotkey='3', 'Language Hotkey'='3' y 'Layout Hotkey'='3' en "
              "HKCU\\Keyboard Layout\\Toggle. Desactiva Alt+Shift y Ctrl+Shift para "
              "cambiar de idioma o de distribución; Win+Space y el resto de métodos de "
              "entrada siguen funcionando. Atlas requiere cerrar sesión para que el "
              "cambio se note; el motor no puede forzarlo.",
         risk="Safe", security="Neutral",
         build_note="la clave Keyboard Layout\\Toggle existe en 19045 y en Windows 11",
         extra_ledgers=["atlas:manifest:qol/set-keyboard-switching"]),
]

ATLAS_TWEAK_SPECS = [
    dict(id="system.error-reporting.crash-control", atlas_tweak="qol/system/crash-control-qol.psd1",
         name="Configurar el control de fallos (pantalla azul y volcados)",
         desc="Deja la pantalla azul en pantalla sin reiniciar (AutoReboot=0), fija un "
              "volcado pequeño de 256 KiB (CrashDumpEnabled=3), conserva el registro del "
              "evento (LogEvent=1), muestra los parámetros del fallo (DisplayParameters=1) "
              "y apaga el volcado de StorageTelemetry. REDUCE el diagnóstico: sigue "
              "quedando un minidump analizable, pero ya no hay volcado completo de memoria "
              "y el equipo se queda detenido en la pantalla azul hasta que alguien lo "
              "reinicie.",
         risk="Medium", security="Reduces",
         build_note="CrashControl existe en 19045 y en Windows 11; el volcado pequeño "
                    "es el modo 3 desde Windows 8"),
    dict(id="system.error-reporting.wpbt-disable", atlas_tweak="qol/system/disable-wpbt.psd1",
         name="Impedir la ejecución del programa WPBT del firmware",
         desc="Pone DisableWpbtExecution=1 en HKLM\\SYSTEM\\CurrentControlSet\\Control\\"
              "Session Manager. WPBT permite que el firmware ejecute un binario en cada "
              "arranque; el propio pin avisa de que Microsoft no documenta este valor. "
              "Evita software OEM que se reinstala solo, a costa de una función del "
              "firmware: se declara Medium porque cambia el arranque, no Safe.",
         risk="Medium", security="Improves",
         build_note="el valor se lee en el arranque de 19045 y de Windows 11"),
    dict(id="system.menu-delay.disable", atlas_tweak="qol/shell/disable-menu-delay.psd1",
         name="Quitar el retardo de los submenús",
         desc="Pone MenuShowDelay='0' en HKCU\\Control Panel\\Desktop: los submenús se "
              "abren en cuanto el puntero se posa sobre ellos, sin la espera por defecto. "
              "Sólo afecta a la respuesta visual del menú de la sesión.",
         risk="Safe", security="Neutral",
         build_note="MenuShowDelay existe en 19045 y en Windows 11"),
    dict(id="system.time.ntp-servers", atlas_tweak="misc/config-time.psd1",
         name="Usar los servidores de hora de pool.ntp.org",
         desc="Escribe NtpServer='0.pool.ntp.org 1.pool.ntp.org 2.pool.ntp.org "
              "3.pool.ntp.org' y Type='NTP' en HKLM\\SYSTEM\\CurrentControlSet\\Services\\"
              "W32Time\\Parameters. El pin además arranca el servicio w32time y ejecuta "
              "w32tm /config /update y w32tm /resync con IgnoreErrors: esas tres cosas no "
              "son de registro y aquí no se declaran, así que la capacidad queda en "
              "Specified (los valores quedan escritos, la resincronización la hace "
              "Windows en su siguiente ciclo).",
         risk="Low", security="Neutral", state="Specified",
         omit="Services: Start de w32time; Run: w32tm /config /update y w32tm /resync",
         build_note="W32Time\\Parameters existe en 19045 y en Windows 11"),
    dict(id="system.oem-information.identify", atlas_tweak="misc/config-oem-information.psd1",
         name="Escribir la información OEM del sistema",
         desc="Escribe Manufacturer, SupportURL y SupportPhone en HKLM\\SOFTWARE\\"
              "Microsoft\\Windows\\CurrentVersion\\OEMInformation, los tres valores que "
              "Windows muestra en Información del sistema. Los literales son los del pin "
              "(atribución de Atlas), no una identidad inventada para EVO.",
         risk="Safe", security="Neutral",
         build_note="OEMInformation existe en 19045 y en Windows 11"),
]

# Capacidad que no sale de un bloque `Registry` sino de un script con clave y
# valor literales: se leen del pin las dos líneas y se comprueba la forma.
STATIC_SCRIPT_SPECS = [
    dict(id="system.settings-page-visibility.hide",
         script="qol/set-hidden-settings-pages.ps1",
         name="Ocultar las páginas de Configuración que Atlas considera rotas",
         desc="Escribe SettingsPageVisibility='hide:recovery;maps;maps-downloadmaps;"
              "privacy;privacy-feedback;privacy-activityhistory;search-permissions;"
              "privacy-general;sync;mobile-devices;mobile-devices-addphone;workplace;"
              "family-group;deviceusage;home' en HKLM\\SOFTWARE\\Microsoft\\Windows\\"
              "CurrentVersion\\Policies\\Explorer. Muchas de esas páginas son las que "
              "usan los ajustes de privacidad: ocultarlas también las hace más difíciles "
              "de encontrar. El valor del pin es una lista COMPLETA: sobrescribe la que "
              "el usuario tuviera, no la amplía (a diferencia de la ayuda incremental de "
              "Atlas, que edita una página por vez). Se puede deshacer porque el motor "
              "guarda el valor previo.",
         risk="Low", security="Neutral",
         build_note="la directiva SettingsPageVisibility existe en 19045 y en Windows 11"),
]


def winutil_registry_actions(tweak: str) -> list[dict]:
    entry = W_TWEAKS.get(tweak)
    if entry is None:
        raise SystemExit(f"el tweak {tweak} no existe en el pin de WinUtil")
    actions = []
    for order, item in enumerate(entry.get("registry") or [], start=1):
        hive, key = b10.split_path(item["Path"])
        actions.append({
            "type": "registry",
            "order": order,
            "description": f"{item['Name']} en {hive}",
            "hive": HIVES[hive],
            "keyPath": key,
            "valueName": item["Name"],
            "value": str(item["Value"]),
            "valueType": item.get("Type", "DWord"),
            "operation": "Set",
        })
    return actions


def winutil_service_actions(tweak: str) -> list[dict]:
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


def script_props(script: str) -> list[dict]:
    """Valores de `New-ItemProperty … -Name 'X' -Type T -Value V` del pin.

    Sólo se aceptan literales (comillas simples y número entero o 'DWord'): si
    aparece una variable en el valor, el script falla en vez de inventar.
    """
    pattern = re.compile(
        r"New-ItemProperty\s+-Path\s+'(HK[A-Z]+):\\\\?([^']+)'\s+"
        r"-Name\s+'([^']+)'\s+-Type\s+(\w+)\s+-Value\s+('[^']*'|\d+)")
    found = []
    for match in pattern.finditer(script):
        hive, key, name, kind, raw = match.groups()
        value = raw[1:-1] if raw.startswith("'") else raw
        found.append({"hive": HIVES[hive], "keyPath": key, "valueName": name,
                      "valueType": kind, "value": value})
    if not found:
        raise SystemExit("el script del pin no declara New-ItemProperty literales")
    return found


def static_script_pair(script: str) -> tuple[str, str, str]:
    """($key de HKLM, $value, ruta relativa) de un script con ambos literales."""
    path = ATLAS_TWEAKS / script
    text = path.read_text(encoding="utf-8", errors="replace")
    key = re.search(r"^\$key\s*=\s*'(HKLM:\\[^']+)'", text, re.M)
    value = re.search(r"^\$value\s*=\s*'([^']+)'", text, re.M)
    if not key or not value:
        raise SystemExit(f"{script}: no se encontraron $key y $value literales en el pin")
    return key.group(1), value.group(1), str(path.relative_to(UPSTREAM / "atlas"))


def line_of(script: str, needle: str) -> int:
    path = ATLAS_TWEAKS / script
    return b10.rel_line(path, needle)


def base(cap_id: str, name: str, desc: str, risk: str, security: str,
         actions: list[dict], builds: list[int] | None, state: str,
         variants: list[str], provenance: str) -> dict:
    return {
        "id": cap_id,
        "name": name,
        "description": desc,
        "sectionId": 9,
        "risk": risk,
        "securityImpact": security,
        # Un servicio se cambia con elevación aunque no haya registro de por medio.
        "privilege": "Admin" if any(a["type"] == "service"
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

    # ------------------------------------------------------------------ WinUtil
    for spec in WINUTIL_SPECS:
        if spec.get("feature"):
            entry = W_FEATURES.get(spec["winutil"])
            if entry is None:
                raise SystemExit(f"la entrada {spec['winutil']} no existe en feature.json")
            script = entry.get("InvokeScript") or []
            script = script[0] if isinstance(script, list) and script else str(script)
            values = script_props(script)
            actions = [
                {"type": "registry", "order": i, "description": f"{v['valueName']} en HKLM",
                 "hive": v["hive"], "keyPath": v["keyPath"], "valueName": v["valueName"],
                 "value": v["value"], "valueType": v["valueType"], "operation": "Set"}
                for i, v in enumerate(values, start=1)
            ]
            ledger = f"winutil:feature:{spec['winutil']}"
            provenance = (
                f"{WINUTIL_PIN}:config/feature.json#{spec['winutil']} (Type="
                f"{entry.get('Type') or 'sin Type'}). Literales leidos de InvokeScript: "
                + "; ".join(f"{a['valueName']}={a['value']}" for a in actions)
                + ". El pin ademas registra la tarea AutoRegBackup (Register-ScheduledTask, "
                  "diaria a las 00:30): crear una tarea no es una operacion de "
                  "ServiceAction/TaskAction y no se declara; por eso State=Specified. "
                  "Reversibilidad (ADR-0003): Reversible - valores de registro con valor "
                  "previo guardado por el motor. "
                + f"Builds: {spec['build_note']}. ledger_refs: {ledger}"
            )
        elif spec.get("services"):
            actions = winutil_service_actions(spec["winutil"])
            provenance = (
                f"{WINUTIL_PIN}:config/tweaks.json#{spec['winutil']}. Servicios y tipos de "
                "inicio tomados de la fuente: "
                + "; ".join(f"{a['serviceName']}={a['startupType']}" for a in actions)
                + ". Semantica: `StartupType` es lo que WinUtil aplica y `OriginalType` lo "
                  "que restaura su propio deshacer; el motor guarda el tipo previo. "
                  "Reversibilidad (ADR-0003): Reversible - el motor registra el tipo de "
                  "inicio anterior de cada servicio y lo devuelve al deshacer. "
                + f"Builds: {spec['build_note']}. "
                + f"ledger_refs: winutil:tweak:{spec['winutil']}, "
                  "winutil:tweak-op:WPFTweaksServices:service:0"
            )
        else:
            actions = winutil_registry_actions(spec["winutil"])
            entry = W_TWEAKS[spec["winutil"]]
            values = "; ".join(f"{a['valueName']}={a['value']}" for a in actions)
            provenance = (
                f"{WINUTIL_PIN}:config/tweaks.json#{spec['winutil']} (Type="
                f"{entry.get('Type') or 'sin Type'}). Valores tomados de la fuente: "
                f"{values}. Semantica: en un Toggle de WinUtil `Value` es el valor que se "
                "escribe y `OriginalValue` el que restaura su deshacer "
                "(functions/private/Invoke-WinUtilTweaks.ps1:34-46). "
                "Reversibilidad (ADR-0003): Reversible - valores de registro con valor "
                "previo guardado por el motor. "
                + ("Privilegio Admin por escribir en HKLM. "
                   if any(a["hive"] == "LocalMachine" for a in actions) else "")
                + f"Builds: {spec['build_note']}. "
                + f"ledger_refs: winutil:tweak:{spec['winutil']}"
            )
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"], spec["risk"], spec["security"],
            actions, spec.get("builds"), spec.get("state", "Implemented"),
            ["Evo", "WinUtil"], provenance))

    # ------------------------------------------------------- Atlas (Toggles)
    for spec in ATLAS_TOGGLE_SPECS:
        relative, state = spec["atlas_toggle"]
        actions, skipped, source = b10.atlas_actions(relative, state)
        # La línea del pin va en la provenance, no en la acción: el contrato de
        # `RegistryAction` es cerrado y no tiene ese campo (lo rechazaría el
        # cargador estricto si se colara como propiedad desconocida).
        lines = sorted({a["line"] for a in actions if a.get("line")}) or [0]
        for action in actions:
            action.pop("line", None)
        refs = f"{source}:{lines[0]}" + (f"-{lines[-1]}" if len(lines) > 1 else "")
        blocked = ""
        if skipped:
            blocked = (" No expresable como RegistryAction y por tanto NO aplicado: "
                       + ", ".join(skipped) + " (el motor solo borra valores, no claves).")
        ledgers = [f"atlas:toggle:{Path(relative).stem}"] + spec.get("extra_ledgers", [])
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"], spec["risk"], spec["security"],
            actions, spec.get("builds"), spec.get("state", "Implemented"),
            ["Evo", "Atlas"],
            f"{ATLAS_PIN}:{refs} (estado '{state}'). Valores tomados del bloque Registry "
            "del pin: "
            + "; ".join(
                (f"{a['valueName'] or '(predeterminado)'}={a['value']}"
                 if a["operation"] == "Set" else f"{a['valueName']} (borrado)")
                for a in actions)
            + "." + blocked
            + " Reversibilidad (ADR-0003): Reversible - valores de registro con valor "
              "previo guardado por el motor. "
            + f"Builds: {spec['build_note']}. "
            + "ledger_refs: " + ", ".join(ledgers)))

    # ------------------------------------------------- Atlas (Scripts/Tweaks)
    for spec in ATLAS_TWEAK_SPECS:
        relative = f"Tweaks/{spec['atlas_tweak']}"
        actions, skipped, source = b10.atlas_actions(relative, None)
        # La línea del pin va en la provenance, no en la acción: el contrato de
        # `RegistryAction` es cerrado y no tiene ese campo (lo rechazaría el
        # cargador estricto si se colara como propiedad desconocida).
        lines = sorted({a["line"] for a in actions if a.get("line")}) or [0]
        for action in actions:
            action.pop("line", None)
        refs = f"{source}:{lines[0]}" + (f"-{lines[-1]}" if len(lines) > 1 else "")
        if skipped:
            raise SystemExit(f"{relative}: operaciones no expresables {skipped}")
        omit = spec.get("omit", "")
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"], spec["risk"], spec["security"],
            actions, spec.get("builds"), spec.get("state", "Implemented"),
            ["Evo", "Atlas"],
            f"{ATLAS_PIN}:{refs}. Valores tomados del bloque Registry del pin: "
            + "; ".join(f"{a['valueName']}={a['value'] or '(cadena vacia)'}"
                        for a in actions)
            + "."
            + (f" El pin ADEMAS hace algo que no es registro y NO se declara: {omit}. "
               "Por eso la capacidad queda en State=Specified." if omit else "")
            + " Reversibilidad (ADR-0003): Reversible - valores de registro con valor "
              "previo guardado por el motor. "
            + f"Builds: {spec['build_note']}. "
            + "ledger_refs: atlas:manifest:"
            + spec["atlas_tweak"].replace(".psd1", "")))

    # --------------------------------------------- Atlas (clave y valor fijos)
    for spec in STATIC_SCRIPT_SPECS:
        key, value, source = static_script_pair(spec["script"])
        hive, key_path = b10.split_path(key)
        actions = [{
            "type": "registry", "order": 1,
            "description": f"SettingsPageVisibility en {hive}",
            "hive": HIVES[hive], "keyPath": key_path,
            "valueName": "SettingsPageVisibility",
            "value": value, "valueType": "String", "operation": "Set",
        }]
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"], spec["risk"], spec["security"],
            actions, spec.get("builds"), "Implemented", ["Evo", "Atlas"],
            f"{ATLAS_PIN}:{source}:{line_of(spec['script'], '$value')} "
            f"(clave en la linea {line_of(spec['script'], '$key')}). "
            "Valor literal del pin: SettingsPageVisibility='" + value + "'. "
            "Reversibilidad (ADR-0003): Reversible - valores de registro con valor previo "
            "guardado por el motor. "
            f"Builds: {spec['build_note']}. "
            "ledger_refs: atlas:manifest:qol/set-hidden-settings-pages"))

    capabilities.sort(key=lambda c: c["id"])
    return {
        "metadata": {
            "version": "1.0.0",
            "schemaVersion": 1,
            "provenance": (
                f"Paso 10, seccion 9 (oleada 3). Fuentes: {WINUTIL_PIN}, {ATLAS_PIN}. "
                "Los literales de valor se leen del pin con "
                "tools/ledger_extract/build_section9_catalog.py; ninguno se escribe a mano."
            ),
            "generatedBy": "paso 10 (oleada 3)",
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
            print("section9_system_registry.json NO reproducible: el fichero del disco difiere",
                  file=sys.stderr)
            return 1
        print(f"section9_system_registry.json reproducible: OK "
              f"({len(document['capabilities'])} capacidades)")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"capacidades: {len(document['capabilities'])} | "
          f"acciones: {sum(len(c['actions']) for c in document['capabilities'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
