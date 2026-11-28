# Informe ETAPA 6-D — Paso 5: conteo real de capacidades `Implemented` + usos de `Evo.Testing` en `src/Evo.App` + tabla de Evo.App.Tests

## Tabla de Evo.App.Tests (run 46082726973, sha `7ef772f49b616a3e309655f021d5778ae459cee0`, ambos runners)

| Test (clase.método) | Línea declarada | Resultado en test-console.txt (windows-2025) | Resultado en test-console.txt (windows-11-arm) | Veredicto |
|---|---|---|---|---|
| Evo.App.Tests.Tests.Windows_NoCompatible_NoAplicaNada | 158 | Passed [< 1 ms] | Passed [< 1 ms] | PASA |
| Evo.App.Tests.Tests.Build_Desconocido_NoAplicaNada | 171 | Passed [2 ms] | Passed [1 ms] | PASA |
| Evo.App.Tests.Tests.Build_Conocido_Cliente_Compatible | 181 | Passed [3 ms] | Passed [3 ms] | PASA |
| Evo.App.Tests.Tests.Specified_No_Ejecutable | 196 | Passed [2 ms] | Passed [2 ms] | PASA |
| Evo.App.Tests.Tests.Critical_Bloqueada | 210 | Passed [3 ms] | Passed [2 ms] | PASA |
| Evo.App.Tests.Tests.RestorePoint_Bloqueada_SinServicio | 221 | Passed [1 ms] | Passed [< 1 ms] | PASA |
| Evo.App.Tests.Tests.Simular_DryRun_No_Muta_Fake | 263 | Passed [29 ms] | Passed [25 ms] | PASA |
| Evo.App.Tests.Tests.AplicarYDeshacer_Fake_Vuelve_Al_Estado_Original | 263 | Passed [8 ms] | Passed [5 ms] | PASA |
| Evo.App.Tests.Tests.Diecisiete_Secciones_Titulos_Exactos | 285 | Passed [< 1 ms] | Passed [< 1 ms] | PASA |
| Evo.App.Tests.Tests.Seccion_Sin_Capacidades_Muestra_Sin_Capacidades_Todavia | 320 | Passed [< 1 ms] | Passed [< 1 ms] | PASA |
| Evo.App.Tests.Tests.Privilege_Admin_NoAdmin_Muestra_Aviso | 334 | Passed [< 1 ms] | Passed [< 1 ms] | PASA |
| Evo.App.Tests.Tests.TrustedInstaller_No_Disponible | 361 | Passed [28 ms] | Passed [26 ms] | PASA |
| Evo.App.Tests.Tests.Confirmacion_No_Impide_Mutar_Fake | 376 | Passed [10 ms] | Passed [15 ms] | PASA |
| Evo.App.Tests.Tests.Restauracion_Pendiente_No_Llama_Al_Motor | 401 | Passed [< 1 ms] | Passed [< 1 ms] | PASA |
| Evo.App.Tests.Tests.Tarea_O_Comando_No_Disponible_Todavia | 419 | Passed [1 ms] | Passed [1 ms] | PASA |

Todos los 15 tests de `Evo.App.Tests` aparecen como `Passed` en el `test-console.txt` literal de ambos runners → **PASA**. Líneas obtenidas con `grep -n "\[Fact\]\|public async Task\|public void " tests/Evo.App.Tests/Tests.cs`.

## Conteo real de capacidades `Implemented` (script de solo lectura sobre `catalog/capabilities/*.json`)

Comando ejecutado: `python3 /tmp/paso4_count.py` (script que lee `catalog/capabilities/*.json`, filtra `state == "Implemented"`, conta tipos de acción y grupos de bloqueo).

Resultado:
- Total capabilities en catálogo: 88
- Total `Implemented`: **69**
- Total `Specified`: 19

### 1) Valores distintos de "type" de las acciones de las `Implemented`

| type | cantidad |
|---|---|
| registry | 162 |
| command | 14 |
| service | 10 |
| task | 5 |
| registryCreateKey | 2 |
| registryDeleteKey | 1 |

Tipos clasificados como tarea programada / comando / proceso externo: `command`, `task`.

### 2) Cuentas por grupo sobre `Implemented` (ids listados, <= 15)

