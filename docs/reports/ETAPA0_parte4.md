ETAPA 0 — REVALIDAR HALLAZGOS DE AUDITORÍA DEL MOTOR (SOLO LECTURA) [PARTE 4/5]

Rama: `arena/ab2d6de7-evo-optimizer-on` (base `402af190` de main). HEAD = `908f6ad`. Reglas ETAPA 0: SOLO LECTURA, sin commits/pushes, sin `gh pr ready`, sin merge, sin `git push --force`.

---

### HALLADIZO H6 — Critical exige RestoreLevel.FullBackup y ConfirmationType.TypeOperationName; IRestorePointService sin implementación real

`CapabilityRules.MinimumRestore(RiskLevel.Critical)` = `RestoreLevel.FullBackup` (línea 19). `MinimumConfirmation(RiskLevel.Critical)` = `ConfirmationType.TypeOperationName` (línea 30); validación: Critical exige TypeOperationName (líneas 175-179). `IRestorePointService` es solo interfaz (líneas 29-39): la implementación real (WMI `SystemRestore.CreateRestorePoint` / `Checkpoint-Computer`) NO existe (ADR-0004 estado Propuesto). `EngineCoordinator` aborta sin mutar si `_restorePoints` is null, no disponible, o `CreateAsync` falla (líneas 290-318).

Función completa — `CapabilityRules` (`src/Evo.Core/Models/CapabilityRules.cs`, `nl -ba`):

```
    10    public static class CapabilityRules
    11    {
    13    public static RestoreLevel MinimumRestore(RiskLevel risk) => risk switch
    14    {
    15        RiskLevel.Safe => RestoreLevel.None,
    16        RiskLevel.Low => RestoreLevel.SessionUndo,
    17        RiskLevel.Medium => RestoreLevel.RestorePoint,
    18        RiskLevel.High => RestoreLevel.RestorePoint,
    19        RiskLevel.Critical => RestoreLevel.FullBackup,
    20        _ => RestoreLevel.FullBackup,
    21    };

    24    public static ConfirmationType MinimumConfirmation(RiskLevel risk) => risk switch
    25    {
    26        RiskLevel.Safe => ConfirmationType.None,
    27        RiskLevel.Low => ConfirmationType.SimpleClick,
    28        RiskLevel.Medium => ConfirmationType.Summary,
    29        RiskLevel.High => ConfirmationType.SummaryAndRestorePoint,
    30        RiskLevel.Critical => ConfirmationType.TypeOperationName,
    31        _ => ConfirmationType.TypeOperationName,
    32    };
...
   175        if (capability.Risk == RiskLevel.Critical &&
   176            capability.Confirmation != ConfirmationType.TypeOperationName)
   177        {
   178            errors.Add($"'{capability.Id}': Critical exige TypeOperationName.");
   179        }
```

Función completa — `IRestorePointService` (`src/Evo.Core/Restore/IRestorePointService.cs`, `nl -ba`):

```
   29    public interface IRestorePointService
   30    {
   36        Task<bool> IsAvailableAsync(CancellationToken cancellationToken = default);
   37

   39        Task<RestorePointResult> CreateAsync(string description, CancellationToken cancellationToken = default);
   40    }
```
(comentario líneas 22-27: implementación real — WMI `SystemRestore.CreateRestorePoint` o `Checkpoint-Computer` — NO existe todavía; estado Propuesto).

Función completa — `EngineCoordinator` puerta de restore point (`src/Evo.Engine/EngineCoordinator.cs`, `nl -ba`):

```
   285                if (template.AcceptNoRestorePoint)
   286                {
   287                    // Declarado: el usuario asume el riesgo. Se registra en el resumen.
   288                    restorePointWaived = true;
   289                }
   290                else if (_restorePoints is null)
   291                {
   292                    return Aborted(
   293                        plan, mode, stopwatch, planned,
   294                        "El contrato exige punto de restauración y el motor no tiene " +
   295                        "servicio de puntos configurado: se aborta sin mutar nada.",
   296                        confirmed: confirmed, confirmationType: confirmationType);
   297                }
   298                else if (!await IsRestorePointAvailableAsync(cancellationToken))
   299                {
   300                    return Aborted(
   301                        plan, mode, stopwatch, planned,
   302                        "La Protección del sistema no está disponible: no se puede crear el " +
   303                        "punto de restauración y el contrato lo exige. Se aborta sin mutar nada " +
   304                        "(fail-closed).",
   305                        confirmed: confirmed, confirmationType: confirmationType);
   306                }
   307                else
   308                {
   309                    var created = await _restorePoints.CreateAsync(
   310                        $"EVO CLEAN — {plan.Capability.Id}", cancellationToken).ConfigureAwait(false);
   311

   312                    if (!created.Success || string.IsNullOrWhiteSpace(created.Id))
   313                    {
   314                        return Aborted(
   315                            plan, mode, stopwatch, planned,
   316                            $"No se pudo crear el punto de restauración " +
   317                            $"({created.ErrorMessage}): se aborta sin mutar nada (fail-closed).",
   318                            confirmed: confirmed, confirmationType: confirmationType);
   319                    }
   320                }
```

Veredicto: **CONFIRMADO** — `src/Evo.Core/Models/CapabilityRules.cs:19,30,175-179`; `src/Evo.Core/Restore/IRestorePointService.cs:29-39`; `src/Evo.Engine/EngineCoordinator.cs:290-318`.

Tests hoy para H6:
- `CapabilityContractTests.CriticalExigeTypeOperationName` (línea 42)
- `CapabilityContractTests.CriticalConTypeOperationNameYFullBackupEsValido` (línea 55)
- `RestorePointGateTests` (gate de punto de restauración)

---

### HALLADIZO H7 — RegistryDeleteKeyExecutor: límites de tamaño después del snapshot; tope de profundidad en recorrido

El tope de profundidad aplica durante el recorrido (`depth>=64` → devuelve `Array.Empty` de subclaves, línea 192-194). Los límites de tamaño (`MaxValues`/`MaxKeys`/`MaxDepth`) se comprueban DESPUÉS sobre la instantánea ya tomada (línea 112-121: `snapshot.Exceeds(_limits)` → fail-closed, no se borra).

Función completa — límites (`src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs`, `nl -ba`):

```
   112        var tooBig = snapshot.Exceeds(_limits);
   113        if (tooBig is not null)
   114        {
   115            return Task.FromResult(ActionResult.Fail(
   116                action.Key,
   117                $"La instantánea de '{deleteAction.KeyPath}' supera el límite " +
   118                $"({tooBig}): no se borra (fail-closed).",
   119                "present",
   120                Describe(deleteAction)));
   121        }
...
   189            // Tope duro de recursión del propio recorrido: los límites de tamaño
   190            // se comprueban DESPUÉS, sobre la instantánea ya tomada, pero un árbol
   191            // patológico no debe poder colgar el recorrido.
   192            IReadOnlyList<string> childNames = depth >= 64
   193                ? Array.Empty<string>()
   194                : reader.GetSubKeyNames(hive, path);
```

Veredicto: **CONFIRMADO** — `src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs:112-121,192-194`.

Tests hoy para H7:
- `Wave4EngineTests.DeleteKey_SnapshotOverTheLimitAbortsWithoutDeleting` (línea 155)
- `Wave4EngineTests.DeleteKey_DepthOverTheLimitAbortsBeforeDeleting` (línea 249)

---

FIN PARTE 4/5. Continúa en PARTE 5/5 (H8-H10, tabla final, cierre).