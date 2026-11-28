#!/usr/bin/env python3
"""Lista todos los ficheros de cada upstream en su SHA fijado (REQ-005).

Lee inventory/upstream.lock.json, verifica que el clon cacheado está en el SHA
del lock y escribe inventory/upstream/<repo>.files.tsv con las columnas:

    path    size    blob_sha    ext    top_dir

- path     : ruta relativa con '/' (como la reporta git ls-tree -r)
- size     : tamaño del blob en bytes
- blob_sha : sha1 del blob en git
- ext      : extensión en minúsculas sin punto ('' si no tiene; '.gitignore' -> '')
- top_dir  : primer componente de la ruta ('.' si el fichero está en la raíz)

Ningún fichero se omite: el TSV es la base de la partición (REQ-005).

Uso:
    python3 tools/ledger_extract/list_files.py
    python3 tools/ledger_extract/list_files.py --only winutil --json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCK = ROOT / "inventory" / "upstream.lock.json"
DEFAULT_DEST = Path("/tmp/upstream")
DEFAULT_OUT = ROOT / "inventory" / "upstream"

COLUMNS = ("path", "size", "blob_sha", "ext", "top_dir")


class ListError(RuntimeError):
    pass


def git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], cwd=str(cwd), text=True, capture_output=True)
    if check and proc.returncode != 0:
        raise ListError(f"git {' '.join(args)} falló: {proc.stderr.strip()}")
    return proc


def head_sha(repo: Path) -> str:
    return git(["rev-parse", "HEAD"], repo).stdout.strip()


def extension(path: str) -> str:
    name = PurePosixPath(path).name
    if name.startswith(".") and name.count(".") == 1:
        return ""  # .gitignore, .editorconfig
    suffix = PurePosixPath(path).suffix
    return suffix[1:].lower() if suffix else ""


def top_dir(path: str) -> str:
    parts = PurePosixPath(path).parts
    return parts[0] if len(parts) > 1 else "."


def list_tree(repo: Path) -> list[dict]:
    """git ls-tree -r -l: <mode> SP <type> SP <object> SP+ <size> TAB <path>."""
    out = git(["ls-tree", "-r", "-l", "--full-tree", "HEAD"], repo).stdout
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        meta, _, path = line.partition("\t")
        fields = meta.split()
        if len(fields) < 4:
            raise ListError(f"línea de ls-tree inesperada: {line!r}")
        obj = fields[2]
        size = fields[3]
        rows.append(
            {
                "path": path,
                "size": int(size) if size.isdigit() else 0,
                "blob_sha": obj,
                "ext": extension(path),
                "top_dir": top_dir(path),
            }
        )
    return rows


def write_tsv(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(COLUMNS)]
    for r in rows:
        lines.append("\t".join(str(r[c]) for c in COLUMNS))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def process(source: dict, dest: Path, out_dir: Path) -> dict:
    name = source["name"]
    repo = dest / name
    expected = source["sha"]
    if not (repo / ".git").is_dir():
        raise ListError(f"clon ausente en {repo}; ejecuta fetch_upstream.py primero")
    actual = head_sha(repo)
    if actual != expected:
        raise ListError(
            f"{name}: SHA del clon {actual} != SHA del lock {expected}"
        )
    rows = list_tree(repo)
    tsv = out_dir / f"{name}.files.tsv"
    write_tsv(rows, tsv)
    exts: dict[str, int] = {}
    for r in rows:
        exts[r["ext"] or "(sin extensión)"] = exts.get(r["ext"] or "(sin extensión)", 0) + 1
    return {
        "name": name,
        "repo": source["repo"],
        "sha_expected": expected,
        "sha_actual": actual,
        "sha_match": True,
        "files": len(rows),
        "bytes": sum(r["size"] for r in rows),
        "tsv": str(tsv),
        "extensions": dict(sorted(exts.items(), key=lambda kv: -kv[1])),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--only", action="append")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("schema") != 1:
        print(f"lock schema no soportado: {lock.get('schema')}", file=sys.stderr)
        return 2
    sources = lock["sources"]
    if args.only:
        sources = [s for s in sources if s["name"] in set(args.only)]

    results, failure = [], False
    for s in sources:
        try:
            results.append(process(s, args.dest, args.out))
        except ListError as exc:
            failure = True
            results.append({"name": s["name"], "status": "ERROR", "error": str(exc)})

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            if "error" in r:
                print(f"[ERROR] {r['name']}: {r['error']}")
                continue
            print(f"[OK] {r['name']} ({r['repo']})")
            print(f"  sha lock/clon : {r['sha_expected']} == {r['sha_actual']}")
            print(f"  ficheros      : {r['files']}  ({r['bytes']} bytes)")
            print(f"  tsv           : {r['tsv']}")
            top = list(r["extensions"].items())[:8]
            print("  extensiones   : " + ", ".join(f"{e}={n}" for e, n in top))
    return 1 if failure else 0


if __name__ == "__main__":
    sys.exit(main())
