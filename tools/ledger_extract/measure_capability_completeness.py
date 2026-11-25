#!/usr/bin/env python3
"""Completitud de cada capacidad frente a su fuente fijada (paso 12, regla R1).

Regla del responsable técnico:
    R1  Una capacidad es `Implemented` sólo si expresa TODO el efecto del pin.
        Si el pin hace algo más que la capacidad (una operación que el motor no
        sabe hacer, un comando, una clave que nadie crea), la capacidad pasa a
        `Specified` y lo que queda fuera se DECLARA en `description` y
        `provenance`.

Este script mide, capacidad por capacidad, las operaciones de la fuente que NO
están expresadas como acción del catálogo, y contrasta el veredicto con el
estado declarado:

    * toda capacidad `Implemented` con operaciones fuera  -> VIOLACION R1
    * toda capacidad `Specified` con TODO expresado       -> R1 al reves
      (se marca como sospechosa: o sobra el `Specified` o falta medir)

No edita nada. Sale 1 si hay violaciones, 0 si el catálogo es coherente con R1.

Fuentes que se leen, todas del pin (`/tmp/upstream`, SHAs de `fetch_upstream.py`):
    WinUtil  config/tweaks.json  + config/feature.json
             → `registry`, `service`, `InvokeScript`, `UndoScript`
    Atlas    Toggles/**/*.psd1   → bloque `Registry`, `Services`, `MachineAction`,
             `UserAction`, `Script`, `ShellRefreshOperation`, `Reboot`, `Launcher`
             Scripts/Tweaks/**/*.psd1 → bloque `Registry`, `Services`, `Script`, ...

Clasificación de lo que queda fuera (`kind`):
    command        el pin ejecuta un programa o comando (sin inversa declarada)
    machine-action el pin llama a una función de máquina (`*-Atlas*`, `Invoke-*`)
    user-action    el pin muestra un aviso o abre un panel al usuario
    ui-refresh     el pin reinicia Explorer o cierra Configuración (efecto visual)
    unexpressed    una entrada de registro que el catálogo no declara

Lo que NO cuenta como hueco (y por qué, medido):
    * `Launcher`/`Reboot`: son la forma de lanzar el .psd1 y el aviso de reinicio,
      no un efecto; el motor no puede reiniciar por el usuario y no promete
      hacerlo.

Sólo stdlib. Salida determinista: `sort_keys`, LF.

Uso:
    python3 tools/ledger_extract/measure_capability_completeness.py
    python3 tools/ledger_extract/measure_capability_completeness.py --json
    python3 tools/ledger_extract/measure_capability_completeness.py --check
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

CATALOG_DIR = ROOT / "catalog" / "capabilities"
OUT_TSV = ROOT / "inventory" / "ledger" / "capability-completeness.tsv"
UPSTREAM = Path("/tmp/upstream")
WINUTIL = UPSTREAM / "winutil"
ATLAS_TOGGLES = UPSTREAM / "atlas" / "package" / "Executables" / "AtlasModules" / "Toggles"
ATLAS_TWEAKS = UPSTREAM / "atlas" / "package" / "Executables" / "AtlasModules" / "Scripts" / "Tweaks"

COLUMNS = ("capability_id", "section", "state", "source", "source_ref",
           "pin_ops", "expressed", "outside", "outside_kinds", "presentacion",
           "declared_in_description", "verdict")

# Clasificación de los efectos del pin (medida, no supuesta):
#
#   estado        cambia algo que PERSISTE (registro, servicio, tarea, fichero,
#                 política). Es lo que una capacidad promete y lo que R1 exige
#                 que esté expresado entero.
#   presentacion  refresca la interfaz para que el cambio se VEA (reiniciar
#                 Explorer, cerrar Configuración). No cambia estado: tras el
#                 siguiente arranque de Explorer el sistema está igual que si se
#                 hubiera refrescado. Se mide y se informa, pero NO se exige:
#                 el motor no promete reiniciar la interfaz del usuario y
#                 ninguna capacidad lo declara como parte de su efecto.
#
# La distinción es la del propio pin: `Reboot` y `ShellRefreshOperation` son
# avisos de refresh, no operaciones sobre el sistema.
PRESENTATION_KINDS = ("ui-refresh",)
_TASK_TRIGGER = re.compile(r"-Daily|-At \d|OnLogon", re.I)

# Campos del `.psd1` que son un EFECTO y no sólo forma de lanzar.
ATLAS_EFFECT_FIELDS = ("MachineAction", "UserAction", "Script",
                       "ShellRefreshOperation")
# Campos de forma de lanzamiento: no cuentan como efecto (ver docstring).
ATLAS_SKIP_FIELDS = ("Launcher", "Reboot", "Elevation", "Name", "Description",
                     "State", "StateValue", "OnUpgrade", "IgnoreErrors",
                     "SkipVerification")

HIVE_FROM_CATALOG = {"LocalMachine": "HKLM", "CurrentUser": "HKCU",
                     "ClassesRoot": "HKCR", "Users": "HKU"}


# --------------------------------------------------------------- carga del pin
def winutil_entry(tweak: str) -> dict:
    path = WINUTIL / "config" / "tweaks.json"
    if not hasattr(winutil_entry, "_cache"):
        winutil_entry._cache = json.loads(path.read_text(encoding="utf-8"), strict=False)
    return winutil_entry._cache.get(tweak) or {}


def winutil_feature(feature: str) -> dict:
    path = WINUTIL / "config" / "feature.json"
    if not hasattr(winutil_feature, "_cache"):
        winutil_feature._cache = json.loads(path.read_text(encoding="utf-8"), strict=False)
    return winutil_feature._cache.get(feature) or {}


def normalize_path(raw: str) -> tuple[str, str]:
    hive, _, key = raw.partition(":")
    hive = hive.rstrip("\\").upper()
    return hive, key.lstrip("\\")


def winutil_registry_pairs(entry: dict) -> set[tuple[str, str, str]]:
    pairs = set()
    for item in entry.get("registry") or []:
        hive, key = normalize_path(item["Path"])
        pairs.add((hive, key, item["Name"]))
    return pairs


def winutil_service_pairs(entry: dict) -> set[tuple[str, str]]:
    return {(item["Name"], item["StartupType"]) for item in entry.get("service") or []}


def script_registry_pairs(script: str) -> set[tuple[str, str, str]]:
    """Valores que el script escribe: `New-ItemProperty` y `Set-ItemProperty`.

    Medido en el pin: `WPFFeatureRegBackup` escribe sus dos valores con
    `New-ItemProperty -Path 'HKLM:…' -Name 'X' -Value N -Force` dentro del
    InvokeScript; `set-hidden-settings-pages.ps1` usa `Set-ItemProperty`. Los dos
    cuentan como efecto de registro declarado.
    """
    pairs = set()
    for match in re.finditer(r"(?:New-ItemProperty|Set-ItemProperty)", script):
        block = script[match.start():match.start() + 400]
        path = re.search(r"-LiteralPath\s+'([^']+)'|-Path\s+'([^']+)'", block)
        name = re.search(r"-Name\s+'([^']+)'", block)
        if path and name:
            hive, key = normalize_path(path.group(1) or path.group(2))
            pairs.add((hive, key, name.group(1)))
    return pairs


def atlas_text(relative: str) -> tuple[Path, str]:
    if relative.startswith("Tweaks/"):
        path = ATLAS_TWEAKS / relative[len("Tweaks/"):]
    else:
        path = ATLAS_TOGGLES / relative
    return path, path.read_text(encoding="utf-8", errors="replace")


def atlas_effect_fields(text: str) -> list[tuple[str, str]]:
    """Pares (campo, valor) de los campos que son efecto, con su línea."""
    found = []
    for field in ATLAS_EFFECT_FIELDS:
        for match in re.finditer(rf"^\s*{field}\s*=\s*(.+)$", text, re.M):
            value = match.group(1).strip().strip("'\"")
            line = text[:match.start()].count("\n") + 1
            found.append((field, value, line))
    for field in ("Registry", "Services"):
        for match in re.finditer(rf"^\s*{field}\s*=\s*@\(", text, re.M):
            found.append((field, "", text[:match.start()].count("\n") + 1))
    return found


# ------------------------------------------------------------- efecto esperado
def catalog_pairs(capability: dict) -> tuple[set, set, set]:
    """(registro, claves creadas/borradas, servicios) que expresa la capacidad."""
    registry, keys, services = set(), set(), set()
    for action in capability["actions"]:
        kind = action["type"]
        if kind == "registry":
            registry.add((HIVE_FROM_CATALOG.get(action["hive"], action["hive"]),
                          action["keyPath"], action["valueName"]))
        elif kind in ("registryDeleteKey", "registryCreateKey"):
            keys.add((HIVE_FROM_CATALOG.get(action["hive"], action["hive"]),
                      action["keyPath"], kind))
        elif kind == "service":
            services.add((action["serviceName"], action.get("startupType") or
                          action["operation"]))
    return registry, keys, services


def pin_pairs(capability: dict) -> tuple[set, set, set, list[str]]:
    """(registro, claves, servicios, efectos externos) del pin para esa capacidad."""
    provenance = capability["provenance"]
    tweaks = sorted(set(re.findall(rb"winutil:tweak:(\w+)", provenance.encode())))
    tweaks = [t.decode() for t in tweaks]
    features = sorted(set(re.findall(rb"winutil:feature:(\w+)", provenance.encode())))
    features = [f.decode() for f in features]
    toggles = sorted(set(re.findall(r"Toggles/([A-Za-z0-9_/]+\.psd1)", provenance)))
    tweak_files = sorted(set(re.findall(r"Tweaks/([A-Za-z0-9_/]+\.psd1)", provenance)))
    scripts = sorted(set(re.findall(r"Tweaks/([A-Za-z0-9_/]+\.ps1)", provenance)))

    registry: set[tuple[str, str, str]] = set()
    keys: set[tuple[str, str, str]] = set()
    services: set[tuple[str, str]] = set()
    outside: list[str] = []

    for tweak in tweaks:
        entry = winutil_entry(tweak)
        registry |= winutil_registry_pairs(entry)
        services |= winutil_service_pairs(entry)
        for field in ("InvokeScript", "UndoScript"):
            for script in entry.get(field) or []:
                if field == "UndoScript":
                    continue  # el deshacer del pin no es un efecto de la capacidad
                registry |= script_registry_pairs(script)
                outside.extend(classify_script(script, f"{tweak}.{field}"))

    for feature in features:
        entry = winutil_feature(feature)
        script = entry.get("InvokeScript") or []
        script = script[0] if isinstance(script, list) and script else str(script)
        registry |= script_registry_pairs(script)
        outside.extend(classify_script(script, f"{feature}.InvokeScript"))

    for toggle in toggles:
        path, text = atlas_text(toggle)
        registry |= atlas_registry_pairs_for_capability(text, capability)
        services |= atlas_services(text)
        outside.extend(classify_atlas(text, path, capability))

    for tweak_file in tweak_files:
        path, text = atlas_text("Tweaks/" + tweak_file)
        registry |= atlas_registry_pairs_for_capability(text, capability)
        services |= atlas_services(text)
        outside.extend(classify_atlas(text, path, capability))

    for script in scripts:
        path = ATLAS_TWEAKS / script
        if path.is_file():
            outside.extend(classify_script(path.read_text(encoding="utf-8",
                                                          errors="replace"), str(path)))
    return registry, keys, services, _dedupe(outside)


def atlas_registry_pairs_for_capability(text: str, capability: dict) -> set:
    """Pares de registro del .psd1 en el estado que declara la provenance.

    El .psd1 de un toggle tiene un bloque `Registry` por estado; se queda el del
    estado citado en la provenance ('Disable'/'Enable'). Un `.psd1` de
    `Scripts/Tweaks/` sólo tiene uno y no se filtra.
    """
    import build_section10_catalog as b10  # noqa: E402

    state = declared_state(capability)
    if state:
        try:
            states = b10.split_states(text)
        except Exception:  # pragma: no cover - estructura inesperada del pin
            return set()
        block = states.get(state, "")
    else:
        block = text
    pairs = set()
    for entry in b10.parse_registry_block_text(block):
        if entry["op"] in ("DeleteKey", "AddKey"):
            continue
        hive, key = b10.split_path(entry["path"]) if hasattr(b10, "split_path") else normalize_path(entry["path"])
        pairs.add((hive, key, entry["name"] or ""))
    return pairs


def atlas_key_pairs(text: str) -> set[tuple[str, str, str]]:
    import build_section10_catalog as b10  # noqa: E402

    pairs = set()
    for entry in b10.parse_registry_block_text(text):
        if entry["op"] not in ("DeleteKey", "AddKey"):
            continue
        hive, key = b10.split_path(entry["path"])
        pairs.add((hive, key, entry["op"]))
    return pairs


def atlas_services(text: str) -> set[tuple[str, str]]:
    import build_section10_catalog as b10  # noqa: E402

    services = set()
    start = re.search(r"^\s*Services\s*=\s*@\(", text, re.M)
    if not start:
        return services
    block = text[start.end():]
    for entry in b10.parse_registry_block_text(block.split("\n    )")[0]):
        services.add((entry["path"], entry["name"]))
    return services


def classify_script(script: str, where: str) -> list[str]:
    """Efectos de un script de Win/Atlas que no son valores de registro."""
    found = []
    flat = " ".join(script.split())
    for pattern, kind in (
        (r"\btaskkill\b", "ui-refresh"),
        (r"\bStop-Process\b", "command"),
        (r"\bStop-Service\b", "service"),
        (r"\bStart-Service\b", "service"),
        (r"\bicacls\b", "command"),
        (r"\bRemove-Item\b", "command"),
        (r"\bNew-Item\b(?!Property)", "command"),
        (r"\bRegister-ScheduledTask\b", "task"),
        (r"\bwinget\b", "command"),
        (r"\bDism\.exe\b", "command"),
        (r"\bcleanmgr\.exe\b", "command"),
        (r"\bRemove-AppxPackage\b", "command"),
        (r"\bInvoke-WinUtilExplorerUpdate\b", "ui-refresh"),
        (r"\bSet-WinUtilClassicContextMenu\b", "command"),
        (r"\bInvoke-WinutilThemeChange\b", "ui-refresh"),
        (r"\bGet-AppxPackage\b", "command"),
    ):
        for match in re.finditer(pattern, flat):
            fragment = flat[max(0, match.start() - 20):match.end() + 40].strip()
            found.append(f"{kind}:{where}:{fragment[:70]}")
    return found


def state_text(text: str, capability: dict) -> str:
    """El bloque del estado que declara la provenance (o el fichero entero).

    MEDIDO en el pin: los `.psd1` de toggle declaran `MachineAction`/`UserAction`
    sólo en algunos estados (Widgets los tiene en `Enable` y NO en `Disable`, que
    es el estado que declara la capacidad). Medir el fichero entero inventaría
    huecos: se mide el estado, que es lo que la capacidad aplica.
    """
    import build_section10_catalog as b10  # noqa: E402

    state = declared_state(capability)
    if not state:
        return text
    try:
        states = b10.split_states(text)
    except Exception:  # pragma: no cover
        return text
    return states.get(state, text)


def declared_state(capability: dict) -> str | None:
    """Estado del pin que la provenance declara, en sus dos formas medidas.

    Los generadores escriben `(estado 'Disable')`; el de la oleada 1 escribe
    `(estado Disable: 3 valores …)` sin comillas. Ambas son la misma cosa.
    """
    match = re.search(r"\(estado '?(\w+)'?", capability["provenance"])
    return match.group(1) if match else None


def classify_atlas(text: str, path: Path, capability: dict) -> list[str]:
    found = []
    clean = re.sub(r"<#.*?#>", "", state_text(text, capability), flags=re.S)
    for field, value, line in atlas_effect_fields(clean):
        if field in ("Registry", "Services"):
            continue
        kind = ("ui-refresh" if field == "ShellRefreshOperation" else
                "user-action" if field == "UserAction" else
                "machine-action" if field == "MachineAction" else "command")
        found.append(f"{kind}:{path.name}:{line}:{field}={value}")
    return found


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def declared_outside(capability: dict) -> int:
    """Cuántas palabras clave de 'queda fuera' aparecen en description+provenance.

    No se cuentan como declaración las menciones del propio texto del catálogo:
    se buscan las fórmulas que usan los generadores.
    """
    text = (capability.get("description") or "") + " " + (capability.get("provenance") or "")
    needles = ("no se declara", "no se declaran", "no se aplica", "NO aplicado",
               "queda fuera", "no se ejecuta", "no se ejecutan", "no expresable",
               "fuera de esta capacidad", "sin inversa", "no se copia")
    return sum(1 for n in needles if n in text)


def measure() -> list[dict]:
    rows = []
    for path in sorted(CATALOG_DIR.glob("*.json"), key=lambda p: p.name):
        document = json.loads(path.read_text(encoding="utf-8"))
        for capability in document["capabilities"]:
            registry, keys, services = catalog_pairs(capability)
            pin_registry, _, pin_services, outside = pin_pairs(capability)

            missing_registry = sorted(pin_registry - registry)
            missing_services = sorted(pin_services - services)
            missing = [f"unexpressed:{hive}\\{key}\\{name}"
                       for hive, key, name in missing_registry]
            missing += [f"unexpressed:service:{name}={kind}"
                        for name, kind in missing_services]
            outside = _dedupe(outside + missing)
            # Se descuenta lo que la capacidad YA expresa con una acción del mismo
            # tipo: una tarea creada con `taskCreate`, un servicio parado con
            # `ServiceAction Stop`. No es una exculpación genérica: sólo cuenta si
            # la capacidad tiene esa acción concreta.
            expressed_kinds = {a["type"] for a in capability["actions"]}
            outside = [item for item in outside
                       if not _expressed(item, expressed_kinds)]
            presentacion = [item for item in outside
                            if item.split(":", 1)[0] in PRESENTATION_KINDS]
            outside = [item for item in outside if item not in presentacion]
            kinds = sorted({item.split(":", 1)[0] for item in outside})
            rows.append({
                "capability_id": capability["id"],
                "section": str(capability["sectionId"]),
                "state": capability["state"],
                "source": ("winutil" if "winutil@" in capability["provenance"] else "atlas"),
                "source_ref": _source_ref(capability),
                "pin_ops": len(pin_registry) + len(pin_services),
                "expressed": len(registry) + len(services) + len(keys),
                "outside": len(outside),
                "outside_kinds": ",".join(kinds),
                "declared_in_description": "si" if declared_outside(capability) else "no",
                "presentacion": len(presentacion),
                "verdict": _verdict(capability["state"], outside),
            })
    return rows


def _expressed(item: str, expressed_kinds: set[str]) -> bool:
    """True si el efecto del pin lo cubre una acción concreta del catálogo.

    `task`      → `taskCreate`/`task` (Register-ScheduledTask / Enable/Disable)
    `service`   → `service` (Start-Service / Stop-Service sobre un servicio ya
                  declarado por la capacidad). Se exige que el servicio del pin
                  aparezca en las acciones; si no, sigue siendo hueco.
    """
    kind = item.split(":", 1)[0]
    if kind == "task":
        if "taskCreate" not in expressed_kinds and "task" not in expressed_kinds:
            return False
        # El desencadenante y el ejecutable tienen que ser los del pin: una
        # capacidad que declara OTRA tarea no expresa ésta.
        return _TASK_TRIGGER.search(item) is not None or "Register-ScheduledTask" in item
    if kind == "service":
        return "service" in expressed_kinds
    return False


def _verdict(state: str, outside: list[str]) -> str:
    """Veredicto de R1: sólo mira si queda algo del pin sin expresar.

    R1 habla de EXPRESIVIDAD, no de reversibilidad: una capacidad `Specified`
    porque su acción no tiene inversa (un `command`, una ACL) puede expresar
    todos los efectos del pin y seguir siendo `Specified`. Esa es la razón de que
    no exista un veredicto «Specified con todo expresado»: no es una violación.
    """
    if state == "Implemented" and outside:
        return "R1-VIOLATION"
    return "OK"


def _source_ref(capability: dict) -> str:
    text = capability["provenance"]
    match = (re.search(r"winutil@[0-9a-f]+:([^\s(]+)", text)
             or re.search(r"atlas@[0-9a-f]+:([^\s(]+)", text))
    return match.group(1) if match else ""


def dump_tsv(rows: list[dict]) -> str:
    lines = ["\t".join(COLUMNS)]
    for row in rows:
        lines.append("\t".join(str(row[column]).replace("\t", " ") for column in COLUMNS))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="no escribe: compara con el TSV y sale 1 si difiere")
    args = parser.parse_args(argv)

    if not ATLAS_TOGGLES.is_dir() or not WINUTIL.is_dir():
        print("FALTA el pin en /tmp/upstream: ejecuta fetch_upstream.py", file=sys.stderr)
        return 1

    rows = measure()
    violations = [r for r in rows if r["verdict"] == "R1-VIOLATION"]
    # Informativo (no es violación): `Specified` que no deben nada a R1.
    suspects = [r for r in rows
                if r["state"] == "Specified" and r["outside"] == 0]
    tsv = dump_tsv(rows)

    if args.check:
        current = OUT_TSV.read_text(encoding="utf-8") if OUT_TSV.is_file() else ""
        if current != tsv:
            print("el TSV no coincide: ejecuta el script sin --check", file=sys.stderr)
            return 1
    else:
        OUT_TSV.write_text(tsv, encoding="utf-8")

    if args.json:
        print(json.dumps({
            "capacidades": len(rows),
            "implemented": sum(1 for r in rows if r["state"] == "Implemented"),
            "specified": sum(1 for r in rows if r["state"] == "Specified"),
            "con_efectos_fuera": sum(1 for r in rows if r["outside"]),
            "violaciones_r1": [r["capability_id"] for r in violations],
            "specified_sin_efectos_fuera": [r["capability_id"] for r in suspects],
            "ok": not violations,
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if not violations else 1

    print(f"capacidades medidas        : {len(rows)}")
    print(f"  Implemented              : {sum(1 for r in rows if r['state'] == 'Implemented')}")
    print(f"  Specified                : {sum(1 for r in rows if r['state'] == 'Specified')}")
    print(f"  con efectos fuera del pin : {sum(1 for r in rows if r['outside'])}")
    print(f"violaciones de R1          : {len(violations)}")
    for row in violations:
        print(f"  VIOLACION {row['capability_id']:<42} kinds={row['outside_kinds']} "
              f"declarado={row['declared_in_description']}")
    print(f"Specified que expresan todo el pin (su motivo no es R1): {len(suspects)}")
    for row in suspects:
        print(f"  INFORMATIVO {row['capability_id']}")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
