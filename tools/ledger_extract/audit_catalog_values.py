#!/usr/bin/env python3
"""Auditoría de los valores del catálogo contra las fuentes fijadas (paso 8b).

Sospecha que motiva el script: que el catálogo copie el `OriginalValue` de
WinUtil (o el valor de "deshacer") en vez del valor que WinUtil aplica.

Para cada `RegistryAction` de `catalog/capabilities/*.json`:
  1. normaliza (hive, clave, nombre) y busca la misma tupla en
     `inventory/ledger/winutil-tweak-ops.tsv` (columnas `value` y
     `original_value`);
  2. busca la misma tupla en los bloques `Registry = @( ... )` de los `.psd1`
     de Tweaks del pin de Atlas, leyendo el pin en memoria con
     `tools/ledger_extract/fetch_upstream.py`; el literal se lee del pin y NO se
     escribe al ledger (se guarda solo el valor comparado en el TSV de salida).

Significado de estado (T1a del paso 8c, medido en el pin):
- WinUtil `Invoke-WinUtilTweaks.ps1:34-46` escribe `Value` al aplicar y
  `OriginalValue` al deshacer; `Get-WinUtilToggleStatus.ps1:44` marca la casilla
  como encendida cuando el registro vale exactamente `Value`. Por tanto, en una
  entrada con `Type: Toggle`, **`Value` es el estado ENCENDIDO** de la casilla y
  `OriginalValue` el APAGADO. En una entrada sin `Type` (botón de "aplicar") no
  hay casilla que interpretar: `Value` es lo que se escribe y `OriginalValue` lo
  que se restaura al deshacer.

Relación de cada fila:
    equals-apply    coincide con `Value` de una fuente sin `Type` (botón)
    equals-on       coincide con `Value` de un Toggle, que es el estado ENCENDIDO
    equals-off      coincide con `OriginalValue` de un Toggle (estado APAGADO)
    equals-original coincide con `OriginalValue` de una fuente sin `Type`
    differs         no coincide con ninguno de los dos
    no-source       ninguna fuente toca esa tupla
    ambiguous       varias fuentes la tocan y no coinciden entre sí

Cualquier fila `equals-original` o `differs` exige una excepción razonada en
`catalog/exceptions/value-deviations.json`; si falta, el script sale con 1.

Sin cuerpos de código: sólo se comparan literales de valor. Celdas <= 400
caracteres. Salida determinista: orden estable, LF, UTF-8 sin BOM.

Uso:
    python3 tools/ledger_extract/audit_catalog_values.py            # TSV + resumen
    python3 tools/ledger_extract/audit_catalog_values.py --json     # resumen JSON
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = ROOT / "catalog" / "capabilities"
WINUTIL_OPS = ROOT / "inventory" / "ledger" / "winutil-tweak-ops.tsv"
OUT_TSV = ROOT / "inventory" / "ledger" / "catalog-value-audit.tsv"
EXCEPTIONS = ROOT / "catalog" / "exceptions" / "value-deviations.json"
UPSTREAM = Path("/tmp/upstream")
ATLAS_TWEAKS = "package/Executables/AtlasModules/Scripts/Tweaks"
ATLAS_TOGGLES = "package/Executables/AtlasModules/Toggles"

COLUMNS = ("capability_id", "hive", "key", "name", "catalog_value", "source",
           "source_ref", "source_apply_value", "source_original_value",
           "source_tweak_type", "relation")
RELATIONS = ("equals-apply", "equals-on", "equals-off", "equals-original",
             "differs", "no-source", "ambiguous")
# Relaciones que exigen una excepción razonada en value-deviations.json.
NEEDS_EXCEPTION = ("equals-off", "equals-original", "differs")
MAX_CELL = 400

HIVE_ALIASES = {
    "hklm": "HKLM", "hkcu": "HKCU", "hkcr": "HKCR", "hku": "HKU",
    "hkey_local_machine": "HKLM", "hkey_current_user": "HKCU",
    "hkey_classes_root": "HKCR", "hkey_users": "HKU",
}
SYNC_HIVES = {
    "LocalMachine": "HKLM", "CurrentUser": "HKCU",
    "ClassesRoot": "HKCR", "Users": "HKU",
}


def norm_key(key: str) -> str:
    return key.replace("/", "\\").strip("\\").lower()


def split_hive(path: str) -> tuple[str, str]:
    """'HKLM:\\SOFTWARE\\X' -> ('HKLM', 'SOFTWARE\\X')."""
    cleaned = path.replace("Registry::", "").replace("/", "\\")
    if ":" in cleaned:
        hive, rest = cleaned.split(":", 1)
    elif "\\" in cleaned:
        hive, rest = cleaned.split("\\", 1)
        rest = rest
    else:
        return "", norm_key(cleaned)
    return HIVE_ALIASES.get(hive.strip().lower(), hive.strip().upper()), norm_key(rest)


def norm_value(value: object) -> str:
    """Normaliza un literal a texto comparable."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.startswith("'") and text.endswith("'") and len(text) >= 2:
        text = text[1:-1]
    if text.lower() in ("<removeentry>", "<delete>"):
        return "<RemoveEntry>"
    return text.rstrip("}").strip()


