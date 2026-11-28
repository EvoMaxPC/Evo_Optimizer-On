# Informe ETAPA 6-E — Corregir detección de arquitectura de la app + 2 deudas de la 6-D

## Rama y commits (todos subidos a origin; HEAD final en origin)

- Rama: `arena/ab2d6de7-evo-optimizer-on`.
- Push 1 (6-E): `7f91652fe9fa07ee291fba6641565a8017335c1a` (arquitectura RuntimeInformation + tests nuevos + csproj) → CI falló build (CS0120).
- Push 2 (6-E): `e40026946e1bf5ee960f9857d7aa7eaf17e5da02` (califica enum Architecture) → CI falló build (Wasm64 + using).
- Push 3 (6-E): `14669fcc56ea10b54cd643503197fd36d28ec576` (quita Wasm64 + fix using + etapa6e.md + PRUEBA_EN_VM.md) → CI falló build (using Evo.Core.Execution); ledger-verify success.
- Push 4 (6-F): `223608f3df3c91a6d3563e0f0e084a953d5af09f` (fix using Evo.Engine.Execution) → CI falló build (SecurityException using).
- Push 5 (6-F): `e4755a820c0dffb968d7f26619b85b6d54f72c18` (GetKind propaga permisos; corrige aserción detector) → CI falló build (falta using System.Security).
- Push 6 (6-F): `4cfc7fb2c09d3dd1915abf522d0e44e718060d28` (agrega using System.Security) → **CI verde en todos los workflows**.
- HEAD final (origin y local): `4cfc7fb2c09d3dd1915abf522d0e44e718060d28`.
- Límite de 3 pushes de 6-F agotado. Este informe (etapa6e.md) se actualizó en commit local; no queda pendiente de push de código porque CI ya está verde.

## PASO 1 — Causa real del string vacío (demostrada con código literal)

### a) Quién genera el mensaje
`src/Evo.Detection/WindowsDetector.cs:104`:
```csharp
Reason = $"Arquitectura '{architecture}' no declarada para {release.DisplayName}.",
```
(src/Evo.Detection es de solo lectura en esta etapa: no se toca.)

### b) ISystemEnvironment completo (src/Evo.Core/System/ISystemEnvironment.cs)
```csharp
public interface ISystemEnvironment
{
    int CurrentBuild { get; }        // build del kernel
    int UBR { get; }                 // Update Build Revision
    string EditionID { get; }        // p. ej. Professional
    string InstallationType { get; } // Client o Server
    string Architecture { get; }     // x64, arm64 o x86
    bool IsAdmin { get; }
    bool IsElevated { get; }
}
```

### c) src/Evo.App/WindowsSystemEnvironment.cs (ANTES de la corrección)
```csharp
public string Architecture => ReadString("ProcessorArchitecture") ?? string.Empty;
```
Leía `ProcessorArchitecture` de `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion`. En la VM Windows 11 25H2 ese valor devuelve `""`.

### d) WindowsDetector (src/Evo.Detection, solo lectura)
`Detect()` hace `architecture = Normalize(_environment.Architecture)` (línea 45), luego `if (!release.SupportsArchitecture(architecture))` (líneas 90-97) → `ArchitectureRejected` con "Arquitectura '' no declarada...".

### e) Arquitecturas del catálogo (catalog/windows-releases.json, solo lectura)
Valores distintos del campo `architectures` y a qué builds aplican:
```
arm64: [(19045, 'Windows 10 22H2'), (22631, 'Windows 11 23H2'), (26100, 'Windows 11 24H2'), (26200, 'Windows 11 25H2'), (27600, 'Windows 11 26H2')]
x64:   [(19045, 'Windows 10 22H2'), (22631, 'Windows 11 23H2'), (26100, 'Windows 11 24H2'), (26200, 'Windows 11 25H2'), (27600, 'Windows 11 25H2')]
```
Todas las arquitecturas declaradas en el catálogo: exactamente `['arm64', 'x64']`.

### f) Dónde se crea el entorno real
`src/Evo.App/MainWindow.xaml.cs:21`: `var environment = new WindowsSystemEnvironment();` → pasado al detector en `MainViewModel.cs:118`.

### Causa real (frase)
`WindowsSystemEnvironment.Architecture` leía `ProcessorArchitecture` del registro, que en la VM devuelve string vacío `""`; `Normalize("")` devolvía `""`, `SupportsArchitecture("")` era falso, y el detector rechazaba con "Arquitectura '' no declarada para Windows 11 25H2." aunque build/UBR/edición/Cliente se detectaban bien.

