#!/usr/bin/env python3
"""Categoría de upstream -> sección del inventario del usuario (paso 8c).

Problema que resuelve: en `upstream-capability-map.tsv` la mayoría de filas se
quedaban sin `section_guess` porque la regla de parecido de texto está prohibida
(R2 del paso 4e). Pero los datos estructurados **sí** traen categoría: WinUtil
declara `category`+`panel` en `tweaks.json`, `feature.json` y `appx.json`; Atlas
declara `group` en `Toggles/catalog.json` y organiza sus `.psd1` en directorios.

Este script no adivina ítem a ítem: propone **una sección por categoría**, con el
motivo escrito. Si una categoría mezcla secciones se marca `mixed` (el reparto
por ítem queda para el paso siguiente) y si no hay base se marca `unassigned`.
Ninguna fila se fuerza.

Categorías que se recorren (todas las distintas que existen en el pin):
    winutil-tweak    category de config/tweaks.json (4)
    winutil-feature  category de config/feature.json (5)
    winutil-appx     Category de config/appx.json (6)
    winutil-dns      config/dns.json (sin categoría: un solo grupo)
    winutil-preset   config/preset.json (sin categoría: un solo grupo)
    winutil-theme    config/themes.json (sin categoría: un solo grupo)
    atlas-toggle     group de atlas-toggles.tsv (8)
    atlas-manifest   directorio de los dos primeros niveles bajo Tweaks/ (+ raíz)

`items` es cuántas filas del universo de 435 usan esa categoría.
`reviewed` es siempre "no": la revisión es del responsable, no del agente.

Salida: inventory/partition/category-section-map.tsv
        source  category_key  items  section  basis  reviewed

Determinista: orden por (source, category_key), LF, UTF-8 sin BOM, celdas <= 400.

Uso:
    python3 tools/ledger_extract/build_category_section_map.py [--json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "inventory" / "ledger"
OUT = ROOT / "inventory" / "partition" / "category-section-map.tsv"
UPSTREAM = Path("/tmp/upstream")
WINUTIL_CONFIG = UPSTREAM / "winutil" / "config"

COLUMNS = ("source", "category_key", "items", "section", "basis", "reviewed")
MAX_CELL = 400
REVIEWED = "no"

# Titulos literales de docs/requirements/INVENTARIO_USUARIO.md (no se editan).
SECTION_TITLES = {
    1: "LIMPIEZA Y ELIMINACION DE COMPONENTES",
    2: "DEBLOAT DE WINDOWS",
    3: "TELEMETRIA Y PRIVACIDAD",
    4: "OPTIMIZACION DE SERVICIOS",
    5: "OPTIMIZACION DE CPU Y RENDIMIENTO",
    6: "OPTIMIZACION GAMING",
    7: "MEMORIA Y APLICACIONES EN SEGUNDO PLANO",
    8: "ADMINISTRACION DE INICIO Y APAGADO",
    9: "REGISTRO DE WINDOWS Y CONFIGURACION DEL SISTEMA",
    10: "EXPLORADOR DE ARCHIVOS E INTERFAZ",
    11: "RED Y CONECTIVIDAD",
    12: "WINDOWS UPDATE Y MANTENIMIENTO",
    13: "SEGURIDAD Y PROTECCION",
    14: "REPARACION Y DIAGNOSTICO",
    15: "ADMINISTRACION DE APLICACIONES",
    16: "FUNCIONES DE INSTALACION Y ADMINISTRACION AVANZADA",
    17: "CAPACIDADES ADICIONALES QUE NO DEBEMOS PERDER",
}

# (source, category_key) -> (section, basis)
# section: "1".."17" | "mixed" | "unassigned"
PROPOSALS: dict[tuple[str, str], tuple[str, str]] = {
    # --- WinUtil tweaks.json -------------------------------------------------
    ("winutil-tweak", "Customize Preferences"): (
        "mixed",
        "Categoria 'Customize Preferences' (panel 2, 25 items): la conciliacion la "
        "reparte entre 9 REGISTRO Y CONFIGURACION DEL SISTEMA (17 lineas Mapped), "
        "10 EXPLORADOR E INTERFAZ (11) y 2/5/6/8 (4). Mezcla real: el reparto por "
        "item va en el paso siguiente."),
    ("winutil-tweak", "Essential Tweaks"): (
        "mixed",
        "Categoria 'Essential Tweaks' (panel 1, 18 items): medida en 2 DEBLOAT (5), "
        "10 EXPLORADOR (3) y 13/5/6/7/9 (una cada una). WinUtil agrupa por "
        "'esencial' (lo que el autor recomienda), no por area del sistema."),
    ("winutil-tweak", "Performance Plans - NOT FOR LAPTOPS"): (
        "5",
        "Categoria 'Performance Plans' + seccion 5 OPTIMIZACION DE CPU Y RENDIMIENTO: "
        "son los planes de energia Ultimate/High Performance. Sin lineas Mapped en "
        "la conciliacion (0 medidas), asi que la seccion es propuesta, no medida."),
    ("winutil-tweak", "z__Advanced Tweaks - CAUTION"): (
        "mixed",
        "Categoria 'z__Advanced Tweaks - CAUTION' (panel 1, 24 items): medida en 2 "
        "DEBLOAT (6), 7 MEMORIA/SEGUNDO PLANO (4), 11 RED (2), 13 SEGURIDAD (2) y "
        "10/3/9 (una cada una). Mezcla real; el prefijo z__ es solo orden de UI."),
    # --- WinUtil feature.json ------------------------------------------------
    ("winutil-feature", "Features"): (
        "mixed",
        "Categoria 'Features' (10 items: Hyper-V, WSL, NFS, Sandbox, .NET...): cada "
        "caracteristica de Windows cae en un area distinta; medida en 12 y 13. El "
        "reparto por item va en el paso siguiente."),
    ("winutil-feature", "Fixes"): (
        "mixed",
        "Categoria 'Fixes' (6 items: NTP, AutoLogon, Update Reset, Network Reset, "
        "DISM, WinGet): medida en 14 REPARACION (4), 11 RED (1) y 12 UPDATE (1). "
        "Son reparaciones de areas distintas."),
    ("winutil-feature", "Legacy Windows Panels"): (
        "mixed",
        "Categoria 'Legacy Windows Panels' (14 accesos directos a paneles antiguos): "
        "medida en 13; pero incluye Firewall (13), Conexiones de red (11), "
        "Administracion de equipos (9) y Panel de control (10). Mezcla real."),
    ("winutil-feature", "Powershell Profile Powershell 7+ Only"): (
        "16",
        "Categoria 'Powershell Profile' + seccion 16 FUNCIONES DE INSTALACION Y "
        "ADMINISTRACION AVANZADA: instala/desinstala un perfil de PowerShell del "
        "propio WinUtil. Sin lineas Mapped: propuesta."),
    ("winutil-feature", "Remote Access"): (
        "11",
        "Categoria 'Remote Access' (OpenSSH Server) + seccion 11 RED Y "
        "CONECTIVIDAD: medida en 11 (1 linea Mapped)."),
    # --- WinUtil appx.json ---------------------------------------------------
    ("winutil-appx", "Bing & Web Services"): (
        "15",
        "appx.json = desinstalacion de paquetes provisionados -> seccion 15 "
        "ADMINISTRACION DE APLICACIONES. La subcategoria ('Bing & Web Services') "
        "describe el proveedor, no el area del sistema."),
    ("winutil-appx", "Developer Tools"): (
        "15", "appx.json -> 15 ADMINISTRACION DE APLICACIONES (paquete AppX)."),
    ("winutil-appx", "Microsoft Apps"): (
        "15", "appx.json -> 15 ADMINISTRACION DE APLICACIONES (paquete AppX)."),
    ("winutil-appx", "Microsoft Ecosystem"): (
        "15", "appx.json -> 15 ADMINISTRACION DE APLICACIONES (paquete AppX)."),
    ("winutil-appx", "Utilities & Productivity"): (
        "15", "appx.json -> 15 ADMINISTRACION DE APLICACIONES (paquete AppX)."),
    ("winutil-appx", "Xbox & Gaming"): (
        "15",
        "appx.json -> 15 ADMINISTRACION DE APLICACIONES. Se elige 15 y no 6 "
        "GAMING porque el item es un paquete AppX desinstalable, no un ajuste de "
        "juego."),
    # --- WinUtil sin campo de categoria -------------------------------------
    ("winutil-dns", "config/dns.json"): (
        "11",
        "dns.json son proveedores DNS (8) -> 11 RED Y CONECTIVIDAD. El fichero no "
        "tiene campo de categoria; el grupo es el fichero entero."),
    ("winutil-preset", "config/preset.json"): (
        "mixed",
        "preset.json (4 presets: Standard, Minimal, Advanced, AppxDefault) son "
        "listas de claves de varias secciones (tweaks + appx). La seccion la "
        "heredarian los items que agrupan, no el preset."),
    ("winutil-theme", "config/themes.json"): (
        "10", "themes.json (Light/Dark) -> 10 EXPLORADOR E INTERFAZ."),
    # --- Atlas toggles (campo group) ----------------------------------------
    ("atlas-toggle", "Advanced"): (
        "mixed",
        "Grupo 'Advanced' (3 toggles: MicrosoftStore, ProcessExplorer, "
        "ToggleWindowsUpdates) toca 15, 14 y 12: mezcla real."),
    ("atlas-toggle", "Boot"): (
        "8",
        "Grupo 'Boot' (8 toggles: AdvancedBootOptions, BootLogo, NewBootMenu, "
        "SpinningAnimations...) -> 8 ADMINISTRACION DE INICIO Y APAGADO."),
    ("atlas-toggle", "General"): (
        "mixed",
        "Grupo 'General' (29 toggles: AutomaticUpdates, BackgroundApps, Copilot, "
        "DeliveryOptimisation, Hibernation...): medido en 9 (2) y 2 (1); cubre "
        "debloat, memoria, update y sistema. Mezcla real."),
    ("atlas-toggle", "Interface"): (
        "10",
        "Grupo 'Interface' (26 toggles: Animation, CompactView, Gallery, Home, "
        "LockScreen, Taskbar...) -> 10 EXPLORADOR E INTERFAZ; las 3 lineas Mapped "
        "medidas caen en 10."),
    ("atlas-toggle", "Security"): (
        "13",
        "Grupo 'Security' (7 toggles: ConfigVBS, Mitigations, ToggleDefender...) "
        "-> 13 SEGURIDAD Y PROTECCION; medido 1 linea en 13."),
    ("atlas-toggle", "Services"): (
        "4",
        "Grupo 'Services' (7 toggles: Bluetooth, LanmanWorkstation, Printing, "
        "SuperFetch...) -> 4 OPTIMIZACION DE SERVICIOS; medido 1 linea en 4."),
    ("atlas-toggle", "Software"): (
        "15",
        "Grupo 'Software' (InstallSoftware, RemoveEdge, RemovePythonStorePrompt) "
        "-> 15 ADMINISTRACION DE APLICACIONES."),
    ("atlas-toggle", "Troubleshooting"): (
        "14",
        "Grupo 'Troubleshooting' (AtlasHealth, FixErrors2502and2503, "
        "RepairWindowsComponents, SafeMode...) -> 14 REPARACION Y DIAGNOSTICO."),
    # --- Atlas manifest (directorio del .psd1) ------------------------------
    ("atlas-manifest", "debloat/(raiz)"): (
        "2",
        "Tweaks/debloat/*.psd1 (5 ficheros: content-delivery, storage-sense, "
        "reserved-storage, scheduled-tasks, unused-security-pages) -> 2 DEBLOAT."),
    ("atlas-manifest", "misc/(raiz)"): (
        "mixed",
        "Tweaks/misc/*.psd1 (8 ficheros: create-shortcuts, config-time, "
        "rebuild-perf-counters, register-user-upgrade...): sin area comun. Mezcla real."),
    ("atlas-manifest", "networking/(raiz)"): (
        "11", "Tweaks/networking/*.psd1 sueltos -> 11 RED Y CONECTIVIDAD."),
    ("atlas-manifest", "networking/shares"): (
        "11", "Tweaks/networking/shares (3) -> 11 RED Y CONECTIVIDAD (recursos compartidos)."),
    ("atlas-manifest", "performance/(raiz)"): (
        "5", "Tweaks/performance/*.psd1 sueltos (7) -> 5 OPTIMIZACION DE CPU Y RENDIMIENTO."),
    ("atlas-manifest", "performance/system"): (
        "5", "Tweaks/performance/system (3) -> 5 OPTIMIZACION DE CPU Y RENDIMIENTO."),
    ("atlas-manifest", "privacy/(raiz)"): (
        "3",
        "Tweaks/privacy/*.psd1 sueltos: disable-activity-feed, disallow-user-activity-upload, "
        "search-settings, disallow-ms-accounts... -> 3 TELEMETRIA Y PRIVACIDAD."),
    ("atlas-manifest", "privacy/advertising"): (
        "3", "Tweaks/privacy/advertising (2) -> 3 TELEMETRIA Y PRIVACIDAD."),
    ("atlas-manifest", "privacy/apps"): (
        "3", "Tweaks/privacy/apps (4) -> 3 TELEMETRIA Y PRIVACIDAD (historial de apps)."),
    ("atlas-manifest", "privacy/cloud"): (
        "3", "Tweaks/privacy/cloud (4) -> 3 TELEMETRIA Y PRIVACIDAD."),
    ("atlas-manifest", "privacy/telemetry"): (
        "3", "Tweaks/privacy/telemetry (7) -> 3 TELEMETRIA Y PRIVACIDAD."),
    ("atlas-manifest", "qol/(raiz)"): (
        "mixed",
        "Tweaks/qol/*.psd1 sueltos (25 ficheros: config-start-menu, bcdedit-tweaks, "
        "disable-store-auto-updates, disable-tips, visual-effects...): interfaz, "
        "arranque y update mezclados. Mezcla real."),
    ("atlas-manifest", "qol/appearance"): (
        "10", "Tweaks/qol/appearance (3) -> 10 EXPLORADOR E INTERFAZ."),
    ("atlas-manifest", "qol/ease-of-access"): (
        "10", "Tweaks/qol/ease-of-access (4) -> 10 EXPLORADOR E INTERFAZ (accesibilidad)."),
    ("atlas-manifest", "qol/explorer"): (
        "10", "Tweaks/qol/explorer (36) -> 10 EXPLORADOR DE ARCHIVOS E INTERFAZ."),
    ("atlas-manifest", "qol/shell"): (
        "10", "Tweaks/qol/shell (11) -> 10 EXPLORADOR E INTERFAZ (shell de Windows)."),
    ("atlas-manifest", "qol/startup-shutdown"): (
        "8", "Tweaks/qol/startup-shutdown (4) -> 8 ADMINISTRACION DE INICIO Y APAGADO."),
    ("atlas-manifest", "qol/system"): (
        "9", "Tweaks/qol/system (2) -> 9 REGISTRO Y CONFIGURACION DEL SISTEMA."),
    ("atlas-manifest", "qol/taskbar"): (
        "10", "Tweaks/qol/taskbar (7) -> 10 EXPLORADOR E INTERFAZ (barra de tareas)."),
    ("atlas-manifest", "qol/windows-update"): (
        "12", "Tweaks/qol/windows-update (8) -> 12 WINDOWS UPDATE Y MANTENIMIENTO."),
    ("atlas-manifest", "scripts/(raiz)"): (
        "mixed",
        "Tweaks/scripts/*.psd1 (8: disable-core-isolation, disable-mitigations, "
        "disable-pnp, set-file-associations, set-power-settings...): seguridad, "
        "reparacion y rendimiento mezclados. Mezcla real."),
    ("atlas-manifest", "qol/security"): (
        "13",
        "Tweaks/qol/security/disable-uac-secure-desktop.psd1: PromptOnSecureDesktop=0, es "
        "decir DESACTIVA la proteccion de UAC -> 13 SEGURIDAD Y PROTECCION. El directorio "
        "cuelga de qol/ (calidad de vida) pero el objeto es seguridad; se sigue el efecto, "
        "no el arbol."),
    ("atlas-manifest", "security/(raiz)"): (
        "13",
        "Tweaks/security/*.psd1 (3: block-anonymous-enum-sam, "
        "disable-automatic-restart-signon, disable-remote-assistance) -> 13 SEGURIDAD."),
}


def load_pin_json(name: str):
    path = WINUTIL_CONFIG / name
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"), strict=False)


def manifest_key(psd1_path: str) -> str:
    """'.../Tweaks/qol/explorer/x.psd1' -> 'qol/explorer'; '.../Tweaks/misc/y.psd1' -> 'misc/(raiz)'."""
    marker = "/Tweaks/"
    rest = psd1_path.split(marker, 1)[-1] if marker in psd1_path else psd1_path
    parts = [p for p in rest.split("/") if p]
    if len(parts) < 2 or parts[1].endswith(".psd1"):
        return f"{parts[0]}/(raiz)"
    return f"{parts[0]}/{parts[1]}"


def item_categories() -> list[tuple[str, str, str]]:
    """(upstream_id, source_group, category_key) para el universo de 435 filas."""
    out: list[tuple[str, str, str]] = []

    tweaks = load_pin_json("tweaks.json") or {}
    features = load_pin_json("feature.json") or {}
    appx = load_pin_json("appx.json") or {}

    with (LEDGER / "winutil-items.tsv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            item, kind = row["item_id"], row["kind"]
            attrs = json.loads(row.get("attrs_json") or "{}")
            if kind == "tweak":
                key = attrs.get("category") or (tweaks.get(item.split(":", 2)[-1], {}) or {}).get("category")
                out.append((item, "winutil-tweak", key or "unassigned"))
            elif kind == "feature":
                key = (features.get(item.split(":", 2)[-1], {}) or {}).get("category")
                out.append((item, "winutil-feature", key or "unassigned"))
            elif kind == "appx":
                key = attrs.get("category") or (appx.get(item.split(":", 2)[-1], {}) or {}).get("Category")
                out.append((item, "winutil-appx", key or "unassigned"))
            elif kind == "dns-provider":
                out.append((item, "winutil-dns", "config/dns.json"))
            elif kind == "preset":
                out.append((item, "winutil-preset", "config/preset.json"))
            elif kind == "theme":
                out.append((item, "winutil-theme", "config/themes.json"))
            # nav-entry: sin categoria; no entra en este mapa (not-a-capability).

    with (LEDGER / "atlas-toggles.tsv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            out.append((row["item_id"], "atlas-toggle", row.get("category") or "unassigned"))

    with (LEDGER / "atlas-manifest.tsv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            out.append((row["item_id"], "atlas-manifest", manifest_key(row["psd1_path"])))
    return out


def build() -> list[dict]:
    counts: Counter = Counter()
    for _item, group, key in item_categories():
        counts[(group, key)] += 1

    rows: list[dict] = []
    for (group, key), items in sorted(counts.items()):
        section, basis = PROPOSALS.get(
            (group, key),
            ("unassigned", "Sin propuesta: el agente no tiene base medida para esta categoria."))
        rows.append({
            "source": group,
            "category_key": key,
            "items": items,
            "section": section,
            "basis": f"{basis} (seccion {section}: {SECTION_TITLES[int(section)]})"
                     if section.isdigit() else basis,
            "reviewed": REVIEWED,
        })
    return rows


def index() -> dict[str, tuple[str, str]]:
    """upstream_id -> (section, category_key)."""
    return {item: (PROPOSALS.get((group, key), ("unassigned", ""))[0], key)
            for item, group, key in item_categories()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not WINUTIL_CONFIG.is_dir():
        print(f"AVISO: no hay pin en {WINUTIL_CONFIG}; las categorias de "
              "feature.json no se pueden medir", file=sys.stderr)

    rows = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (str(v)[:MAX_CELL] if k == "basis" else v)
                             for k, v in row.items()})

    by_section = Counter(r["section"] for r in rows)
    summary = {
        "categorias": len(rows),
        "items": sum(r["items"] for r in rows),
        "por_section": dict(sorted(by_section.items())),
        "asignadas": sum(r["items"] for r in rows if r["section"].isdigit()),
        "mixed": sum(r["items"] for r in rows if r["section"] == "mixed"),
        "unassigned": sum(r["items"] for r in rows if r["section"] == "unassigned"),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(f"categorias mapeadas : {summary['categorias']}")
    print(f"items cubiertos     : {summary['items']}")
    print(f"  con seccion       : {summary['asignadas']}")
    print(f"  mixed             : {summary['mixed']}")
    print(f"  unassigned        : {summary['unassigned']}")
    for section, count in sorted(summary["por_section"].items(),
                                 key=lambda kv: (not kv[0].isdigit(), kv[0])):
        print(f"  seccion {section:11s} {count} categorias")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
