#!/usr/bin/env python3
"""Efectos declarados en el codigo de Atlas (mejor esfuerzo, sin PowerShell).

Fuentes (todas del pin fijado):

1. cuerpos de funciones `scope=product` de `atlas-functions.tsv`
2. codigo de nivel superior de `.ps1` / `.psm1` (fuera de funciones)
3. `.cmd` y `.vbs`
4. bloques `Script` de los `.psd1`

Salida: `inventory/ledger/atlas-effects.tsv`

Columnas:
    item_id  path  container  line  effect_type  command  target
    target_kind  value  sha256_line

- `container` = nombre de la funcion o `<top>`.
- `target_kind`: `literal` (comilla simple/doble literal o ruta HK* sin
  variables), `variable` (`$x`), `unresolved` (no se puede determinar).
- `value`: solo si es literal y <= 120 caracteres; si no, cadena vacia.
- `sha256_line`: sha256 de la linea normalizada. **Nunca** se guarda el cuerpo
  ni el texto de la linea.

Limitaciones declaradas: es un analisis lexico por lineas con regex. No evalua
variables, no sigue `&`/dot-sourcing, no interpreta condicionales. Cada
deteccion es "esta llamada aparece en esta linea", no "este efecto ocurre".

Uso:
    python3 tools/ledger_extract/extract_atlas_effects.py [--json]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = Path("/tmp/upstream/atlas")
FUNCS = ROOT / "inventory" / "ledger" / "atlas-functions.tsv"
PART = ROOT / "inventory" / "partition" / "results" / "atlas.tsv"
OUT_DIR = ROOT / "inventory" / "ledger"
TWEAKS_DIR = "package/Executables/AtlasModules/Scripts/Tweaks"

COLUMNS = ("item_id", "path", "container", "line", "effect_type", "command",
           "target", "target_kind", "value", "sha256_line")

# Orden importante: gana la primera regla que casa en la linea.
# (tipo, patron del comando, regex de captura del objetivo)
RULES: list[tuple[str, str, re.Pattern]] = [
    ("registry", "Set-ItemProperty",
     re.compile(r"\bSet-ItemProperty\b[^\n]*?(?:-Path|-LiteralPath)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("registry", "New-ItemProperty",
     re.compile(r"\bNew-ItemProperty\b[^\n]*?(?:-Path|-LiteralPath)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("registry", "Remove-ItemProperty",
     re.compile(r"\bRemove-ItemProperty\b[^\n]*?(?:-Path|-LiteralPath)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("registry", "New-Item",
     re.compile(r"\bNew-Item\b[^\n]*?(?:-Path|-LiteralPath)\s+(\"[^\"]*(?:HKLM|HKCU|HKCR|HKU|HKCC|REGISTRY)[^\"]*\"|'[^']*(?:HKLM|HKCU|HKCR|HKU|HKCC|REGISTRY)[^']*')", re.I)),
    ("registry", "Remove-Item",
     re.compile(r"\bRemove-Item\b[^\n]*?(?:-Path|-LiteralPath)\s+(\"[^\"]*(?:HKLM|HKCU|HKCR|HKU|HKCC|REGISTRY)[^\"]*\"|'[^']*(?:HKLM|HKCU|HKCR|HKU|HKCC|REGISTRY)[^']*')", re.I)),
    ("registry", "Set-Item",
     re.compile(r"\bSet-Item\b[^\n]*?(?:-Path|-LiteralPath)\s+(\"[^\"]*(?:HKLM|HKCU|HKCR|HKU|HKCC|REGISTRY)[^\"]*\"|'[^']*(?:HKLM|HKCU|HKCR|HKU|HKCC|REGISTRY)[^']*')", re.I)),
    ("registry", "reg add",
     re.compile(r"\breg(?:\.exe)?\s+add\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("registry", "reg delete",
     re.compile(r"\breg(?:\.exe)?\s+delete\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("registry", "reg import",
     re.compile(r"\breg(?:\.exe)?\s+import\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("service", "Set-Service",
     re.compile(r"\bSet-Service\b[^\n]*?(?:-Name)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("service", "Stop-Service",
     re.compile(r"\bStop-Service\b[^\n]*?(?:-Name)?\s*(\"[^\"]*\"|'[^']*'|\S+)?", re.I)),
    ("service", "Start-Service",
     re.compile(r"\bStart-Service\b[^\n]*?(?:-Name)?\s*(\"[^\"]*\"|'[^']*'|\S+)?", re.I)),
    ("service", "sc",
     re.compile(r"\bsc(?:\.exe)?\s+(?:config|stop|start|delete)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("scheduled-task", "Disable-ScheduledTask",
     re.compile(r"\bDisable-ScheduledTask\b[^\n]*?(?:-TaskName|-TaskPath)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("scheduled-task", "Enable-ScheduledTask",
     re.compile(r"\bEnable-ScheduledTask\b[^\n]*?(?:-TaskName|-TaskPath)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("scheduled-task", "Unregister-ScheduledTask",
     re.compile(r"\bUnregister-ScheduledTask\b[^\n]*?(?:-TaskName|-TaskPath)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("scheduled-task", "schtasks",
     re.compile(r"\bschtasks(?:\.exe)?\b[^\n]*?(?:/TN)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("boot", "bcdedit",
     re.compile(r"\bbcdedit(?:\.exe)?\b[^\n]*?(/\w+)\s+(\"[^\"]*\"|\S+)?", re.I)),
    ("network", "netsh",
     re.compile(r"\bnetsh(?:\.exe)?\s+([\w ]{1,40}?)(?:\s+\w+)?(?=\s|$|\")", re.I)),
    ("network", "Set-DnsClientServerAddress",
     re.compile(r"\bSet-DnsClientServerAddress\b[^\n]*?(?:-InterfaceAlias|-InterfaceIndex)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("network", "Set-NetAdapter",
     re.compile(r"\bSet-NetAdapter\w*\b[^\n]*?(?:-Name)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("network", "Disable-NetAdapterBinding",
     re.compile(r"\bDisable-NetAdapterBinding\b[^\n]*?(?:-Name|-ComponentID)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("power", "powercfg",
     re.compile(r"\bpowercfg(?:\.exe)?\s+([/-]\w+)", re.I)),
    ("appx", "Remove-AppxPackage",
     re.compile(r"\bRemove-AppxPackage\b[^\n]*?(?:-Package)?\s*(\"[^\"]*\"|'[^']*'|\$\S+|\S+)?", re.I)),
    ("appx", "Remove-AppxProvisionedPackage",
     re.compile(r"\bRemove-AppxProvisionedPackage\b[^\n]*?(?:-PackageName)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("dism", "dism",
     re.compile(r"\bdism(?:\.exe)?\b[^\n]*?(/Disable-Feature|/Enable-Feature|/Add-Capability|/Remove-Capability|/Add-Package|/Remove-Package|/Online)", re.I)),
    ("dism", "Disable-WindowsOptionalFeature",
     re.compile(r"\b(?:Disable|Enable)-WindowsOptionalFeature\b[^\n]*?(?:-FeatureName)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("dism", "Remove-WindowsCapability",
     re.compile(r"\b(?:Remove|Add)-WindowsCapability\b[^\n]*?(?:-Name)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("defender", "Set-MpPreference",
     re.compile(r"\bSet-MpPreference\b[^\n]*?(?:-(\w+))", re.I)),
    ("defender", "Add-MpPreference",
     re.compile(r"\bAdd-MpPreference\b[^\n]*?(?:-(\w+))", re.I)),
    ("file", "Remove-Item",
     re.compile(r"\bRemove-Item\b[^\n]*?(?:-Path|-LiteralPath)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("file", "Move-Item",
     re.compile(r"\bMove-Item\b[^\n]*?(?:-Path|-LiteralPath)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("file", "Copy-Item",
     re.compile(r"\bCopy-Item\b[^\n]*?(?:-Path|-LiteralPath)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("process", "Stop-Process",
     re.compile(r"\bStop-Process\b[^\n]*?(?:-Name)?\s*(\"[^\"]*\"|'[^']*'|\S+)?", re.I)),
    ("process", "taskkill",
     re.compile(r"\btaskkill(?:\.exe)?\b[^\n]*?(?:/IM)\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("ownership", "takeown",
     re.compile(r"\btakeown(?:\.exe)?\b[^\n]*?(/F)\s+(\"[^\"]*\"|\S+)?", re.I)),
    ("ownership", "icacls",
     re.compile(r"\bicacls(?:\.exe)?\s+(\"[^\"]*\"|'[^']*'|\S+)", re.I)),
    ("ownership", "TrustedInstaller",
     re.compile(r"\bTrustedInstaller\b", re.I)),
    ("filesystem-config", "fsutil",
     re.compile(r"\bfsutil(?:\.exe)?\s+(\w+)", re.I)),
]

EXE_RE = re.compile(r"([\w.-]+\.exe)\b", re.I)
VAR_RE = re.compile(r"^\$|^\$\(|^\$\{")
PS_HIVE_RE = re.compile(r"^(HKLM|HKCU|HKCR|HKU|HKCC|HK+\\)", re.I)

# Comandos excluidos de other-exe: no son invocaciones de efecto propio.
EXE_SKIP = {"cmd.exe", "powershell.exe", "pwsh.exe", "conhost.exe", "reg.exe",
            "sc.exe", "bcdedit.exe", "netsh.exe", "powercfg.exe", "dism.exe",
            "schtasks.exe", "taskkill.exe", "takeown.exe", "icacls.exe",
            "fsutil.exe", "where.exe", "whoami.exe"}

PS_EXT = (".ps1", ".psm1")


# ------------------------------------------------------------------ helpers
def norm_line(line: str) -> str:
    return " ".join(line.strip().split())


def line_sha(line: str) -> str:
    return hashlib.sha256(norm_line(line).lower().encode("utf-8")).hexdigest()


def classify_target(tok: str | None) -> tuple[str, str, str]:
    """Devuelve (target, target_kind, value)."""
    if not tok:
        return "", "unresolved", ""
    t = tok.strip().strip(";,)")
    if not t:
        return "", "unresolved", ""
    quoted = (t.startswith("'") and t.endswith("'")) or \
             (t.startswith('"') and t.endswith('"'))
    body = t[1:-1] if quoted else t
    if "$" in body:
        return body, "variable", ""
    if quoted or PS_HIVE_RE.match(body) or re.match(r"^[A-Za-z]:\\", body) \
            or body.startswith(("/", "\\")):
        return body, "literal", (body if len(body) <= 120 else "")
    return body, "unresolved", ""


def strip_comment(line: str) -> str:
    s = line.strip()
    if s.startswith("#"):
        return ""
    return line


def code_flags(line: str) -> list[bool]:
    """Marca cada caracter como codigo (True) o dentro de una cadena (False).

    PowerShell: comillas simples literales ('' escapa), dobles con backtick.
    Se usa para descartar llamadas que solo aparecen dentro de un texto, como
    `throw "reg.exe import failed"`.
    """
    flags = [True] * len(line)
    i = 0
    quote = ""
    while i < len(line):
        c = line[i]
        if quote:
            flags[i] = False
            if quote == "'" and c == "'" and i + 1 < len(line) and line[i + 1] == "'":
                flags[i + 1] = False
                i += 2
                continue
            if c == "`" and quote == '"' and i + 1 < len(line):
                flags[i + 1] = False
                i += 2
                continue
            if c == quote:
                quote = ""
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            flags[i] = False
            i += 1
            continue
        i += 1
    return flags


PS_DRIVE_NON_FILE_RE = re.compile(r"^(Function|Env|Variable|Alias|Cert|WSMan|HKLM|HKCU|HKCR|HKU|HKCC|Registry):", re.I)


def detect(line: str) -> list[tuple[str, str, str, str, str]]:
    """Devuelve (effect_type, command, target, target_kind, value)."""
    out = []
    seen = set()
    flags = code_flags(line)
    for etype, cmd, rx in RULES:
        m = None
        for cand in rx.finditer(line):
            if flags[cand.start()]:
                m = cand
                break
        if not m:
            continue
        groups = [g for g in m.groups() if g]
        tok = groups[-1] if groups else ""
        if etype == "boot" and m.lastindex and m.lastindex >= 1:
            tok = m.group(2) or m.group(1)
        if etype == "ownership" and cmd == "takeown":
            tok = m.group(2) or m.group(1)
        target, kind, value = classify_target(tok)
        # Remove-Item/Move-Item/Copy-Item sobre HKCU:\... es registro, no
        # fichero: ya lo emite la regla de registry de esta misma linea.
        if etype == "file" and PS_DRIVE_NON_FILE_RE.match(target or ""):
            if (target or "").split(":")[0].lower() in (
                    "hklm", "hkcu", "hkcr", "hku", "hkcc", "registry"):
                continue
            kind, value = "unresolved", ""
        key = (etype, cmd)
        if key in seen:
            continue
        seen.add(key)
        out.append((etype, cmd, target, kind, value))
    # Si la linea ya tiene un efecto de registro, el generico "file" del mismo
    # comando es el mismo efecto descrito dos veces.
    if any(t == "registry" for t, *_ in out):
        out = [e for e in out if not (e[0] == "file" and any(
            e[1] == f[1] for f in out if f[0] == "registry"))]
    # other-exe: cualquier .exe no clasificado arriba
    for m in EXE_RE.finditer(line):
        exe = m.group(1)
        if exe.lower() in EXE_SKIP:
            continue
        if any(c == exe for _, c, _, _, _ in out):
            continue
        out.append(("other-exe", exe, "", "unresolved", ""))
    return out


# ------------------------------------------------------------------ fuentes
def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def product_functions() -> list[tuple[str, str, int, int]]:
    with FUNCS.open(encoding="utf-8") as fh:
        return [(r["path"], r["name"], int(r["line_start"]), int(r["line_end"]))
                for r in csv.DictReader(fh, delimiter="\t")
                if r["scope"] == "product"]


def ps_targets() -> list[str]:
    with PART.open(encoding="utf-8") as fh:
        return sorted(r["path"] for r in csv.DictReader(fh, delimiter="\t")
                      if r["treatment"] == "extract"
                      and r["path"].endswith((".ps1", ".psm1", ".cmd", ".vbs")))


def psd1_script_blocks(text: str) -> list[tuple[int, str]]:
    """Extrae (linea_inicial, contenido) de los bloques Script de un .psd1.

    Formatos vistos en Atlas:
        Script = @' ... '@          (here-string)
        Script = 'una linea'
        Script = @( 'a', 'b' )
    """
    blocks: list[tuple[int, str]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if re.match(r"\s*Script\s*=", lines[i]):
            start = i
            chunk = [lines[i]]
            # here-string
            m = re.search(r"@(['\"])\s*$", lines[i])
            if m:
                quote = m.group(1) + "@"
                j = i + 1
                while j < len(lines):
                    chunk.append(lines[j])
                    if lines[j].strip().startswith(quote):
                        break
                    j += 1
                blocks.append((start + 1, "\n".join(chunk)))
                i = j + 1
                continue
            # array o multilinea hasta parentesis cerrado
            depth = lines[i].count("(") - lines[i].count(")")
            j = i + 1
            while depth > 0 and j < len(lines):
                chunk.append(lines[j])
                depth += lines[j].count("(") - lines[j].count(")")
                j += 1
            blocks.append((start + 1, "\n".join(chunk)))
            i = max(j, i + 1)
            continue
        i += 1
    return blocks


def build(root: Path) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    counters: defaultdict[tuple[str, str], int] = defaultdict(int)
    stats = {"funciones_product": 0, "funciones_con_efecto": 0,
             "ficheros_top": 0, "cmd_vbs": 0, "psd1_script": 0}
    fn_lines: defaultdict[str, list[tuple[int, int]]] = defaultdict(list)

    def emit(path: str, container: str, lineno: int, line: str) -> None:
        for etype, cmd, target, kind, value in detect(line):
            k = (path, container)
            item = f"atlas:effect:{path}::{container}#{counters[k]}"
            counters[k] += 1
            rows.append({
                "item_id": item, "path": path, "container": container,
                "line": lineno, "effect_type": etype, "command": cmd,
                "target": target, "target_kind": kind, "value": value,
                "sha256_line": line_sha(line),
            })

    # 1. funciones product
    for path, name, start, end in product_functions():
        stats["funciones_product"] += 1
        fn_lines[path].append((start, end))
        text = read_text(root / path).splitlines()
        before = len(rows)
        for n in range(start, min(end, len(text)) + 1):
            line = strip_comment(text[n - 1]) if n - 1 < len(text) else ""
            if line:
                emit(path, name, n, line)
        if len(rows) > before:
            stats["funciones_con_efecto"] += 1

    # 2/3. codigo de nivel superior + .cmd/.vbs
    for rel in ps_targets():
        p = root / rel
        if not p.is_file():
            continue
        text = read_text(p).splitlines()
        if rel.endswith(PS_EXT):
            stats["ficheros_top"] += 1
            ranges = fn_lines.get(rel, [])
            for n, line in enumerate(text, 1):
                if any(s <= n <= e for s, e in ranges):
                    continue
                line = strip_comment(line)
                if line:
                    emit(rel, "<top>", n, line)
        else:
            stats["cmd_vbs"] += 1
            for n, line in enumerate(text, 1):
                s = line.strip()
                if not s or s.lower().startswith(("rem ", "::", "@echo")):
                    continue
                emit(rel, "<top>", n, line)

    # 4. bloques Script de .psd1
    for p in sorted((root / TWEAKS_DIR).rglob("*.psd1")):
        rel = str(p.relative_to(root)).replace("\\", "/")
        text = read_text(p)
        for start, block in psd1_script_blocks(text):
            stats["psd1_script"] += 1
            for off, line in enumerate(block.splitlines()):
                line = strip_comment(line)
                if line:
                    emit(rel, "<script>", start + off, line)

    rows.sort(key=lambda r: r["item_id"])
    meta = {**stats, "efectos": len(rows)}
    return rows, meta


# ------------------------------------------------------------------- salida
def write_tsv(path: Path, rows: list[dict]) -> None:
    lines = ["\t".join(COLUMNS)]
    for r in rows:
        lines.append("\t".join(str(r.get(c, "")) for c in COLUMNS))
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def summarise(rows: list[dict], meta: dict) -> dict:
    by_type = Counter(r["effect_type"] for r in rows)
    by_kind = Counter(r["target_kind"] for r in rows)
    exes = Counter(r["command"] for r in rows if r["effect_type"] == "other-exe")
    unresolved = Counter(r["effect_type"] for r in rows
                         if r["target_kind"] == "unresolved")
    return {
        **meta,
        "por_tipo": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "por_target_kind": dict(sorted(by_kind.items())),
        "other_exe": dict(sorted(exes.items(), key=lambda kv: -kv[1])),
        "unresolved_por_tipo": dict(sorted(unresolved.items(), key=lambda kv: -kv[1])),
        "ficheros": len({r["path"] for r in rows}),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=ATLAS)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows, meta = build(args.root)
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "atlas-effects.tsv"
    write_tsv(out, rows)
    summary = summarise(rows, meta)
    summary["sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"efectos               : {meta['efectos']} en {summary['ficheros']} ficheros")
        print(f"funciones product     : {meta['funciones_product']} "
              f"({meta['funciones_con_efecto']} con >=1 efecto)")
        print(f"ficheros top-level    : {meta['ficheros_top']} | .cmd/.vbs: {meta['cmd_vbs']}"
              f" | bloques Script .psd1: {meta['psd1_script']}")
        print("por tipo:")
        for k, v in summary["por_tipo"].items():
            print(f"  {k:20s} {v}")
        print("por target_kind:")
        for k, v in summary["por_target_kind"].items():
            print(f"  {k:20s} {v}")
        print(f"other-exe distintos   : {len(summary['other_exe'])}")
        for k, v in list(summary["other_exe"].items())[:20]:
            print(f"  {k:28s} {v}")
        print(f"sha256                : {summary['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
