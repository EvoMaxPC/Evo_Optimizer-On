#!/usr/bin/env python3
"""
Informe de capacidades `Specified` por commit.

Para cada sha fijada (830290c, 0d72efa, cb75abe..., 231564b...) y para HEAD,
lee los ficheros `catalog/capabilities/*.json` con `git show <sha>:<ruta>`
y produce:

(a) tabla "id | sección | motivo literal" de las capacidades `Specified` de HEAD.
    El motivo es la frase exacta de `description`/`provenance` que declara
    lo omitido (R1), completa, no cortada.

(b) tabla "id | 0d72efa | cb75abe | 231564b | HEAD" con el `State` de cada
    capacidad en cada commit (o "no existía" si la capacidad no estaba).

Determinista: ordena por id y por nombre de fichero. Solo stdlib.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SHA_FIJAS = [
    "830290c",
    "0d72efa",
    "cb75abe34a4feb256f57f8de76b03bbd05a08e0b",
    "231564b7764499d086eb6c06a31af29a79b95c39",
]

CATALOG_GLOBS = [
    "catalog/capabilities/section1_cleanup.json",
    "catalog/capabilities/section2_debloat.json",
    "catalog/capabilities/section3_telemetry.json",
    "catalog/capabilities/section9_system_registry.json",
    "catalog/capabilities/section10_explorer_ui.json",
]


def _git_show(sha: str, ruta: str) -> str | None:
    """Devuelve el contenido de <ruta> en <sha> mediante git show, o None si no existe."""
    try:
        resultado = subprocess.run(
            ["git", "show", f"{sha}:{ruta}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return resultado.stdout
    except subprocess.CalledProcessError:
        return None


def _leer_capacidades(sha: str | None) -> dict[str, dict]:
    """Lee todos los JSON de capacidades para una sha (None = HEAD/disco)."""
    resultado: dict[str, dict] = {}
    for ruta in CATALOG_GLOBS:
        if sha is None:
            p = Path(ruta)
            if not p.is_file():
                continue
            texto = p.read_text(encoding="utf-8")
        else:
            texto = _git_show(sha, ruta)
            if texto is None:
                continue
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError:
            continue
        for cap in datos.get("capabilities", []):
            cid = cap.get("id")
            if cid:
                resultado[cid] = cap
    return resultado


def _seccion_de(cap: dict) -> str:
    """Infere la sección del id de la capacidad."""
    cid = cap.get("id", "")
    if cid.startswith("system."):
        return "9"
    if cid.startswith(("cleanup.", "debloat.", "privacy.")):
        # cleanup -> 1, debloat -> 2, privacy -> 3
        if cid.startswith("cleanup."):
            return "1"
        if cid.startswith("debloat."):
            return "2"
        if cid.startswith("privacy."):
            return "3"
    if cid.startswith("explorer."):
        return "10"
    return "?"


def _motivo_literal(cap: dict) -> str:
    """Extrae la frase exacta de description/provenance que declara lo omitido (R1)."""
    desc = cap.get("description", "") or ""
    prov = cap.get("provenance", "") or ""
    # Busca la marca R1 en description primero, luego en provenance.
    for texto in (desc, prov):
        idx = texto.find("FUERA DE ESTA CAPACIDAD (R1)")
        if idx >= 0:
            # Devuelve desde un poco antes de la marca hasta el final de la frase.
            inicio = max(0, idx - 80)
            fin = min(len(texto), idx + 200)
            return texto[inicio:fin].replace("\n", " ").strip()
        idx2 = texto.find("R1 (paso 12)")
        if idx2 >= 0:
            inicio = max(0, idx2 - 80)
            fin = min(len(texto), idx2 + 200)
            return texto[inicio:fin].replace("\n", " ").strip()
    # Si no hay marca R1, devuelve el principio de description como motivo.
    if desc:
        return desc[:200].replace("\n", " ").strip()
    if prov:
        return prov[:200].replace("\n", " ").strip()
    return ""


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Informe de capacidades Specified por commit.",
    )
    parser.add_argument(
        "--sha",
        action="append",
        default=list(SHA_FIJAS) + ["HEAD"],
        help="sha a inspeccionar (puede repetirse; HEAD se añade si se omite)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="ruta de salida del informe (por defecto stdout)",
    )
    args = parser.parse_args(argv)

    shas = args.sha
    if "HEAD" not in shas:
        shas = list(shas) + ["HEAD"]

    # Lee capacidades por sha
    caps_por_sha: dict[str | None, dict[str, dict]] = {}
    for sha in shas:
        caps_por_sha[sha] = _leer_capacidades(None if sha == "HEAD" else sha)

    # Todas las capacidades Specified en HEAD
    head_caps = caps_por_sha.get("HEAD", {})
    specified_head = {
        cid: cap for cid, cap in head_caps.items() if cap.get("state") == "Specified"
    }

    salida: list[str] = []
    salida.append("=== (a) Capacidades Specified en HEAD (motivo literal) ===")
    salida.append("")
    salida.append("id | sección | motivo literal")
    salida.append("-" * 100)
    for cid in sorted(specified_head):
        cap = specified_head[cid]
        seccion = _seccion_de(cap)
        motivo = _motivo_literal(cap)
        salida.append(f"{cid} | sec{seccion} | {motivo}")
    salida.append("")
    salida.append(f"Total Specified en HEAD: {len(specified_head)}")
    salida.append("")

    # Todas las ids conocidas en cualquier sha
    todas_ids: set[str] = set()
    for sha in shas:
        todas_ids.update(caps_por_sha[sha].keys())

    salida.append("=== (b) State de cada capacidad por commit ===")
    salida.append("")
    salida.append("id | " + " | ".join(s for s in shas) + "")
    salida.append("-" * (10 + 14 * len(shas)))
    for cid in sorted(todas_ids):
        fila = [cid]
        for sha in shas:
            cap = caps_por_sha[sha].get(cid)
            if cap is None:
                fila.append("no existía")
            else:
                fila.append(cap.get("state", "?"))
        salida.append(" | ".join(fila))
    salida.append("")

    texto = "\n".join(salida) + "\n"

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(texto, encoding="utf-8")
        print(f"Escrito {args.out}")
    else:
        print(texto, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