# --------------------------------------------------------------------------- catalogo
def catalog_registry_actions() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(CATALOG_DIR.glob("*.json"), key=lambda p: p.name):
        document = json.loads(path.read_text(encoding="utf-8"))
        for capability in document.get("capabilities", []):
            for action in capability.get("actions", []):
                if action.get("type") != "registry":
                    continue
                hive = SYNC_HIVES.get(action["hive"], action["hive"])
                rows.append(
                    {
                        "capability_id": capability["id"],
                        "hive": hive,
                        "key": norm_key(action["keyPath"]),
                        "name": action["valueName"],
                        "catalog_value": (
                            "<RemoveEntry>"
                            if action["operation"] == "Delete"
                            else norm_value(action.get("value"))
                        ),
                        "catalog_operation": action["operation"],
                        "file": path.name,
                    }
                )
    return rows


# --------------------------------------------------------------------------- winutil
def load_winutil() -> dict[tuple[str, str, str], list[dict]]:
    index: dict[tuple[str, str, str], list[dict]] = {}
    if not WINUTIL_OPS.is_file():
        return index
    with WINUTIL_OPS.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["kind"] != "registry" or row["direction"] != "apply":
                continue
            hive, key = split_hive(row["target"])
            entry = {
                "source": "winutil",
                "source_ref": row["item_id"],
                # `tweak_type` es la columna nueva del paso 8c: distingue un
                # Toggle (Value = casilla encendida) de un boton de aplicar.
                "tweak_type": row.get("tweak_type", "") or "none",
                "apply": norm_value(row["value"]),
                "original": norm_value(row["original_value"]),
            }
            index.setdefault((hive, key, row["name"].lower()), []).append(entry)
    return index


# --------------------------------------------------------------------------- atlas
FIELD_RES = {
    "path": re.compile(r"\bPath\s*=\s*'([^']*)'"),
    "name": re.compile(r"\bName\s*=\s*'([^']*)'"),
    "data": re.compile(r"\bData\s*=\s*('[^']*'|[^;\s,}]+)"),
    "operation": re.compile(r"\bOperation\s*=\s*'([^']*)'"),
}


def balanced_hashtables(text: str) -> list[str]:
    """Trocea `@{ … }` de un texto respetando comillas y `@( … )`.

    Hace falta porque las rutas de Atlas llevan llaves dentro de comillas
    (`CLSID\\{e88865ea-…}`) y hay valores que son `@(0x0E, …)`.
    """
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


STATE_NAME = re.compile(r"Name\s*=\s*'([^']+)'")
STATE_VALUE = re.compile(r"StateValue\s*=")


