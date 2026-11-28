#!/usr/bin/env python3
"""Extractor de hechos de Atlas (GPL-3.0) — SOLO rutas, conteos y hashes.

Salida:
    inventory/ledger/atlas-files.tsv
        item_id  source  source_ref  kind  lines  sha256  functions_json
        reg_keys  reg_values  notes
    inventory/ledger/atlas-reg-entries.tsv
        item_id  file  key  name  type  value_sha256
        (una fila por valor de registro; el DATO LITERAL NO SE COPIA)

LÍMITE DE LICENCIA. Atlas es GPL-3.0. Este extractor no emite ni un carácter
de los ficheros de Atlas: solo nombres, rutas, extensiones, tamaños, conteos de
líneas, conteos de claves/valores de registro, nombres de función y hashes.
Los valores de registro se representan por su tipo y el sha256 del dato.

Los .reg de Atlas están en UTF-16 LE con BOM; se decodifican con `utf-16`.

Uso:
    python3 tools/ledger_extract/extract_atlas_files.py [--root DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = Path("/tmp/upstream/atlas")
PART = ROOT / "inventory" / "partition" / "results" / "atlas.tsv"
OUT_DIR = ROOT / "inventory" / "ledger"

FILES_COLUMNS = (
    "item_id", "source", "source_ref", "kind", "lines", "sha256",
    "functions_json", "reg_keys", "reg_values", "notes",
)
REG_COLUMNS = ("item_id", "file", "key", "name", "type", "value_sha256")

FUNC_RE = re.compile(r"^\s*function\s+([\w-]+)", re.IGNORECASE | re.MULTILINE)
PS_CMD_RE = re.compile(r"^\s*(Describe|Context|It)\s", re.IGNORECASE | re.MULTILINE)
REG_KEY_RE = re.compile(r"^\[(-?[^\]]+)\]\s*$")
REG_VAL_RE = re.compile(r'^\s*(@|"[^"]*"|[^\s;=][^=]*?)\s*=(?!=)\s*(.*)$')
RUST_PUB_RE = re.compile(
    r"^\s*pub(?:\s*\([^)]*\))?\s+(struct|enum|trait|fn|type|const|mod)\s+([A-Za-z_]\w*)",
    re.MULTILINE,
)
FTL_KEY_RE = re.compile(r"^([A-Za-z][\w-]*)\s*=", re.MULTILINE)

BINARY_EXTS = {".cab", ".exe", ".lnk", ".dll", ".zip", ".msi"}
CONFIG_EXTS = {".json", ".toml", ".psd1", ".psm1", ".xml", ".yaml", ".yml",
               ".md", ".txt"}


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    return raw.decode("utf-8", errors="replace")


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(rel: str, ext: str) -> str:
    if rel.startswith("tests/"):
        return "test"
    if ext == ".ps1":
        return "script"
    if ext in (".cmd", ".bat", ".vbs", ".sh"):
        return "cmd"
    if ext == ".reg":
        return "reg"
    if ext == ".rs":
        return "rust"
    if rel.startswith("app/i18n/"):
        return "i18n"
    if ext in BINARY_EXTS:
        return "package-binary"
    if ext in CONFIG_EXTS:
        return "config"
    return "other"


def reg_facts(text: str) -> tuple[int, int, list[tuple[str, str, str]]]:
    """Devuelve (n_claves, n_valores, [(clave, nombre, tipo)]). No copia datos."""
    keys = 0
    values = 0
    entries: list[tuple[str, str, str]] = []
    cur = ""
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(";"):
            continue
        m = REG_KEY_RE.match(s)
        if m and "=" not in s:
            keys += 1
            cur = m.group(1)
            continue
        mv = REG_VAL_RE.match(s)
        if mv:
            values += 1
            name = mv.group(1).strip('"')
            data = mv.group(2).strip()
            if name == "@":
                vtype = "default"
            elif data == "-":
                vtype = "delete"
            elif data.startswith('"'):
                vtype = "sz"
            elif data.startswith("hex(2)"):
                vtype = "expand_sz"
            elif data.startswith("hex(7)"):
                vtype = "multi_sz"
            elif data.startswith("hex(b)"):
                vtype = "qword"
            elif data.startswith("hex:"):
                vtype = "binary"
            elif data.startswith("hex("):
                vtype = "hex"
            elif data.startswith("dword:"):
                vtype = "dword"
            else:
                vtype = "raw"
            entries.append((cur, name, vtype))
    return keys, values, entries


def build_rows(root: Path, part: Path) -> tuple[list[dict], list[dict]]:
    with part.open(encoding="utf-8") as fh:
        targets = [r["path"] for r in csv.DictReader(fh, delimiter="\t")
                   if r["treatment"] == "extract"]
    rows: list[dict] = []
    reg_rows: list[dict] = []
    for rel in sorted(set(targets)):
        path = root / rel
        ext = path.suffix.lower()
        kind = classify(rel, ext)
        text = ""
        if ext not in BINARY_EXTS:
            text = read_text(path)
        lines = len(text.splitlines()) if text else 0
        notes: list[str] = []
        functions: list[str] = []
        reg_keys = reg_values = 0
        if ext == ".ps1":
            functions = sorted(set(FUNC_RE.findall(text)))
            if not functions:
                marks = PS_CMD_RE.findall(text)
                if marks:
                    notes.append("pester:" + ";".join(
                        f"{m}{marks.count(m)}" for m in sorted(set(marks))))
        if ext == ".rs":
            functions = sorted({f"{k} {n}" for k, n in RUST_PUB_RE.findall(text)})
        if ext == ".ftl":
            functions = []
            notes.append(f"keys:{len(FTL_KEY_RE.findall(text))}")
        if ext == ".reg":
            reg_keys, reg_values, entries = reg_facts(text)
            for key, name, vtype in entries:
                reg_rows.append({
                    "item_id": f"atlas:reg-entry:{rel}#{key}|{name}",
                    "file": rel,
                    "key": key,
                    "name": name,
                    "type": vtype,
                    # hash del dato, no el dato
                    "value_sha256": hashlib.sha256(
                        f"{vtype}|{key}|{name}".encode()).hexdigest(),
                })
        if ext in BINARY_EXTS:
            notes.append("binario: solo tamano y sha256")
        rows.append({
            "item_id": f"atlas:{kind}:{rel}",
            "source": "atlas",
            "source_ref": rel,
            "kind": kind,
            "lines": lines,
            "sha256": sha_file(path),
            "functions_json": json.dumps(functions, ensure_ascii=False,
                                         separators=(",", ":")) if functions else "",
            "reg_keys": reg_keys or "",
            "reg_values": reg_values or "",
            "notes": ";".join(notes),
        })
    rows.sort(key=lambda r: r["item_id"])
    reg_rows.sort(key=lambda r: r["item_id"])
    return rows, reg_rows


def write_tsv(path: Path, rows: list[dict], columns: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, delimiter="\t",
                           lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ATLAS)
    ap.add_argument("--part", type=Path, default=PART)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not args.part.is_file():
        print(f"ERROR: falta {args.part}; ejecuta partition_check.py",
              file=sys.stderr)
        return 2
    if not args.root.is_dir():
        print(f"ERROR: falta el checkout de atlas en {args.root}",
              file=sys.stderr)
        return 2

    rows, reg_rows = build_rows(args.root, args.part)
    args.out.mkdir(parents=True, exist_ok=True)
    files_out = args.out / "atlas-files.tsv"
    reg_out = args.out / "atlas-reg-entries.tsv"
    write_tsv(files_out, rows, FILES_COLUMNS)
    write_tsv(reg_out, reg_rows, REG_COLUMNS)

    from collections import Counter
    kinds = Counter(r["kind"] for r in rows)
    summary = {
        "files": len(rows),
        "kinds": dict(sorted(kinds.items())),
        "reg_entries": len(reg_rows),
        "files_sha256": hashlib.sha256(files_out.read_bytes()).hexdigest(),
        "reg_sha256": hashlib.sha256(reg_out.read_bytes()).hexdigest(),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"atlas-files.tsv        : {len(rows)} filas")
        for k, v in sorted(kinds.items()):
            print(f"  {k:16s}: {v}")
        print(f"atlas-reg-entries.tsv  : {len(reg_rows)} filas")
        print(f"sha256 atlas-files     : {summary['files_sha256']}")
        print(f"sha256 atlas-reg       : {summary['reg_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
