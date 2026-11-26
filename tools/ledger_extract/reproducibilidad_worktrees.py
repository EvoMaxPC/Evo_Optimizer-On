#!/usr/bin/env python3
"""
Comprobación de reproducibilidad (paso 12g/G4) mediante worktrees temporales.

Para cada par de commits (A, B) se checkea A y B en worktrees temporales bajo
`.git/worktrees/repro-<sha>-<i>`, se ejecuta un script del repo en cada uno y
se compara la salida:

- Pares iguales (A == A): la salida DEBE ser idéntica (reproducible).
- Pares distintos (A != B): la salida PUEDE diferir (se registra la diferencia).

Uso:
    python3 tools/ledger_extract/reproducibilidad_worktrees.py
    python3 tools/ledger_extract/reproducibilidad_worktrees.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WTREE_ROOT = ROOT / ".git" / "worktrees"

# Script del repo que se ejecuta en cada worktree para medir reproducibilidad.
# Es `report_specified_history.py` (paso 12g/G1): lee catalogos con `git show`
# y es determinista para una misma sha.
SCRIPT = ROOT / "tools" / "ledger_extract" / "report_specified_history.py"

# Parejas (A, B) a comprobar. Las iguales validan reproducibilidad; la cruzada
# valida que el script detecta cambios entre commits.
PARES = [
    ("830290c", "830290c"),
    ("830290c", "0d72efa"),
    ("0d72efa", "0d72efa"),
    ("HEAD", "HEAD"),
]


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))


def _worktree_dir(sha: str, idx: int) -> Path:
    return WTREE_ROOT / f"repro-{sha}-{idx}"


def _fetch_sha(sha: str) -> None:
    """Asegura que el objeto `sha` esté disponible localmente.

    El CI clona con `fetch-depth: 1`, que solo trae el commit del puntaje;
    los commits históricos de la pareja (830290c, 0d72efa...) no estan en el
    clone superficial. Se trae explícitamente cada sha (y sus ancestros) desde
    origin antes de crear el worktree.
    """
    _run(["git", "fetch", "origin", sha], ROOT)


def _checkout(sha: str, idx: int) -> Path:
    """Checkea `sha` en un worktree temporal y devuelve su ruta."""
    wdir = _worktree_dir(sha, idx)
    if wdir.is_dir():
        _run(["git", "worktree", "remove", "--force", str(wdir)], ROOT)
    _fetch_sha(sha)
    resultado = _run(
        ["git", "worktree", "add", "--detach", str(wdir), sha], ROOT
    )
    if resultado.returncode != 0:
        raise SystemExit(
            f"no se pudo hacer worktree de {sha}: {resultado.stderr}"
        )
    return wdir


def _ejecutar_en(wdir: Path) -> str:
    """Ejecuta el script del repo en `wdir` y devuelve su stdout."""
    resultado = _run([sys.executable, str(SCRIPT)], wdir)
    if resultado.returncode != 0:
        raise SystemExit(
            f"el script falló en {wdir}: {resultado.stderr}"
        )
    return resultado.stdout


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def limpiar() -> None:
    """Elimina los worktrees temporales de ejecuciones previas."""
    if WTREE_ROOT.is_dir():
        for wdir in WTREE_ROOT.iterdir():
            if wdir.is_dir() and wdir.name.startswith("repro-"):
                _run(["git", "worktree", "remove", "--force", str(wdir)], ROOT)


def medir() -> list[dict]:
    filas: list[dict] = []
    limpiar()
    for a, b in PARES:
        wa = _checkout(a, 0)
        wb = _checkout(b, 1)
        try:
            salida_a = _ejecutar_en(wa)
            salida_b = _ejecutar_en(wb)
        finally:
            _run(["git", "worktree", "remove", "--force", str(wa)], ROOT)
            _run(["git", "worktree", "remove", "--force", str(wb)], ROOT)
        igual = salida_a == salida_b
        filas.append({
            "par": f"{a}/{b}",
            "igual": igual,
            "sha_a": _sha(salida_a),
            "sha_b": _sha(salida_b),
        })
    return filas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="no escribe: compara con el resultado esperado y sale 1 si difiere")
    args = parser.parse_args(argv)

    filas = medir()
    ok = True
    for fila in filas:
        a, b = fila["par"].split("/")
        mismos_commits = a == b
        if mismos_commits and not fila["igual"]:
            print(f"ERROR: {fila['par']} debería ser reproducible pero no lo es",
                  file=sys.stderr)
            ok = False
        print(f"{fila['par']}: {'reproducible' if fila['igual'] else 'difiere'} "
              f"(sha256_a={fila['sha_a'][:12]} sha256_b={fila['sha_b'][:12]})")

    if not ok:
        return 1
    print("reproducibilidad worktrees: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
