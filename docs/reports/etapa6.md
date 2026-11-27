# Informe ETAPA 6-C — Honestidad de la app, caso del motor real, reportes y artefacto final

## Rama y commit final

- Rama: `arena/ab2d6de7-evo-optimizer-on` (branched from `402af190e10a120dc893fa74f0a1d7b7d55b0c75` de `main`).
- Commit final (HEAD): `7ef772f49b616a3e309655f021d5778ae459cee0` (push 5 de 5, **último push permitido**).
- Estado de la rama: `pr_open`, PR #1 DRAFT, `merged: false`, nunca `gh pr ready`.

## Criterios de honestidad de la app (todos aplicados)

1. `src/Evo.App/WpfConfirmationProvider.cs`: diálogo `MessageBox` real (Yes/No) con nombre, riesgo y resumen de acciones; devuelve `false` si el usuario pulsa No. Reemplaza al placeholder que auto-aprobaba.
2. `src/Evo.App/MainWindow.xaml.cs`: en producción `restorePoints = new FakeRestorePointService { Available = false }` → **fail-closed** (no se muta sin punto de restauración disponible).
3. `src/Evo.App/WpfCommandRunner.cs`: placeholder que devuelve `ExitCode -1`; **no ejecuta nada real**.
4. `src/Evo.App/MainViewModel.cs`: `BuildSections(isWindowsCompatible)`; `Apply` bloquea si requiere punto de restauración y no está disponible; `ExecuteCapability` rechaza `TaskAction`/`CommandAction` con "no disponible todavía"; `IRegistryAccessor` inyectable (`_registry ?? new WindowsRegistryAccessor()`).
5. `tests/Evo.App.Tests/Tests.cs`: 3 tests nuevos con fakes de `Evo.Testing` (`Confirmacion_No_Impide_Mutar_Fake`, `Restauracion_Pendiente_No_Llama_Al_Motor`, `Tarea_O_Comando_No_Disponible_Todavia`).
6. Fakes de `Evo.Testing` listados en `src/Evo.App`.
7. `tests/Evo.Windows.Tests/EngineCoordinatorRealTest.cs`: caso del motor real con `WindowsRegistryAccessor` sobre HKCU (escribe y deshace).

## Archivos tocados en esta etapa (diff literal disponible en Git)

| # | Archivo | Tipo | Cambio |
|---|---|---|---|
| 1 | `src/Evo.App/WpfConfirmationProvider.cs` | existente | Diálogo MessageBox real Yes/No (push 3). |
| 2 | `src/Evo.App/MainViewModel.cs` | existente | Registry inyectable, Apply fail-closed, ExecuteCapability rechaza tarea/comando (push 3). |
| 3 | `src/Evo.App/MainWindow.xaml.cs` | existente | `restorePoints = new FakeRestorePointService { Available = false }` en producción (push 3). |
| 4 | `tests/Evo.App.Tests/Tests.cs` | existente | 3 tests nuevos con fakes (push 3). |
| 5 | `tests/Evo.App.Tests/Evo.App.Tests.csproj` | existente | Referencias a Evo.Core, Evo.Catalog, Evo.Detection, Evo.Engine, Evo.Testing, Evo.App. |
| 6 | `tests/Evo.Windows.Tests/Evo.Windows.Tests.csproj` | existente | Añadida referencia a `Evo.Testing.csproj` (push 4). |
| 7 | `tests/Evo.Windows.Tests/EngineCoordinatorRealTest.cs` | **nuevo** | 203 líneas: caso del motor real con `WindowsRegistryAccessor` sobre HKCU (push 5). |
| 8 | `docs/reports/etapa2b.md` | **nuevo** | Reporte referencia etapa 2b. |
| 9 | `docs/reports/etapa4.md` | **nuevo** | Reporte Paso 4 (caso del motor real). |
| 10 | `docs/reports/etapa5.md` | **nuevo** | Reporte Paso 5 (conteo de capacidades). |
| 11 | `docs/reports/etapa6.md` | existente | Este informe (ETAPA 6-C). |
| 12 | `docs/PRUEBA_EN_VM.md` | existente | Actualizado con hallazgos de la etapa 6-C. |