def atlas_states(text: str) -> list[tuple[str, str]]:
    """Estado -> interior del estado, en el orden del fichero.

    Un `.psd1` de Toggles declara varios estados con `StateValue`; los de Tweaks
    no declaran estados (una sola forma de aplicarse). Sin esta separación, un
    toggle con Data 0 en un estado y 1 en otro aparece como `ambiguous` aunque
    el catálogo esté copiando exactamente uno de los dos.
    """
    text = re.sub(r"#[^\n]*", "", text)
    marker = text.find("States")
    if marker < 0:
        return []
    paren = text.find("@(", marker)
    if paren < 0:
        return []
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

    states: list[tuple[str, str]] = []
    for body in balanced_hashtables(block):
        if not STATE_VALUE.search(body):
            continue
        name = STATE_NAME.search(body)
        if name:
            states.append((name.group(1), body[2:-1]))
    return states


def atlas_entries(path: Path, rel: str) -> list[dict]:
    """Entradas de los bloques `Registry = @( ... )` de un .psd1, con línea."""
    text = path.read_text(encoding="utf-8", errors="replace")
    # Hashtables anidadas en un valor (`VerifyWithToggle = @{ ... }`) rompen el
    # conteo de profundidad y fusionan entradas: se colapsan antes de recorrer.
    for _ in range(3):
        text = re.sub(r"=\s*@\{[^{}]*\}", "= @{}", text)
    # Los comentarios pueden contener comillas o llaves: se eliminan para no
    # partir las entradas por la mitad (una entrada comentada no es una op).
    text = re.sub(r"#[^\n]*", "", text)
    lines = text.split("\n")
    entries: list[dict] = []
    inside = False
    depth = 0
    current: dict | None = None
    start_line = 0
    for number, line in enumerate(lines, start=1):
        if not inside:
            if re.match(r"^\s*Registry\s*=\s*@\(", line):
                inside = True
                depth = 0
            continue
        if current is None:
            if "@{" in line:
                current = {"line": number, "text": line}
                depth = line.count("@{") - line.count("}")
                if depth <= 0:
                    entries.append(current)
                    current = None
                continue
            if ")" in line and "@{" not in line:
                inside = False
            continue
        current["text"] += "\n" + line
        depth += line.count("@{") - line.count("}")
        if depth <= 0:
            entries.append(current)
            current = None

    parsed: list[dict] = []
    for entry in entries:
        body = entry["text"]
        path_match = FIELD_RES["path"].search(body)
        name_match = FIELD_RES["name"].search(body)
        if not path_match or not name_match:
            continue
        data_match = FIELD_RES["data"].search(body)
        operation_match = FIELD_RES["operation"].search(body)
        operation = operation_match.group(1) if operation_match else "Set"
        value = "<RemoveEntry>" if operation.lower() == "delete" else (
            norm_value(data_match.group(1)) if data_match else "")
        hive, key = split_hive(path_match.group(1))
        parsed.append(
            {
                "source": "atlas",
                "source_ref": f"atlas@ec3c4058:{rel}:{entry['line']}",
                "hive": hive,
                "key": key,
                "name": name_match.group(1).lower(),
                "apply": value,
                "original": "",
            }
        )
    return parsed


def atlas_toggle_states(path: Path, rel: str) -> list[dict]:
    """Entradas de registro de un `.psd1` de Toggles, con el estado del que salen."""
    text = path.read_text(encoding="utf-8", errors="replace")
    parsed: list[dict] = []
    for state_name, body in atlas_states(text):
        for entry in balanced_hashtables(body):
            path_match = FIELD_RES["path"].search(entry)
            name_match = FIELD_RES["name"].search(entry)
            if not path_match or not name_match:
                continue
            data_match = FIELD_RES["data"].search(entry)
            operation_match = FIELD_RES["operation"].search(entry)
            operation = operation_match.group(1) if operation_match else "Set"
            value = "<RemoveEntry>" if operation.lower() == "delete" else (
                norm_value(data_match.group(1)) if data_match else "")
            if operation.lower() != "delete" and not data_match:
                # Sin Data no hay literal comparable: no se inventa uno.
                continue
            hive, key = split_hive(path_match.group(1))
            parsed.append(
                {
                    "source": "atlas-toggle",
                    "source_ref": f"atlas@ec3c4058:{rel}:{state_name}",
                    "hive": hive,
                    "key": key,
                    "name": name_match.group(1).lower(),
                    "apply": value,
                    "original": "",
                    "state": state_name,
                }
            )
    return parsed


