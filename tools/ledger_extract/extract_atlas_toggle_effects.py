#!/usr/bin/env python3
"""Grafo de llamadas de Atlas, efectos alcanzables por toggle y referencias a .psd1.

Entradas (del pin fijado, ya extraidas):
    inventory/ledger/atlas-functions.tsv      (1 563 funciones)
    inventory/ledger/atlas-effects.tsv        (efectos por funcion / <top>)
    inventory/ledger/atlas-toggle-bridge.tsv  (92 refs catalogo -> funcion)

Salidas:
    inventory/ledger/atlas-toggle-effects.tsv
        toggle_id, state, function_name, direct_effects, transitive_effects,
        effect_types, depth_max, has_cycle
    inventory/ledger/atlas-psd1-refs.tsv
        psd1, name, referenced_by_ps1, referenced_by_psm1,
        referenced_by_json, referenced_by_rs, referenced_by_manifest, total

APROXIMACION DECLARADA (no hay PowerShell en el sandbox):
- Una "llamada" es la aparicion del nombre de otra funcion como palabra
  completa (`\\bNombre\\b`) en el cuerpo de una funcion. No distingue
  definicion de uso, ni alcance, ni importacion de modulo. Da falsos positivos
  (el nombre dentro de una cadena cuenta) y falsos negativos (llamada construida
  con `& $nombre`). Se informa como cota superior.
- Profundidad maxima 5. Los ciclos se detectan y se marcan, no se expanden.
- Los efectos de una funcion son los que `extract_atlas_effects.py` encontro en
  sus lineas; los de `<top>` NO se atribuyen a ninguna funcion.

Uso:
    python3 tools/ledger_extract/extract_atlas_toggle_effects.py [--json]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = Path("/tmp/upstream/atlas")
LEDGER = ROOT / "inventory" / "ledger"
FUNCS = LEDGER / "atlas-functions.tsv"
EFFECTS = LEDGER / "atlas-effects.tsv"
BRIDGE = LEDGER / "atlas-toggle-bridge.tsv"
TWEAKS_DIR = "package/Executables/AtlasModules/Scripts/Tweaks"
MANIFEST = "package/Executables/AtlasModules/Scripts/Tweaks/tweaks.manifest.psd1"

MAX_DEPTH = 5
COLUMNS = ("toggle_id", "state", "function_name", "direct_effects",
           "transitive_effects", "effect_types", "depth_max", "has_cycle")
REF_COLUMNS = ("psd1", "name", "referenced_by_ps1", "referenced_by_psm1",
               "referenced_by_json", "referenced_by_rs", "referenced_by_manifest",
               "manifest_state", "total")


# ------------------------------------------------------------------ lectura
def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def call_graph(funcs: list[dict]) -> tuple[dict, dict, dict]:
    """Devuelve (grafo, efectos_directos, profundidad_real)."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    ignored: list[str] = []
    for r in funcs:
        # "script" y "global" no son funciones de Atlas: vienen de una linea
        # `function script:Foo` / `function global:Foo` mal recortada. Un nombre
        # de una sola palabra minuscula es un ambito de PowerShell, no un nombre
        # de funcion propio, y como palabra completa casa con casi todo.
        if re.fullmatch(r"[a-z]+", r["name"]):
            ignored.append(r["name"])
            continue
        by_name[r["name"]].append(r)

    # El grafo se resuelve por nombre: un nombre repetido se une (union).
    calls: dict[str, set[str]] = defaultdict(set)
    lines_of: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for name, rows in by_name.items():
        for r in rows:
            lines_of[name].append((r["path"], int(r["line_start"]), int(r["line_end"])))

    # cache de cuerpos por (path, inicio, fin)
    body_cache: dict[tuple[str, int, int], str] = {}

    def body(path: str, start: int, end: int) -> str:
        key = (path, start, end)
        if key not in body_cache:
            text = (ATLAS / path).read_text(encoding="utf-8", errors="replace")
            body_cache[key] = "\n".join(text.splitlines()[start - 1:end])
        return body_cache[key]

    patterns = {n: re.compile(rf"\b{re.escape(n)}\b", re.IGNORECASE) for n in by_name}
    for name in by_name:
        for path, start, end in lines_of[name]:
            text = body(path, start, end)
            for other, rx in patterns.items():
                if other == name:
                    continue
                if rx.search(text):
                    calls[name].add(other)

    # efectos directos por nombre de funcion
    direct: dict[str, list[str]] = defaultdict(list)
    for r in read_tsv(EFFECTS):
        if r["container"] in ("<top>", "<script>"):
            continue
        direct[r["container"]].append(r["effect_type"])
    return calls, direct, {"nombres": len(by_name),
                           "nombres_ignorados": sorted(set(ignored))}


