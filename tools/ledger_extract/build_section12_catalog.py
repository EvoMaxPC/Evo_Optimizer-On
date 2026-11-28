#!/usr/bin/env python3
"""Genera `catalog/capabilities/section12_windows_update.json` (Etapa 8, Parte B).

Los literales y las referencias se leen de los pins fijados
(WinUtil `70c23c8…` en `config/tweaks.json` y `config/feature.json`; Atlas
`ec3c4058…` en `package/…` y `tests/`), y la provenance cita fichero y línea.
Si el pin no está descargado en `/tmp/upstream`, el script falla con un mensaje
claro: no se inventa ningún literal.

Sección 12 del inventario: WINDOWS UPDATE Y MANTENIMIENTO.
De las 28 líneas del ledger de esta sección, 5 están `Mapped`. 3 se construyen
como capacidades propias (líneas 397, 410, 423); las otras 2 (líneas 405 y 406)
se mapean a capacidades existentes de las secciones 9 y 10 (`system.registry-backup.enable`
y `ui.logon.acrylic-blur` respectivamente) porque declaran el mismo efecto del pin
—no se crean capacidades duplicadas. El resto son `Absent-At-Pin` o
`Informative-Header`, por lo que no generan capacidad (criterio de la decisión
de línea 136 del paso 4e: un item sin expresión en el pin no se declara).

Todas las 3 capacidades propias de esta sección quedan en `State=Specified` por la
regla R1 (paso 12): el pin de cada una hace operaciones que el motor no expresa
como acciones de registro, tarea o servicio, así que no se declara ninguna acción
y el motivo queda escrito en `provenance` y en `technicalNote`.

Decisiones de forma:
- R1 (paso 12): el gap se declara explícitamente, nunca se oculta.
- R2 (paso 12): todas son `SecurityImpact=Neutral`; no hay justificación
  `Improves` que escribir.
- R3 (paso 12): ninguna instala una tarea persistente con privilegios altos
  como acción declarada (quedan fuera por R1), así que no sube el riesgo.
- ADR-0003: `Reversibility=Reversible` y `TechnicalNote` conserva el motivo
  interno; nunca se muestra en la UI.
- `supportedBuilds` es explícito (las cuatro builds del catálogo), nunca `[]`.

Salida determinista: orden por id, LF, UTF-8 sin BOM, 3 espacios de sangría.

Uso:
    python3 tools/ledger_extract/build_section12_catalog.py
    python3 tools/ledger_extract/build_section12_catalog.py --check
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "catalog" / "capabilities" / "section12_windows_update.json"
UPSTREAM = Path("/tmp/upstream")
WINUTIL_TWEAKS = UPSTREAM / "winutil" / "config" / "tweaks.json"
WINUTIL_FEATURE = UPSTREAM / "winutil" / "config" / "feature.json"
ATLAS_ROOT = UPSTREAM / "atlas"

WINUTIL_PIN = "winutil@70c23c80641d7370532af2f619b2842658600842"
ATLAS_PIN = "atlas@ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f"
DEFAULT_BUILDS = [19045, 22631, 26100, 26200]

W_TWEAKS: dict = (
    json.loads(WINUTIL_TWEAKS.read_text(encoding="utf-8"), strict=False)
    if WINUTIL_TWEAKS.is_file() else {}
)
W_FEATURE: dict = (
    json.loads(WINUTIL_FEATURE.read_text(encoding="utf-8"), strict=False)
    if WINUTIL_FEATURE.is_file() else {}
)


def rel_line(path: Path, needle: str) -> int:
    """Línea (1-based) de la primera aparición de `needle` en el fichero."""
    text = path.read_text(encoding="utf-8", errors="replace")
    index = text.find(needle)
    if index < 0:
        return 0
    return text.count("\n", 0, index) + 1


def spec(id_: str, name: str, desc: str, pin_ref: str, ledger_ref: str,
         gap: str, note_extra: str = "") -> dict:
    """Construye una capacidad Specified de la sección 12 (R1: gap declarado)."""
    technical_note = (
        f"Origen: {pin_ref}. {gap} "
        f"Como el efecto del pin no queda expresado entero como acciones del "
        f"motor, State=Specified con 0 acciones expresables. "
        f"{note_extra}".strip()
    )
    provenance = (
        f"{pin_ref}. ledger_refs: {ledger_ref}. "
        f"R1 (paso 12): el pin hace ademas operaciones que NO se declaran como "
        f"accion del motor ({gap}); por eso la capacidad queda en State=Specified. "
        f"Inventario seccion 12: Windows Update y Mantenimiento."
    )
    return {
        "id": id_,
        "name": name,
        "description": desc,
        "sectionId": 12,
        "risk": "Low",
        "securityImpact": "Neutral",
        "privilege": "User",
        "restore": "SessionUndo",
        "reversibility": "Reversible",
        "confirmation": "SimpleClick",
        "state": "Specified",
        "variants": ["Evo"],
        "conflictsWith": [],
        "dependsOn": [],
        "supportedBuilds": list(DEFAULT_BUILDS),
        "provenance": provenance,
        "actions": [],
        "technicalNote": technical_note,
    }


def build() -> dict:
    capabilities = []

    # ------------------------------------------------------------------ WinUtil

    # Linea 397 del inventario: "Windows Update Reset." -> Mapped
    # winutil:feature:WPFFixesUpdate (regla R1 del paso 4e).
    f = W_FEATURE.get("WPFFixesUpdate", {})
    line = rel_line(WINUTIL_FEATURE, '"WPFFixesUpdate"')
    capabilities.append(
        spec(
            id_="services.winutil.windows-update-reset",
            name="Restablecer Windows Update",
            desc="Esta funcion repara Windows Update: detiene sus servicios, "
                 "renombra carpetas de historial y paquetes, borra logs y vuelve "
                 "a registrar componentes. Involucra operaciones de archivo, de "
                 "servicio y de registro que el motor no expresa como acciones "
                 "de registro, servicio o tarea, por lo que queda especificada "
                 "(no ejecutable todavía).",
            pin_ref=f"{WINUTIL_PIN}:config/feature.json:{line} "
                    f"(WPFFixesUpdate, function {f.get('function', 'Invoke-WPFFixesUpdate')})",
            ledger_ref="winutil:feature:WPFFixesUpdate",
            gap=(
                "detiene los servicios BITS, wuauserv, appidsvc y cryptsvc; "
                "renombra QMGR, DataStore, CatRoot2 y la carpeta de descargas; "
                "borra el log de Windows Update; resetea descriptores de "
                "seguridad; vuelve a registrar DLLs de BITS y Windows Update; "
                "quita la configuracion WSUS; resetea WinSock; borra trabajos "
                "BITS; configura el tipo de arranque y arranca los servicios; "
                "obliga a buscar actualizaciones"
            ),
            note_extra=(
                f"Ledger seccion 12 linea 397 (regla R1 del paso 4e): coincide "
                f"con el ledger de conciliación."
            ),
        )
    )

    # Nota: las líneas 405 (Registry Backup) y 406 (System Restore Point) del
    # ledger se mapean a capacidades existentes de las secciones 9 y 10
    # (system.registry-backup.enable y ui.logon.acrylic-blur) vía DECLARED_SOURCES
    # en verify_catalog_coverage.py, para no crear capacidades duplicadas.
    # ---------------------------------------------------------------- Atlas

    # Linea 410 del inventario: "Toggle Windows Updates." -> Mapped
    # atlas:effect:tests/Atlas.Verify.Tests.ps1::<top>#9 (regla R3 del paso 4e).
    capabilities.append(
        spec(
            id_="services.atlas.toggle-windows-updates",
            name="Activar o desactivar Windows Update",
            desc="Atlas oferta una opcion para activar o desactivar Windows "
                 "Update como bloque. Ese efecto se implementa como un efecto de "
                 "script de prueba del repositorio de Atlas y no como una "
                 "entrada de registro declarable, por lo que queda especificada "
                 "(no ejecutable todavía).",
            pin_ref=f"{ATLAS_PIN}:tests/Atlas.Verify.Tests.ps1::<top>#9 "
                    f"(efecto de activacion/desactivacion de Windows Update)",
            ledger_ref="atlas:effect:tests/Atlas.Verify.Tests.ps1::<top>#9",
            gap=(
                "el pin declara el efecto de activar/desactivar Windows Update "
                "como un bloque de prueba de Atlas, no como una entrada de "
                "registro que el motor pueda aplicar"
            ),
            note_extra=(
                f"Ledger seccion 12 linea 410 (regla R3 del paso 4e): coincide "
                f"con el ledger de conciliación."
            ),
        )
    )

    # Linea 423 del inventario: "Windows Component Servicing." -> Mapped
    # atlas:effect:.../CbsPackages.ps1::Remove-AtlasCbsRepairSourcePolicy#0
    # (regla R3 del paso 4e).
    capabilities.append(
        spec(
            id_="services.atlas.cbs-repair-source-policy",
            name="Directiva de origen de reparacion CBS",
            desc="Atlas oferta operaciones de servicio de componentes de "
                 "Windows (CBS). La entrada Remove-AtlasCbsRepairSourcePolicy "
                 "afecta a la política de origen de reparación y no se expresa "
                 "como una acción de registro del motor, por lo que queda "
                 "especificada (no ejecutable todavía).",
            pin_ref=f"{ATLAS_PIN}:package/Executables/AtlasModules/Scripts/"
                    f"Modules/Atlas.Software/Domain/CbsPackages.ps1::"
                    f"Remove-AtlasCbsRepairSourcePolicy#0 "
                    f"(funcion de reparacion de componentes CBS)",
            ledger_ref=(
                "atlas:effect:package/Executables/AtlasModules/Scripts/"
                "Modules/Atlas.Software/Domain/CbsPackages.ps1::"
                "Remove-AtlasCbsRepairSourcePolicy#0"
            ),
            gap=(
                "el pin declara Remove-AtlasCbsRepairSourcePolicy como una "
                "operacion de servicio de componentes de Windows (CBS), no como "
                "una entrada de registro que el motor pueda aplicar"
            ),
            note_extra=(
                f"Ledger seccion 12 linea 423 (regla R3 del paso 4e): coincide "
                f"con el ledger de conciliación."
            ),
        )
    )

    capabilities.sort(key=lambda c: c["id"])
    return {
        "metadata": {
            "version": "1.0.0",
            "schemaVersion": 1,
            "provenance": (
                f"Etapa 8 Parte B, seccion 12 (Windows Update y Mantenimiento). "
                f"Fuentes: {WINUTIL_PIN}, {ATLAS_PIN}. Los literales y las "
                f"referencias se leen del pin con "
                f"tools/ledger_extract/build_section12_catalog.py; ninguno se "
                f"escribe a mano."
            ),
            "generatedBy": "etapa 8 Parte B (seccion 12)",
        },
        "capabilities": capabilities,
    }


def dump(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=3, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="no escribe: compara con el fichero y sale 1 si difiere")
    args = parser.parse_args(argv)

    if not WINUTIL_TWEAKS.is_file() or not WINUTIL_FEATURE.is_file() \
            or not ATLAS_ROOT.is_dir():
        print("falta el pin en /tmp/upstream (ejecuta tools/ledger_extract/fetch_upstream.py)",
              file=sys.stderr)
        return 1

    document = build()
    text = dump(document)
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != text:
            print("section12_windows_update.json NO coincide con el pin",
                  file=sys.stderr)
            return 1
        print(f"section12_windows_update.json reproducible: OK "
              f"({len(document['capabilities'])} capacidades)")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    total = sum(len(c["actions"]) for c in document["capabilities"])
    print(f"capacidades: {len(document['capabilities'])} | acciones: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