def load_atlas() -> dict[tuple[str, str, str], list[dict]]:
    index: dict[tuple[str, str, str], list[dict]] = {}
    if not (UPSTREAM / "atlas").is_dir():
        return index
    # 1) Tweaks: una sola forma de aplicarse.
    base = UPSTREAM / "atlas" / ATLAS_TWEAKS
    if base.is_dir():
        for path in sorted(base.rglob("*.psd1"), key=lambda p: str(p)):
            rel = path.relative_to(UPSTREAM / "atlas").as_posix()
            for entry in atlas_entries(path, rel):
                index.setdefault((entry["hive"], entry["key"], entry["name"]), []).append(entry)
    # 2) Toggles: el catálogo copia UN estado concreto (normalmente el que
    #    anuncia el efecto de la capacidad). Se indexan por estado para que la
    #    auditoría no confunda «hay dos estados con valores distintos» con
    #    «las fuentes discrepan».
    toggles = UPSTREAM / "atlas" / ATLAS_TOGGLES
    if toggles.is_dir():
        for path in sorted(toggles.rglob("*.psd1"), key=lambda p: str(p)):
            rel = path.relative_to(UPSTREAM / "atlas").as_posix()
            for entry in atlas_toggle_states(path, rel):
                index.setdefault((entry["hive"], entry["key"], entry["name"]), []).append(entry)
    return index


# --------------------------------------------------------------------------- relaciones
def classify(catalog_value: str, candidates: list[dict]) -> tuple[str, str, str, str, str]:
    """Devuelve (relation, source, source_ref, apply, original).

    Antes de decidir, se queda con las fuentes que COINCIDEN con el valor del
    catálogo si alguna lo hace: así un toggle de Atlas con estados 0 y 1 no sale
    `ambiguous` cuando el catálogo copia uno de ellos exactamente. Si ninguna
    coincide y hay varios literales distintos, sí es `ambiguous` de verdad.
    """
    if not candidates:
        return ("no-source", "", "", "", "", "")

    matching = [c for c in candidates if c["apply"] == catalog_value]
    if matching and len({c["apply"] for c in candidates}) > 1:
        candidates = matching

    distinct = {(c["source"], c["source_ref"], c["apply"], c.get("tweak_type", ""))
                for c in candidates}
    applies = {c["apply"] for c in candidates}
    if len(applies) > 1:
        first = sorted(candidates, key=lambda c: (c["source"], c["source_ref"]))[0]
        return ("ambiguous", first["source"], first["source_ref"],
                "|".join(sorted(applies)), "", first.get("tweak_type", ""))

    first = sorted(candidates, key=lambda c: (c["source"], c["source_ref"]))[0]
    apply_value = first["apply"]
    original = first["original"]
    tweak_type = first.get("tweak_type", "")
    is_toggle = tweak_type == "Toggle"

    if catalog_value == apply_value:
        # En un Toggle, Value es la casilla ENCENDIDA; en un boton, lo que aplica.
        relation = "equals-on" if is_toggle else "equals-apply"
    elif original and catalog_value == original:
        relation = "equals-off" if is_toggle else "equals-original"
    else:
        relation = "differs"
    _ = distinct
    return (relation, first["source"], first["source_ref"], apply_value, original,
            tweak_type)


def load_exceptions() -> set[tuple[str, str, str, str]]:
    if not EXCEPTIONS.is_file():
        return set()
    document = json.loads(EXCEPTIONS.read_text(encoding="utf-8"))
    keys = set()
    for entry in document.get("deviations", []):
        keys.add((entry["capability_id"], entry["hive"], norm_key(entry["key"]),
                  entry["name"]))
    return keys