## PASO 2 — Corrección aplicada

Archivo modificado: `src/Evo.App/WindowsSystemEnvironment.cs`.

- `using System.Runtime.InteropServices;` y `using System.Runtime.CompilerServices;`.
- `[assembly: InternalsVisibleTo("Evo.App.Tests")]` para poder testear el mapeo sin Windows.
- `public string Architecture => MapArchitecture(RuntimeInformation.OSArchitecture);`
- Método puro y estático (mapea exactamente a los strings del catálogo `x64`/`arm64`; lo no declarado → valor no compatible, nunca se inventa compatibilidad):
```csharp
internal static string MapArchitecture(Architecture architecture) => architecture switch
{
    global::System.Runtime.InteropServices.Architecture.X64 => "x64",
    global::System.Runtime.InteropServices.Architecture.Arm64 => "arm64",
    global::System.Runtime.InteropServices.Architecture.X86 => "x86",
    var other => $"desconocido-{other}",
};
```
`X86` → `"x86"` (no declarado en catálogo → el detector lo rechaza, no se inventa compatibilidad). Cualquier otro (Arm, desconocido) → `"desconocido-..."` (no declarado → rechazado).

### Otros miembros de ISystemEnvironment que pueden devolver vacío silenciosamente (reporte, sin cambiar para no expandir alcance)
- `EditionID`: `ReadString("EditionID") ?? string.Empty` → puede ser vacío silencioso (no afecta compatibilidad, que se resuelve por build). Reportado, no corregido.
- `UBR`: `0` si falla → silencioso pero no crítico. Reportado, no corregido.
- `InstallationType`: `?? string.Empty` → vacío, pero el detector lo rechaza ("solo Client").
- `CurrentBuild`: `0` si falla → el detector lo rechaza ("No se pudo leer CurrentBuildNumber").

## PASO 3 — Tests nuevos (PASA en test-console.txt de ambos runners)

Archivos nuevos:
- `tests/Evo.App.Tests/ArchitectureTests.cs`: `[Theory]` de mapeo (X64→x64, Arm64→arm64, X86→x86, Arm→desconocido) + `EntornoReal_Arquitectura_NoVacia_Y_DeclaradaEnCatalogo` (instancia `WindowsSystemEnvironment` real, verifica arquitectura no vacía y presente en `catalog/windows-releases.json` leído con `WindowsReleaseCatalog.LoadFromFile`).
- `tests/Evo.Windows.Tests/DetectorRealArchitectureTests.cs`: `DetectorReal_NoRechazaPorArquitecturaVacia` — `WindowsDetector` con `WindowsSystemEnvironment` real + `WindowsRegistryAccessor` real + `WindowsReleaseCatalog` real; verifica que `resultado.Architecture` no esté vacía y que el motivo no contenga "Arquitectura ''".

Referencias agregadas (imprescindibles): `Evo.Windows.Tests.csproj` referencia ahora también `Evo.App` y `Evo.Detection`.

## PASO 4 — Deuda 1: rollback real de RegistryDeleteKeyExecutor

Archivo nuevo: `tests/Evo.Windows.Tests/RegistryDeleteKeyRealRollbackTest.cs`.

Test `BorradoReal_RestauraValores_Kinds_Y_Subclave`:
- Siembra bajo `HKCU\Software\EvoClean.Tests\<Guid>`: DWord `ValDWord`=42, String `ValStr`="hola", Binary `ValBin`=[1,2,3], subclave `Sub` con DWord `SubVal`=99.
- Ejecuta `RegistryDeleteKeyExecutor` real (Recursive=true) con `WindowsRegistryAccessor` real.
- Verifica borrado (clave no existe) + 1 journal entry.
- `RollbackAsync` real + verifica: clave recreada, valores restaurados (42 / "hola" / [1,2,3]), **kinds restaurados** (DWord/String/Binary vía `GetKind`), subclave `Sub` existe con `SubVal`=99.
- `Dispose()` borra la clave de prueba (recursiva).

**Resultado:** PASÓ en test-console.txt de ambos runners → cierra la deuda 1 de la 6-D (antes solo comprobaba valores y existencia de la clave, no kinds ni subclaves).

## PASO 5 — Deuda 2: GetKind acotado

Archivo modificado: `src/Evo.Windows/WindowsRegistryAccessor.cs`.