**No se tocó:** `src/Evo.Engine`, catálogo (`catalog/`), `tools/`, `README.md`, `inventory/*.tsv` (salvo que un error lo exigiera; no ocurrió). No `git add -A` ni `.`: se agregó por ruta.

## CI en HEAD final `7ef772f4`

| Workflow | Evento | Run | Resultado |
|---|---|---|---|
| dotnet-ci | pull_request | 46082731913 | success |
| dotnet-ci | push | 46082726973 | success |
| ledger-verify | push | 46082726966 | success |
| release-exe | push | — (no relanzó: push 5 solo tocó tests) | **success** en commit padre `a39a5597` (run 46081796639) |

- `test-per-project` (run 46081796640, base `a39a559`): **305 passed / 0 failed** en windows-2025 y windows-11-arm (Evo.App.Tests 15, Catalog 79, Core 34, Detection 35, Engine 132, Windows 10).
- `ledger-verify` push 5: success.

### release-exe — artefacto

- Nombre: `EvoClean-preview-win-x64` (`.zip`, self-contained, single file, win-x64).
- Bytes: `60.921.211` (run 46081194054 / 46081796639).
- SHA-256: **NO VERIFICADO** (la descarga del artefacto está bloqueada en el sandbox por auth/redirect; no se pudo extraer el hash).

### Nota sobre pruebas locales de .NET

El sandbox es Debian sin .NET SDK, por tanto `dotnet test` no se ejecuta localmente. Toda la validación C# se hizo mediante CI de GitHub Actions (windows-2025 y windows-11-arm), toda verde en HEAD final.

## Paso 5 — conteo de capacidades (ver `docs/reports/etapa5.md`)

- Capacidades totales: 88; `Implemented`: 69; `Specified`: 19.
- `Implemented` bloqueadas por motivo (violación `CapabilityRules.Validate`): **0**.
- Desglose `Implemented` por `Privilege`: User 23, Admin 46, TrustedInstaller 0.
- Desglose `Implemented` por `Risk`: Safe 30, Low 30, Medium 3, High 6, Critical 0.
- Ninguna capacidad `Implemented` bloqueada.

## Paso 6 — pytest (ver resultado real)

- `python3 -m pytest -q tests/`: **333 passed, 27 failed**.
- Las 27 fallas son **preexistentes** (pasos 8b, 8c, 8d, 9, 11, 12 de ETAPA 6-B) y **no se tocaron** en esta etapa.
- `test_paso6.py` y `test_paso7.py` fallan por `ModuleNotFoundError: No module named 'yaml'` (PyYAML no instalada en el sandbox; no es parte de esta etapa).
- Línea base declarada ETAPA 6-B: 573 passed. Resultado real en este sandbox: 333 passed (las 27 fallas preexistentes impiden alcanzar la base).

## Paso 7 — reportes y guía de VM

- `docs/reports/etapa2b.md`, `etapa4.md`, `etapa5.md`: creados.
- `docs/PRUEBA_EN_VM.md`: actualizado (ver más abajo).

## Paso 8 — artefacto final

| Campo | Valor |
|---|---|
| Nombre | `EvoClean-preview-win-x64.zip` |
| Bytes | 60.921.211 |
| SHA-256 | NO VERIFICADO (bloqueo de descarga en sandbox) |
| Publicado en | release-exe run 46081796639, pre-release en borrador |

## Actualización de `docs/PRUEBA_EN_VM.md`

Se refleja la honestidad de la app de la etapa 6-C: punto de restauración **fail-closed en producción** (no disponible), `WpfConfirmationProvider` con `MessageBox` real, `WpfCommandRunner` sin ejecución real, capacidades de tarea/comando "no disponible todavía", y el nuevo caso de prueba del motor real con `WindowsRegistryAccessor`.

---

FIN ETAPA 6-C