def build_rows() -> list[dict]:
    winutil = load_winutil()
    atlas = load_atlas()
    rows = []
    for action in catalog_registry_actions():
        key = (action["hive"], action["key"], action["name"].lower())
        candidates = winutil.get(key, []) + atlas.get(key, [])
        relation, source, source_ref, apply_value, original, tweak_type = classify(
            action["catalog_value"], candidates)
        rows.append(
            {
                "capability_id": action["capability_id"],
                "hive": action["hive"],
                "key": action["key"],
                "name": action["name"],
                "catalog_value": action["catalog_value"],
                "source": source,
                "source_ref": source_ref,
                "source_apply_value": apply_value,
                "source_original_value": original,
                "source_tweak_type": tweak_type,
                "relation": relation,
            }
        )
    rows.sort(key=lambda r: (r["capability_id"], r["hive"], r["key"], r["name"]))
    return rows


def trim(row: dict) -> dict:
    return {k: (v[:MAX_CELL] if isinstance(v, str) else v) for k, v in row.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="resumen JSON")
    parser.add_argument("--check-only", action="store_true",
                        help="no escribe el TSV, solo valida las excepciones")
    args = parser.parse_args(argv)

    rows = build_rows()
    exceptions = load_exceptions()

    distribution = Counter(r["relation"] for r in rows)
    unsafe = [
        r for r in rows
        if r["relation"] in NEEDS_EXCEPTION
        and (r["capability_id"], r["hive"], norm_key(r["key"]), r["name"]) not in exceptions
    ]
    stale = [
        key for key in sorted(exceptions)
        if not any(
            (r["capability_id"], r["hive"], norm_key(r["key"]), r["name"]) == key
            and r["relation"] in NEEDS_EXCEPTION
            for r in rows
        )
    ]

    if not args.check_only:
        OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
        with OUT_TSV.open("w", encoding="utf-8", newline="\n") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t",
                                    lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow(trim(row))

    # Recuento por sección del catálogo, para poder informar de cuántas acciones
    # de la sección 10 entraron en la auditoría (no se estima: se cuenta).
    section_of = {}
    catalog_dir = ROOT / "catalog" / "capabilities"
    for path in sorted(catalog_dir.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for definition in document.get("capabilities", []):
            section_of[definition["id"]] = str(definition.get("sectionId", ""))

    summary = {
        "filas": len(rows),
        "por_seccion": dict(sorted(Counter(
            section_of.get(r["capability_id"], "?") for r in rows).items())),
        "distribucion": dict(sorted(distribution.items())),
        "excepciones": len(exceptions),
        "sin_excepcion": len(unsafe),
        "excepciones_obsoletas": [list(k) for k in stale],
        "seguras": len(rows) - sum(distribution.get(r, 0) for r in NEEDS_EXCEPTION),
    }

    ok = not unsafe and not stale
    if args.json:
        summary["ok"] = ok
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if ok else 1

    print(f"acciones de registro auditadas : {summary['filas']}")
    print(f"  distribucion                 : {summary['distribucion']}")
    print(f"  por seccion del catalogo     : {summary['por_seccion']}")
    print(f"  excepciones declaradas       : {summary['excepciones']}")
    print(f"  sin excepcion (debe ser 0)   : {summary['sin_excepcion']}")
    if unsafe:
        print("\nFILAS INSEGURAS SIN EXCEPCION:")
        for row in unsafe:
            print(f"  {row['capability_id']} {row['hive']}\\{row['key']}\\{row['name']}"
                  f" cat={row['catalog_value']} src={row['source_apply_value']}"
                  f" ({row['relation']})")
    if stale:
        print("\nEXCEPCIONES OBSOLETAS (ya no son desviacion):")
        for key in stale:
            print(f"  {key}")
    print("\nveredicto:", "OK" if ok else "FALLA")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
