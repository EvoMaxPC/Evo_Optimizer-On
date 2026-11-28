#!/usr/bin/env python3
"""Conciliacion DEFINITIVA del inventario del responsable (588 lineas).

Entrada:
    docs/requirements/INVENTARIO_USUARIO.md          (**solo lectura**)
    inventory/ledger/winutil-items.tsv               162 items
    inventory/ledger/winutil-apps.tsv                239 apps
    inventory/ledger/atlas-toggles.tsv               91 toggles
    inventory/ledger/atlas-manifest.tsv              182 entradas de manifiesto
    inventory/ledger/atlas-effects.tsv               986 efectos
    inventory/ledger/winutil-tweak-ops.tsv           179 operaciones
    docs/inventory-recon/seccion16-17-probe.tsv       39 sondas

Salida:
    inventory/ledger/inventory-reconciliation.tsv    588 filas
    docs/requirements/CONCILIACION_INVENTARIO.md     resumen legible

Estados (exactamente cinco, sin variantes):
    Mapped            ajuste/tweak/toggle/servicio/clave presente en WinUtil o
                      Atlas en el pin, con al menos un `mapped_id` del ledger.
    Mapped-To-App     linea de la seccion 15 que corresponde a una entrada de
                      `winutil-apps.tsv`.
    EVO-Exclusive     requerimiento propio de EVO (secciones 6, 7, 14, 17 y las
                      lineas "Capacidad EVO a desarrollar:").
    Absent-At-Pin     funcionalidad de Atlas/WinUtil nombrada en el inventario
                      que en el pin NO existe como codigo/parser ejecutable.
    Informative-Header encabezados, notas metodologicas y cabeceras de tabla.

Reglas, en orden (gana la primera que aplica):
    E1  encabezado de seccion / nota metodologica / cabecera de tabla  -> Informative-Header
    E2  linea marcada como EVO (bloque EVO de la seccion o prefijo)     -> EVO-Exclusive
    E3  seccion 16/17 con sonda `dudoso` o sin ficheros                -> Absent-At-Pin
    E4  seccion 15 con app de `winutil-apps.tsv`                        -> Mapped-To-App
    E5  R1/R2/R3 del borrador del paso 4e con candidato valido          -> Mapped
    E6  resto                                                           -> Absent-At-Pin

Ninguna linea puede quedar sin estado; lo comprueba `validate_reconciliation.py`.

Uso:
    python3 tools/ledger_extract/build_final_reconciliation.py [--json]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

import count_inventory as ci  # noqa: E402
import build_conciliacion as bc  # noqa: E402

LEDGER = ROOT / "inventory" / "ledger"
OUT_TSV = LEDGER / "inventory-reconciliation.tsv"
OUT_MD = ROOT / "docs" / "requirements" / "CONCILIACION_INVENTARIO.md"

STATUSES = ("Mapped", "Mapped-To-App", "EVO-Exclusive", "Absent-At-Pin",
            "Informative-Header")
COLUMNS = ("seccion", "linea", "fuente_declarada", "texto", "status",
           "mapped_ids", "confidence", "rationale")

# Bloque EVO: desde la linea que lo anuncia hasta la linea de cierre del bloque.
EVO_START = re.compile(r"^(EVO CLEAN|Capacidad EVO a desarrollar:)", re.I)
EVO_STOP = re.compile(r"^(Estas últimas capacidades|AtlasOS|WinUtil|"
                      r"Fuentes de arquitectura|GitHub\+1)", re.I)
# Encabezados de columna de la tabla aplanada de la seccion 17 y de los
# encabezados de modo que el conteo ya marca como `general`.
MODE_HEADERS = {"WinUtil", "AtlasOS"}

# Lineas del inventario que son funcionalidad nombrada pero NO existe en el pin
# como codigo/parser ejecutable. Medido en los pasos 4b/4c/4e; ver
# docs/reports/paso5.md (seccion T1) para la evidencia de cada una.
ABSENT_KEYWORDS = (
    "ame wizard", "playbook", "iso creation", "iso injection", "creación de usb",
    "creacion de usb", "instalación de iso", "instalacion de iso",
    "upgrade system", "install plan", "install session", "installation phases",
    "choices phase", "features phase", "services phase", "tweaks phase",
    "components phase", "software phase", "shell refresh", "appx support",
    "windows transition", "environment phase", "pre-install",
    "new user initialization", "atlas manager", "trustedinstaller broker",
)

# Secciones con preponderancia EVO declarada por el encargo (6, 7, 14, 17) no se
# fuerzan enteras: solo se aplican EVO_START/E2 y la palabra "evo".
GAMING_EVO = ("perfil", "detección del juego", "rededucción", "reducción temporal",
              "suspensión temporal", "recuperación del estado", "registro de fps",
              "comparación antes", "preparación automática", "control de procesos")


# Correcciones medidas en el paso 9 (oleada 2). El paso 4e dejo estas lineas en
# `Absent-At-Pin` por un falso negativo: el TEXTO de la linea no casa con el
# ledger y no se miro que si hubiera efecto. Ahora que existe seccion 10 en el
# catalogo, cada una se puede comprobar contra el pin. Se indexa por
# (seccion, linea) y NO por texto: el texto puede repetirse en dos secciones.
# Evidencia de cada una en docs/reports/paso9.md.
MAPPED_OVERRIDES: dict[tuple[int, str], tuple[str, str]] = {
    (10, "326"): ("winutil:tweak:WPFTweaksRightClickMenu",
                  "falso negativo del paso 4e: WinUtil aplica el menu contextual clasico "
                  "(functions/private/Set-WinUtilClassicContextMenu, invocado por "
                  "WPFTweaksRightClickMenu) y Atlas tiene el mismo efecto en OldContextMenu.psd1"),
    (10, "339"): ("atlas:toggle:AppIconThumbnail",
                  "falso negativo del paso 4e: Atlas lo expone como toggle "
                  "(Toggles/Interface/AppIconThumbnail.psd1, ShowTypeOverlay)"),
    (10, "341"): ("atlas:toggle:CompactView",
                  "falso negativo del paso 4e: Atlas lo expone como toggle "
                  "(Toggles/Interface/CompactView.psd1, UseCompactMode)"),
    (10, "343"): ("winutil:tweak-op:WPFTweaksEdgeDebloat:registry:0",
                  "falso negativo del paso 4e: el efecto real esta en el debloat de Edge, "
                  "que ya estaba mapeado como Mapped en la linea 9:291"),
    (10, "344"): ("atlas:toggle:ExtractContextMenu",
                  "falso negativo del paso 4e: Atlas lo expone como toggle "
                  "(Toggles/Interface/ExtractContextMenu.psd1)"),
    (10, "347"): ("winutil:tweak-op:WPFToggleNumLock:registry:0",
                  "falso negativo del paso 4e: la linea del inventario agrupa los atajos de "
                  "teclado; en el pin el unico efecto de esa familia es NumLock al iniciar"),
    # Correcciones medidas en el paso 10 (oleada 3, seccion 9).
    (9, "265"): ("winutil:tweak:WPFTweaksServices",
                 "mapeo erroneo del paso 4e: la linea dice 'Services.' y en el pin el unico "
                 "efecto de servicios de esa familia es WPFTweaksServices "
                 "(config/tweaks.json: CscService, DiagTrack, MapsBroker, StorSvc, "
                 "SharedAccess). La regla R3 habia casado el texto con un artefacto de las "
                 "pruebas de Atlas (tests/Atlas.Toggles.Tests.ps1), que no es producto"),
    (9, "308"): ("atlas:toggle:KeyboardShortcuts",
                 "mapeo erroneo del paso 4e: la linea esta en el bloque AtlasOS y Atlas SI "
                 "expone Toggles/Interface/KeyboardShortcuts.psd1, que escribe Hotkey, "
                 "Language Hotkey y Layout Hotkey en HKCU\\Keyboard Layout\\Toggle; el "
                 "paso 4e la habia casado con el NumLock de WinUtil, que es otro ajuste"),
    # Falsos negativos del paso 4e medidos en el paso 10: la regla R3 no cruzó el
    # texto con el item del ledger, pero el pin lo implementa y ahora hay
    # capacidad que lo cubre. Evidencia en docs/reports/paso10.md (T0-e).
    (9, "269"): ("atlas:manifest:qol/system/disable-wpbt",
                 "falso negativo del paso 4e: la linea esta en el bloque AtlasOS y el "
                 "pin implementa WPBT en Scripts/Tweaks/qol/system/disable-wpbt.psd1 "
                 "(DisableWpbtExecution=1 en HKLM\\SYSTEM\\CurrentControlSet\\Control\\"
                 "Session Manager); la capacidad system.error-reporting.wpbt-disable lo "
                 "declara"),
    (9, "302"): ("atlas:manifest:misc/config-oem-information",
                 "falso negativo del paso 4e: el pin implementa OEM Information en "
                 "Scripts/Tweaks/misc/config-oem-information.psd1 (Manufacturer, "
                 "SupportURL y SupportPhone en HKLM\\SOFTWARE\\Microsoft\\Windows\\"
                 "CurrentVersion\\OEMInformation); la capacidad "
                 "system.oem-information.identify lo declara"),
    (9, "307"): ("atlas:toggle:KeyboardShortcuts",
                 "falso negativo del paso 4e: la linea 'Keyboard Switching' del bloque "
                 "AtlasOS es el manifiesto qol/set-keyboard-switching, cuyo script "
                 "(set-keyboard-switching.ps1) no escribe valores propios: aplica el "
                 "estado del toggle KeyboardShortcuts, que es el mismo efecto que la "
                 "linea 308 y que declara system.keyboard-shortcuts.disable"),
    (9, "316"): ("atlas:manifest:qol/set-hidden-settings-pages",
                 "mapeo erroneo del paso 4e: la linea esta en el bloque AtlasOS y Atlas "
                 "escribe SettingsPageVisibility en "
                 "Scripts/Tweaks/qol/set-hidden-settings-pages.ps1; el paso 4e la habia "
                 "casado con WPFTweaksTelemetry:registry:7, que es AcceptedPrivacyPolicy y "
                 "no la visibilidad de paginas"),
    # Correcciones medidas en el paso 7 (oleada 1, seccion 4 "Optimizacion de servicios").
    # El paso 4e dejo estas lineas en `Absent-At-Pin` pero el pin SI las implementa.
    # Linea 121 "Services — configuración de inicio Manual." (bloque WinUtil): WPFTweaksServices
    # SÍ se expresa en el pin (config/tweaks.json:146) y las capacidades
    # services.winutil.cscservice/diagtrack/mapsbroker/sharedaccess/storsvc declaran
    # winutil@70c23c80641d7370532af2f619b2842658600842:config/tweaks.json:WPFTweaksServices,
    # por lo que la linea 121 queda Mapped (no Absent-At-Pin).
    (4, "121"): ("winutil:tweak:WPFTweaksServices",
                 "medido en el paso 7: WPFTweaksServices se expresa en el pin "
                 "(config/tweaks.json:146) y las capacidades services.winutil.cscservice, "
                 "diagtrack, mapsbroker, sharedaccess y storsvc declaran "
                 "winutil@70c23c80641d7370532af2f619b2842658600842:config/tweaks.json:WPFTweaksServices; "
                 "la linea 121 describe esa configuracion de inicio de servicios de WinUtil."),
    (4, "127"): ("winutil:tweak:WPFTweaksSvcHostSplitting",
                 "el pin implementa Service Host Splitting en WPFTweaksSvcHostSplitting "
                 "(config/tweaks.json:180): escribe SvcHostSplitThresholdInKB en "
                 "HKLM\\\\SYSTEM\\\\CurrentControlSet\\\\Control. El valor depende de la memoria "
                 "fisica (no es literal fijo), por eso la capacidad queda en State=Specified."),
    (4, "131"): ("atlas:toggle:LanmanWorkstation",
                 "el pin implementa Lanman Workstation en Toggles/Services/LanmanWorkstation.psd1 "
                 "(estado Disable): KSecPkg, LanmanServer, LanmanWorkstation, mrxsmb, mrxsmb20, "
                 "rdbss y srv2 a StartupType Disabled/Manual. La MachineAction "
                 "Set-AtlasSmbDirectFeature no se declara (R1), por eso State=Specified."),
    (4, "132"): ("atlas:toggle:NetworkDiscovery",
                 "el pin implementa Network Discovery en Toggles/Services/NetworkDiscovery.psd1 "
                 "(estado Disable): fdPHost, FDResPub, lmhosts y SSDPSRV a StartupType Disabled. "
                 "Estado Disable sin MachineAction, expresable completo."),
    (4, "133"): ("atlas:toggle:NVidiaDisplayContainer",
                 "el pin implementa NVIDIA Display Container en Toggles/Services/NVidiaDisplayContainer.psd1 "
                 "(estado Disable): solo declara MachineAction Set-AtlasNVidiaDisplayContainerState, "
                 "sin registro ni tipo de servicio expresables. No cabe en acciones del motor: State=Specified."),
    (4, "134"): ("atlas:toggle:Printing",
                 "el pin implementa Printing en Toggles/Services/Printing.psd1 (estado Disable): "
                 "solo declara MachineAction Set-AtlasPrintingMachineState y ContextAction, sin "
                 "registro ni tipo de servicio expresables. No cabe en acciones del motor: State=Specified."),
    (4, "135"): ("atlas:toggle:SuperFetch",
                 "el pin implementa SuperFetch/SysMain en Toggles/Services/SuperFetch.psd1 "
                 "(estado Disable): solo declara MachineAction Set-AtlasSuperFetchMachineState, sin "
                 "registro ni tipo de servicio expresables. No cabe en acciones del motor: State=Specified."),
    # Seccion 9, linea 278 "System Tray Configuration." (bloque WinUtil).
    # El paso 7 lo mueve a MAPPED_OVERRIDES: el pin SI tiene WPFToggleBatteryPercentage
    # (config/tweaks.json:1395) y WPFTweaksDisableNotifications (config/tweaks.json:1116).
    (9, "278"): ("winutil:tweak:WPFToggleBatteryPercentage",
                 "medido en el paso 7: el pin de WinUtil no tiene un ajuste unico de "
                 "'configuracion de la bandeja'; config/tweaks.json declara dos ajustes "
                 "concretos - 'System Tray Notifications & Calendar - Disable' "
                 "(WPFTweaksDisableNotifications, linea 1116) y 'System Tray Battery "
                 "Percentage' (WPFToggleBatteryPercentage, linea 1395) - y no una "
                 "'configuracion de la bandeja' generica. `xaml/` no tiene pagina de "
                 "bandeja. Se cubre WPFToggleBatteryPercentage con la capacidad "
                 "system.tray.battery-percentage (seccion 9)."),
}

# Lineas que el paso 4e dejo en `Mapped` por la regla R3 y que en el pin NO tienen
# el efecto que anuncia la linea. Se corrigen a `Absent-At-Pin`, con la medicion.
ABSENT_OVERRIDES: dict[tuple[int, str], str] = {
    # Seccion 4, linea 136 "Windows Update Services." (bloque AtlasOS).
    (4, "136"): ("medido en el paso 7: el pin tiene toggles generales de actualizacion "
                 "(ToggleWindowsUpdates.psd1, AutomaticUpdates.psd1) pero no un toggle "
                 "especifico llamado 'Windows Update Services'. No hay candidato de ledger "
                 "que mapee a esta linea (REQ-002: no inventar)."),
    # Seccion 4, linea 144 "Reset Services." (bloque AtlasOS).
    (4, "144"): ("medido en el paso 7: el pin tiene Defaults.ps1 en Atlas.Network/Domain "
                 "(Invoke-AtlasWindowsNetworkDefault) pero es un script de restablecimiento de red, "
                 "no un toggle de servicios con el efecto que anuncia la linea. "
                 "El mapped_id que puso el paso 4e (regla R3 contra tests de Atlas) no es producto. (REQ-002)"),
}


def read_tsv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def probes() -> dict[str, dict]:
    out = {}
    for r in read_tsv(ROOT / "docs" / "inventory-recon" / "seccion16-17-probe.tsv"):
        out[r["item"].strip().lower()] = r
    return out


def apps_in_text(texto: str, index) -> list[str]:
    """`item_id` de winutil-apps cuyo nombre de producto aparece en el texto.

    Exige >= 4 caracteres para no casar 'go' o 'cc'. Devuelve como maximo 5,
    ordenados por longitud descendente (el nombre mas especifico gana).
    """
    n = bc.norm(texto)
    hits = []
    for item_id, norm_label, label in index:
        if len(norm_label) < 4:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(norm_label)}(?![a-z0-9])", n):
            hits.append((len(norm_label), item_id))
    hits.sort(reverse=True)
    return [i for _, i in hits][:5]


S17_HEADERS = {"Funcionalidad", "WinUtil", "AtlasOS",
               "También hay funcionalidades que no son optimizaciones directas, "
               "pero forman parte de las herramientas que debemos estudiar."}


def is_s17_header(texto: str) -> bool:
    return texto.strip().rstrip(".") in {h.rstrip(".") for h in S17_HEADERS}


def s17_label_status(feature: str) -> str:
    n = bc.norm(feature)
    for kw in ("creacion de usb", "instalacion de iso", "perfiles y presets"):
        if kw in n:
            return "Absent-At-Pin"
    return "EVO-Exclusive"


def s17_label_reason(feature: str) -> str:
    if s17_label_status(feature) == "Absent-At-Pin":
        return ("el pin no tiene creador de USB ni motor de ISO propio; "
                "EVO lo implementa de forma nativa")
    return "requisito transversal del responsable, lo asume EVO"


def s17_match(feature: str, file_index) -> tuple[list[str], str]:
    """Busca la fila de la seccion 17 en los ficheros de Atlas.

    Se compara el nombre de la funcionalidad con el nombre del fichero
    (sin extension) y con la ruta. Devuelve (ids, motivo).
    """
    n = bc.norm(feature)
    hits: list[tuple[int, str]] = []
    for item_id, norm_path, fname in file_index:
        stem = bc.norm(fname.rsplit(".", 1)[0])
        if not stem or len(stem) < 3:
            continue
        # Solo se acepta que el nombre del fichero CONTENGA el nombre de la
        # funcionalidad (nunca al reves: 'iso' dentro de 'instalacion de iso'
        # casaba con iso.rs) y con al menos 5 caracteres.
        if stem == n or (len(n) >= 5 and len(stem) >= 5 and n in stem):
            hits.append((len(stem), item_id))
    hits.sort(reverse=True)
    ids = []
    for _, i in hits:
        if i not in ids:
            ids.append(i)
    if ids:
        return ids, f"fichero de Atlas con nombre coincidente ('{feature}')"
    return [], ""


def service_index() -> dict[str, str]:
    """nombre de servicio normalizado -> item_id de la operacion que lo toca."""
    out: dict[str, str] = {}
    for r in read_tsv(LEDGER / "winutil-tweak-ops.tsv"):
        if r["kind"] == "service" and r["name"]:
            out.setdefault(bc.norm(r["name"]), r["item_id"])
    for r in read_tsv(LEDGER / "atlas-tweak-ops.tsv"):
        if r["value_name"]:
            out.setdefault(bc.norm(r["value_name"]), r["item_id"])
    return out


# --------------------------------------------------------------------- E1
def informative(seccion: int, texto: str, bucket: str) -> str | None:
    s = texto.strip()
    if s in MODE_HEADERS:
        return "encabezado de modo (WinUtil/AtlasOS) de la tabla aplanada"
    if ci.is_note(s):
        return "nota metodologica (regla d del conteo)"
    if s.startswith("Fuentes de arquitectura"):
        return "fuente citada, no una capacidad"
    if s == "GitHub+1":
        return "referencia bibliografica, no una capacidad"
    if seccion == 17 and len(s.split()) <= 4 and not s.endswith("."):
        return "cabecera de tabla aplanada de la seccion 17"
    return None


# --------------------------------------------------------------------- E3
def absent_probe(texto: str, prb: dict[str, dict]) -> str | None:
    n = bc.norm(texto)
    for item, r in prb.items():
        if n == bc.norm(item) or (len(n) > 8 and bc.norm(item).startswith(n)):
            if "dudoso" in r["patron"] or int(r["atlas_ficheros"]) == 0:
                return (f"sonda '{r['item']}': atlas={r['atlas_ficheros']}, "
                        f"winutil={r['winutil_ficheros']}"
                        + (", patron dudoso" if "dudoso" in r["patron"] else ""))
            return None
    for kw in ABSENT_KEYWORDS:
        if kw in n:
            return f"'{kw}' no existe como codigo ejecutable en el pin"
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--md", type=Path, default=ci.DEFAULT_MD)
    ap.add_argument("--tsv", type=Path, default=OUT_TSV)
    ap.add_argument("--report", type=Path, default=OUT_MD)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    sections, body_start = ci.parse(args.md)
    raw = args.md.read_text(encoding="utf-8").splitlines()

    # linea -> seccion y bucket declarado (mismo criterio que count_inventory)
    sec_at: dict[int, int] = {}
    for s in sections:
        sec_at[s["linea"]] = s["numero"]

    sources = bc.load_sources()
    targets = bc.effect_targets()
    df = bc.token_df(sources)
    prb = probes()
    apps_index = [(r["item_id"], bc.norm(r["label"]), r["label"])
                  for r in read_tsv(LEDGER / "winutil-apps.tsv")]
    # claves de servicio / claves de registro del inventario que si existen en el pin
    svc_ids = service_index()
    file_index = [(r["item_id"], bc.norm(r["source_ref"]),
                   r["source_ref"].rsplit("/", 1)[-1]) for r in
                  read_tsv(LEDGER / "atlas-files.tsv")]
    known_text: set[str] = set()

    # ids validos por ledger de origen
    valid_ids: dict[str, set[str]] = {
        "winutil-items": {r["item_id"] for r in read_tsv(LEDGER / "winutil-items.tsv")},
        "winutil-apps": {r["item_id"] for r in read_tsv(LEDGER / "winutil-apps.tsv")},
        "atlas-toggles": {r["item_id"] for r in read_tsv(LEDGER / "atlas-toggles.tsv")},
        "atlas-manifest": {r["item_id"] for r in read_tsv(LEDGER / "atlas-manifest.tsv")},
        "atlas-effects": {r["item_id"] for r in read_tsv(LEDGER / "atlas-effects.tsv")},
        "winutil-tweak-ops": {r["item_id"] for r in read_tsv(LEDGER / "winutil-tweak-ops.tsv")},
    }
    all_valid = set().union(*valid_ids.values())

    rows: list[dict] = []
    cur_sec: int | None = None
    bucket = "general"
    in_evo = False
    s17_row: str | None = None
    prev_text: str | None = None
    sec_iter = iter(sections)
    nxt = next(sec_iter, None)

    for idx, line in enumerate(raw[body_start:], start=body_start + 1):
        prev_text = raw[idx - 2].strip() if idx >= 2 else None
        if nxt is not None and idx == nxt["linea"]:
            cur_sec = nxt["numero"]
            title = nxt["titulo"]
            bucket = "general"
            in_evo = False
            nxt = next(sec_iter, None)
            # Los encabezados de seccion NO son lineas del conteo (588 excluye
            # encabezados): se usan solo para saber en que seccion estamos.
            continue
        if cur_sec is None or not line.strip():
            continue

        texto = html.unescape(line).strip()

        # bloque EVO
        if EVO_START.match(texto):
            in_evo = True
        elif EVO_STOP.match(texto):
            in_evo = False

        # fuente declarada (reglas d y e del conteo)
        if ci.NO_MODE_SECTION_TITLE == sections[cur_sec - 1]["titulo"] or ci.is_note(texto):
            fuente = "general"
        else:
            nb = ci.bucket_of(texto)
            if nb:
                bucket = nb
            fuente = bucket

        # --- E0 tabla aplanada de la seccion 17: cada fila de datos es un
        # requisito del responsable, no una cabecera. Se resuelve por su celda
        # "Funcionalidad".
        if cur_sec == 17:
            if is_s17_header(texto):
                rows.append({
                    "seccion": 17, "linea": idx, "fuente_declarada": "general",
                    "texto": texto[:bc.TEXTO_MAX], "status": "Informative-Header",
                    "mapped_ids": "", "confidence": "alta",
                    "rationale": "cabecera o nota de la tabla aplanada de la seccion 17",
                })
                continue
            if not s17_row:
                s17_row = texto
                rows.append({
                    "seccion": 17, "linea": idx, "fuente_declarada": "general",
                    "texto": texto[:bc.TEXTO_MAX],
                    "status": s17_label_status(texto),
                    "mapped_ids": "", "confidence": "media",
                    "rationale": ("celda 'Funcionalidad' de la tabla: %s"
                                  % s17_label_reason(texto)),
                })
                continue
            # el resto de celdas de la fila (Sí / No / columnas de modo)
            if bc.norm(texto) == "no como motor propio":
                rows.append({
                    "seccion": 17, "linea": idx, "fuente_declarada": "general",
                    "texto": texto[:bc.TEXTO_MAX], "status": "Absent-At-Pin",
                    "mapped_ids": "", "confidence": "alta",
                    "rationale": ("fila '%s': Atlas declara TrustedInstaller, pero en el "
                                  "pin no hay motor propio reutilizable" % s17_row),
                })
                continue
            if bc.norm(texto) in ("si", "no") or texto in MODE_HEADERS:
                rows.append({
                    "seccion": 17, "linea": idx, "fuente_declarada": "general",
                    "texto": texto[:bc.TEXTO_MAX], "status": "Informative-Header",
                    "mapped_ids": "", "confidence": "alta",
                    "rationale": ("celda de columna (WinUtil/AtlasOS) de la fila "
                                  "'%s'; no es una operacion atomica" % s17_row),
                })
                continue
            s17_ids, s17_why = s17_match(s17_row, file_index)
            rows.append({
                "seccion": 17, "linea": idx, "fuente_declarada": "general",
                "texto": texto[:bc.TEXTO_MAX],
                "status": "Mapped" if s17_ids else "EVO-Exclusive",
                "mapped_ids": "|".join(s17_ids[:5]), "confidence": "media" if s17_ids else "baja",
                "rationale": (s17_why if s17_ids else
                              "fila de la tabla de la seccion 17 sin implementacion "
                              "en el pin: la asume EVO"),
            })
            continue

        # --- E0 correcciones medidas del paso 10 (lineas que el pin NO implementa)
        rejected = ABSENT_OVERRIDES.get((cur_sec, str(idx)))
        if rejected:
            rows.append({
                "seccion": cur_sec, "linea": idx, "fuente_declarada": fuente,
                "texto": texto[:bc.TEXTO_MAX], "status": "Absent-At-Pin",
                "mapped_ids": "", "confidence": "alta", "rationale": rejected,
            })
            continue

        # --- E0 correcciones medidas del paso 9 (antes de cualquier heuristica)
        forced = MAPPED_OVERRIDES.get((cur_sec, str(idx)))
        if forced:
            rows.append({
                "seccion": cur_sec, "linea": idx, "fuente_declarada": fuente,
                "texto": texto[:bc.TEXTO_MAX], "status": "Mapped",
                "mapped_ids": forced[0], "confidence": "alta",
                "rationale": forced[1],
            })
            continue

        # --- E1 informativos
        why = informative(cur_sec, texto, fuente)
        if why:
            rows.append({
                "seccion": cur_sec, "linea": idx, "fuente_declarada": fuente,
                "texto": texto[:bc.TEXTO_MAX], "status": "Informative-Header",
                "mapped_ids": "", "confidence": "alta", "rationale": why,
            })
            continue

        # --- E2 EVO
        if in_evo or fuente == "evo":
            rows.append({
                "seccion": cur_sec, "linea": idx, "fuente_declarada": fuente,
                "texto": texto[:bc.TEXTO_MAX], "status": "EVO-Exclusive",
                "mapped_ids": "", "confidence": "alta",
                "rationale": ("bloque 'EVO CLEAN' del inventario: requisito propio"
                              if in_evo else "linea marcada como capacidad EVO"),
            })
            continue

        # --- E2b servicios / claves que SI existen en el pin
        svc_hit = svc_ids.get(bc.norm(texto.rstrip(".")))
        if svc_hit:
            rows.append({
                "seccion": cur_sec, "linea": idx, "fuente_declarada": fuente,
                "texto": texto[:bc.TEXTO_MAX], "status": "Mapped",
                "mapped_ids": svc_hit, "confidence": "alta",
                "rationale": "nombre de servicio presente en las operaciones del ledger",
            })
            continue

        # --- E3 ausente en el pin
        why = absent_probe(texto, prb)
        if why:
            rows.append({
                "seccion": cur_sec, "linea": idx, "fuente_declarada": fuente,
                "texto": texto[:bc.TEXTO_MAX], "status": "Absent-At-Pin",
                "mapped_ids": "", "confidence": "media", "rationale": why,
            })
            continue

        # --- E4 apps de la seccion 15
        regla, cands, conf, _estado = bc.classify(texto, sources, targets, df)
        app_ids = [c for c in cands if c.startswith("winutil:catalog-entry:")]
        # La seccion 15 nombra aplicaciones por su nombre de producto; R1/R2 del
        # paso 4e no las encontraba porque la etiqueta del catalogo no coincide
        # con la redaccion del inventario. Se anade una regla explicita SOLO
        # para esta seccion: nombre de producto contenido en el texto.
        if cur_sec == 15 and not app_ids:
            app_ids = apps_in_text(texto, apps_index)
        if cur_sec == 15 and app_ids:
            rows.append({
                "seccion": cur_sec, "linea": idx, "fuente_declarada": fuente,
                "texto": texto[:bc.TEXTO_MAX], "status": "Mapped-To-App",
                "mapped_ids": "|".join(app_ids[:5]), "confidence": "alta",
                "rationale": f"entrada de applications.json ({regla})",
            })
            continue

        # --- E5 mapeado
        if cands and all(c in all_valid for c in cands):
            rows.append({
                "seccion": cur_sec, "linea": idx, "fuente_declarada": fuente,
                "texto": texto[:bc.TEXTO_MAX], "status": "Mapped",
                "mapped_ids": "|".join(cands[:5]), "confidence": conf,
                "rationale": f"regla {regla} del paso 4e: coincide con el ledger",
            })
            continue

        # --- E6 resto
        rows.append({
            "seccion": cur_sec, "linea": idx, "fuente_declarada": fuente,
            "texto": texto[:bc.TEXTO_MAX], "status": "Absent-At-Pin",
            "mapped_ids": "", "confidence": "baja",
            "rationale": ("sin candidato en los ledgers y no es requisito EVO: "
                          "no hay nada que mapear en el pin"),
        })

    rows.sort(key=lambda r: r["linea"])
    write_tsv(args.tsv, rows)
    meta = summarise(rows)
    write_report(args.report, rows, meta)
    summary = {**meta, "sha256": hashlib.sha256(args.tsv.read_bytes()).hexdigest()}

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    print(f"filas          : {meta['filas']} (esperado 588)")
    print(f"por estado     : {meta['por_estado']}")
    for sec, c in meta["por_seccion"].items():
        print(f"  sec {sec:>2}: " + " ".join(f"{k}={v}" for k, v in c.items()))
    print(f"sha256         : {summary['sha256']}")
    return 0


def summarise(rows: list[dict]) -> dict:
    por_estado = Counter(r["status"] for r in rows)
    por_seccion: dict[int, Counter] = defaultdict(Counter)
    for r in rows:
        por_seccion[r["seccion"]][r["status"]] += 1
    return {
        "filas": len(rows),
        "por_estado": {s: por_estado.get(s, 0) for s in STATUSES},
        "por_seccion": {int(k): dict(v) for k, v in sorted(por_seccion.items())},
        "por_confianza": dict(sorted(Counter(r["confidence"] for r in rows).items())),
        "sin_mapped_id": sum(1 for r in rows
                             if r["status"] in ("Mapped", "Mapped-To-App")
                             and not r["mapped_ids"]),
        "con_mapped_id": sum(1 for r in rows if r["mapped_ids"]),
    }


def write_tsv(path: Path, rows: list[dict]) -> None:
    lines = ["\t".join(COLUMNS)]
    for r in rows:
        cells = []
        for c in COLUMNS:
            v = str(r.get(c, ""))
            v = v.replace("\t", " ").replace("\r", " ").replace("\n", " ")
            cells.append(v[:400])
        lines.append("\t".join(cells))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def write_report(path: Path, rows: list[dict], meta: dict) -> None:
    titles = {s["numero"]: s["titulo"] for s in ci.parse(ci.DEFAULT_MD)[0]}
    out = [
        "# Conciliación del inventario del responsable",
        "",
        "Generado por `tools/ledger_extract/build_final_reconciliation.py`.",
        "Fuente: `docs/requirements/INVENTARIO_USUARIO.md` (solo lectura,",
        "sha256 `0b6aeaef…f709`). **No se modifica el inventario.**",
        "",
        f"Total: **{meta['filas']}** líneas no vacías.",
        "",
        "## Estados",
        "",
        "| estado | líneas | qué significa |",
        "|---|---:|---|",
        "| `Mapped` | {} | existe como tweak/toggle/servicio/clave en el pin, con id |".format(
            meta["por_estado"]["Mapped"]),
        "| `Mapped-To-App` | {} | entrada de `winutil-apps.tsv` (sección 15) |".format(
            meta["por_estado"]["Mapped-To-App"]),
        "| `EVO-Exclusive` | {} | requisito propio de EVO |".format(
            meta["por_estado"]["EVO-Exclusive"]),
        "| `Absent-At-Pin` | {} | nombrado en el inventario, no existe en el pin |".format(
            meta["por_estado"]["Absent-At-Pin"]),
        "| `Informative-Header` | {} | encabezado, nota o cabecera de tabla |".format(
            meta["por_estado"]["Informative-Header"]),
        "",
        "## Tabla 17 × 5",
        "",
        "| sección | título | Mapped | Mapped-To-App | EVO-Exclusive | Absent-At-Pin | Informative-Header | total |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    tot = Counter()
    for sec in sorted(meta["por_seccion"]):
        c = meta["por_seccion"][sec]
        vals = [c.get(s, 0) for s in STATUSES]
        tot.update({s: v for s, v in zip(STATUSES, vals)})
        out.append(f"| {sec} | {titles.get(sec, '')[:44]} | "
                   + " | ".join(str(v) for v in vals)
                   + f" | {sum(vals)} |")
    out.append("| **Σ** | | " + " | ".join(str(tot[s]) for s in STATUSES)
               + f" | **{sum(tot.values())}** |")
    out += [
        "",
        "## Reglas aplicadas",
        "",
        "1. `Informative-Header`: encabezados de sección, encabezados de modo",
        "   (`WinUtil`/`AtlasOS`), notas metodológicas y referencias",
        "   bibliográficas.",
        "2. `EVO-Exclusive`: todo el bloque que abre `EVO CLEAN` o",
        "   `Capacidad EVO a desarrollar:` y cierra con la nota «Estas últimas",
        "   capacidades…» o el siguiente encabezado de modo.",
        "3. `Absent-At-Pin`: la sonda de `seccion16-17-probe.tsv` da `atlas=0` o",
        "   patrón dudoso, o el texto cae en la lista de funcionalidades que en",
        "   el pin no existen como código ejecutable.",
        "4. `Mapped-To-App`: sección 15 y candidato `winutil:catalog-entry:*`.",
        "5. `Mapped`: regla R1/R2/R3 del paso 4e con candidato presente en los",
        "   ledgers; se añaden dos reglas propias: `apps_in_text()` (nombre de",
        "   producto de `winutil-apps.tsv`, ≥4 caracteres, con límites de",
        "   palabra) y `service_index()` (servicios de `winutil-tweak-ops.tsv`",
        "   cruzados con `value_name` de `atlas-tweak-ops.tsv`).",
        "6. `Absent-At-Pin` (resto): sin candidato y sin ser requisito EVO.",
        "7. Sección 17: la tabla está aplanada en el inventario (una celda por",
        "   línea). La primera celda de cada fila es la `Funcionalidad` y se",
        "   clasifica como requisito (`EVO-Exclusive`, o `Absent-At-Pin` para",
        "   las tres que ningún pin implementa: perfiles y presets, instalación",
        "   de ISO, creación de USB); las celdas `Sí`/`No` y las cabeceras",
        "   `Funcionalidad`/`WinUtil`/`AtlasOS` son `Informative-Header`;",
        "   `No como motor propio` es `Absent-At-Pin`.",
        "",
        "## Límites",
        "",
        "- `Absent-At-Pin` **no** afirma que la funcionalidad no exista en",
        "  Windows: solo que no hay código/parser en el pin medido.",
        "- `Mapped` usa la coincidencia de etiquetas del paso 4e; su precisión",
        "  está auditada en `docs/reports/paso4e.md`.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(out) + "\n").encode("utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