`GetKind` antes (catch genérico tragaba todo):
```csharp
try { return key.GetValueKind(valueName); } catch { return RegistryValueKind.Unknown; }
```

`GetKind` después (catch-all que devuelve Unknown para valor/clave inexistente; `UnauthorizedAccessException` y `SecurityException` se propagan):
```csharp
try
{
    return key.GetValueKind(valueName);
}
catch (UnauthorizedAccessException)
{
    throw;
}
catch (SecurityException)
{
    throw;
}
catch
{
    // Valor o clave inexistente (u otro fallo de lectura): se trata como
    // desconocido, como hace el resto del motor.
    return RegistryValueKind.Unknown;
}
```

Comprobación de fail-closed: `src/Evo.Engine/EngineCoordinator.cs` líneas 351-381 atrapan `Exception` (excepto OutOfMemoryException) del `executor.ExecuteAsync` y las convierten en `ActionResult.Fail` (sin mutar). Por tanto propagar una excepción de permisos desde `GetKind` es seguro: el motor la convierte en fallo.

No se agregó test de fallo de permisos: no es posible simular `UnauthorizedAccessException` en CI de Windows (el runner corre con privilegios de administrador). Se reporta como tal. `GetStatus` de servicios no se cambió en esta ronda (solo se reporta).

## PASO 6 — CI y artefacto (HEAD final `4cfc7fb2c09d3dd1915abf522d0e44e718060d28`)

| Run id | Workflow | Evento | head_sha (40 chars) | Conclusión |
|---|---|---|---|---|
| 46090885986 | dotnet-ci | push | 4cfc7fb2c09d3dd1915abf522d0e44e718060d28 | success |
| 46090890624 | dotnet-ci | pull_request | 4cfc7fb2c09d3dd1915abf522d0e44e718060d28 | success |
| 46090885980 | ledger-verify | push | 4cfc7fb2c09d3dd1915abf522d0e44e718060d28 | success |
| 46090885961 | release-exe | push | 4cfc7fb2c09d3dd1915abf522d0e44e718060d28 | success |

PR #1: `draft:true`, `merged:false`, head `4cfc7fb2c09d3dd1915abf522d0e44e718060d28` (verificado con `gh api repos/EvoMaxPC/Evo_Optimizer-On/pulls/1`).

### test-per-project.txt literal del dotnet-ci push (run 46090885986, ambos runners)

```
Evo.App.Tests: total=20 passed=20 failed=0
Evo.Catalog.Tests: total=79 passed=79 failed=0
Evo.Core.Tests: total=34 passed=34 failed=0
Evo.Detection.Tests: total=35 passed=35 failed=0
Evo.Engine.Tests: total=132 passed=132 failed=0
Evo.Windows.Tests: total=13 passed=13 failed=0
```
Total: **313 passed / 0 failed** (> 306 ✓). Evo.App.Tests pasó de 15 a 20 (+5 tests nuevos de 6-E: 4 casos Theory de mapeo + 1 Fact entorno real). Evo.Windows.Tests pasó de 11 a 13 (+2 tests nuevos de 6-E: detector real + rollback real).

### test-console.txt: tests nuevos de 6-E (todos Passed en ambos runners)

| Test | Línea real (grep -n) | Resultado windows-2025 | Resultado windows-11-arm |
|---|---|---|---|
| ArchitectureMappingTests.MapArchitecture_...(X86, "x86") | `tests/Evo.App.Tests/ArchitectureTests.cs:21` | Passed [8 ms] | Passed [20 ms] |
| ArchitectureMappingTests.MapArchitecture_...(Arm, "desconocido-Arm") | `tests/Evo.App.Tests/ArchitectureTests.cs:21` | Passed [1 ms] | Passed [1 ms] |
| ArchitectureMappingTests.MapArchitecture_...(X64, "x64") | `tests/Evo.App.Tests/ArchitectureTests.cs:21` | Passed [< 1 ms] | Passed [< 1 ms] |
| ArchitectureMappingTests.MapArchitecture_...(Arm64, "arm64") | `tests/Evo.App.Tests/ArchitectureTests.cs:21` | Passed [< 1 ms] | Passed [< 1 ms] |
| ArchitectureMappingTests.EntornoReal_Arquitectura_NoVacia_Y_DeclaradaEnCatalogo | `tests/Evo.App.Tests/ArchitectureTests.cs` (Fact) | Passed [74 ms] | Passed [53 ms] |
| RegistryDeleteKeyRealRollbackTest.BorradoReal_RestauraValores_Kinds_Y_Subclave | `tests/Evo.Windows.Tests/RegistryDeleteKeyRealRollbackTest.cs` | Passed [67 ms] | Passed [51 ms] |
| DetectorRealArchitectureTests.DetectorReal_NoRechazaPorArquitecturaVacia | `tests/Evo.Windows.Tests/DetectorRealArchitectureTests.cs` | Passed [101 ms] | Passed [63 ms] |

