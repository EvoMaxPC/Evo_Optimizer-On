#!/usr/bin/env python3
"""Genera la matriz de cobertura maestra del paso 5.

Entradas  : inventory/ledger/*.tsv  (pins Atlas + WinUtil)
Salida    : docs/reports/matriz-cobertura.md

Contenido:
1. Totales de los cinco estados de la conciliacion y tabla cruzada 17x5 con
   totales de fila y columna.
2. WinUtil: cuantos de sus 162 items y 239 apps quedan mapeados/catalogados.
3. Atlas: 91 toggles, 182 entradas de manifiesto y 327 ficheros .reg.
4. Total de capacidades atomicas consolidadas para el catalogo EVO.

Uso:
    python3 tools/ledger_extract/generate_coverage_matrix.py
    python3 tools/ledger_extract/generate_coverage_matrix.py --report docs/reports/matriz-cobertura.md
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "inventory" / "ledger"
RECON = LEDGER / "inventory-reconciliation.tsv"
DEFAULT_OUT = ROOT / "docs" / "reports" / "matriz-cobertura.md"
STATUSES = ("Mapped", "Mapped-To-App", "EVO-Exclusive", "Absent-At-Pin",
            "Informative-Header")
SHORT = {
    "Mapped": "Mapped",
    "Mapped-To-App": "M-App",
    "EVO-Exclusive": "EVO",
    "Absent-At-Pin": "Ausente",
    "Informative-Header": "Info",
}
APP_PREFIX = "winutil:catalog-entry:"


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def load() -> dict:
    recon = read_tsv(RECON)
    res: dict = {"recon": recon}
    for name in ("winutil-items", "winutil-apps", "atlas-toggles",
                 "atlas-manifest", "atlas-reg-entries", "atlas-files",
                 "atlas-tweak-files", "atlas-effects", "winutil-tweak-ops"):
        p = LEDGER / f"{name}.tsv"
        res[name] = read_tsv(p) if p.is_file() else []
    return res


def build_matrix(recon: list[dict]) -> tuple[dict, dict, dict]:
    """Devuelve (por_seccion, totales_estado, totales_seccion)."""
    por_seccion: dict[int, Counter] = defaultdict(Counter)
    for r in recon:
        por_seccion[int(r["seccion"])][r["status"]] += 1
    totales_estado = Counter(r["status"] for r in recon)
    totales_seccion = {s: sum(c.values()) for s, c in por_seccion.items()}
    return por_seccion, totales_estado, totales_seccion


def coverage(recon: list[dict], data: dict) -> dict:
    """Cruza los `mapped_ids` de la conciliacion con cada ledger de origen."""
    items = {r["item_id"] for r in data["winutil-items"]}
    apps = {r["item_id"] for r in data["winutil-apps"]}
    toggles = {r["item_id"] for r in data["atlas-toggles"]}
    manifest = data["atlas-manifest"]
    manifest_ids = {r["item_id"] for r in manifest}
    reg_entries = {r["item_id"] for r in data["atlas-reg-entries"]}
    reg_files = {r["source_ref"] for r in data["atlas-files"]
                 if r["source_ref"].lower().endswith(".reg")}
    tweak_ops = {r["item_id"] for r in data["winutil-tweak-ops"]}
    effects = {r["item_id"] for r in data["atlas-effects"]}

    # ids distintos, no ocurrencias
    mapped_ids = sorted({m for r in recon
                         for m in (r["mapped_ids"] or "").split("|") if m})
    items_hit = {m for m in mapped_ids if m in items}
    apps_hit = {m for m in mapped_ids if m in apps}
    toggles_hit = {m for m in mapped_ids if m in toggles}
    manifest_hit = {m for m in mapped_ids if m in manifest_ids}
    reg_hit = {m for m in mapped_ids if m in reg_entries}
    effects_hit = {m for m in mapped_ids if m in effects}
    op_hit = {m for m in mapped_ids if m in tweak_ops}
    conocidos = items | apps | toggles | manifest_ids | reg_entries | effects | tweak_ops
    otros = [m for m in mapped_ids if m not in conocidos]

    return {
        "winutil_items": len(items), "winutil_items_hit": len(items_hit),
        "winutil_apps": len(apps), "winutil_apps_hit": len(apps_hit),
        "ids_totales": len(mapped_ids), "ids_otros": len(otros),
        "atlas_toggles": len(toggles), "atlas_toggles_hit": len(toggles_hit),
        "atlas_manifest": len(manifest_ids),
        "atlas_manifest_enabled": sum(1 for r in manifest
                                      if r["enabled"] == "true"),
        "atlas_manifest_hit": len(manifest_hit),
        "atlas_regs": len(reg_entries), "atlas_regs_files": len(reg_files),
        "atlas_regs_hit": len(reg_hit),
        "atlas_files": len(data["atlas-files"]),
        "atlas_effects": len(effects), "atlas_effects_hit": len(effects_hit),
        "winutil_ops": len(tweak_ops), "winutil_ops_hit": len(op_hit),
        "atomicos": len(mapped_ids),
    }


def pct(a: int, b: int) -> str:
    return f"{100.0 * a / b:.1f} %" if b else "n/d"


def render(data: dict) -> str:
    recon = data["recon"]
    por_seccion, totales_estado, totales_seccion = build_matrix(recon)
    cov = coverage(recon, data)
    total = len(recon)
    sha_tsv = hashlib.sha256(RECON.read_bytes()).hexdigest()

    out: list[str] = []
    w = out.append
    w("# Matriz de cobertura maestra — paso 5\n")
    w("Generado por `tools/ledger_extract/generate_coverage_matrix.py`. "
      "No editar a mano.\n")
    w(f"- Filas de la conciliacion: **{total}**")
    w(f"- `inventory/ledger/inventory-reconciliation.tsv` sha256 "
      f"`{sha_tsv}`")
    w("- Pins: Atlas `ec3c4058`, WinUtil `70c23c80`\n")

    w("## 1. Totales por estado\n")
    w("| Estado | Filas | % |")
    w("|---|---:|---:|")
    for s in STATUSES:
        w(f"| `{s}` | {totales_estado.get(s, 0)} | {pct(totales_estado.get(s, 0), total)} |")
    w(f"| **Total** | **{total}** | 100.0 % |\n")

    w("## 2. Tabla cruzada seccion x estado\n")
    w("| Sec | " + " | ".join(SHORT[s] for s in STATUSES) + " | Total |")
    w("|---|" + "---:|" * (len(STATUSES) + 1))
    for sec in sorted(por_seccion):
        c = por_seccion[sec]
        w(f"| {sec} | " + " | ".join(str(c.get(s, 0)) for s in STATUSES)
          + f" | {totales_seccion[sec]} |")
    w("| **Total** | " + " | ".join(f"**{totales_estado.get(s, 0)}**" for s in STATUSES)
      + f" | **{total}** |\n")

    w("## 3. Cobertura WinUtil\n")
    w("| Conjunto | Total | Mapeados | Cobertura |")
    w("|---|---:|---:|---:|")
    w(f"| Items de WinUtil | {cov['winutil_items']} | {cov['winutil_items_hit']} | "
      f"{pct(cov['winutil_items_hit'], cov['winutil_items'])} |")
    w(f"| Operaciones de tweak de WinUtil | {cov['winutil_ops']} | "
      f"{cov['winutil_ops_hit']} | {pct(cov['winutil_ops_hit'], cov['winutil_ops'])} |")
    w(f"| Apps de WinUtil | {cov['winutil_apps']} | {cov['winutil_apps_hit']} | "
      f"{pct(cov['winutil_apps_hit'], cov['winutil_apps'])} |")
    w("")
    w("Las apps se referencian con `winutil:catalog-entry:<id>` desde la seccion 15; "
      "los items con `winutil:item:*` / `winutil:tweak-op:*` / "
      "`winutil:feature:*`.\n")

    w("## 4. Cobertura Atlas\n")
    w("| Conjunto | Total | Mapeados | Cobertura |")
    w("|---|---:|---:|---:|")
    w(f"| Toggles | {cov['atlas_toggles']} | {cov['atlas_toggles_hit']} | "
      f"{pct(cov['atlas_toggles_hit'], cov['atlas_toggles'])} |")
    w(f"| Entradas de manifiesto | {cov['atlas_manifest']} "
      f"({cov['atlas_manifest_enabled']} habilitadas) | {cov['atlas_manifest_hit']} | "
      f"{pct(cov['atlas_manifest_hit'], cov['atlas_manifest'])} |")
    w(f"| Valores `.reg` (`atlas-reg-entries.tsv`) | {cov['atlas_regs']} | "
      f"{cov['atlas_regs_hit']} | {pct(cov['atlas_regs_hit'], cov['atlas_regs'])} |")
    w(f"| Ficheros `.reg` | {cov['atlas_regs_files']} | — | n/d |")
    w(f"| Efectos de script (`atlas-effects.tsv`) | {cov['atlas_effects']} | "
      f"{cov['atlas_effects_hit']} | {pct(cov['atlas_effects_hit'], cov['atlas_effects'])} |")
    w(f"| Ficheros inventariados (`atlas-files.tsv`) | {cov['atlas_files']} | — | n/d |\n")

    w("## 5. Capacidades atomicas para el catalogo EVO\n")
    w("| Concepto | Valor |")
    w("|---|---:|")
    w(f"| `mapped_ids` distintos en toda la conciliacion | {cov['atomicos']} |")
    w(f"| De ellos, apps de WinUtil | {cov['winutil_apps_hit']} |")
    w(f"| De ellos, items de WinUtil | {cov['winutil_items_hit']} |")
    w(f"| De ellos, toggles Atlas | {cov['atlas_toggles_hit']} |")
    w(f"| De ellos, entradas de manifiesto Atlas | {cov['atlas_manifest_hit']} |")
    w(f"| De ellos, operaciones de tweak de WinUtil | {cov['winutil_ops_hit']} |")
    w(f"| De ellos, efectos de script de Atlas | {cov['atlas_effects_hit']} |")
    w(f"| De ellos, valores `.reg` de Atlas | {cov['atlas_regs_hit']} |")
    w(f"| De ellos, sin ledger de origen reconocido | {cov['ids_otros']} |")
    w("")
    w("Ademas, las filas `EVO-Exclusive` "
      f"({totales_estado.get('EVO-Exclusive', 0)}) son capacidades que el catalogo "
      "EVO debe aportar por si mismo, sin contraparte en los pins.\n")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", default=str(DEFAULT_OUT))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    data = load()
    if not data["recon"]:
        print("ERROR: falta la conciliacion; ejecuta antes "
              "build_final_reconciliation.py", file=sys.stderr)
        return 1
    md = render(data)
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8", newline="\n")

    por_seccion, totales_estado, _ = build_matrix(data["recon"])
    resumen = {
        "filas": len(data["recon"]),
        "por_estado": {s: totales_estado.get(s, 0) for s in STATUSES},
        "secciones": len(por_seccion),
        "cobertura": coverage(data["recon"], data),
        "sha256_tsv": hashlib.sha256(RECON.read_bytes()).hexdigest(),
    }
    if args.json:
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
    else:
        print(f"informe: {out}")
        print(f"filas  : {resumen['filas']}  estados: {len(STATUSES)}  "
              f"secciones: {resumen['secciones']}")
        for s in STATUSES:
            print(f"  {s:20s} {resumen['por_estado'][s]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