| Grupo | Cantidad | Ids |
|---|---|---|
| Restore == RestorePoint | 3 | system.error-reporting.crash-control, system.error-reporting.wpbt-disable, system.sleep.s3-enable |
| Confirmation in {SummaryAndRestorePoint, TypeOperationName} | 6 | cleanup.recycle.bin, cleanup.winsxs.component, debloat.appx.consumer, debloat.cortana.remove, debloat.onedrive.uninstall, debloat.telemetry.appx |
| Risk == Critical | 0 | (ninguna) |
| Privilege == TrustedInstaller | 0 | (ninguna) |
| acciones de tarea programada o comando/proceso externo (`command`, `task`) | 14 | cleanup.memory.dumps, cleanup.recycle.bin, cleanup.temp.system, cleanup.temp.user, cleanup.wer.reports, cleanup.winsxs.component, debloat.appx.consumer, debloat.cortana.remove, debloat.onedrive.uninstall, debloat.settings.home, debloat.start.recommendations, debloat.telemetry.appx, debloat.widgets.disable, privacy.ceip.tasks |

### 3) Capacidades `Implemented` sin NINGUNO de esos bloqueos

- Con al menos un bloqueo: 17
- Sin ningún bloqueo: **52**
- Total: 69 (52 + 17 = 69) ✓

**Sin bloqueo por Privilege:**
| Privilege | Cantidad |
|---|---|
| Admin | 30 |
| User | 22 |

**Sin bloqueo por Risk:**
| Risk | Cantidad |
|---|---|
| Safe | 26 |
| Low | 26 |

## Lista de CADA uso de `Evo.Testing` dentro de `src/Evo.App`

| Archivo:línea | Uso | Para qué |
|---|---|---|
| src/Evo.App/CapabilityViewModel.cs:11 | comentario doc `/// ... fakes de <see cref="Evo.Testing"/>.` | Documenta que las capacidades se prueban con fakes de Evo.Testing |
| src/Evo.App/Evo.App.csproj:18 | `<ProjectReference Include="..\Evo.Testing\Evo.Testing.csproj" />` | Referencia de proyecto a Evo.Testing (para usar Fake* en pruebas/creación de la app) |
| src/Evo.App/MainViewModel.cs:15 | `using Evo.Testing;` | Importa el namespace de fakes |
| src/Evo.App/MainViewModel.cs:201 | `new FakeRegistryAccessor()` | Crea detector con fake de registro en `CreateForTest` (camino de prueba, no producción) |
| src/Evo.App/MainWindow.xaml.cs:4 | `using Evo.Testing;` | Importa el namespace de fakes |
| src/Evo.App/MainWindow.xaml.cs:26 | `new FakeRestorePointService { Available = false }` | Punto de restauración **fail-closed en producción** (no disponible) |

## Diff literal de producción de la app tocada en la 6-C (`git diff a39a559^..a39a559 -- src/Evo.App`)

3 archivos: `MainViewModel.cs`, `MainWindow.xaml.cs`, `WpfConfirmationProvider.cs` (56 insertions, 12 deletions). Incluido íntegro en `docs/reports/etapa6.md` / sección de cambios de la app. Resumen:

- `MainViewModel.cs`: agrega `IRegistryAccessor? _registry` inyectable; `Apply` hace puerta fail-closed de punto de restauración ("Requiere punto de restauración: pendiente"); `ExecuteCapability` rechaza `TaskAction`/`CommandAction` ("no disponible todavía"); `ActionContext.Registry = _registry ?? new WindowsRegistryAccessor()`.
- `MainWindow.xaml.cs`: `restorePoints = new FakeRestorePointService { Available = false }` (era `new FakeRestorePointService()` sin `Available = false`).
- `WpfConfirmationProvider.cs`: reemplaza placeholder que auto-aprobaba por `MessageBox.Show` real con Yes/No, nombre, riesgo y resumen de acciones; devuelve `false` si el usuario elige "No".

## Código de `src/Evo.App/WpfCommandRunner.cs` con `nl -ba` (25 líneas)

```
     1: using Evo.Core.System;
     2:
     3: namespace Evo.App;
     4:
     5: /// <summary>Ejecutor de comandos externos para WPF (placeholder: no disponible).</summary>
     6: /// <remarks>
     7: /// Las tareas programadas y comandos externos se indican como "no disponible
     8: /// todavía" en la UI. Este placeholder devuelve error para cualquier comando.
     9: /// </remarks>
    10: public sealed class WpfCommandRunner : ICommandRunner
    11: {
    12:     public Task<CommandResult> RunCommandAsync(
    13:         string fileName,
    14:         IReadOnlyList<string> arguments,
    15:         System.Threading.CancellationToken cancellationToken = default)
    16:     {
    17:         return Task.FromResult(new CommandResult
    18:         {
    19:             ExitCode = -1,
    20:             StandardOutput = string.Empty,
    21:             StandardError = "Comandos externos no disponibles en esta versión.",
    22:         });
    23:     }
    24: }
```

`WpfCommandRunner` **no ejecuta nada real**: devuelve `ExitCode = -1` y un mensaje de error para cualquier comando. Es el placeholder de "no disponible todavía".
