#!/usr/bin/env python3
"""Genera `catalog/capabilities/section10_explorer_ui.json` (paso 9, oleada 2).

Los VALORES de cada acción no se escriben a mano aquí: se leen del pin fijado
(WinUtil `70c23c8…` en `config/tweaks.json`; Atlas `ec3c4058…` en
`package/Executables/AtlasModules/Toggles/` y `Scripts/Tweaks/`) y la provenance
cita fichero y línea. Si el pin no está descargado en `/tmp/upstream`, el script
falla con un mensaje claro: no se inventa ningún literal.

Decisiones de forma:
- `Value` de WinUtil es el estado ENCENDIDO de la casilla (medido en 8c/8d:
  `Invoke-WinUtilTweaks.ps1:34-46`); `OriginalValue` es el apagado. Para un
  Toggle de WinUtil se escribe `Value`, es decir, la casilla encendida, salvo
  que la capacidad declare lo contrario (`semantics` en la especificación).
- En Atlas cada toggle tiene estados con nombre; se toma el estado que produce
  el efecto que anuncia la capacidad de EVO (`atlas_state`).
- Las entradas de Atlas con `Operation = DeleteKey` / `AddKey` no se pueden
  expresar como `RegistryAction` (el motor sólo sabe borrar VALORES): se omiten
  de las acciones y se declaran en la descripción y en la provenance.
- Binarios: `Data = @(0x90, 0x12, …)` se serializa en base64, que es el formato
  que entiende `RegistryValueType.Binary` del motor.

Salida determinista: orden por id, LF, UTF-8 sin BOM, 3 espacios de sangría.

Uso:
    python3 tools/ledger_extract/build_section10_catalog.py
    python3 tools/ledger_extract/build_section10_catalog.py --check
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "catalog" / "capabilities" / "section10_explorer_ui.json"
UPSTREAM = Path("/tmp/upstream")
WINUTIL_TWEAKS = UPSTREAM / "winutil" / "config" / "tweaks.json"
ATLAS_TOGGLES = UPSTREAM / "atlas" / "package" / "Executables" / "AtlasModules" / "Toggles"
ATLAS_TWEAKS = UPSTREAM / "atlas" / "package" / "Executables" / "AtlasModules" / "Scripts" / "Tweaks"

WINUTIL_PIN = "winutil@70c23c80641d7370532af2f619b2842658600842"
ATLAS_PIN = "atlas@ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f"
BUILDS_W11 = [22631, 26100, 26200]
# Builds que el catálogo declara soportadas (misma lista que `windows-releases.json`).
DEFAULT_BUILDS = [19045, 22631, 26100, 26200]

# El `config/tweaks.json` del pin tiene caracteres de control en algunas
# descripciones: `strict=False` los tolera sin tocar el fichero del upstream.
W_TWEAKS: dict = (
    json.loads(WINUTIL_TWEAKS.read_text(encoding="utf-8"), strict=False)
    if WINUTIL_TWEAKS.is_file() else {}
)

# ---------------------------------------------------------------- especificación
# Cada entrada: id, tweak de WinUtil o (toggle, estado) de Atlas, metadatos.
# `builds` vacío = las cuatro builds del catálogo. El contrato (ADR-0003) exige
# que `supportedBuilds` sea EXPLICITO: al escribir el JSON, la lista vacía se
# sustituye por las cuatro builds del catálogo, nunca se deja como `[]`.
WINUTIL_SPECS = [
    dict(id="explorer.file-extensions.show", tweak="WPFToggleShowExt",
         name="Mostrar las extensiones de archivo",
         desc="Pone HideFileExt=0 en el Explorador para que se vea la extensión real "
              "de cada archivo (por ejemplo `factura.pdf.exe` en vez de `factura.pdf`). "
              "Se deshace con el diario: el valor anterior se guarda antes de escribir.",
         risk="Safe", security="Improves", builds=[]),
    dict(id="explorer.hidden-files.show", tweak="WPFToggleHiddenFiles",
         name="Mostrar los archivos y carpetas ocultos",
         desc="Pone Hidden=1 en el Explorador para que se vean los elementos con "
              "atributo oculto. Aumenta lo que se ve, no cambia permisos ni borra nada.",
         risk="Safe", security="Improves", builds=[]),
    dict(id="ui.theme.dark", tweak="WPFToggleDarkMode",
         name="Activar el tema oscuro de Windows",
         desc="Pone AppsUseLightTheme=0 y SystemUsesLightTheme=0: el sistema y las "
              "aplicaciones que siguen el tema del sistema pasan a oscuro. Sólo estética; "
              "el diario guarda los dos valores previos.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="ui.scrollbars.always-visible", tweak="WPFToggleScrollbars",
         name="Mantener las barras de desplazamiento siempre visibles",
         desc="Pone DynamicScrollbars=0 para que Windows no oculte las barras de "
              "desplazamiento cuando no se usan. Útil con ratón y en pantallas táctiles "
              "donde el gesto no es evidente.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="ui.taskbar.icons-centered", tweak="WPFToggleTaskbarAlignment",
         name="Centrar los iconos de la barra de tareas",
         desc="Pone TaskbarAl=1 (iconos centrados). Es la alineación por defecto de "
              "Windows 11: TaskbarAl no existe antes de 22000.",
         risk="Safe", security="Neutral", builds=BUILDS_W11,
         builds_note="Builds: TaskbarAl (centrado de iconos de la barra) sólo existe en "
                     "Windows 11; en 19045 la clave se escribe pero Explorer no la lee, así "
                     "que la capacidad no se ofrece ahí."),
    dict(id="ui.taskbar.search-icon", tweak="WPFToggleTaskbarSearch",
         name="Mostrar el icono de búsqueda en la barra de tareas",
         desc="Pone SearchboxTaskbarMode=1. Sólo controla si el cuadro de búsqueda se "
              "muestra como icono en la barra; no cambia el motor de búsqueda.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="ui.taskbar.task-view-button", tweak="WPFToggleTaskView",
         name="Mostrar el botón Vista de tareas",
         desc="Pone ShowTaskViewButton=1 para que el botón de Vista de tareas aparezca "
              "en la barra. El atajo Win+Tab sigue funcionando se muestre o no el botón.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="ui.snapping.windows", tweak="WPFToggleWindowSnapping",
         name="Activar el ajuste de ventanas",
         desc="Pone WindowArrangementActive=1 (valor de tipo String en el pin) para que "
              "arrastrar una ventana al borde la ajuste a media pantalla o a una esquina.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="ui.logon.acrylic-blur", tweak="WPFToggleLoginBlur",
         name="Quitar el desenfoque acrílico de la pantalla de inicio de sesión",
         desc="Pone DisableAcrylicBackgroundOnLogon=0 en HKLM, que es el estado que "
              "mantiene el desenfoque acrílico del fondo de la pantalla de inicio de "
              "sesión. La casilla de WinUtil se llama 'Logon Screen Acrylic Blur' y su "
              "eje es el contrario: barra apagada = 0 = desenfoque activo.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="ui.taskbar.end-task", tweak="WPFTweaksEndTaskOnTaskbar",
         name="Añadir «Finalizar tarea» al menú contextual de la barra de tareas",
         desc="Pone TaskbarEndTask=1 en TaskbarDeveloperSettings. Añade una opción al "
              "menú de la barra de tareas para cerrar un programa colgado sin abrir el "
              "Administrador de tareas. No finaliza nada por sí sola.",
         risk="Low", security="Neutral", builds=BUILDS_W11,
         builds_note="Builds: TaskbarEndTask no existe en Windows 10 ni en 22000/22621 "
                     "sin la actualización que lo introdujo; se limita a las builds del "
                     "catálogo que lo leen (22631, 26100 y 26200)."),
    dict(id="ui.numlock.startup", tweak="WPFToggleNumLock",
         name="Activar Bloq Num al iniciar sesión",
         desc="Pone InitialKeyboardIndicators='2' en HKU\\.Default y en HKCU. Afecta al "
              "estado de la tecla Bloq Num en el siguiente inicio de sesión, no al "
              "teclado en uso.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="ui.lockscreen.hide", tweak="WPFToggleDisableLockscreen",
         name="Omitir la pantalla de bloqueo",
         desc="Pone NoLockScreen=1 en la directiva de Personalización (HKLM): al "
              "arrancar y al despertar se va directo al inicio de sesión. No desactiva "
              "el bloqueo de sesión ni el apagado de pantalla; reduce una capa visual, "
              "por eso el impacto en seguridad se declara.",
         risk="Low", security="Reduces", builds=[]),
    dict(id="ui.notifications.center-hide", tweak="WPFTweaksDisableNotifications",
         name="Quitar el Centro de notificaciones",
         desc="Pone DisableNotificationCenter=1 y ToastEnabled=0. El primer valor es una "
              "directiva de usuario; el segundo apaga los avisos emergentes. No cambia "
              "qué aplicaciones pueden notificar, sólo si se muestran.",
         risk="Low", security="Neutral", builds=[]),
]

# Atlas: (fichero relativo dentro de Toggles, estado), o dentro de Scripts/Tweaks.
ATLAS_SPECS = [
    dict(id="explorer.gallery.hide", file="Interface/Gallery.psd1", state="Disable",
         name="Ocultar Galería en el Explorador",
         desc="Pone System.IsPinnedToNameSpaceTree=0 en el CLSID de Galería para que no "
              "aparezca en el panel de navegación. La Galería sigue existiendo: sólo deja "
              "de estar anclada.",
         risk="Safe", security="Neutral", builds=BUILDS_W11,
         builds_note="Builds: la Galería del Explorador es una carpeta de Windows 11 "
                     "(su CLSID {e88865ea-...} no existe en 19045)."),
    dict(id="explorer.home.hide", file="Interface/Home.psd1", state="Disable",
         name="Ocultar Inicio en el Explorador y abrir en Este equipo",
         desc="Desancla Inicio del panel de navegación (IsPinnedToNameSpaceTree=0) y pone "
              "LaunchTo=1 para que el Explorador abra en Este equipo. El estado 'Disable' "
              "del pin además BORRA la clave HKLM Desktop\\NameSpace\\{f874310e…}; esa "
              "operación es DeleteKey y el motor sólo sabe borrar valores, así que no se "
              "declara: se aplica la parte de valores y se dice aquí.",
         risk="Low", security="Neutral", builds=BUILDS_W11,
         builds_note="Builds: la carpeta Inicio (CLSID {f874310e-...}) y LaunchTo son de "
                     "Windows 11; 19045 no se declara."),
    dict(id="ui.context-menu.classic", file="Interface/OldContextMenu.psd1", state="Enable",
         variants=["Evo", "Atlas", "WinUtil"],
         extra_provenance=(
             " El mismo efecto existe en WinUtil: "
             f"{WINUTIL_PIN}:config/tweaks.json:1172 invoca "
             "functions/private/Set-WinUtilClassicContextMenu.ps1, que escribe el mismo "
             "CLSID {86ca1aa0-34aa-4e8b-a509-50c905bae2a2}. Ledger: "
             "winutil:tweak:WPFTweaksRightClickMenu (linea 10:326 del inventario, "
             "'Previous Right-Click Menu')."),
         name="Restaurar el menú contextual clásico de Windows 11",
         desc="Escribe la cadena vacía en el valor predeterminado de InprocServer32 del "
              "CLSID {86ca1aa0-34aa-4e8b-a509-50c905bae2a2}. El menú antiguo sólo se "
              "activa cuando ese valor existe y está vacío: con la clave desnuda Windows "
              "sigue mostrando el menú compacto. Es exclusivo de Windows 11: en Windows 10 "
              "ese CLSID no interviene y por eso no se declara 19045.",
         risk="Low", security="Neutral", builds=BUILDS_W11,
         builds_note="Builds: el CLSID {86ca1aa0-34aa-4e8b-a509-50c905bae2a2} es el del "
                     "menú contextual de Windows 11; Windows 10 no lo usa."),
    dict(id="explorer.compact-view.enable", file="Interface/CompactView.psd1", state="Enable",
         name="Activar la vista compacta del Explorador",
         desc="Pone UseCompactMode=1 para reducir el espacio entre elementos de una "
              "carpeta. Sólo cambia la densidad visual de la lista.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="ui.visual-effects.minimal", file="Interface/Animation.psd1", state="Disable",
         name="Reducir las animaciones de la interfaz",
         desc="Aplica el conjunto de efectos visuales de Atlas: menos animaciones en la "
              "barra de tareas, menús y vistas en miniatura, y Desenfoque/Peek apagados. "
              "Incluye UserPreferencesMask, un binario de 8 bytes que se escribe tal cual "
              "viene del pin (base64 en el catálogo). El pin pide cerrar sesión para que "
              "surta efecto completo; el motor no puede hacerlo por ti.",
         risk="Low", security="Neutral", builds=[]),
    dict(id="explorer.check-boxes.disable", file="Tweaks/qol/explorer/disable-check-boxes.psd1",
         state=None,
         name="Quitar las casillas de selección del Explorador",
         desc="Pone AutoCheckSelect=0 para que seleccionar varios archivos requiera Ctrl o "
              "arrastrar un marco, como en Windows clásico.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="explorer.app-icon-thumbnails.hide", file="Interface/AppIconThumbnail.psd1",
         state="Disable",
         name="Quitar el icono de la aplicación sobre las miniaturas",
         desc="Pone ShowTypeOverlay=0 para que la miniatura de un archivo no lleve encima "
              "el icono de la aplicación que lo abre. Sólo cambia la vista de miniaturas.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="explorer.extract-context-menu.add", file="Interface/ExtractContextMenu.psd1",
         state="Enable",
         name="Añadir «Extraer» al menú contextual de los archivos comprimidos",
         desc="Quita cuatro CLSID de la lista de extensiones de shell bloqueadas "
              "(HKLM Shell Extensions\Blocked), que es como Windows desactiva el menú "
              "«Extraer» de los comprimidos. El estado 'Disable' del pin hace lo contrario: "
              "escribe una cadena vacía en esos mismos valores, que es lo que los bloquea.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="explorer.recent-items.disable", file="Interface/RecentItems.psd1",
         state="Disable",
         name="Quitar los elementos recientes del Explorador y del menú Inicio",
         desc="Escribe nueve valores de directiva y de usuario para que no se guarden ni se "
              "muestren los documentos y programas usados recientemente (Start_TrackDocs, "
              "Start_TrackProgs, NoRecentDocsHistory, ClearRecentDocsOnExit y compañía). "
              "El pin añade una acción de máquina para la página de Configuración que no es "
              "de registro y aquí no se declara.",
         risk="Low", security="Improves", builds=[]),
    dict(id="explorer.removable-drives.sidebar", file="Interface/RemovableDrivesInSidebar.psd1",
         state="Enable",
         name="Mostrar las unidades extraíbles en el panel de navegación",
         desc="Escribe la cadena «Removable Drives» como valor predeterminado de la clave "
              "DelegateFolders\{F5FB2C77-…} en las dos vistas de registro (64 y WOW6432Node). "
              "El estado contrario del pin borra esas dos CLAVES, operación que el motor no "
              "sabe hacer.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="explorer.shortcut-icon.classic", file="Interface/ShortcutIcon.psd1",
         state="Classic",
         name="Usar la flecha clásica en los accesos directos",
         desc="Escribe Shell Icons\29 con la flecha clásica de Atlas (ExpandString a un .ico "
              "del paquete). El estado «None» del pin usa la flecha en blanco y «Default» "
              "borra el valor.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="ui.snap-layouts.disable", file="Interface/SnapLayouts.psd1", state="Disable",
         name="Desactivar los diseños de acoplado",
         desc="Pone EnableSnapAssistFlyout=0 y EnableSnapBar=0 para que al pasar el ratón por "
              "el botón de maximizar no aparezcan los diseños de acoplado ni la barra de "
              "acoplar.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="ui.verbose-messages.enable", file="Interface/VerboseMessages.psd1",
         state="Enable",
         name="Mostrar mensajes detallados durante el arranque y el apagado",
         desc="Pone verbosestatus=1 en la directiva del sistema: en vez de «Espere…» se ve "
              "qué está haciendo Windows. Sólo informa; no cambia el arranque.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="explorer.quick-access.hide", file="Interface/QuickAccess.psd1", state="Disable",
         name="Quitar Acceso rápido del Explorador",
         desc="Pone HubMode=1 en HKLM para que el panel de navegación no muestre Acceso "
              "rápido.",
         risk="Safe", security="Neutral", builds=[]),
    dict(id="explorer.long-paths.enable", file="Tweaks/qol/explorer/enable-long-paths.psd1",
         state=None,
         name="Activar las rutas largas (más de 260 caracteres)",
         desc="Pone LongPathsEnabled=1 en HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem. "
              "Quita el límite MAX_PATH para las aplicaciones que lo respetan; las que no, "
              "siguen fallando. Requiere reinicio de las aplicaciones afectadas.",
         risk="Low", security="Neutral", builds=[]),
    dict(id="explorer.shortcut-text.hide", file="Tweaks/qol/explorer/remove-shortcut-text.psd1",
         state=None,
         name="Quitar el sufijo «- Acceso directo» de los accesos directos",
         desc="Pone ShortcutNameTemplate='\"%s.lnk\"' en NamingTemplates para que un acceso "
              "directo nuevo no lleve el sufijo. Sólo afecta a los accesos creados después.",
         risk="Safe", security="Neutral", builds=[]),
]


# --------------------------------------------------------------------- utilidades
def rel_line(path: Path, needle: str) -> int:
    """Línea (1-based) de la primera aparición de `needle` en el fichero."""
    text = path.read_text(encoding="utf-8", errors="replace")
    index = text.find(needle)
    if index < 0:
        return 0
    return text.count("\n", 0, index) + 1


def winutil_registry(tweak: str) -> tuple[list[dict], str]:
    entry = W_TWEAKS.get(tweak)
    if entry is None:
        raise SystemExit(f"el tweak {tweak} no existe en el pin de WinUtil")
    actions = []
    for order, item in enumerate(entry.get("registry", []), start=1):
        hive, key = split_path(item["Path"])
        actions.append(
            {
                "type": "registry",
                "order": order,
                "description": f"{item['Name']} = {item['Value']} en {hive}",
                "hive": {"HKLM": "LocalMachine", "HKCU": "CurrentUser",
                         "HKCR": "ClassesRoot", "HKU": "Users"}[hive.upper()],
                "keyPath": key,
                "valueName": item["Name"],
                "operation": "Set",
                "valueType": item.get("Type", "DWord"),
                "value": str(item["Value"]),
            }
        )
    return actions, tweak


def atlas_entries_in(text: str) -> list[str]:
    """Trocea las hashtables `@{ … }` de un texto, sin cortar por dentro.

    Dos trampas medidas en el pin:
    - las rutas llevan llaves dentro de comillas (`CLSID\{e88865ea-…}`), así que
      un regex `@\{[^{}]*\}` parte la entrada por la mitad;
    - hay valores que también son `@( … )` (`Mask = @(0x0E, …)`), así que la
      profundidad tiene que contar llaves y paréntesis, no sólo llaves.
    """
    entries: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("@{", index)
        if start < 0:
            return entries
        depth, cursor, in_quote = 0, start, False
        closed = False
        while cursor < len(text):
            char = text[cursor]
            if char == "'":
                in_quote = not in_quote
            elif not in_quote:
                if char in "{(":
                    depth += 1
                elif char in "})":
                    depth -= 1
                    if depth == 0:
                        entries.append(text[start:cursor + 1])
                        closed = True
                        break
            cursor += 1
        index = cursor + 1 if closed else len(text)
    return entries


def entry_spans(text: str) -> list[str]:
    """Cada `@{ … }` de un bloque `Registry`, uno a uno (no anidan)."""
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
                elif char in "})":
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
    "path": re.compile(r"Path\s*=\s*'([^']*)'"),
    "name": re.compile(r"Name\s*=\s*'([^']*)'"),
    "type": re.compile(r"Type\s*=\s*'([^']*)'"),
    "data": re.compile(r"Data\s*=\s*(@\([^)]*\)|'[^']*'|[^;{}\s,]+)"),
    "op": re.compile(r"Operation\s*=\s*'([^']*)'"),
}


def parse_registry_block(path: Path) -> list[dict]:
    """Entradas del bloque `Registry = @( … )` de un .psd1, con línea."""
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"#[^\n]*", "", text)
    lines = text.split("\n")
    entries, inside, depth_start = [], False, 0
    for number, line in enumerate(lines, start=1):
        if not inside:
            if re.match(r"^\s*Registry\s*=\s*@\(", line):
                inside, depth_start = True, number
            continue
        for body in entry_spans(line):
            path_match, name_match = FIELD["path"].search(body), FIELD["name"].search(body)
            if not path_match or not name_match:
                continue
            operation = FIELD["op"].search(body)
            op = operation.group(1) if operation else "Set"
            data_match = FIELD["data"].search(body)
            type_match = FIELD["type"].search(body)
            entries.append(
                {
                    "line": number,
                    "path": path_match.group(1),
                    "name": name_match.group(1),
                    "type": type_match.group(1) if type_match else "",
                    "op": op,
                    "data": data_match.group(1) if data_match else "",
                    # `Operation = 'Delete'` borra el VALOR y no lleva Data; si se
                    # tratara como Set se escribiría la cadena vacía, que es otra
                    # cosa (y en el menú contextual clásico, justo lo contrario).
                    "has_data": data_match is not None,
                }
            )
    _ = depth_start
    return entries


def split_path(path: str) -> tuple[str, str]:
    """'HKCU:\\X' o 'HKCU\\X' -> ('HKCU', 'X'). El pin usa las dos formas."""
    if ":" in path:
        hive, key = path.split(":", 1)
    else:
        hive, key = path.split("\\", 1)
    return hive.strip().upper(), key.lstrip("\\")


def psd1_value(raw: str) -> str:
    """Literal de PowerShell -> texto del catálogo (binario en base64)."""
    raw = raw.strip()
    if raw.startswith("@(") and raw.endswith(")"):
        numbers = [int(x, 16) if x.lower().startswith("0x") else int(x)
                   for x in re.findall(r"0x[0-9A-Fa-f]+|\b\d+\b", raw)]
        return base64.b64encode(bytes(numbers)).decode("ascii")
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    return raw


def atlas_actions(relative: str, state: str | None) -> tuple[list[dict], list[str], str]:
    """Acciones del estado pedido y lista de operaciones no expresables."""
    if relative.startswith("Tweaks/"):
        path = ATLAS_TWEAKS / relative[len("Tweaks/"):]
        entries = parse_registry_block(path)
    else:
        path = ATLAS_TOGGLES / relative
        text = path.read_text(encoding="utf-8", errors="replace")
        states = split_states(text)
        if state not in states:
            raise SystemExit(f"{relative}: estado '{state}' no encontrado")
        entries = parse_registry_block_text(states[state])
    actions, skipped = [], []
    for entry in entries:
        hive, key = split_path(entry["path"])
        if entry["op"] in ("DeleteKey", "AddKey"):
            skipped.append(f"{entry['op']} {hive}\\{key}")
            continue
        operation = entry["op"]
        if operation.lower() == "delete":
            operation = "Delete"
        elif not entry["has_data"]:
            raise SystemExit(
                f"{relative}: {entry['name'] or '(predeterminado)'} en "
                f"{entry['path']} sin Data ni Operation: no se inventa un literal")
        actions.append(
            {
                "order": len(actions) + 1,
                "hive": {"HKLM": "LocalMachine", "HKCU": "CurrentUser",
                         "HKCR": "ClassesRoot", "HKU": "Users"}[hive],
                "keyPath": key,
                "valueName": entry["name"],
                "value": psd1_value(entry["data"]),
                "valueType": entry["type"] or "String",
                "operation": operation,
                "line": entry["line"],
                "description": f"{entry['name'] or '(predeterminado)'} en {hive}",
            }
        )
    return actions, skipped, str(path.relative_to(UPSTREAM / "atlas"))


def balanced_spans(block: str, opener: str = "@{") -> list[str]:
    """Trocea `@{ … }` de primer nivel, respetando comillas y `@( … )`.

    Es la misma mecánica que `atlas_entries_in`, pero devuelve sólo las
    hashtables que NO están dentro de otra: el bloque `States` es una lista de
    estados y cada estado lleva su propia lista `Registry` de entradas, que no
    deben confundirse con los estados.
    """
    spans: list[str] = []
    index = 0
    while index < len(block):
        start = block.find(opener, index)
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
                elif char in "})":
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


def split_states(text: str) -> dict[str, str]:
    """Trocea el bloque `States = @( … )` en estado -> texto del estado."""
    text = re.sub(r"#[^\n]*", "", text)
    marker = text.find("States")
    if marker < 0:
        return {}
    paren = text.find("@(", marker)
    if paren < 0:
        return {}
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

    states: dict[str, str] = {}
    for body in balanced_spans(block):
        if "StateValue" not in body:
            continue
        name = re.search(r"Name\s*=\s*'([^']+)'", body)
        if name:
            # Se guarda el INTERIOR del estado (sin su `@{ … }`): así el
            # troceador de entradas devuelve las entradas `Registry`, no el
            # estado entero.
            states.setdefault(name.group(1), body[2:-1])
    return states


def parse_registry_block_text(text: str) -> list[dict]:
    """Igual que `parse_registry_block` pero sobre un trozo de texto ya aislado."""
    entries = []
    for body in entry_spans(text):
        path_match = FIELD["path"].search(body)
        if not path_match:
            continue
        name_match = FIELD["name"].search(body)
        if not name_match:
            continue
        operation = FIELD["op"].search(body)
        data_match = FIELD["data"].search(body)
        type_match = FIELD["type"].search(body)
        entries.append(
            {
                "line": 0,
                "path": path_match.group(1),
                "name": name_match.group(1),
                "type": type_match.group(1) if type_match else "",
                "op": operation.group(1) if operation else "Set",
                "data": data_match.group(1) if data_match else "",
                "has_data": data_match is not None,
            }
        )
    return entries


def atlas_line(relative: str, name: str) -> int:
    path = (ATLAS_TWEAKS / relative[len("Tweaks/"):]) if relative.startswith("Tweaks/") \
        else (ATLAS_TOGGLES / relative)
    return rel_line(path, name)


def build() -> dict:
    capabilities = []
    for spec in WINUTIL_SPECS:
        actions, tweak = winutil_registry(spec["tweak"])
        line = rel_line(WINUTIL_TWEAKS, f'"{tweak}"')
        entry = W_TWEAKS[tweak]
        capabilities.append(
            {
                "id": spec["id"],
                "name": spec["name"],
                "description": spec["desc"],
                "sectionId": 10,
                "risk": spec["risk"],
                "securityImpact": spec["security"],
                "privilege": "Admin" if any(a["hive"] in ("LocalMachine", "Users")
                                          for a in actions) else "User",
                "restore": "SessionUndo",
                "reversibility": "Reversible",
                "confirmation": CONFIRM[spec["risk"]],
                "state": "Implemented",
                "variants": ["Evo", "WinUtil"],
                "conflictsWith": [],
                "dependsOn": [],
                "supportedBuilds": spec["builds"] or DEFAULT_BUILDS,
                "provenance": (
                    f"{WINUTIL_PIN}:config/tweaks.json:{line} (#{tweak}, "
                    f"Type={entry.get('Type') or 'sin Type'}). "
                    f"Valores tomados de la fuente: "
                    + "; ".join(f"{a['valueName']}={a['value']}" for a in actions)
                    + ". Semantica: en un Toggle de WinUtil `Value` es la casilla "
                    "ENCENDIDA y `OriginalValue` la apagada "
                    "(functions/private/Invoke-WinUtilTweaks.ps1:34-46, "
                    "Get-WinUtilToggleStatus.ps1:44). Reversibilidad (ADR-0003): "
                    "Reversible - el motor guarda el valor previo de cada clave antes "
                    "de escribir y lo restaura al deshacer. "
                    + ("Privilegio Admin por escribir en HKLM. " if any(
                        a["hive"] == "LocalMachine" for a in actions) else "")
                    + spec.get("extra_provenance", "")
                    + (spec.get("builds_note", "")
                       if spec["builds"] else
                       "Builds: las cuatro del catalogo (extension de archivo, ocultos, "
                       "tema, barras, ajuste de ventanas, Bloq Num, busqueda y Vista de "
                       "tareas son claves que existen en 19045 y en las tres de Windows 11). ")
                    + f"ledger_refs: winutil:tweak:{tweak}"
                ),
                "actions": actions,
            }
        )

    for spec in ATLAS_SPECS:
        actions, skipped, source_path = atlas_actions(spec["file"], spec["state"])
        lines = sorted({line for line in (a.pop("line") for a in actions) if line}) or \
            [atlas_line(spec["file"], "Registry")]
        refs = f"{source_path}:{lines[0]}-{lines[-1]}" if len(lines) > 1 else f"{source_path}:{lines[0]}"
        blocked = ""
        if skipped:
            blocked = (" No expresable como RegistryAction y por tanto NO aplicado: "
                       + ", ".join(skipped) + " (el motor solo borra valores, no claves).")
        capabilities.append(
            {
                "id": spec["id"],
                "name": spec["name"],
                "description": spec["desc"],
                "sectionId": 10,
                "risk": spec["risk"],
                "securityImpact": spec["security"],
                "privilege": "Admin" if any(a["hive"] in ("LocalMachine", "Users")
                                          for a in actions) else "User",
                "restore": "SessionUndo",
                "reversibility": "Reversible",
                "confirmation": CONFIRM[spec["risk"]],
                "state": "Implemented",
                "variants": spec.get("variants", ["Evo", "Atlas"]),
                "conflictsWith": [],
                "dependsOn": [],
                "supportedBuilds": spec["builds"] or DEFAULT_BUILDS,
                "provenance": (
                    f"{ATLAS_PIN}:{refs}"
                    + (f" (estado '{spec['state']}')" if spec["state"] else "")
                    + ". Valores tomados del bloque Registry del pin: "
                    + "; ".join(
                        f"{a['valueName'] or '(predeterminado)'}="
                        f"{a['value'] if a['value'] != '' else '(cadena vacia)'}"
                        for a in actions)
                    + "." + blocked
                    + spec.get("extra_provenance", "")
                    + spec.get("builds_note", "")
                    + (" " if spec.get("builds_note") else "")
                    + " Reversibilidad (ADR-0003): Reversible - valores de registro con "
                    "valor previo guardado por el motor."
                    # Referencia al ledger: los toggles de Atlas viven en
                    # `atlas:toggle:<Nombre>`; los tweaks de `Scripts/Tweaks/`, en
                    # `atlas:manifest:<ruta sin Tweaks/ ni .psd1>`.
                    + (" ledger_refs: atlas:toggle:" + spec["file"].rsplit("/", 1)[-1].removesuffix(".psd1")
                       if spec["file"].startswith("Interface/")
                       else " ledger_refs: atlas:manifest:"
                            + spec["file"].replace("Tweaks/", "").removesuffix(".psd1"))
                ),
                "actions": actions,
            }
        )

    capabilities.sort(key=lambda c: c["id"])
    return {
        "metadata": {
            "version": "1.0.0",
            "schemaVersion": 1,
            "provenance": (
                f"Paso 9, seccion 10 (oleada 2). Fuentes: {WINUTIL_PIN}, {ATLAS_PIN}. "
                "Los literales de valor se leen del pin con "
                "tools/ledger_extract/build_section10_catalog.py; ninguno se escribe a mano."
            ),
            "generatedBy": "paso 9 (oleada 2)",
        },
        "capabilities": capabilities,
    }


CONFIRM = {"Safe": "None", "Low": "SimpleClick", "Medium": "Summary",
           "High": "SummaryAndRestorePoint", "Critical": "TypeOperationName"}


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
            print("section10_explorer_ui.json NO coincide con el pin", file=sys.stderr)
            return 1
        print(f"section10_explorer_ui.json reproducible: OK ({len(document['capabilities'])} capacidades)")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    total = sum(len(c["actions"]) for c in document["capabilities"])
    print(f"capacidades: {len(document['capabilities'])} | acciones: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
