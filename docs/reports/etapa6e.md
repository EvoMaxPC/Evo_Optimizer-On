# Informe ETAPA 6-E — Corregir detección de arquitectura de la app + 2 deudas de la 6-D

## Rama y commits

- Rama: `arena/ab2d6de7-evo-optimizer-on`.
- Push 1: `7f91652fe9fa...` (corrección src + tests nuevos + csproj) → CI falló (2 errores de build).
- Push 2: `e40026946e1b...` (califica enum Architecture) → CI falló (mismos 2 errores, tests nuevos no compilaban).
- Push 3: `—` (corrige Wasm64 + using Evo.Engine.Execution + agrega etapa6e.md + actualiza PRUEBA_EN_VM.md). CI pendiente de confirmar tras el push.

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
`X86` → `"x86"` (no declarado en catálogo → el detector lo rechaza, no se inventa compatibilidad). Cualquier otro (Arm, Wasm64, desconocido) → `"desconocido-..."` (no declarado → rechazado).

### Otros miembros de ISystemEnvironment que pueden devolver vacío silenciosamente (reporte, sin cambiar para no expandir alcance)
- `EditionID`: `ReadString("EditionID") ?? string.Empty` → puede ser vacío silencioso (no afecta compatibilidad, que se resuelve por build). Reportado, no corregido.
- `UBR`: `0` si falla → silencioso pero no crítico. Reportado, no corregido.
- `InstallationType`: `?? string.Empty` → vacío, pero el detector lo rechaza ("solo Client").
- `CurrentBuild`: `0` si falla → el detector lo rechaza ("No se pudo leer CurrentBuildNumber").

## PASO 3 — Tests nuevos (PASA solo si confirman en test-console.txt de ambos runners)

Archivos nuevos:
- `tests/Evo.App.Tests/ArchitectureTests.cs` (32 líneas aprox.): `[Theory]` de mapeo (X64→x64, Arm64→arm64, X86→x86, Arm→desconocido) + `EntornoReal_Arquitectura_NoVacia_Y_DeclaradaEnCatalogo` (instancia `WindowsSystemEnvironment` real, verifica arquitectura no vacía y presente en `catalog/windows-releases.json` leído con `WindowsReleaseCatalog.LoadFromFile`).
- `tests/Evo.Windows.Tests/DetectorRealArchitectureTests.cs` (32 líneas aprox.): `DetectorReal_NoRechazaPorArquitecturaVacia` — `WindowsDetector` con `WindowsSystemEnvironment` real + `WindowsRegistryAccessor` real + `WindowsReleaseCatalog` real; verifica que `resultado.Architecture` no esté vacía y que el motivo no contenga "Arquitectura ''".

Referencias agregadas (imprescindibles): `Evo.Windows.Tests.csproj` referencia ahora también `Evo.App` y `Evo.Detection`.

## PASO 4 — Deuda 1: rollback real de RegistryDeleteKeyExecutor

Archivo nuevo: `tests/Evo.Windows.Tests/RegistryDeleteKeyRealRollbackTest.cs` (113 líneas aprox.).

Test `BorradoReal_RestauraValores_Kinds_Y_Subclave`:
- Siembra bajo `HKCU\Software\EvoClean.Tests\<Guid>`: DWord `ValDWord`=42, String `ValStr`="hola", Binary `ValBin`=[1,2,3], subclave `Sub` con DWord `SubVal`=99.
- Ejecuta `RegistryDeleteKeyExecutor` real (Recursive=true) con `WindowsRegistryAccessor` real.
- Verifica borrado (clave no existe) + 1 journal entry.
- `RollbackAsync` real + verifica: clave recreada, valores restaurados (42 / "hola" / [1,2,3]), **kinds restaurados** (DWord/String/Binary vía `GetKind`), subclave `Sub` existe con `SubVal`=99.
- `Dispose()` borra la clave de prueba (recursiva).

## PASO 5 — Deuda 2: GetKind acotado

Archivo modificado: `src/Evo.Windows/WindowsRegistryAccessor.cs`.

`GetKind` antes (catch genérico tragaba todo):
```csharp
try { return key.GetValueKind(valueName); } catch { return RegistryValueKind.Unknown; }
```
`GetKind` después (solo ArgumentException → Unknown; permisos se propagan):
```csharp
try { return key.GetValueKind(valueName); }
catch (ArgumentException) { return RegistryValueKind.Unknown; }
// UnauthorizedAccessException / SecurityException se propagan.
```

Comprobación de fail-closed: `src/Evo.Engine/EngineCoordinator.cs` líneas 351-381 atrapan `Exception` (excepto OutOfMemoryException) del `executor.ExecuteAsync` y las convierten en `ActionResult.Fail` (sin mutar). Por tanto propagar una excepción de permisos desde `GetKind` es seguro: el motor la convierte en fallo.

No se agregó test de fallo de permisos: no es posible simular `UnauthorizedAccessException` en CI de Windows (el runner corre con privilegios de administrador). Se reporta como tal. `GetStatus` de servicios no se cambió en esta ronda (solo se reporta).

## PASO 6 — CI y artefacto (se confirma tras el push 3)

| Run id | Workflow | Evento | head_sha | Conclusión |
|---|---|---|---|---|
| — | dotnet-ci | push | pendiente | pendiente |
| — | dotnet-ci | pull_request | pendiente | pendiente |
| — | ledger-verify | push | pendiente | pendiente |
| — | release-exe | push | pendiente | pendiente |

Se rellena con `gh api` tras el push 3. `test-per-project.txt` literal de ambos runners se pega en este informe tras confirmar PASA (total > 306, 0 fallos). Artefacto: salida real de `gh api .../artifacts`. SHA-256: NO VERIFICADO si no se obtiene.

PR #1: `draft:true`, `merged:false` (verificado con `gh api repos/EvoMaxPC/Evo_Optimizer-On/pulls/1`).

## Desviaciones
- No se pudo simular fallo de permisos en `GetKind` (CI de Windows como admin): no hay test de ese caso; se reportó.
- `EditionID`/`UBR` pueden devolver vacío silencioso: reportados, no corregidos (fuera de la causa del hallazgo, para no expandir alcance).

## Supuestos
- Los 2 errores de build del push 1/2 (`Wasm64`, `using Evo.Engine.Execution`) se corrigen en el push 3.

## Riesgos
- Si el push 3 no deja CI verde, la etapa no cumple el criterio 6 y habría que reportar sin push adicional (límite de 3 push alcanzado).
