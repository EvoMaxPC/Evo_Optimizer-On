"""Tests para report_specified_history.py.

Verifica que el script lee correctamente los catalogos de cada sha
y produce las tablas (a) y (b) con los valores esperados.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "ledger_extract" / "report_specified_history.py"

SHA_FIJAS = [
    "830290c",
    "0d72efa",
    "cb75abe34a4feb256f57f8de76b03bbd05a08e0b",
    "231564b7764499d086eb6c06a31af29a79b95c39",
]


def _run(extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def _tabla_b(resultado: subprocess.CompletedProcess) -> list[list[str]]:
    """Extrae las filas de la tabla (b) como lista de celdas."""
    lineas = resultado.stdout.splitlines()
    en_tabla_b = False
    filas: list[list[str]] = []
    for linea in lineas:
        if "=== (b) State de cada capacidad por commit ===" in linea:
            en_tabla_b = True
            continue
        if not en_tabla_b:
            continue
        if not linea.strip() or linea.startswith("-"):
            continue
        if linea.startswith("id |"):
            continue
        celdas = [c.strip() for c in linea.split("|")]
        filas.append(celdas)
    return filas


def test_ejecuta_sin_errores() -> None:
    """El script debe ejecutarse con codigo de salida 0."""
    resultado = _run()
    assert resultado.returncode == 0, resultado.stderr


def test_tiene_seccion_a() -> None:
    """La salida debe incluir la seccion (a) con motivo literal."""
    resultado = _run()
    assert "=== (a) Capacidades Specified en HEAD (motivo literal) ===" in resultado.stdout


def test_tiene_seccion_b() -> None:
    """La salida debe incluir la seccion (b) con estado por commit."""
    resultado = _run()
    assert "=== (b) State de cada capacidad por commit ===" in resultado.stdout


def test_cabecera_tabla_a() -> None:
    """La tabla (a) debe tener la cabecera correcta (con acento en seccion)."""
    resultado = _run()
    assert "id | secci\u00f3n | motivo literal" in resultado.stdout


def test_cabecera_tabla_b() -> None:
    """La tabla (b) debe incluir las 5 columnas de sha."""
    resultado = _run()
    for sha in SHA_FIJAS + ["HEAD"]:
        assert sha in resultado.stdout


def test_19_specified_en_head() -> None:
    """HEAD debe tener exactamente 18 capacidades Specified (tras 12c/G2:
    solo ntp-servers paso a Implemented; hibernation.hide, mitigations.disable
    y las otras tres siguen Specified porque el pin deja efectos de maquina no
    expresables)."""
    resultado = _run()
    assert "Total Specified en HEAD: 18" in resultado.stdout


def test_seis_specified_de_seccion9() -> None:
    """Las 6 capacidades de seccion 9 deben estar en Specified en HEAD."""
    resultado = _run()
    salida = resultado.stdout
    for cid in [
        "system.hibernation.hide",
        "system.location.consent-deny",
        "system.mitigations.disable",
        "system.oem-information.identify",
        "system.registry-backup.enable",
    ]:
        # Busca la fila en la tabla (a): "cid | sec9 | motivo..."
        assert f"{cid} | sec9 |" in salida, (
            f"{cid} no encontrado como Specified sec9 en la salida"
        )


def test_estado_por_commit_es_consistente() -> None:
    """Cada fila de la tabla (b) debe tener 6 celdas (id + 5 shas)."""
    resultado = _run()
    filas = _tabla_b(resultado)
    assert len(filas) > 0, "la tabla (b) no tiene filas"
    for celdas in filas:
        assert len(celdas) == 6, f"esperaba 6 celdas, obtuvo {len(celdas)}: {celdas}"
        for celda in celdas[1:]:
            assert celda in (
                "Implemented",
                "Specified",
                "Stub",
                "no existía",
            ), f"estado inesperado '{celda}' en: {celdas}"


def test_ntp_servers_estado_por_commit() -> None:
    """system.time.ntp-servers: no es Specified en commits antiguos, sí en HEAD."""
    resultado = _run()
    filas = _tabla_b(resultado)
    for celdas in filas:
        if celdas[0] == "system.time.ntp-servers":
            # celdas[1]=830290c, celdas[2]=0d72efa, celdas[3]=cb75abe, celdas[4]=231564b, celdas[5]=HEAD
            # 0d72efa: Specified, cb75abe: Implemented, 231564b: Implemented, HEAD: Specified
            assert celdas[2] == "Specified", f"0d72efa debería tener ntp-servers como Specified: {celdas}"
            assert celdas[3] != "Specified", f"cb75abe no debería tener ntp-servers como Specified: {celdas}"
            assert celdas[4] != "Specified", f"231564b no debería tener ntp-servers como Specified: {celdas}"
            assert celdas[5] == "Implemented", f"HEAD debe tener ntp-servers como Implemented (G2): {celdas}"
            return
    pytest.fail("no se encontro la fila de system.time.ntp-servers en la tabla (b)")


def test_retracta_afirmacion_12c() -> None:
    """El informe 12c afirmaba 4 Specified en sec9 en 0d72efa y cb75abe; es falso."""
    resultado = _run()
    filas = _tabla_b(resultado)
    especificado_0d72efa_sec9: list[str] = []
    especificado_cb75abe_sec9: list[str] = []
    for celdas in filas:
        cid = celdas[0]
        if cid.startswith("system."):
            if celdas[2] == "Specified":  # 0d72efa
                especificado_0d72efa_sec9.append(cid)
            if celdas[3] == "Specified":  # cb75abe
                especificado_cb75abe_sec9.append(cid)
    assert len(especificado_0d72efa_sec9) != 4, (
        f"0d72efa no tiene 4 Specified en sec9; tiene {len(especificado_0d72efa_sec9)}: "
        f"{especificado_0d72efa_sec9}"
    )
    assert len(especificado_cb75abe_sec9) != 4, (
        f"cb75abe no tiene 4 Specified en sec9; tiene {len(especificado_cb75abe_sec9)}: "
        f"{especificado_cb75abe_sec9}"
    )


def test_salida_escrita_con_out() -> None:
    """Con --out el script escribe al fichero indicado."""
    destino = ROOT / "tmp_report_specified_history.txt"
    if destino.exists():
        destino.unlink()
    try:
        resultado = _run(["--out", str(destino)])
        assert resultado.returncode == 0, resultado.stderr
        assert destino.exists()
        contenido = destino.read_text(encoding="utf-8")
        assert "=== (a) Capacidades Specified en HEAD (motivo literal) ===" in contenido
        assert "=== (b) State de cada capacidad por commit ===" in contenido
    finally:
        if destino.exists():
            destino.unlink()
