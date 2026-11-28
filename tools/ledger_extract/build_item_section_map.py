#!/usr/bin/env python3
"""Sección (1-17) de cada ítem upstream, con la regla y la evidencia (paso 8d).

Entrada:
    inventory/ledger/upstream-capability-map.tsv        (435 filas, universo)
    inventory/partition/category-section-map.tsv        (categoría -> sección)
    inventory/ledger/atlas-tweak-ops.tsv                (claves de los .psd1)
    inventory/ledger/atlas-toggle-keys.tsv              (claves de los toggles)
    inventory/ledger/winutil-tweak-ops.tsv              (claves de los tweaks)
    inventory/ledger/winutil-feature-ops.tsv            (features y sus servicios)
    inventory/ledger/winutil-appx-ops.tsv               (paquetes AppX)

Salida:
    inventory/partition/item-section-map.tsv
        upstream_id  source  label  category_key  section  basis  evidence  reviewed

`section` ∈ 1..17 | "unassigned".
`basis`   ∈ category | manifest-path | effect | name-rule | manual-review.
`reviewed` = "no" siempre: la revisión es del responsable.

Las reglas están documentadas con ejemplo real en
`docs/inventory-recon/seccion-por-item-reglas.md`; este script solo las aplica
en el orden que allí se describe (categoría -> ruta -> efecto -> nombre).
Ninguna regla compara textos por parecido: son listas cerradas de términos y
claves.

Determinista: orden por (source, upstream_id), LF, UTF-8 sin BOM, celdas <= 400.

Uso:
    python3 tools/ledger_extract/build_item_section_map.py [--json]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_category_section_map as csm  # noqa: E402

LEDGER = ROOT / "inventory" / "ledger"
PART = ROOT / "inventory" / "partition"
OUT = PART / "item-section-map.tsv"

COLUMNS = ("upstream_id", "source", "label", "category_key", "section",
           "basis", "evidence", "reviewed")
MAX_CELL = 400
REVIEWED = "no"
BASIS = ("category", "manifest-path", "effect", "name-rule", "manual-review")

# --- Reglas de EFECTO -------------------------------------------------------
# (clave, sección, patrón sobre la clave/valor normalizado, evidencia legible)
EFFECT_RULES: list[tuple[str, str, re.Pattern[str], str]] = [
    ("svc:diagtrack", "3", re.compile(r"^svc:(?:diagtrack|wersvc)$"), "svc:diagtrack"),
    ("svc:wsearch", "9", re.compile(r"^svc:wsearch$"), "svc:wsearch"),
    ("svc:lfsvc", "3", re.compile(r"^svc:lfsvc$"), "svc:lfsvc"),
    ("key:WindowsUpdate", "12",
     re.compile(r"(windowsupdate|updatepolicy|windows\\update)", re.IGNORECASE),
     "key:WindowsUpdate"),
    ("key:WindowsAI", "2", re.compile(r"windowsai|\\aia\\", re.IGNORECASE), "key:WindowsAI"),
    ("key:CloudContent", "3",
     re.compile(r"cloudcontent|contentdeliverymanager", re.IGNORECASE), "key:CloudContent"),
    ("key:Search", "10",
     re.compile(r"currentversion\\search\\|\\windows search", re.IGNORECASE),
     "key:Search"),
    ("key:Explorer\\Advanced", "10",
     re.compile(r"explorer\\advanced", re.IGNORECASE), "key:Explorer\\Advanced"),
    ("key:Explorer", "10",
     re.compile(r"currentversion\\(policies\\)?explorer", re.IGNORECASE), "key:Explorer"),
    ("key:DeliveryOptimization", "12",
     re.compile(r"deliveryoptimization", re.IGNORECASE), "key:DeliveryOptimization"),
    ("key:Control Panel", "10", re.compile(r"control panel", re.IGNORECASE),
     "key:Control Panel"),
    ("key:Policies\\Personalization", "10",
     re.compile(r"personalization", re.IGNORECASE),
     "key:Policies\\Microsoft\\Windows\\Personalization"),
    ("key:SystemRestore", "14", re.compile(r"systemrestore", re.IGNORECASE),
     "key:SystemRestore"),
    ("key:Memory Management", "5", re.compile(r"memory management", re.IGNORECASE),
     "key:Session Manager\\Memory"),
    ("key:Defender", "13",
     re.compile(r"windows defender|\\defender", re.IGNORECASE), "key:Defender"),
    ("key:Session Manager\\Power", "5",
     re.compile(r"session manager\\power|platformaoacoverride", re.IGNORECASE),
     "key:Power"),
    ("key:Control\\Power", "5", re.compile(r"^power\\|control\\power", re.IGNORECASE),
     "key:Power"),
    ("key:GraphicsDrivers", "10", re.compile(r"graphicsdrivers|\\dwm", re.IGNORECASE),
     "key:GraphicsDrivers"),
    ("key:Keyboard Layout", "10", re.compile(r"keyboard layout", re.IGNORECASE),
     "key:Control Panel"),
    ("feat:net", "11",
     re.compile(r"^feat:.*(servicesfornfs|clientfornfs|nfs-)"), "feat:net"),
    ("feat:virt", "16",
     re.compile(r"^feat:.*(hyper-v|virtualmachineplatform|subsystem-linux|"
                r"disposableclientvm|sandbox|netfx|\.net)"), "feat:virt"),
    ("feat:media", "15",
     re.compile(r"^feat:.*(windowsmediaplayer|mediaplayback|directplay|legacycomponents)"),
     "feat:media"),
    ("appx:*", "15", re.compile(r"^appx:"), "appx:*"),
    ("svc:set", "4", re.compile(r"^svc:.+"), "svc:set"),
]

# --- Reglas de NOMBRE -------------------------------------------------------
# Términos propios por área. El orden importa: el primero que casa gana.
NAME_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    # 13 — seguridad: sólo términos que en el pin designan protección real.
    ("name:security", "13",
     ("mitigation", "core-isolation", "bitlocker", "firewall", "uac", "defender",
      "wpbt", "secure-boot")),
    # 3 — telemetría y privacidad.
    ("name:telemetry", "3",
     ("telemetry", "feedback", "activity", "location", "advertising", "consumer",
      "spotlight", "privacy", "diagnostic")),
    # 2 — debloat de terceros: el catálogo ya mete estas en la sección 2
    # (debloat.network.adobe-blocklist, debloat.drivers.razer/logitech).
    ("name:debloat-apps", "2", ("adobe", "razer", "logitech", "brave", "edge-debloat")),
    # 12 — Windows Update y mantenimiento.
    ("name:update", "12",
     ("windows-update", "windows updates", "update reset", "pause update",
      "delivery optimization", "delivery optimisation", "cbs", "dism",
      "update drivers", "driver updates")),
    # 8 — arranque y apagado.
    ("name:boot", "8", ("boot", "bcdedit", "autologon", "legacy-recovery")),
    # 11 — red.
    ("name:network", "11",
     ("network", "dns", "file sharing", "sharing", "wifi", "teredo", "ipv6", "ntp",
      "rdp", "netbios", "smb", "device metadata")),
    # 6 — gaming.
    ("name:gaming", "6", ("game", "gaming", "xbox", "fsogamebar")),
    # 7 — memoria y segundo plano.
    ("name:memory", "7", ("background app", "background", "hiber", "sleep", "memory",
                          "svchost")),
    # 5 — CPU y rendimiento (energía incluida).
    ("name:power", "5", ("power", "cpu idle", "timer resolution", "performance plan",
                         "sleep study")),
    # 14 — reparación y diagnóstico.
    ("name:repair", "14",
     ("repair", "reset", "corruption", "perf-counter", "perfcounters",
      "restore point",
      "system restore", "verbose", "bsod", "safe mode", "error")),
    # 1 — limpieza.
    ("name:cleanup", "1", ("temp", "temporary", "cleanup", "recycle",
                           "reserved storage", "storage sense")),
    # 4 — servicios.
    ("name:service", "4", ("service",)),
    # 16 — instalación y administración avanzada.
    ("name:admin", "16", ("winget", "powershell profile", "shutup")),
    # 2 — debloat/IA: quitar funciones del sistema (Recall, Copilot).
    ("name:ai", "2", ("windows ai", "copilot", "recall", "click to do")),
    # 15 — administración de aplicaciones.
    ("name:apps", "15",
     ("appx", "store", "onedrive", "office", "outlook", "phone link",
      "process explorer", "app archival", "edge")),
    # 10 — Explorador e interfaz.
    ("name:explorer", "10",
     ("explorer", "start menu", "start-menu", "taskbar", "wallpaper",
      "visual effects", "mouse", "touch", "sound", "dark", "scrollbar", "shortcut",
      "context menu", "right-click", "lock screen", "lock-screen", "animation",
      "bing", "settings home", "logon", "widget", "recommendations",
      "hidden files", "file extensions", "file associations", "dynamic lighting",
      "spell", "usb", "settings banner", "start folder", "hidden settings",
      "num lock", "sticky keys", "window snapping", "task view", "game mode",
      "long path", "storage sense", "sounds", "battery percentage", "widgets",
      "notifications")),
    # 9 — registro y configuración del sistema.
    ("name:system", "9",
     ("registry backup", "indexing", "time", "keyboard switching", "oem",
      "work or school", "workplace")),
]

MANIFEST_DIR_RULE = re.compile(
    r"/Tweaks/(?P<area>qol|privacy|performance|networking|security|debloat|scripts|misc)/")


def load_rows() -> list[dict]:
    with (LEDGER / "upstream-capability-map.tsv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_tsv(name: str) -> list[dict]:
    path = LEDGER / name
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def effect_signals() -> dict[str, list[str]]:
    """upstream_id -> lista de señales de efecto (claves ya en minúsculas)."""
    signals: dict[str, list[str]] = defaultdict(list)

    for row in load_tsv("winutil-tweak-ops.tsv"):
        item = f"winutil:tweak:{row['tweak_id']}"
        if row.get("kind") == "service" and row.get("name"):
            signals[item].append(f"svc:{row['name'].lower()}")
        elif row.get("target"):
            signals[item].append(f"key:{row['target']}\\{row['name']}".lower())
        elif row.get("effect_types"):
            for effect in row["effect_types"].split("|"):
                if effect == "appx":
                    signals[item].append("appx:efecto-declarado")
                else:
                    signals[item].append(f"effect:{effect}")

    for row in load_tsv("winutil-feature-ops.tsv"):
        item = f"winutil:feature:{row['tweak_id']}"
        if row.get("kind") == "feature" and row.get("name"):
            signals[item].append(f"feat:{row['name']}".lower())
        elif row.get("kind") == "service" and row.get("name"):
            signals[item].append(f"svc:{row['name'].lower()}")

    for row in load_tsv("winutil-appx-ops.tsv"):
        signals[f"winutil:appx:{row['tweak_id']}"].append(
            f"appx:{row.get('name', '')}".lower())

    manifest_path_by_item = {
        row["item_id"]: row["psd1_path"] for row in load_tsv("atlas-manifest.tsv")}
    for row in load_tsv("atlas-tweak-ops.tsv"):
        item = next((i for i, p in manifest_path_by_item.items() if p == row["path"]), None)
        if item is None:
            continue
        signals[item].append(
            f"key:{row['hive']}\\{row['key']}\\{row['value_name']}".lower())

    for row in load_tsv("atlas-toggle-keys.tsv"):
        signals[f"atlas:toggle:{row['toggle_id']}"].append(
            f"key:{row['hive']}\\{row['key']}\\{row['value_name']}".lower())

    return {item: sorted(set(values)) for item, values in signals.items()}


def effect_candidates(signals: list[str]) -> tuple[set[str], str]:
    """Secciones que proponen los efectos del ítem, con la evidencia de la primera.

    Si los efectos apuntan a MÁS de una sección, el efecto no decide: se devuelve
    el conjunto y el llamante pasa a la regla de nombre. Así un ítem que toca
    `Explorer` y además desinstala un paquete AppX no se queda con la sección de
    la primera clave que aparezca.
    """
    services = {s for s in signals if s.startswith("svc:")}
    if len(services) >= 3:
        return {"4"}, "svc:set-multiple"

    # Tipo de efecto declarado en el propio ledger de WinUtil (`effect_types`).
    # Sólo se usa cuando el efecto es de una sola área.
    declared = sorted({s.split(":", 1)[1] for s in signals if s.startswith("effect:")})
    if len(declared) == 1:
        mapping = {"power": "5", "boot": "8", "network": "11", "dism": "1",
                   "file": "1"}
        section = mapping.get(declared[0])
        if section:
            return {section}, f"effect:{declared[0]}"

    found: dict[str, str] = {}
    for _key, section, pattern, evidence in EFFECT_RULES:
        for signal in signals:
            if pattern.search(signal):
                found.setdefault(section, evidence)
                break
    return set(found), (next(iter(found.values())) if found else "")


CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def tokenize(label: str) -> list[str]:
    """'BitLocker' -> ['bit', 'locker']; 'Right-Click Menu' -> ['right','click','menu'].

    El nombre del ítem se parte por sus palabras reales (camelCase y
    separadores). No es parecido textual: es el propio nombre del ítem.
    """
    spaced = CAMEL_RE.sub(" ", label)
    spaced = re.sub(r"[-_./&+()]+", " ", spaced)
    return [token for token in spaced.lower().split() if token]


def matches(tokens: list[str], term: str) -> bool:
    """True si una secuencia de tokens contiguos concatena el término.

    Así 'BitLocker' (tokens bit+locker) casa con el término 'bitlocker', y
    'Windows Restore' NO casa con 'store' porque la concatenación de tokens
    contiguos es 'windowsrestore', no 'store'.
    """
    needle = "".join(tokenize(term))
    if not needle:
        return False
    for start in range(len(tokens)):
        joined = ""
        for end in range(start, len(tokens)):
            joined += tokens[end]
            # Se admite el plural inglés del término ('perf-counters').
            if joined in (needle, f"{needle}s"):
                return True
            if not needle.startswith(joined) and not f"{needle}s".startswith(joined):
                break
    return False


def apply_name(label: str) -> tuple[str, str] | None:
    tokens = tokenize(label)
    for key, section, terms in NAME_RULES:
        for term in terms:
            if matches(tokens, term):
                return section, key
    return None


def apply_manifest_path(path: str | None) -> tuple[str, str] | None:
    if not path:
        return None
    match = MANIFEST_DIR_RULE.search(path)
    if not match:
        return None
    area = match.group("area")
    mapping = {
        "debloat": "2", "privacy": "3", "security": "13", "networking": "11",
        "performance": "5",
    }
    if area in mapping:
        return mapping[area], f"path:{area}"
    return None


# Motivo escrito de los `unassigned` que no son "no hay dato": el ítem existe
# pero no tiene efecto propio (abre una ventana, agrupa claves o instala un
# perfil). Se declara aquí para que el informe no tenga que suponerlo.
NO_EFFECT_REASON = {
    "winutil:nav-entry": "entrada de navegacion de la UI de WinUtil: no tiene efecto propio",
    "winutil:preset": "preset = lista de claves de varias secciones; heredaria 2, 3, 9 y 15 a la vez",
    "winutil:feature:WPFPanel": "abre un panel de Windows; no muta nada, no hay efecto que ubicar",
    "winutil:feature:WPFFeatureInstall": "boton que instala las caracteristicas marcadas: su seccion depende de cuales",
    "winutil:tweak:WPFOOSUbutton": "lanza una herramienta de terceros: el efecto lo hace ella, no este item",
    "atlas:manifest:scripts/backup-services": "copia el estado de los servicios antes de tocarlos; el efecto es de quien los cambia",
    "atlas:manifest:scripts/disable-pnp": "script sin operacion estructurada medida en el pin (0 filas en atlas-tweak-ops)",
    "atlas:manifest:scripts/set-profile-pictures": "script sin operacion estructurada medida; toca perfiles de usuario, area no declarada",
    "atlas:manifest:misc/create-shortcuts": "crea accesos directos, no cambia configuracion: fuera de las 17 areas",
    "atlas:manifest:misc/delete-windows-specific-files": "borra ficheros concretos de Windows; el alcance no esta medido en el pin",
    "atlas:manifest:misc/make-measuresleep-admin": "cambia permisos de un ejecutable, no configuracion de las 17 areas",
    "atlas:manifest:misc/rebuild-perf-counters": "reconstruye contadores de rendimiento; reparacion sin area fija en el inventario",
    "atlas:manifest:misc/register-user-upgrade": "registra una entrada de arranque propia de Atlas: no es una de las 17 areas",
    "atlas:toggle:GiveAccessToMenu": "oculta una entrada del menu contextual: el dato del pin no declara clave",
    "winutil:tweak:WPFToggleLongPaths": "alarga la ruta maxima de Win32: no encaja en ninguna de las 17 areas declaradas",
    "winutil:tweak:WPFTweaksPreventDeviceMetadataFromNetwork": "bloquea metadatos de dispositivos: a caballo entre red (11) y debloat (2), sin evidencia para elegir",
    "atlas:manifest:scripts/disable-mitigations": "desactiva mitigaciones de CPU: seguridad (13) y rendimiento (5) a la vez, sin evidencia para elegir",
}


def no_effect_reason(item: str) -> str:
    for prefix, reason in NO_EFFECT_REASON.items():
        if item.startswith(prefix):
            return reason
    return ""


def build() -> list[dict]:
    category = csm.index()            # upstream_id -> (sección o mixed, categoría)
    signals = effect_signals()
    manifest_paths = {
        row["item_id"]: row["psd1_path"] for row in load_tsv("atlas-manifest.tsv")}

    rows: list[dict] = []
    for row in sorted(load_rows(), key=lambda r: (r["source"], r["upstream_id"])):
        item = row["upstream_id"]
        section_of_category, category_key = category.get(item, ("", ""))
        label = row.get("label", "")

        section = "unassigned"
        basis = "manual-review"
        evidence = ""

        if section_of_category.isdigit():
            section, basis = section_of_category, "category"
            evidence = f"category:{category_key}"
        else:
            by_path = apply_manifest_path(manifest_paths.get(item))
            effect_sections, effect_evidence = effect_candidates(signals.get(item, []))
            by_name = apply_name(label)
            if by_path:
                section, basis = by_path[0], "manifest-path"
                evidence = by_path[1]
            elif len(effect_sections) == 1:
                section, basis = next(iter(effect_sections)), "effect"
                evidence = effect_evidence
            elif by_name:
                section, basis = by_name[0], "name-rule"
                evidence = by_name[1]
            else:
                evidence = (no_effect_reason(item)
                            or f"sin evidencia propia (categoria {category_key or '?'})")

        rows.append({
            "upstream_id": item,
            "source": row["source"],
            "label": label[:MAX_CELL],
            "category_key": category_key or "(sin categoria)",
            "section": section,
            "basis": basis,
            "evidence": evidence[:MAX_CELL],
            "reviewed": REVIEWED,
        })
    return rows


def unnamed_reason(row: dict) -> str:
    """Motivo legible de un `unassigned`, a partir de su evidencia."""
    return row["evidence"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    rows = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    by_section = Counter(r["section"] for r in rows)
    by_basis = Counter(r["basis"] for r in rows)
    by_rule = Counter(r["evidence"].split(":")[0] + ":" + r["evidence"]
                      for r in rows if r["basis"] in ("effect", "name-rule"))
    source_x_section = Counter((r["source"], r["section"]) for r in rows)
    unassigned = [r for r in rows if r["section"] == "unassigned"]
    unassigned_by_category = Counter(r["category_key"] for r in unassigned)

    summary = {
        "filas": len(rows),
        "asignadas": len(rows) - len(unassigned),
        "unassigned": len(unassigned),
        "por_seccion": dict(sorted(by_section.items(),
                                   key=lambda kv: (not kv[0].isdigit(), kv[0]))),
        "por_basis": dict(sorted(by_basis.items())),
        "por_regla": dict(sorted(by_rule.items())),
        "source_x_section": {f"{s}|{sec}": n
                             for (s, sec), n in sorted(source_x_section.items())},
        "unassigned_por_categoria": dict(sorted(unassigned_by_category.items())),
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"items mapeados      : {summary['filas']}")
    print(f"  con seccion       : {summary['asignadas']}")
    print(f"  unassigned        : {summary['unassigned']}")
    print(f"por basis           : {summary['por_basis']}")
    print("por regla           :")
    for rule, count in summary["por_regla"].items():
        print(f"  {rule:40s} {count}")
    print("unassigned por categoria:")
    for key, count in summary["unassigned_por_categoria"].items():
        print(f"  {key:40s} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
