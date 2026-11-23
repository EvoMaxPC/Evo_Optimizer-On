"""Tests de tools/ledger_extract/count_inventory.py.

Cubre: encabezado válido e inválido, cambio de clasificación, reinicio por
sección e invariante de suma. Usa ficheros temporales, no el inventario real.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "count_inventory.py"
spec = importlib.util.spec_from_file_location("count_inventory", SCRIPT)
ci = importlib.util.module_from_spec(spec)
sys.modules["count_inventory"] = ci
spec.loader.exec_module(ci)

HEADER = (
    "# INVENTARIO_USUARIO (fuente: mensaje original del responsable, sin editar)\n"
    "\n"
)


def build(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "inv.md"
    p.write_text(HEADER + body, encoding="utf-8")
    return p


# --- encabezados válidos e inválidos -----------------------------------------

def test_encabezado_valido_bullet(tmp_path):
    """'- TÍTULO EN MAYÚSCULAS' abre sección y el título pierde el guion."""
    p = build(tmp_path, "- LIMPIEZA Y ELIMINACIÓN\nfoo\nbar\n")
    sections, _ = ci.parse(p, "bullet")
    assert len(sections) == 1
    assert sections[0]["titulo"] == "LIMPIEZA Y ELIMINACIÓN"
    assert sections[0]["nonempty"] == 2


def test_encabezados_invalidos_no_abren_seccion(tmp_path):
    """Minúsculas, texto tras el título y líneas de contenido NO son encabezado."""
    p = build(
        tmp_path,
        "- LIMPIEZA Y ELIMINACIÓN\n"
        "- minúsculas no cuentan\n"
        "- MAYÚSCULAS con texto adicional.\n"
        "  - SANGRADO\n"
        "contenido\n",
    )
    sections, _ = ci.parse(p, "bullet")
    assert len(sections) == 1, [s["titulo"] for s in sections]
    # las 4 líneas no vacías restantes caen en el cuerpo de la sección 1
    assert sections[0]["nonempty"] == 4


def test_estilo_numeric_es_el_regex_pedido(tmp_path):
    """El estilo numeric usa ^[0-9]{1,2}\\.\\s+[A-ZÁÉÍÓÚÑ] y no casa con bullets."""
    p = build(tmp_path, "1. Alcance\ntexto\n- TÍTULO\nmás texto\n")
    numeric, _ = ci.parse(p, "numeric")
    bullet, _ = ci.parse(p, "bullet")
    assert [s["titulo"] for s in numeric] == ["Alcance"]
    assert [s["titulo"] for s in bullet] == ["TÍTULO"]


# --- clasificación ----------------------------------------------------------

def test_cambio_de_clasificacion(tmp_path):
    """WinUtil/AtlasOS exactos y 'EVO CLEAN...'/'Capacidad EVO a desarrollar:'
    cambian el cubo; el resto va a general."""
    p = build(
        tmp_path,
        "- SECCIÓN\n"
        "nota general\n"
        "WinUtil\n"
        "a\n"
        "b\n"
        "AtlasOS\n"
        "c\n"
        "EVO CLEAN\n"
        "d\n"
        "Capacidad EVO a desarrollar: algo\n"
        "e\n"
        "WinUtil con texto extra no cambia\n",
    )
    sec = ci.parse(p, "bullet")[0][0]
    # La línea del sub-encabezado cuenta como línea no vacía de su propio cubo
    # (convención declarada en el docstring del script).
    assert sec["general"] == 1   # "nota general" (antes de todo sub-encabezado)
    assert sec["winutil"] == 3   # "WinUtil" + a + b
    assert sec["atlas"] == 2     # "AtlasOS" + c
    assert sec["evo"] == 5       # "EVO CLEAN" + d + "Capacidad EVO..." + e
                                 # + "WinUtil con texto extra" (heredó evo)
    assert sec["nonempty"] == 11

def test_la_linea_de_subencabezado_cuenta_en_su_cubo(tmp_path):
    """Convención: 'WinUtil' como línea cuenta 1 en winutil (no es solo un selector)."""
    p = build(tmp_path, "- SECCIÓN\nWinUtil\natlas\nAtlasOS\nx\n")
    sec = ci.parse(p, "bullet")[0][0]
    assert sec["winutil"] == 2   # "WinUtil" + "atlas"
    assert sec["atlas"] == 2     # "AtlasOS" + "x"


def test_winutil_solo_si_es_exacto(tmp_path):
    """'WinUtil ' con espacios o 'WinUtil extra' NO cambia el cubo."""
    p = build(tmp_path, "- SECCIÓN\nWinUtil\nuno\nWinUtil extra\ndos\n")
    sec = ci.parse(p, "bullet")[0][0]
    # "WinUtil" abre el bloque y las líneas siguientes lo heredan:
    # "uno", "WinUtil extra" y "dos" cuentan como winutil.
    assert sec["winutil"] == 4
    assert sec["general"] == 0


# --- reinicio por sección ---------------------------------------------------

def test_reinicio_de_clasificacion_por_seccion(tmp_path):
    """Tras un encabezado, el cubo vuelve a general aunque la anterior acabara en evo."""
    p = build(
        tmp_path,
        "- PRIMERA\nEVO CLEAN\ndentro evo\n"
        "- SEGUNDA\ntras reinicio\n",
    )
    sections, _ = ci.parse(p, "bullet")
    assert len(sections) == 2
    assert sections[0]["evo"] == 2      # "EVO CLEAN" + "dentro evo"
    assert sections[1]["general"] == 1  # "tras reinicio"
    assert sections[1]["evo"] == 0


# --- invariante -------------------------------------------------------------

def test_invariante_suma_en_fichero_sintetico(tmp_path):
    """suma de cubos == lineas_no_vacias en todas las filas."""
    p = build(
        tmp_path,
        "- A\nWinUtil\nx\ny\nAtlasOS\nz\n"
        "- B\nEVO CLEAN\nq\nlibre\n",
    )
    sections, _ = ci.parse(p, "bullet")
    for s in sections:
        assert s["winutil"] + s["atlas"] + s["evo"] + s["general"] == s["nonempty"]
        assert ci.invariant_ok(s)


def test_invariante_sobre_el_inventario_real_si_existe():
    """Si el inventario real está importado, la invariante debe cumplirse."""
    real = ci.DEFAULT_MD
    if not real.is_file() or "<<<PEGA" in real.read_text(encoding="utf-8"):
        pytest.skip("inventario real no importado todavía")
    sections, _ = ci.parse(real, "bullet")
    assert sections, "no se detectaron secciones"
    for s in sections:
        assert ci.invariant_ok(s), f"invariante rota en sección {s['numero']}"