def reach(calls: dict, direct: dict, start: str) -> tuple[set[str], int, bool, list[str]]:
    """Efectos alcanzables desde `start` (BFS, MAX_DEPTH).

    Devuelve (tipos, profundidad_maxima, hay_ciclo, ejemplo_de_ciclo).
    Un ciclo es un nodo alcanzado por el que se vuelve a pasar; se informa el
    camino concreto para que sea verificable, no solo el booleano.
    """
    seen = {start}
    frontier = deque([(start, 0, [start])])
    types: set[str] = set(direct.get(start, []))
    depth_max = 0
    cycle_path: list[str] = []
    while frontier:
        node, d, path = frontier.popleft()
        types.update(direct.get(node, []))
        if d >= MAX_DEPTH:
            continue
        for nxt in sorted(calls.get(node, ())):
            if nxt in seen:
                if not cycle_path and nxt in path:
                    cycle_path = path[path.index(nxt):] + [nxt]
                continue
            seen.add(nxt)
            depth_max = max(depth_max, d + 1)
            frontier.append((nxt, d + 1, path + [nxt]))
    return types, depth_max, bool(cycle_path), cycle_path


# ------------------------------------------------------- referencias a .psd1
def manifest_slugs(text: str) -> tuple[set[str], set[str]]:
    """Slugs habilitados y deshabilitados del manifiesto de tweaks.

    Estructura real del fichero:
        Categories = @( @{ Name = 'networking'; Tweaks = @( 'shares/x' ... ) } ... )
    Los slugs de `Tweaks` son **relativos a la carpeta de la categoria**, asi que
    la ruta completa es `<Name>/<slug>`. Fuera de categoria van como
    `@{ Slug = '...' }` y los deshabilitados, en `Disabled = @( @{ Slug = ... } )`.
    """
    m = re.search(r"^\s*Disabled\s*=\s*@\(", text, re.MULTILINE)
    head, tail = (text, "") if not m else (text[:m.start()], text[m.start():])

    enabled: set[str] = set()
    # cada categoria: Name = '...' seguido de su bloque Tweaks = @( ... )
    for cm in re.finditer(r"Name\s*=\s*'([^']+)'(.*?)(?=Name\s*=\s*'|\Z)",
                          head, re.DOTALL):
        cat, block = cm.group(1), cm.group(2)
        tm = re.search(r"Tweaks\s*=\s*@\((.*?)\)", block, re.DOTALL)
        if not tm:
            continue
        for slug in re.findall(r"'([^']+)'", tm.group(1)):
            enabled.add(f"{cat}/{slug}")
    # los que van fuera de categoria: @{ Slug = '...' }
    enabled |= set(re.findall(r"Slug\s*=\s*'([^']+)'", head))
    disabled = set(re.findall(r"Slug\s*=\s*'([^']+)'", tail))
    return enabled, disabled


