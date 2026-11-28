#!/usr/bin/env python3
"""Borrador de conciliacion inventario -> ledger. NO decide `Mapped`.

Lee `docs/requirements/INVENTARIO_USUARIO.md` **solo en lectura** y, para cada
linea no vacia (588), propone candidatos con cuatro reglas medidas:

    R1  coincidencia exacta de etiqueta/nombre normalizado
    R2  contencion de tokens con nombre propio (>= 2 tokens, no genericos)
    R3  el texto menciona un target literal de los ledgers de efectos/ops
    R4  ninguna de las anteriores

Salida: `inventory/ledger/conciliacion-borrador.tsv`

    seccion  linea  fuente_declarada  texto  regla  candidatos  confianza
    estado_propuesto

- `texto`: la linea normalizada, truncada a 200 caracteres.
- `candidatos`: hasta 5 `item_id`, separados por `|`.
- `confianza`: alta | media | baja | ninguna.
- `estado_propuesto`: propuesto-mapped | propuesto-evo-propio | sin-evidencia |
  informativo.

**PROHIBIDO escribir "Mapped"**: la palabra aparece aqui solo en los valores
`propuesto-mapped`, que son una propuesta. La decision es del responsable.
El invariante esta comprobado en los tests: ninguna celda vale exactamente
`Mapped` y la columna `estado_propuesto` nunca toma ese valor.

Uso:
    python3 tools/ledger_extract/build_conciliacion.py [--json]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ledger_extract"))

import count_inventory as ci  # noqa: E402

LEDGER = ROOT / "inventory" / "ledger"
OUT = LEDGER / "conciliacion-borrador.tsv"

COLUMNS = ("seccion", "linea", "fuente_declarada", "texto", "regla",
           "candidatos", "confianza", "estado_propuesto")

MAX_CANDIDATOS = 5
TEXTO_MAX = 200

# Tokens que no sirven para identificar nada: aparecen en casi todas las lineas.
GENERIC = {
    "windows", "winutil", "atlas", "atlasos", "evo", "clean", "capacidad",
    "desarrollar", "sistema", "sistemas", "configuracion", "configuración",
    "opcion", "opciones", "ajuste", "ajustes", "herramienta", "herramientas",
    "de", "del", "la", "las", "el", "los", "y", "o", "en", "con", "por", "para",
    "un", "una", "que", "se", "su", "sus", "al", "a", "the", "and", "of", "to",
    "interfaz", "usuario", "usuarios", "pantalla", "menu", "menú", "modo",
    "nuevo", "nueva", "todos", "todas", "desde", "hasta", "como", "más", "mas",
    "permitir", "permite", "añadir", "agregar", "quitar", "eliminar", "activar",
    "desactivar", "habilitar", "deshabilitar", "forzar", "mostrar", "ocultar",
}
# Efectos que no identifican un objeto concreto.
GENERIC_TARGETS = {"1", "0", "true", "false", "hkcu", "hklm", "hkcr", "hku",
                   "set-itemproperty", "remove-item", "new-item"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", html.unescape(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def tokens(s: str) -> list[str]:
    return [t for t in norm(s).split() if len(t) >= 3 and t not in GENERIC]


# --------------------------------------------------------------- candidatos
def load_sources() -> dict[str, list[dict]]:
    """item_id + etiqueta normalizada de cada TSV candidato."""
    src: dict[str, list[dict]] = defaultdict(list)

    def add(source: str, item_id: str, label: str) -> None:
        n = norm(label)
        if not n:
            return
        src[source].append({"item_id": item_id, "label": label, "norm": n,
                            "tokens": tokens(label)})

    def tsv(name: str) -> list[dict]:
        p = LEDGER / name
        if not p.is_file():
            return []
        with p.open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh, delimiter="\t"))

    for r in tsv("winutil-items.tsv"):
        add("winutil-items", r["item_id"], r["label"])
    for r in tsv("winutil-apps.tsv"):
        add("winutil-apps", r["item_id"], r["label"])
    for r in tsv("atlas-toggles.tsv"):
        add("atlas-toggles", r["item_id"], r["label"])
    # atlas-tweak-files.tsv no tiene columna `label`: su etiqueta es la ruta
    # relativa del .psd1 sin extension (p.ej. "Tweaks/qol/disable-gallery.psd1").
    for r in tsv("atlas-tweak-files.tsv"):
        stem = r["source_ref"].rsplit("/", 1)[-1].replace(".psd1", "")
        add("atlas-tweak-files", r["item_id"], stem)
    for r in tsv("atlas-manifest.tsv"):
        add("atlas-manifest", r["item_id"], r["id"].replace("/", " "))
    return src


def effect_targets() -> dict[str, str]:
    """target normalizado -> item_id de la primera fila que lo declara."""
    out: dict[str, str] = {}

    def tsv(name: str) -> list[dict]:
        p = LEDGER / name
        return list(csv.DictReader(p.open(encoding="utf-8"), delimiter="\t")) \
            if p.is_file() else []

    for name in ("atlas-effects.tsv", "atlas-tweak-ops.tsv", "winutil-tweak-ops.tsv"):
        for r in tsv(name):
            for key in ("target", "name"):
                v = (r.get(key) or "").strip()
                if not v or len(v) < 4:
                    continue
                n = norm(v.split("\\")[-1].split("/")[-1])
                if len(n) < 4 or n in GENERIC_TARGETS:
                    continue
                out.setdefault(n, r["item_id"])
    return out


# ------------------------------------------------------------------ reglas
def r1(text_norm: str, sources: dict[str, list[dict]]) -> list[tuple[str, str]]:
    """Coincidencia EXACTA de etiqueta normalizada."""
    hits = []
    for source, items in sources.items():
        for it in items:
            if it["norm"] and it["norm"] == text_norm:
                hits.append((source, it["item_id"]))
    return hits


# Un token que aparece en mas de DF_MAX etiquetas no identifica nada: "install",
# "software", "right", "click" estan por todas partes. Umbral fijado ANTES de
# mirar resultados (ver docs/inventory-recon/conciliacion-reglas.md) y no
# ajustado despues.
DF_MAX = 10


def token_df(sources: dict[str, list[dict]]) -> dict[str, int]:
    df: dict[str, int] = defaultdict(int)
    for items in sources.values():
        for it in items:
            for t in set(it["tokens"]):
                df[t] += 1
    return dict(df)


def r2(text: str, sources: dict[str, list[dict]],
       df: dict[str, int]) -> list[tuple[str, str]]:
    """Contencion CONTIGUA: el texto normalizado aparece tal cual en la etiqueta.

    Se exige:
      - >= 2 tokens en el texto,
      - que el texto normalizado sea subcadena de la etiqueta normalizada,
      - que al menos un token sea discriminante (df <= DF_MAX).

    La version anterior comparaba conjuntos de tokens y aceptaba
    "Install Software." -> "Razer Software Auto-Install - Disable": mismos
    tokens, ningun significado comun. La comprobacion de subcadena lo evita sin
    tocar el umbral.
    """
    n = norm(text)
    tt = set(tokens(text))
    if len(tt) < 2:
        return []
    if not any(df.get(t, 0) <= DF_MAX for t in tt):
        return []
    hits = []
    for source, items in sources.items():
        for it in items:
            if not it["norm"]:
                continue
            if n and n in it["norm"]:
                hits.append((source, it["item_id"]))
    return hits


def r3(text: str, targets: dict[str, str]) -> list[tuple[str, str]]:
    """El texto menciona un target literal de los ledgers."""
    n = norm(text)
    hits = []
    for t, item in targets.items():
        if len(t) < 4:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", n):
            hits.append(("target", item))
    return hits


def classify(line: str, sources, targets, df) -> tuple[str, list[str], str, str]:
    """Devuelve (regla, candidatos, confianza, estado_propuesto)."""
    n = norm(line)
    h1 = r1(n, sources)
    if h1:
        return "R1", [i for _, i in h1][:MAX_CANDIDATOS], "alta", "propuesto-mapped"
    h2 = r2(line, sources, df)
    if h2:
        conf = "alta" if len(h2) == 1 else "media"
        return "R2", [i for _, i in h2][:MAX_CANDIDATOS], conf, "propuesto-mapped"
    h3 = r3(line, targets)
    if h3:
        conf = "media" if len(h3) <= 2 else "baja"
        return "R3", [i for _, i in h3][:MAX_CANDIDATOS], conf, "propuesto-mapped"
    return "R4", [], "ninguna", "sin-evidencia"


# ------------------------------------------------------------------- salida
def lines_with_sections(md: Path) -> list[dict]:
    sections, body_start = ci.parse(md)
    raw = md.read_text(encoding="utf-8").splitlines()
    by_line = {s["linea"]: s for s in sections}
    out = []
    current = None
    for idx, line in enumerate(raw[body_start:], start=body_start + 1):
        if idx in by_line:
            current = by_line[idx]
            continue
        if current is None or not line.strip():
            continue
        out.append({
            "seccion": current["numero"],
            "linea": idx,
            "texto_raw": line,
        })
    return out


def build(md: Path = ci.DEFAULT_MD) -> tuple[list[dict], dict]:
    sources = load_sources()
    targets = effect_targets()
    df = token_df(sources)
    sections, _ = ci.parse(md)

    # fuente declarada: el modo vigente de count_inventory.py, línea a línea
    sec_iter = iter(sections)
    cur = next(sec_iter, None)
    bucket = "general"
    fuente_by_line: dict[int, str] = {}
    raw = md.read_text(encoding="utf-8").splitlines()
    body_start = 2
    for idx, line in enumerate(raw[body_start:], start=body_start + 1):
        if cur is not None and idx == cur["linea"]:
            bucket = "general"
            cur = next(sec_iter, None)
            continue
        if cur is None or not line.strip():
            continue
        if cur["titulo"] == ci.NO_MODE_SECTION_TITLE or ci.is_note(line):
            fuente_by_line[idx] = "general"
            continue
        nb = ci.bucket_of(line)
        if nb:
            bucket = nb
        fuente_by_line[idx] = bucket

    rows = []
    for rec in lines_with_sections(md):
        texto = html.unescape(rec["texto_raw"]).strip()
        regla, cands, conf, estado = classify(texto, sources, targets, df)
        rows.append({
            "seccion": rec["seccion"],
            "linea": rec["linea"],
            "fuente_declarada": fuente_by_line.get(rec["linea"], "general"),
            "texto": texto[:TEXTO_MAX],
            "regla": regla,
            "candidatos": "|".join(cands),
            "confianza": conf,
            "estado_propuesto": estado,
        })
    rows.sort(key=lambda r: r["linea"])
    meta = {
        "filas": len(rows),
        "por_regla": dict(sorted(Counter(r["regla"] for r in rows).items())),
        "por_confianza": dict(sorted(Counter(r["confianza"] for r in rows).items())),
        "por_estado": dict(sorted(Counter(r["estado_propuesto"] for r in rows).items())),
        "por_fuente": dict(sorted(Counter(r["fuente_declarada"] for r in rows).items())),
        "con_candidatos": sum(1 for r in rows if r["candidatos"]),
    }
    return rows, meta


def write_tsv(path: Path, rows: list[dict]) -> None:
    lines = ["\t".join(COLUMNS)]
    for r in rows:
        lines.append("\t".join(str(r.get(c, "")).replace("\t", " ").replace("\n", " ")
                               for c in COLUMNS))
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--md", type=Path, default=ci.DEFAULT_MD)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows, meta = build(args.md)
    write_tsv(args.out, rows)
    summary = {**meta, "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest()}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    print(f"filas                 : {meta['filas']} (esperado 588)")
    print(f"por regla             : {meta['por_regla']}")
    print(f"por confianza         : {meta['por_confianza']}")
    print(f"por estado propuesto  : {meta['por_estado']}")
    print(f"por fuente declarada  : {meta['por_fuente']}")
    print(f"con candidatos        : {meta['con_candidatos']}")
    print(f"sha256                : {summary['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
