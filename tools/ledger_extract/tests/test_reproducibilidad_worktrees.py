"""Tests para reproducibilidad_worktrees.py (paso 12g/G4).

Comprueba que ejecutar un script del repo en worktrees temporales de la misma
sha produce salida idéntica (reproducible), y que shas distintas pueden diferir.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "ledger_extract" / "reproducibilidad_worktrees.py"


def _run() -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT)],
                          capture_output=True, text=True, cwd=ROOT)


def test_ejecuta_sin_errores() -> None:
    resultado = _run()
    assert resultado.returncode == 0, resultado.stderr
    assert "reproducibilidad worktrees: OK" in resultado.stdout


def test_pares_iguales_son_reproducibles() -> None:
    """Pares iguales (A/A) deben producir salida idéntica."""
    resultado = _run()
    assert resultado.returncode == 0, resultado.stderr
    for par in ("830290c/830290c", "0d72efa/0d72efa", "HEAD/HEAD"):
        assert f"{par}: reproducible" in resultado.stdout, (
            f"{par} no es reproducible: {resultado.stdout}"
        )


def test_par_distinto_puede_diferir() -> None:
    resultado = _run()
    assert resultado.returncode == 0, resultado.stderr
    assert "830290c/0d72efa: difiere" in resultado.stdout
