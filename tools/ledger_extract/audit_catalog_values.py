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

Relación de cada fila:
    equals-apply    el valor del catálogo coincide con el que aplica la fuente
    equals-original coincide con el `OriginalValue` de la fuente (sospechoso)
    differs         no coincide con ninguno de los dos
    no-source       ninguna fuente toca esa tupla
    ambiguous       dos fuentes tocan la tupla y no coinciden entre sí

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

COLUMNS = ("capability_id", "hive", "key", "name", "catalog_value", "source",
           "source_ref", "source_apply_value", "source_original_value", "relation")
RELATIONS = ("equals-apply", "equals-original", "differs", "no-source", "ambiguous")
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


def load_atlas() -> dict[tuple[str, str, str], list[dict]]:
    index: dict[tuple[str, str, str], list[dict]] = {}
    base = UPSTREAM / "atlas" / ATLAS_TWEAKS
    if not base.is_dir():
        return index
    for path in sorted(base.rglob("*.psd1"), key=lambda p: str(p)):
        rel = path.relative_to(UPSTREAM / "atlas").as_posix()
        for entry in atlas_entries(path, rel):
            index.setdefault((entry["hive"], entry["key"], entry["name"]), []).append(entry)
    return index


# --------------------------------------------------------------------------- relaciones
def classify(catalog_value: str, candidates: list[dict]) -> tuple[str, str, str, str, str]:
    """Devuelve (relation, source, source_ref, apply, original)."""
    if not candidates:
        return ("no-source", "", "", "", "")

    distinct = {(c["source"], c["source_ref"], c["apply"]) for c in candidates}
    applies = {c["apply"] for c in candidates}
    if len(applies) > 1:
        first = sorted(candidates, key=lambda c: (c["source"], c["source_ref"]))[0]
        return ("ambiguous", first["source"], first["source_ref"],
                "|".join(sorted(applies)), "")

    first = sorted(candidates, key=lambda c: (c["source"], c["source_ref"]))[0]
    apply_value = first["apply"]
    original = first["original"]

    if catalog_value == apply_value:
        relation = "equals-apply"
    elif original and catalog_value == original:
        relation = "equals-original"
    else:
        relation = "differs"
    _ = distinct
    return (relation, first["source"], first["source_ref"], apply_value, original)


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
        relation, source, source_ref, apply_value, original = classify(
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
        if r["relation"] in ("equals-original", "differs")
        and (r["capability_id"], r["hive"], norm_key(r["key"]), r["name"]) not in exceptions
    ]
    stale = [
        key for key in sorted(exceptions)
        if not any(
            (r["capability_id"], r["hive"], norm_key(r["key"]), r["name"]) == key
            and r["relation"] in ("equals-original", "differs")
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

    summary = {
        "filas": len(rows),
        "distribucion": dict(sorted(distribution.items())),
        "excepciones": len(exceptions),
        "sin_excepcion": len(unsafe),
        "excepciones_obsoletas": [list(k) for k in stale],
        "seguras": len(rows) - distribution.get("equals-original", 0) - distribution.get("differs", 0),
    }

    ok = not unsafe and not stale
    if args.json:
        summary["ok"] = ok
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if ok else 1

    print(f"acciones de registro auditadas : {summary['filas']}")
    print(f"  distribucion                 : {summary['distribucion']}")
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