def psd1_references(root: Path) -> tuple[list[dict], dict]:
    files = sorted((root / TWEAKS_DIR).rglob("*.psd1"))
    # indice de texto por extension (una sola pasada)
    buckets: dict[str, list[tuple[str, str]]] = defaultdict(list)
    exts = {".ps1": "ps1", ".psm1": "psm1", ".json": "json", ".rs": "rs"}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        k = exts.get(p.suffix.lower())
        if not k:
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        try:
            buckets[k].append((rel, p.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue

    manifest_txt = ""
    if (root / MANIFEST).is_file():
        manifest_txt = (root / MANIFEST).read_text(encoding="utf-8", errors="replace")
    # El manifiesto declara los slugs de dos formas: cadena suelta en
    # Categories[].Tweaks (habilitado) o hashtable @{ Slug = '...' } (habilitado
    # fuera de categoria o deshabilitado). Se busca el slug como cadena exacta.
    enabled, disabled = manifest_slugs(manifest_txt)
    man_slugs = enabled | disabled

    rows = []
    for p in files:
        rel = str(p.relative_to(root)).replace("\\", "/")
        stem = p.stem
        # slug = ruta relativa a Tweaks/ sin extension (asi lo usa el manifiesto)
        slug = rel[len(TWEAKS_DIR) + 1:-len(".psd1")]
        m = re.search(r"^\s*Name\s*=\s*'([^']*)'", p.read_text(encoding="utf-8",
                                                          errors="replace"),
                      re.MULTILINE)
        name = m.group(1) if m else ""
        counts = {}
        for key, items in buckets.items():
            n = 0
            for frel, txt in items:
                if frel == rel:
                    continue
                if stem and stem in txt:
                    n += 1
                elif slug and slug.replace("/", "\\") in txt:
                    n += 1
            counts[key] = n
        man = 1 if slug in man_slugs else 0
        if slug in disabled:
            estado = "disabled"
        elif slug in enabled:
            estado = "enabled"
        else:
            estado = ""
        rows.append({
            "psd1": rel, "name": name,
            "referenced_by_ps1": counts["ps1"],
            "referenced_by_psm1": counts["psm1"],
            "referenced_by_json": counts["json"],
            "referenced_by_rs": counts["rs"],
            "referenced_by_manifest": man,
            "manifest_state": estado,
            "total": sum(counts.values()) + man,
        })
    rows.sort(key=lambda r: r["psd1"])
    meta = {
        "psd1": len(rows),
        "con_alguna_referencia": sum(1 for r in rows if r["total"]),
        "sin_ninguna": sum(1 for r in rows if not r["total"]),
        "en_manifest": sum(r["referenced_by_manifest"] for r in rows),
        "manifest_enabled": sum(1 for r in rows if r["manifest_state"] == "enabled"),
        "manifest_disabled": sum(1 for r in rows if r["manifest_state"] == "disabled"),
        "no_en_manifest": sum(1 for r in rows if not r["manifest_state"]),
    }
    return rows, meta


# ------------------------------------------------------------------- salida
def write_tsv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    lines = ["\t".join(columns)]
    for r in rows:
        lines.append("\t".join(str(r.get(c, "")) for c in columns))
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def build() -> tuple[list[dict], dict, list[dict], dict]:
    funcs = read_tsv(FUNCS)
    calls, direct, gmeta = call_graph(funcs)
    bridge = read_tsv(BRIDGE)

    rows = []
    cycle_examples: list[dict] = []
    for r in bridge:
        fname = r["function_name"]
        types, depth, cycle, cpath = reach(calls, direct, fname)
        if cpath and len(cycle_examples) < 5:
            cycle_examples.append({"function": fname, "path": cpath})
        rows.append({
            "toggle_id": r["toggle_id"], "state": r["state"],
            "function_name": fname,
            "direct_effects": len(direct.get(fname, [])),
            "transitive_effects": len(types),
            "effect_types": "|".join(sorted(types)),
            "depth_max": depth,
            "has_cycle": "true" if cycle else "false",
        })
    rows.sort(key=lambda r: (r["toggle_id"], r["state"], r["function_name"]))

    type_counter = Counter()
    for r in rows:
        for t in r["effect_types"].split("|"):
            if t:
                type_counter[t] += 1
    states_by_toggle = Counter(r["toggle_id"] for r in rows)
    effects_zero = [f"{r['toggle_id']}/{r['state']}" for r in rows
                    if r["transitive_effects"] == 0]
    meta = {
        **gmeta,
        "filas": len(rows),
        "toggles": len(states_by_toggle),
        "con_un_estado": sum(1 for v in states_by_toggle.values() if v == 1),
        "con_varios_estados": sum(1 for v in states_by_toggle.values() if v > 1),
        "filas_sin_efecto": len(effects_zero),
        "sin_efecto": effects_zero,
        "por_tipo": dict(sorted(type_counter.items(), key=lambda kv: -kv[1])),
        "con_ciclo": sum(1 for r in rows if r["has_cycle"] == "true"),
        "con_directos": sum(1 for r in rows if r["direct_effects"]),
        "nombres_de_llamada": len(calls),
        "nombres_con_llamadas": sum(1 for v in calls.values() if v),
        "ciclos_ejemplo": cycle_examples,
    }
    refs, refmeta = psd1_references(ATLAS)
    return rows, meta, refs, refmeta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows, meta, refs, refmeta = build()
    out = LEDGER / "atlas-toggle-effects.tsv"
    write_tsv(out, COLUMNS, rows)
    out2 = LEDGER / "atlas-psd1-refs.tsv"
    write_tsv(out2, REF_COLUMNS, refs)

    summary = {
        **meta,
        "psd1": refmeta,
        "sha256_toggle_effects": hashlib.sha256(out.read_bytes()).hexdigest(),
        "sha256_psd1_refs": hashlib.sha256(out2.read_bytes()).hexdigest(),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print(f"filas                 : {meta['filas']} ({meta['toggles']} toggles)")
    print(f"con 1 estado          : {meta['con_un_estado']} | varios: {meta['con_varios_estados']}")
    print(f"filas sin efecto      : {meta['filas_sin_efecto']}")
    print(f"filas con efecto dir. : {meta['con_directos']}")
    print(f"con ciclo             : {meta['con_ciclo']}")
    print("tipos alcanzables:")
    for k, v in meta["por_tipo"].items():
        print(f"  {k:18s} {v}")
    print(f"nombres en el grafo   : {meta['nombres_de_llamada']}")
    print(f".psd1                 : {refmeta['psd1']} (con ref: {refmeta['con_alguna_referencia']}"
          f", sin ninguna: {refmeta['sin_ninguna']}, en manifiesto: {refmeta['en_manifest']})")
    print(f"sha256 toggle-effects : {summary['sha256_toggle_effects']}")
    print(f"sha256 psd1-refs      : {summary['sha256_psd1_refs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
