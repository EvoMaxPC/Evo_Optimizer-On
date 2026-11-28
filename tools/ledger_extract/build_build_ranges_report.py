#!/usr/bin/env python3
"""Genera `docs/reports/rangos-build.md` con las cifras MEDIDAS del catálogo.

No hay ninguna cifra escrita a mano: se leen los JSON de
`catalog/capabilities/` y se agrupa por la tupla exacta de `supportedBuilds`.
El fichero se compara en CI (`--check`), así que no se edita a mano.

Uso:
    python3 tools/ledger_extract/build_build_ranges_report.py
    python3 tools/ledger_extract/build_build_ranges_report.py --check
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "catalog" / "capabilities"
OUT = ROOT / "docs" / "reports" / "rangos-build.md"
FULL = [19045, 22631, 26100, 26200]


def load() -> list[dict]:
    capabilities: list[dict] = []
    for path in sorted(CATALOG.glob("*.json"), key=lambda p: p.name):
        document = json.loads(path.read_text(encoding="utf-8"))
        for definition in document.get("capabilities", []):
            capabilities.append(definition)
    return capabilities


def build() -> str:
    capabilities = load()
    groups: Counter = Counter(tuple(c["supportedBuilds"]) for c in capabilities)
    states = Counter(c["state"] for c in capabilities)
    incomplete = [c for c in capabilities if len(c["supportedBuilds"]) < len(FULL)]
    complete = len(capabilities) - len(incomplete)

    lines: list[str] = []
    lines.append("# Rangos de build — capacidades con `supportedBuilds` incompleto")
    lines.append("")
    lines.append("Generado por `tools/ledger_extract/build_build_ranges_report.py` "
                 "a partir de `catalog/capabilities/*.json`. No editar a mano: "
                 "CI compara el fichero con el generado.")
    lines.append("")
    lines.append(f"Catálogo: **{len(capabilities)}** capacidades, "
                 f"{states.get('Implemented', 0)} `Implemented` y "
                 f"{states.get('Specified', 0)} `Specified`.")
    lines.append("")
    lines.append("## Método")
    lines.append("")
    lines.append("Se agrupa por la tupla exacta de `supportedBuilds` (sin normalizar ni "
                 "reordenar) y se contrasta cada grupo incompleto con la `provenance` "
                 "de la capacidad, que cita el pin y la razón del recorte.")
    lines.append("")
    lines.append("## Grupos medidos")
    lines.append("")
    lines.append("| `supportedBuilds` | Capacidades |")
    lines.append("|---|---:|")
    for builds, count in sorted(groups.items(), key=lambda kv: (-len(kv[0]), kv[0])):
        rendered = ", ".join(str(b) for b in builds) if builds else "(vacío)"
        lines.append(f"| `[{rendered}]` | {count} |")
    lines.append("")
    lines.append(f"Con las cuatro builds del catálogo: **{complete}**. "
                 f"Con rango recortado: **{len(incomplete)}**.")
    lines.append("")
    lines.append("## Capacidades con rango recortado")
    lines.append("")
    lines.append("| Capacidad | `supportedBuilds` | `state` | Motivo (de su `provenance`) |")
    lines.append("|---|---|---|---|")
    for definition in sorted(incomplete, key=lambda c: c["id"]):
        provenance = definition["provenance"]
        index = provenance.find("Builds:")
        if index >= 0:
            tail = provenance[index + len("Builds:"):]
            # La nota acaba en el punto o en la referencia al ledger, que va
            # pegada porque la procedencia se concatena sin separador.
            for stop in ("ledger_refs:", " Reversibilidad"):
                if stop in tail:
                    tail = tail.split(stop)[0]
            reason = tail.split(". ")[0].strip().rstrip(".")
        elif "NO VERIFICADO" in provenance:
            # El pin no fija el rango en ningún campo (MinBuild/MaxBuild ni
            # guardas): la capacidad lo dice y por eso queda en `Specified`.
            start = provenance.find("Rango:")
            reason = ("NO VERIFICADO: " + (provenance[start:start + 190].split(". ")[0]
                                           .removeprefix("Rango: ")
                                           if start >= 0 else
                                           "el pin no fija el rango; la procedencia "
                                           "lo marca como NO VERIFICADO"))
        else:
            reason = "sin nota 'Builds:' en la procedencia — NO VERIFICADO"
        rendered = ", ".join(str(b) for b in definition["supportedBuilds"])
        lines.append(
            f"| `{definition['id']}` | `[{rendered}]` | {definition['state']} | {reason} |")
    lines.append("")
    lines.append("## Qué comprueba CI")
    lines.append("")
    lines.append("- `tests/test_paso9.py` exige que TODA capacidad declare "
                 "`supportedBuilds` explícito y que las cinco de la sección 10 sin "
                 "19045 sean exactamente las que no tienen efecto en Windows 10.")
    lines.append("- La nota `Builds:` de la procedencia es obligatoria para cada "
                 "capacidad recortada (lo comprueban los xUnit y el test de Python).")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="no escribe; compara con el fichero del disco")
    args = parser.parse_args(argv)

    text = build()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != text:
            print("rangos-build.md NO reproducible: el fichero del disco difiere",
                  file=sys.stderr)
            return 1
        print("rangos-build.md reproducible: OK")
        return 0

    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"escrito {OUT.relative_to(ROOT)} ({len(text)} caracteres)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
