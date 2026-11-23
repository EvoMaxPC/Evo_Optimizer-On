#!/usr/bin/env python3
"""Sonda de palabras clave sobre los clones de upstream (REQ-005 / REQ-002).

Para cada término cuenta en cuántos FICHEROS aparece, sin distinguir mayúsculas,
en cada repo. Escribe docs/inventory-recon/keyword-probe.tsv con las columnas:

    termino    winutil_ficheros    atlas_ficheros

Y lista aparte los términos con 0 aciertos en ambos y los que dan 0 en uno solo.

Uso:
    python3 tools/ledger_extract/keyword_probe.py
    python3 tools/ledger_extract/keyword_probe.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEST = Path("/tmp/upstream")
DEFAULT_OUT = ROOT / "docs" / "inventory-recon" / "keyword-probe.tsv"

# ~80 términos. Los marcados con (*) son obligatorios por el encargo.
TERMS = [
    # telemetría / privacidad
    "telemetry", "DiagTrack", "CEIP", "debloat", "activity history",
    "location tracking", "tailored experiences", "advertising id", "feedback",
    # seguridad / privilegios
    "TrustedInstaller", "Defender", "BitLocker", "VBS", "Core Isolation",
    "mitigations", "Safe Mode", "UAC", "take ownership",
    # energía / rendimiento
    "hibernat", "SysMain", "prefetch", "MMCSS", "timer resolution", "HAGS",
    "GameDVR", "Game Bar", "fullscreen optimizations", "ultimate performance",
    "powercfg", "Win32 Priority",
    # red
    "Windows Update", "DNS", "Teredo", "LLMNR", "SMB", "IPv6", "NTP",
    "network discovery", "OpenSSH",
    # componentes / limpieza
    "Edge", "OneDrive", "Copilot", "Recall", "Click To Do", "Spotlight",
    "Widgets", "Consumer Features", "Reserved Storage", "Storage Sense",
    "Windows AI", "AppX", "provisioned",
    # gestores de paquetes / reparación
    "winget", "choco", "DISM", "sfc", "ShutUp10", "LibreWolf", "OpenShell",
    "NVCleanstall", "Process Explorer", "WPBT", "Fault Tolerant Heap",
    "Sleep Study", "bcdedit", "boot logo", "ISO", "USB",
    # arquitectura / motor
    "AME Wizard", "Playbook", "Runspace", "Compile.ps1", "Install Plan",
    "Install Session", "Broker", "Toolbox", "Atlas Manager", "Health Check",
    "Pester", "preset", "registry backup", "restore point", "scheduled task",
    "service", "WPF", "xaml", "import", "export",
]


def scan(repo: Path, terms: list[str]) -> dict[str, int]:
    """Cuenta ficheros que contienen cada término (case-insensitive).

    Recorre una vez el árbol y busca todos los términos por fichero para no
    relanzar grep 80 veces.
    """
    hits = {t: 0 for t in terms}
    needles = [(t, t.lower().encode("utf-8")) for t in terms]
    for path in repo.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        low = data.lower()
        for term, needle in needles:
            if needle in low:
                hits[term] += 1
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--terms", type=Path, help="fichero con un término por línea")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    terms = TERMS
    if args.terms:
        terms = [l.strip() for l in args.terms.read_text(encoding="utf-8").splitlines() if l.strip()]

    repos = {}
    for name in ("winutil", "atlas"):
        repo = args.dest / name
        if not repo.is_dir():
            print(f"ERROR: falta el clon {repo}; ejecuta fetch_upstream.py", file=sys.stderr)
            return 2
        repos[name] = scan(repo, terms)
        print(f"[{name}] escaneados; términos con acierto: "
              f"{sum(1 for v in repos[name].values() if v)}/{len(terms)}")

    rows = [(t, repos["winutil"][t], repos["atlas"][t]) for t in terms]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["termino\twinutil_ficheros\tatlas_ficheros"]
    lines += [f"{t}\t{a}\t{b}" for t, a, b in rows]
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    zero_both = [t for t, a, b in rows if a == 0 and b == 0]
    zero_winutil = [t for t, a, b in rows if a == 0 and b > 0]
    zero_atlas = [t for t, a, b in rows if b == 0 and a > 0]

    if args.json:
        print(json.dumps(
            {"terms": len(terms), "rows": [
                {"termino": t, "winutil": a, "atlas": b} for t, a, b in rows],
             "zero_both": zero_both, "zero_winutil": zero_winutil,
             "zero_atlas": zero_atlas}, indent=2, ensure_ascii=False))
    else:
        print(f"\nTSV: {args.out}  ({len(rows)} términos)")
        print(f"0 en ambos      : {zero_both or 'ninguno'}")
        print(f"0 solo en winutil: {zero_winutil or 'ninguno'}")
        print(f"0 solo en atlas  : {zero_atlas or 'ninguno'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
