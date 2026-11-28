#!/usr/bin/env python3
"""Clona/reproduce las fuentes fijadas en inventory/upstream.lock.json.

Solo stdlib (Python 3.11). No copia código al repositorio de EVO: el destino por
defecto es /tmp/upstream/<nombre>, siempre fuera del árbol de trabajo.

Uso:
    python3 tools/ledger_extract/fetch_upstream.py                 # todas
    python3 tools/ledger_extract/fetch_upstream.py --only winutil
    python3 tools/ledger_extract/fetch_upstream.py --dest /tmp/upstream --json
    python3 tools/ledger_extract/fetch_upstream.py --lock ruta/al/lock.json

Garantías:
  * Verifica `git rev-parse HEAD == sha` del lock; si no, FALLA con exit 1.
  * Idempotente: si el clon ya está en el SHA correcto, no hace red.
  * Fallback documentado si el fetch por SHA es rechazado:
        --depth 1 origin <sha>  ->  --depth 50 (rama por defecto)  ->  clon completo
    El fallback usado se declara en el informe de salida (campo `method`).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_LOCK = Path(__file__).resolve().parents[2] / "inventory" / "upstream.lock.json"
DEFAULT_DEST = Path("/tmp/upstream")

# Marcas de fallo típicas de un servidor que no permite fetch por SHA arbitrario
SHA_FETCH_ERRORS = (
    "Server does not allow request for unadvertised object",
    "not our ref",
    "couldn't find remote ref",
    "unable to fetch",
    "remote error: upload-pack",
)


class FetchError(RuntimeError):
    pass


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True
    )
    if check and proc.returncode != 0:
        raise FetchError(
            f"comando falló ({proc.returncode}): {' '.join(cmd)}\n"
            f"--- stdout ---\n{proc.stdout.strip()}\n--- stderr ---\n{proc.stderr.strip()}"
        )
    return proc


def git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return run(["git", *args], cwd=cwd, check=check)


def head_sha(repo: Path) -> str:
    return git("rev-parse", "HEAD", cwd=repo).stdout.strip()


def ensure_repo(repo: Path, url: str) -> None:
    """git init + remote add (o reutiliza el directorio si ya es un repo)."""
    if (repo / ".git").is_dir():
        remotes = git("remote", cwd=repo, check=False).stdout.split()
        if "origin" not in remotes:
            git("remote", "add", "origin", url, cwd=repo)
        else:
            git("remote", "set-url", "origin", url, cwd=repo)
        return
    if repo.exists():
        raise FetchError(f"{repo} existe y no es un repositorio git; bórralo a mano")
    repo.mkdir(parents=True)
    git("init", "-q", cwd=repo)
    git("remote", "add", "origin", url, cwd=repo)


def try_fetch_sha(repo: Path, sha: str, depth: int | None) -> tuple[bool, str]:
    args = ["fetch", "--no-tags", "--quiet"]
    if depth:
        args += ["--depth", str(depth)]
    args += ["origin", sha]
    proc = git(*args, cwd=repo, check=False)
    if proc.returncode == 0:
        return True, "ok"
    blob = (proc.stdout + proc.stderr).strip()
    for marker in SHA_FETCH_ERRORS:
        if marker in blob:
            return False, blob.splitlines()[-1][:300]
    raise FetchError(f"fetch por SHA falló por motivo no clasificado:\n{blob}")


def fetch_and_checkout(repo: Path, sha: str) -> tuple[str, str]:
    """Devuelve (método usado, sha verificado)."""
    # Idempotencia: ya estamos en el SHA pedido.
    if (repo / ".git").is_dir():
        cur = git("rev-parse", "HEAD", cwd=repo, check=False)
        if cur.returncode == 0 and cur.stdout.strip() == sha:
            return "cache", head_sha(repo)

    ok, detail = try_fetch_sha(repo, sha, depth=1)
    method = "fetch --depth 1 <sha>"
    if not ok:
        sys.stderr.write(f"[fallback] depth1 por SHA rechazado: {detail}\n")
        ok, detail = try_fetch_sha(repo, sha, depth=50)
        method = "fetch --depth 50 (rama por defecto)"
        if not ok:
            sys.stderr.write(f"[fallback] depth50 rechazado: {detail}\n")
            git("fetch", "--no-tags", "--quiet", "origin", cwd=repo)
            method = "fetch completo (sin --depth)"

    git("checkout", "-q", "--force", "FETCH_HEAD", cwd=repo)
    return method, head_sha(repo)


def process(source: dict, dest: Path) -> dict:
    name, url, sha = source["name"], source["url"], source["sha"]
    repo = dest / name
    result = {"name": name, "repo": source["repo"], "expected_sha": sha, "path": str(repo)}
    try:
        ensure_repo(repo, url)
        method, actual = fetch_and_checkout(repo, sha)
    except FetchError as exc:
        result.update(status="FAIL", method="n/a", actual_sha=None, error=str(exc))
        return result

    result.update(method=method, actual_sha=actual, status="OK" if actual == sha else "SHA_MISMATCH")
    if actual == sha:
        result["commit_date"] = git(
            "log", "-1", "--format=%ad", "--date=short", cwd=repo
        ).stdout.strip()
        result["commit_subject"] = git(
            "log", "-1", "--format=%s", cwd=repo
        ).stdout.strip()
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    ap.add_argument("--only", action="append", help="nombre de fuente (repetible)")
    ap.add_argument("--json", action="store_true", help="salida JSON")
    ap.add_argument("--clean", action="store_true", help="borra el destino antes de empezar")
    args = ap.parse_args(argv)

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if lock.get("schema") != 1:
        print(f"lock schema no soportado: {lock.get('schema')}", file=sys.stderr)
        return 2

    sources = lock["sources"]
    if args.only:
        wanted = set(args.only)
        sources = [s for s in sources if s["name"] in wanted]
        missing = wanted - {s["name"] for s in sources}
        if missing:
            print(f"fuente(s) no encontradas en el lock: {sorted(missing)}", file=sys.stderr)
            return 2

    if args.clean and args.dest.exists():
        shutil.rmtree(args.dest)
    args.dest.mkdir(parents=True, exist_ok=True)

    results = [process(s, args.dest) for s in sources]

    if args.json:
        print(json.dumps({"dest": str(args.dest), "results": results}, indent=2, ensure_ascii=False))
    else:
        print(f"destino: {args.dest}")
        for r in results:
            print(f"\n[{r['status']}] {r['name']}  ({r['repo']})")
            print(f"  path    : {r['path']}")
            print(f"  esperado: {r['expected_sha']}")
            print(f"  real    : {r.get('actual_sha') or '-'}")
            print(f"  método  : {r['method']}")
            if r.get("commit_date"):
                print(f"  commit  : {r['commit_date']} {r['commit_subject']}")
            if r.get("error"):
                print(f"  ERROR   : {r['error']}")

    return 0 if all(r["status"] == "OK" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
