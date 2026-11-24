# Paso 6 — Cimientos en .NET 10, detector de Windows y contratos de arquitectura

Fecha: 2026-11-23 · Rama `arena/ab2d6de7-evo-optimizer-on` · HEAD de partida `18f114b`.
Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f` · WinUtil `70c23c80641d7370532af2f619b2842658600842`.

---

## T0 — Evidencia

```
$ git rev-parse HEAD
18f114b96e972d69ef7f0aa064fbb9160b1ea112
$ git ls-remote origin refs/heads/arena/ab2d6de7-evo-optimizer-on
18f114b96e972d69ef7f0aa064fbb9160b1ea112	refs/heads/arena/ab2d6de7-evo-optimizer-on
$ sha256sum docs/requirements/INVENTARIO_USUARIO.md
0b6aeaef0aa2142bce342f0cbed6bcd2c19030555ff3a38c3699c8d1dad2f709
```

El sandbox es Debian 12 **sin dotnet** (`dotnet: command not found`): toda
compilación y ejecución de .NET ocurre en GitHub Actions sobre runners Windows.

---

## T1 — Propiedades globales y avisos legales

`Directory.Build.props` (raíz) define, **una sola vez**:

| Propiedad | Valor |
|---|---|
| `TargetFramework` | `net10.0-windows` |
| `Nullable` | `enable` |
| `ImplicitUsings` | `enable` |
| `TreatWarningsAsErrors` | `true` |
| `AnalysisLevel` | `latest` |
| `Company` | `EvoMaxPC` |
| `Product` | `EVO CLEAN` |
| `Copyright` | `Copyright (c) 2026 EvoMaxPC. GPL-3.0-only.` |

Ningún `.csproj` redeclara esas propiedades (lo impone el validador). Los
proyectos de test pueden rebajar `TreatWarningsAsErrors` (analizadores de xUnit).

`THIRD_PARTY_NOTICES.md` gana la **sección 3**: O&O ShutUp10++, Process
Explorer y NVCleanstall **no se redistribuyen**; la descarga la inicia el
usuario contra el sitio del titular y sus licencias no las cubre la GPL-3.0 del
proyecto. Las secciones 1 (WinUtil, MIT) y 2 (Atlas, GPL-3.0-only) se mantienen
con sus pins.

---

## T2 — Catálogo de versiones (`catalog/windows-releases.json`)

| id | build | InstallationType | esuRequired | rango |
|---|---|---|---|---|
| `win10-22h2` | 19045 | Client | **true** | cerrado |
| `win11-23h2` | 22631 | Client | false | cerrado |
| `win11-24h2` | 26100 | Client | false | cerrado |
| `win11-25h2` | 26200 | Client | false | cerrado |
| `win11-26h2` | 27600 | Client | false | abierto hasta `policy.maxSupportedBuild` = 27999 |

Política declarada en el propio dato: `unknownBuild: "reject"`,
`nonClientInstallationType: "reject"`. Cada entrada lleva `provenance` (REQ-002).
Encima de 27999 el build es desconocido (fail-closed), porque 26H2 se declara
como «27600+» y el tope real **NO VERIFICADO**.

---

## T3 — Proyectos y contratos

- `src/Evo.Core`: 7 enums (`RiskLevel`, `SecurityImpact`, `PrivilegeLevel`,
  `RestoreLevel`, `ConfirmationType`, `CapabilityState`, `Variant`) +
  `CompatibilityStatus`; `CapabilityContract` (14 propiedades) y
  `CapabilityRules` (mínimos por riesgo + validación); interfaces
  `ISystemEnvironment`, `IRegistryAccessor`, `IServiceAccessor`,
  `ITaskAccessor`, `IProcessAccessor`, `ICommandRunner`, `ICapabilityExecutor`.
- `src/Evo.Detection`: `WindowsDetector`, `CompatibilityResult`,
  `ServerNotSupportedException`, `WindowsRelease`, `WindowsReleaseCatalog`
  (esquema estricto en código, sin dependencias externas).
- `tests/Evo.Core.Tests` (19 casos) y `tests/Evo.Detection.Tests` (24 casos).

Reglas de riesgo implementadas: `Critical → TypeOperationName`,
`High → SummaryAndRestorePoint`, `RestoreLevel.None` incompatible con
`Risk >= High`, `SecurityImpact.Reduces` exige `Risk >= Medium`,
`TrustedInstaller` exige `Risk >= High`.

Detección: `CurrentBuildNumber`, `UBR`, `EditionID`, `InstallationType` del
registro (`HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion`); `ProductName`
**no** se usa (ERRATA-EVO-003). Orden de veredictos: `Indeterminate` →
`ServerRejected` → `UnknownBuildRejected` → `ArchitectureRejected` →
`SupportedWithWarning`/`Supported`.

---

## T4 — Workflow `.github/workflows/dotnet-ci.yml`

Triggers: push y PR sobre `arena/**` y `main`, con filtros de ruta. Matrix:
`windows-2025` (bloqueante) y `windows-11-arm` (`continue-on-error`, es el único
runner cliente real). Steps: checkout@v4 → setup-dotnet@v4 (`10.0.x`) →
`dotnet --list-sdks` → validador Python → restore → build Release →
test con logger `trx` → resumen de contadores → SHA de artefactos →
`publish-report.sh` a `ci-report`.

---

## T5 — Validador local

`tools/dotnet_tools/validate_dotnet_structure.py` (sin dependencias fuera de la
librería estándar): solución completa y sin GUIDs duplicados, XML de los
`.csproj`, no redeclaración de propiedades heredadas, esquema estricto del
catálogo (builds no solapados, `Client`, rangos, `maxSupportedBuild`,
`provenance`) y presencia de los avisos legales.

```
$ python3 tools/dotnet_tools/validate_dotnet_structure.py
proyectos : 4
  - src/Evo.Core/Evo.Core.csproj
  - src/Evo.Detection/Evo.Detection.csproj
  - tests/Evo.Core.Tests/Evo.Core.Tests.csproj
  - tests/Evo.Detection.Tests/Evo.Detection.Tests.csproj
releases  : 5
estructura .NET: OK
$ echo $?
0
```

---

## T6 — Tests y CI

```
$ python3 -m pytest tools/ledger_extract/tests tests -q
218 passed in 3.80s
```

199 previos + 19 nuevos (`tests/test_paso6.py`). `ledger-verify` ejecuta ahora
las dos carpetas y publica `dotnet-structure.txt`/`.json`.

---

## Desviaciones

1. **`global.json`** con `rollForward: latestFeature` y `allowPrerelease: true`:
   si .NET 10 pasa a GA el pin del SDK no rompe. Si el runner no tiene 10.0.100
   exacto, se acepta la feature band más alta.
2. **`windows-11-arm` con `continue-on-error`**: GitHub puede retirar el runner
   o no tener SDK 10 para ARM64 todavía. Su resultado se publica igual en
   `ci-report`, pero no bloquea el PR (el criterio P5 se evalúa sobre el job
   bloqueante).
3. Los tests rebajan `TreatWarningsAsErrors` a `false` **solo** para los
   analizadores de xUnit; el código de producto lo mantiene en `true`.
4. El paso a `windows-11-arm` como runner de tests de *detección* no valida
   AppX/Store/Explorer: eso sigue reservado a las VM del responsable.

## Supuestos

- `dotnet-version: '10.0.x'` existe ya como canal instalable en los runners
  hosted (a fecha de este commit, .NET 10 está en la ventana GA/preview).
  Si CI demuestra lo contrario, se ajustará a `10.0.x` + `dotnet-quality`.
- La build de Windows 11 26H2 es 27600 y su tope práctico 27999 (elegido en el
  catálogo, no medido).

## Riesgos

- `AnalysisLevel: latest` + `TreatWarningsAsErrors` puede activar analizadores
  CA nuevos con cada feature band del SDK y romper el build sin cambios de
  código. Mitigación: `NoWarn` puntual y `AnalysisMode Default`.
- Las versiones de paquetes xUnit/Test.Sdk no se pudieron verificar contra
  nuget.org desde el sandbox (red bloqueada): **NO VERIFICADO** hasta el primer
  run de CI.
