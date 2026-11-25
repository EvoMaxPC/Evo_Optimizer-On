#!/usr/bin/env python3
"""Estados CONTRARIOS de los toggles de Atlas frente a lo que declara el catálogo (paso 12, T3).

Un toggle de Atlas tiene dos o más estados con efectos distintos (`Disable` /
`Enable`). El catálogo de una capacidad elige UNO y declara sus acciones. El
riesgo que se mide aquí es el que ya apareció dos veces en el repo:

    declarar operaciones del estado CONTRARIO al que la capacidad representa

que es lo que pasó con `explorer.removable-drives.sidebar` (las dos `DeleteKey`
del pin están en el estado `Disable`, y la capacidad enciende) y con la
propuesta de declarar el `AddKey` de `Home` (está en `Enable`, y la capacidad
oculta). Una operación así no es un hueco de expresividad: es un ERROR de
significado que aplicaría lo contrario de lo prometido.

Qué mide, para cada capacidad que sale de un `.psd1` de toggle:

    estado_declarado   el que declara la provenance (`(estado 'X')`)
    estados_del_pin    todos los estados del .psd1 con su número de entradas
    ops_del_estado     operaciones de registro del estado declarado
    ops_contrarias     operaciones de los DEMAS estados (valor/clave distinta)
    veredicto          OK | CONTRARIO-DECLARADO (hay ops del otro estado en las
                       acciones) | PENDIENTE-DECLARADO (el otro estado tiene
                       operaciones que no se declaran: se informa, no es error)

`CONTRARIO-DECLARADO` es un fallo duro: sale 1. `PENDIENTE` es informativo: son
las operaciones que una capacidad futura necesitaría (el caso de Removable
Drives) y quedan escritas en el TSV para que no se pierdan.

Sólo stdlib. Determinista: orden por id, LF.

Uso:
    python3 tools/ledger_extract/measure_toggle_states.py
    python3 tools/ledger_extract/measure_toggle_states.py --json
    python3 tools/ledger_extract/measure_toggle_states.py --check
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

import build_section10_catalog as b10  # noqa: E402

CATALOG_DIR = ROOT / "catalog" / "capabilities"
OUT_TSV = ROOT / "inventory" / "ledger" / "toggle-state-audit.tsv"

COLUMNS = ("capability_id", "section", "toggle", "estado_declarado", "estados_del_pin",
           "ops_del_estado", "ops_contrarias", "contrarias_en_acciones", "veredicto")


def normalize_data(entry: dict) -> str:
    """Dato comparable: los binarios del pin (`@(0x90, …)`) en el mismo texto que
    el catálogo (base64), para que un binario no parezca distinto por formato.
    """
    raw = entry.get("data")
    if raw is None:
        return ""
    text = str(raw).strip().strip("'\"")
    # Escalar: se compara el VALOR, no el formato. El pin escribe a veces 1 y a
    # veces '1' para el mismo dato (DWord frente a String del .psd1); el catálogo
    # conserva el tipo aparte.
    if re.fullmatch(r"-?\d+", text):
        return str(int(text))
    match = re.fullmatch(r"@\((.+)\)", str(raw).strip())
    if not match:
        return text
    try:
        numbers = [int(part.strip(), 0) for part in match.group(1).split(",") if part.strip()]
    except ValueError:
        return str(raw)
    return "base64:" + base64.b64encode(bytes(numbers)).decode("ascii")


def op_key(entry: dict) -> tuple[str, str, str, str, str]:
    """Identidad comparable de una entrada de registro del pin.

    El DATO entra en la identidad, y es la clave de todo el script: en un toggle,
    `Disable` y `Enable` escriben el MISMO valor con datos distintos
    (`AutoCheckSelect=0` frente a `=1`). Comparar sólo (hive, clave, nombre) haría
    que el estado contrario pareciera declarado en las 19 capacidades; el dato
    distingue el efecto y deja a la vista sólo lo que de verdad se cruzó.
    """
    hive, key = b10.split_path(entry["path"])
    if entry["op"] in ("DeleteKey", "AddKey"):
        return (hive, key, entry["op"], "", "")
    return (hive, key, "Set", entry["name"] or "", normalize_data(entry))


def action_keys(capability: dict) -> set[tuple[str, str, str, str, str]]:
    keys = set()
    for action in capability["actions"]:
        if action["type"] not in ("registry", "registryDeleteKey", "registryCreateKey"):
            continue
        hive = {"LocalMachine": "HKLM", "CurrentUser": "HKCU",
                "ClassesRoot": "HKCR", "Users": "HKU"}[action["hive"]]
        if action["type"] == "registryDeleteKey":
            keys.add((hive, action["keyPath"], "DeleteKey", "", ""))
        elif action["type"] == "registryCreateKey":
            keys.add((hive, action["keyPath"], "AddKey", "", ""))
        elif action["type"] == "registry":
            keys.add((hive, action["keyPath"], "Set", action["valueName"] or "",
                      str(action.get("value"))))
    return keys


def declared_state(capability: dict) -> str | None:
    match = re.search(r"\(estado '?(\w+)'?", capability["provenance"])
    return match.group(1) if match else None


def toggle_file(capability: dict) -> str | None:
    match = re.search(r"Toggles/([A-Za-z0-9_/]+\.psd1)", capability["provenance"])
    return match.group(1) if match else None


def measure() -> list[dict]:
    rows = []
    for path in sorted(CATALOG_DIR.glob("*.json"), key=lambda p: p.name):
        document = json.loads(path.read_text(encoding="utf-8"))
        for capability in document["capabilities"]:
            relative = toggle_file(capability)
            if not relative:
                continue
            source = b10.ATLAS_TOGGLES / relative
            text = source.read_text(encoding="utf-8", errors="replace")
            states = b10.split_states(text)
            declared = declared_state(capability)
            if declared not in states:
                continue
            own = {op_key(e) for e in b10.parse_registry_block_text(states[declared])}
            other: set[tuple[str, str, str, str, str]] = set()
            for name, block in states.items():
                if name != declared:
                    other |= {op_key(e) for e in b10.parse_registry_block_text(block)}
            declared_actions = action_keys(capability)
            # Contrario es lo que SOLO aplica el otro estado. Lo que ambos estados
            # escriben igual (un valor compartido, p. ej. FontSmoothing='2') no es
            # contrario: es común al toggle y se aplica igual se elija lo que se
            # elija.
            exclusive_other = other - own
            contrary_in_actions = sorted(declared_actions & exclusive_other)
            pending = sorted(exclusive_other - declared_actions)
            if contrary_in_actions:
                verdict = "CONTRARIO-DECLARADO"
            elif pending:
                verdict = "PENDIENTE-DECLARADO"
            else:
                verdict = "OK"
            rows.append({
                "capability_id": capability["id"],
                "section": str(capability["sectionId"]),
                "toggle": Path(relative).stem,
                "estado_declarado": declared,
                "estados_del_pin": "|".join(
                    f"{name}:{len(b10.parse_registry_block_text(block))}"
                    for name, block in states.items()),
                "ops_del_estado": len(own),
                "ops_contrarias": len(exclusive_other),
                "contrarias_en_acciones": len(contrary_in_actions),
                "veredicto": verdict,
            })
    return rows


def dump_tsv(rows: list[dict]) -> str:
    lines = ["\t".join(COLUMNS)]
    for row in rows:
        lines.append("\t".join(str(row[c]).replace("\t", " ") for c in COLUMNS))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    rows = measure()
    tsv = dump_tsv(rows)
    bad = [r for r in rows if r["veredicto"] == "CONTRARIO-DECLARADO"]

    if args.check:
        current = OUT_TSV.read_text(encoding="utf-8") if OUT_TSV.is_file() else ""
        if current != tsv:
            print("el TSV no coincide: ejecuta el script sin --check", file=sys.stderr)
            return 1
    else:
        OUT_TSV.write_text(tsv, encoding="utf-8")

    if args.json:
        print(json.dumps({
            "capacidades_con_toggle": len(rows),
            "ok": [r["capability_id"] for r in rows if r["veredicto"] == "OK"],
            "pendientes": [r["capability_id"] for r in rows
                           if r["veredicto"] == "PENDIENTE-DECLARADO"],
            "contrarios_declarados": [r["capability_id"] for r in bad],
            "veredicto": "OK" if not bad else "FALLO",
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if not bad else 1

    print(f"capacidades que salen de un toggle : {len(rows)}")
    print(f"  estado declarado sin contrarios   : {sum(1 for r in rows if r['veredicto'] == 'OK')}")
    print(f"  con operaciones pendientes del otro estado: "
          f"{sum(1 for r in rows if r['veredicto'] == 'PENDIENTE-DECLARADO')}")
    for row in rows:
        if row["veredicto"] != "OK":
            print(f"  {row['veredicto']:<22} {row['capability_id']:<40} "
                  f"declarado={row['estado_declarado']} pin={row['estados_del_pin']}")
    print(f"contrarios DECLARADOS (fallo)      : {len(bad)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