Cada línea aparece precedida de `  Passed ` en el `test-console.txt` literal de ambos runners → **PASA**.

**Cierra la deuda 1 de la 6-D:** `BorradoReal_RestauraValores_Kinds_Y_Subclave` PASÓ con `WindowsRegistryAccessor` real bajo HKCU: verifica borrado, restauración de valores, **kinds** (DWord/String/Binary vía `GetKind`) y subclave con su valor tras `RollbackAsync`.

### Artefacto release-exe (run 46090885961, HEAD `4cfc7fb2...`)

Salida real de `gh api repos/EvoMaxPC/Evo_Optimizer-On/actions/runs/46090885961/artifacts --jq '.artifacts[] | {name, size_in_bytes, expired}'`:
```
{"expired":false,"name":"EvoClean-preview-win-x64","size_in_bytes":60924932}
```
- Nombre: `EvoClean-preview-win-x64`.
- Bytes: `60924932`.
- Expirado: false.
- Comparado con el run anterior (46081796639, 60926782 bytes): **distinto** (1.850 bytes menos, build distinto por el cambio de src); no es sospechoso.
- SHA-256: **NO VERIFICADO** (la descarga del artefacto está bloqueada en el sandbox por auth/redirect).

## Windows modificado (AtlasOS) — sección requerida

La hipótesis de que un "Windows modificado (AtlasOS)" causó el error **"Arquitectura '' no declarada para Windows 11 25H2."** **NO está demostrada**. La causa real es un defecto de la app: `WindowsSystemEnvironment.Architecture` leía `ProcessorArchitecture` de `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion`, que en la VM de prueba devolvía string vacío. En un Windows modificado (p. ej. AtlasOS), las fuentes del entorno que lee la app podrían diferir de un Windows "vanilla":

| Fuente del entorno | Qué lee la app | Posible diferencia en Windows modificado |
|---|---|---|
| Arquitectura | `RuntimeInformation.OSArchitecture` (tras la corrección) | Debería reflejar la arquitectura real del SO (x64/arm64). |
| Build | `CurrentBuildNumber` del registro | Podría diferir o no leerse. |
| UBR | `UBR` del registro | Podría diferir o no leerse. |
| Edición | `EditionID` del registro | Podría diferir. |
| InstallationType | `InstallationType` del registro | Podría diferir (Client/Server). |

Tras la corrección, la arquitectura ya NO se lee del registro sino del SO (`RuntimeInformation.OSArchitecture`), mapeado exactamente a los strings del catálogo (`x64`, `arm64`). Las demás fuentes (Build, UBR, Edición, InstallationType) siguen leyéndose del registro y pueden devolver vacío/0 sin avisar (hallazgo menor, reportado en PASO 2, no corregido para no expandir alcance).

**Riesgo declarado:** el CI de GitHub Actions no prueba un Windows modificado (AtlasOS); la verificación final en ese entorno es responsabilidad del equipo del usuario.

## Desviaciones

- No se pudo simular fallo de permisos en `GetKind` (CI de Windows como admin): no hay test de ese caso; se reportó.
- `EditionID`/`UBR` pueden devolver vacío silencioso: reportados, no corregidos (fuera de la causa del hallazgo, para no expandir alcance).
- `docs/reports/etapa6e.md` se actualizó en commit local (no se subió a origin) porque se agotó el límite de 3 pushes de la 6-F; CI ya está verde en origin.

## Supuestos

- Los errores de build del push 1/2 de la 6-E (`Wasm64`, `using Evo.Engine.Execution`) y el error `SecurityException` (falta `using System.Security;`) del push 1/2 de la 6-F se corrieron en pushes subsiguientes.

## Riesgos

- SHA-256 del artefacto NO VERIFICADO (bloqueo de descarga en sandbox).
- `docs/reports/etapa6e.md` actualizado localmente pero no subido a origin (límite de 3 pushes de 6-F agotado).
- `GetStatus` de servicios (`WindowsServiceAccessor`) traga excepciones (`catch { return ServiceStatus.Unknown; }`): reportado, no cambiado en esta ronda.
