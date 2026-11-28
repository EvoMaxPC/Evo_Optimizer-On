#!/usr/bin/env python3
"""Operaciones de registro declaradas en los .psd1 de Tweaks de Atlas (mejor esfuerzo).

No hay PowerShell en el sandbox: se parsea con regex sobre los bloques
`Registry = @( ... )` de cada `.psd1`.

Cada entrada es una hashtable de PowerShell del tipo
`@{ Path = '...'; Name = '...'; Type = '...'; Data = ... }`, posiblemente
multilínea y con comas opcionales.

Salida:
    inventory/ledger/atlas-tweak-ops.tsv
        item_id  path  hive  key  value_name  value_type  value_sha256
        parse_status  unparsed_reason

- `item_id = atlas:tweak-op:<ruta>:<indice>` (índice 0-based por fichero).
- `hive`/`key` salen de `Path`; `value_name` de `Name`; `value_type` de `Type`.
- `value_sha256` = sha256 de `"<hive>|<key>|<nombre>"`: identifica la operación
  sin copiar el dato literal.
- `parse_status`:
    `ok`       Path y Name presentes
    `partial`  falta Path o Name, o el tipo es desconocido
- Las entradas del bloque `Registry` que no se pueden parsear **no se
  descartan**: se cuentan y se listan como `unparsed` en la salida del comando y
  en `docs/reports/paso4c.md`.

Salida determinista: orden por `item_id`, LF, UTF-8 sin BOM.

Uso:
    python3 tools/ledger_extract/extract_atlas_tweak_ops.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = Path("/tmp/upstream/atlas")
TWEAKS_DIR = "package/Executables/AtlasModules/Scripts/Tweaks"
OUT_DIR = ROOT / "inventory" / "ledger"

COLUMNS = ("item_id", "path", "hive", "key", "value_name", "value_type",
           "value_sha256", "parse_status", "unparsed_reason")

REGISTRY_BLOCK_RE = re.compile(r"^\s*Registry\s*=\s*@\(", re.MULTILINE)
FIELD_RES = {
    "path": re.compile(r"\bPath\s*=\s*'([^']*)'", re.IGNORECASE),
    "name": re.compile(r"\bName\s*=\s*'([^']*)'", re.IGNORECASE),
    "type": re.compile(r"\bType\s*=\s*'([^']*)'", re.IGNORECASE),
    "operation": re.compile(r"\bOperation\s*=\s*'([^']*)'", re.IGNORECASE),
}
# El formato PowerShell admite la forma de proveedor "HKLM:\Software\Clave"
# y la de .NET "Registry::HKEY_LOCAL_MACHINE\...". Se normalizan a hive corto.
HIVE_ALIASES = {
    "hklm": "HKLM", "hkcu": "HKCU", "hkcr": "HKCR", "hku": "HKU",
    "hkcc": "HKCC",
    "hkey_local_machine": "HKLM", "hkey_current_user": "HKCU",
    "hkey_classes_root": "HKCR", "hkey_users": "HKU",
    "hkey_current_config": "HKCC",
}
# Las claves de registro contienen GUIDs entre llaves ("CLSID\{...}"), así que
# un regex no-greedy corta la entrada antes de tiempo: se recorren las llaves a
# mano contando profundidad.
ENTRY_START_RE = re.compile(r"@\{")
KNOWN_TYPES = {
    "dword", "qword", "string", "sz", "expandstring", "expand_sz",
    "multistring", "binary", "none", "delete",
}


def split_hive(path: str) -> tuple[str, str]:
    """Normaliza el hive y separa la clave.

    'HKCU\\Software\\X'            -> ('HKCU', 'Software\\X')
    'HKLM:\\SOFTWARE\\X'          -> ('HKLM', 'SOFTWARE\\X')
    'Registry::HKEY_LOCAL_MACHINE\\X' -> ('HKLM', 'X')
    """
    p = path.strip()
    if p.lower().startswith("registry::"):
        p = p.split("::", 1)[1]
    head, _, rest = p.partition("\\")
    head_clean = head.rstrip(":").strip()
    hive = HIVE_ALIASES.get(head_clean.lower(), head_clean.upper())
    return hive, rest


def registry_blocks(text: str) -> list[str]:
    """Devuelve el texto de cada bloque @( ... ) de Registry."""
    blocks: list[str] = []
    for m in REGISTRY_BLOCK_RE.finditer(text):
        i = text.index("(", m.end() - 1)
        depth = 0
        for j in range(i, len(text)):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    blocks.append(text[i + 1:j])
                    break
    return blocks


def iter_entries(block: str):
    """Genera el cuerpo de cada hashtable @{...} del bloque, con llaves anidadas."""
    i = 0
    while True:
        m = ENTRY_START_RE.search(block, i)
        if not m:
            return
        j = m.end() - 1
        depth = 0
        for k in range(j, len(block)):
            if block[k] == "{":
                depth += 1
            elif block[k] == "}":
                depth -= 1
                if depth == 0:
                    yield block[m.end():k]
                    i = k + 1
                    break
        else:
            return


def parse_file(rel: str, text: str) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    unparsed: list[str] = []
    idx = 0
    for block in registry_blocks(text):
        for body in iter_entries(block):
            fields = {}
            for k, rx in FIELD_RES.items():
                m2 = rx.search(body)
                fields[k] = m2.group(1) if m2 else None
            # Una entrada sin Name pero con Operation (p.ej. DeleteKey) es una
            # operacion sobre la CLAVE, no sobre un valor: es `ok`, no `partial`.
            if fields["name"] is None and fields["operation"] and fields["path"]:
                fields["name"] = ""
                fields["type"] = fields["type"] or ""
                op = fields["operation"]
                hive, key = split_hive(fields["path"])
                rows.append({
                    "item_id": f"atlas:tweak-op:{rel}:{idx}",
                    "path": rel,
                    "hive": hive,
                    "key": key,
                    "value_name": "",
                    "value_type": "",
                    "value_sha256": hashlib.sha256(
                        f"{hive}|{key}||{op}".encode()).hexdigest(),
                    "parse_status": "ok",
                    "unparsed_reason": f"key-operation:{op}",
                })
                idx += 1
                continue
            if fields["path"] is None and fields["name"] is None:
                unparsed.append(rel)
                continue
            hive, key = split_hive(fields["path"] or "")
            vtype = (fields["type"] or "").lower()
            status = "ok"
            reason = ""
            if fields["path"] is None or fields["name"] is None:
                status = "partial"
                reason = "falta Path o Name"
            elif vtype and vtype not in KNOWN_TYPES:
                status = "partial"
                reason = f"tipo no reconocido: {vtype}"
            rows.append({
                "item_id": f"atlas:tweak-op:{rel}:{idx}",
                "path": rel,
                "hive": hive,
                "key": key,
                "value_name": fields["name"] or "",
                "value_type": fields["type"] or "",
                "value_sha256": hashlib.sha256(
                    f"{hive}|{key}|{fields['name'] or ''}".encode()).hexdigest(),
                "parse_status": status,
                "unparsed_reason": reason,
            })
            idx += 1
    return rows, unparsed


def targets(root: Path) -> list[Path]:
    return sorted((root / TWEAKS_DIR).rglob("*.psd1"))


def build(root: Path) -> tuple[list[dict], dict]:
    all_rows: list[dict] = []
    with_registry = 0
    unparsed_files: list[str] = []
    for p in targets(root):
        rel = str(p.relative_to(root)).replace("\\", "/")
        text = p.read_text(encoding="utf-8", errors="replace")
        if not REGISTRY_BLOCK_RE.search(text):
            continue
        with_registry += 1
        rows, unparsed = parse_file(rel, text)
        all_rows.extend(rows)
        unparsed_files.extend(unparsed)
    all_rows.sort(key=lambda r: r["item_id"])
    meta = {
        "ficheros_psd1": len(targets(root)),
        "ficheros_con_registry": with_registry,
        "operaciones": len(all_rows),
        "status": dict(sorted(Counter(r["parse_status"] for r in all_rows).items())),
        "hives": dict(sorted(Counter(r["hive"] for r in all_rows).items())),
        "tipos": dict(sorted(Counter(r["value_type"] for r in all_rows).items())),
        "unparsed": len(unparsed_files),
        "unparsed_files": sorted(set(unparsed_files)),
    }
    return all_rows, meta


def write_tsv(path: Path, rows: list[dict]) -> None:
    lines = ["\t".join(COLUMNS)]
    for r in rows:
        lines.append("\t".join(str(r.get(c, "")) for c in COLUMNS))
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ATLAS)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows, meta = build(args.root)
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "atlas-tweak-ops.tsv"
    write_tsv(out, rows)
    summary = {**meta, "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"psd1                  : {meta['ficheros_psd1']}")
        print(f"con bloque Registry   : {meta['ficheros_con_registry']} (esperado 154)")
        print(f"operaciones           : {meta['operaciones']}")
        for k, v in meta["status"].items():
            print(f"  status {k:8s}     : {v}")
        for k, v in meta["hives"].items():
            print(f"  hive   {k:8s}     : {v}")
        for k, v in meta["tipos"].items():
            print(f"  tipo   {k:8s}     : {v}")
        print(f"unparsed              : {meta['unparsed']}")
        for f in meta["unparsed_files"]:
            print(f"   ! {f}")
        print(f"sha256                : {summary['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
