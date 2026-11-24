# ADR-0004 — Puntos de restauración del sistema

- **Estado**: propuesto (paso 8d)
- **Decide**: cómo se crea el punto de restauración que el motor exige antes de
  mutar, sin que el motor conozca la implementación
- **Contexto de código**: `src/Evo.Core/Restore/IRestorePointService.cs`,
  `src/Evo.Core/Confirmation/IConfirmationProvider.cs`,
  `src/Evo.Engine/EngineCoordinator.cs` (puerta previa a la primera mutación),
  `src/Evo.Testing/FakeRestorePointService.cs`,
  `src/Evo.Testing/FakeConfirmationProvider.cs`
- **Sustituye**: la deuda declarada en el paso 8c («`EngineCoordinator` no
  referencia `RestoreLevel` y nadie crea el punto»)

## Contexto

Hasta el paso 8c el catálogo declaraba `Restore = RestorePoint` en 13
capacidades y `Confirmation = SummaryAndRestorePoint` en todas ellas, pero el
motor **no miraba ninguna de las dos cosas**: ejecutaba y punto. La deuda estaba
escrita en `docs/reports/paso8c.md`.

Al cerrarla aparecen dos decisiones distintas que conviene no mezclar:

1. **Quién pide confirmación** y con qué texto, según el riesgo.
2. **Quién crea el punto de restauración** en Windows y cuándo.

La segunda no se puede probar en este repositorio: los runners de CI son
`windows-2025` (edición Server, sin Protección del sistema) y `windows-11-arm`.
Los tests de `Evo.Engine` corren sobre fakes en memoria y **ningún test toca el
sistema**.

## Decisión

### 1. Todo por interfaces (REQ-004)

- `IRestorePointService.IsAvailableAsync()` dice si el sistema puede crear
  puntos. Devuelve `false` —no lanza— cuando la Protección del sistema está
  desactivada.
- `IRestorePointService.CreateAsync(descripción)` devuelve
  `RestorePointResult { Success, Id, ErrorMessage }`. Un resultado con
  `Success = true` **sin `Id`** se trata como fallo: sin identificador el punto
  no se puede enlazar al diario de deshacer.
- `IConfirmationProvider.ConfirmAsync(petición)` recibe el tipo de confirmación,
  el riesgo, el resumen de acciones y si el punto está disponible; devuelve
  `Approved`, `TypedText` y `Reason`.
- El motor recibe ambas por constructor (`EngineCoordinator(..., IRestorePointService?,
  IConfirmationProvider?)`). Si el contrato exige una y no está, **aborta**.

### 2. Orden de la puerta (sólo en `ExecutionMode.Execute`)

1. Se pide la confirmación que exige el contrato (nunca en `DryRun` ni en
   `Audit`). No se gasta un punto en algo que el usuario va a rechazar.
2. Si `Confirmation = TypeOperationName`, el texto escrito debe ser **exactamente**
   el id de la capacidad (`StringComparison.Ordinal`).
3. Si el contrato pide punto —`Restore >= RestorePoint` **o** confirmación
   `SummaryAndRestorePoint` / `TypeOperationName`—:
   - si no hay servicio configurado → aborta;
   - si `IsAvailableAsync` devuelve `false` o lanza → aborta (fail-closed);
   - si `CreateAsync` falla o no devuelve id → aborta (fail-closed);
   - si el usuario pasó `AcceptNoRestorePoint = true` en el contexto → ejecuta y
     el resumen lo declara (`RestorePointWaived = true`).
4. Sólo entonces se ejecuta la primera acción.

Un punto **por plan**, no por acción. El id se guarda en
`ExecutionSummary.RestorePointId` y en `UndoJournal.RestorePointId`, de modo que
las entradas de deshacer y el punto viajan juntos.

Todo aborto de esta puerta queda en `ExecutionSummary.AbortedReason`
(distinto de `BlockedReason`, que es del preflight) y deja `Results` vacío, con
lo que `Mutated` es `false` por construcción.

### 3. La implementación real queda pendiente y con nombre

Este ADR **no** implementa la llamada a Windows. Opciones, con lo que se sabe y
lo que no:

| Opción | Ventaja | Límite conocido | Estado |
| --- | --- | --- | --- |
| WMI `SystemRestore.CreateRestorePoint` (`root\default`, `SRClient`) | Es la API documentada de System Restore; devuelve número de secuencia, que sirve como `Id`. | Requiere que la Protección del sistema esté activa; no funciona en ediciones Server. | **NO VERIFICADO** en este pin ni en este sandbox |
| `Checkpoint-Computer -Description` (módulo `Microsoft.PowerShell.Management`) | Una línea, sin COM; devuelve el control al terminar. | Windows limita cuántos puntos se crean en una ventana de tiempo (frecuencia mínima configurable por `SystemRestorePointCreationFrequency`); el valor por defecto y el comportamiento exacto en 24H2/25H2 **NO VERIFICADO** aquí. | **NO VERIFICADO** |
| `srclient.dll` / COM directo | Control fino de tipo de punto. | Igual de dependiente de la Protección del sistema; más superficie que mantener. | Descartado para la primera versión |

Lo único verificado en el repositorio:

- `WinUtil` desactiva esa frecuencia mínima escribiendo
  `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore\SystemRestorePointCreationFrequency = 0`
  en `WPFTweaksRestorePoint` (`config/tweaks.json`, medido en
  `inventory/ledger/winutil-tweak-ops.tsv`). Es decir: **el límite de frecuencia
  existe** y una fuente del pin lo desactiva explícitamente antes de crear el
  punto. Eso confirma el límite, no su valor por defecto.
- `Atlas` describe su toggle `SystemRestore` como «activa la protección de la
  unidad de Windows, pero **no crea** un punto de restauración ni protege otras
  unidades» (`Toggles/General/SystemRestore.psd1`). Es decir: ni Atlas crea
  puntos; no hay código de referencia que copiar.
- `Atlas` sí **desactiva** System Restore por política
  (`DisableSR = 1`), así que en un sistema preparado por Atlas
  `IsAvailableAsync` debe devolver `false` y el motor debe abortar salvo
  `AcceptNoRestorePoint`. Esto es consecuencia de la política del pin, no una
  suposición.

### 4. Cómo se validará

- **En VM del responsable** (Windows 11 24H2/25H2 cliente, con Protección del
  sistema activada a mano): crear un punto, leer su número de secuencia,
  comprobar que aparece en `Get-ComputerRestorePoint`, y repetir con la
  Protección desactivada para verificar el camino fail-closed.
- **En CI no se valida**: `windows-2025` es Server y el runner ARM no es una
  máquina del usuario. Los tests de CI sólo cubren el motor con fakes.

## Consecuencias

- El motor ya **no** ejecuta una capacidad que exige punto sin tenerlo, salvo
  permiso explícito y registrado.
- Cualquier implementación futura debe encajar en `IRestorePointService`; si
  necesita más datos (tipo de punto, unidad), se amplía la interfaz, no el
  motor.
- `RestorePointWaived` es visible en el resumen: la aplicación puede avisar de
  que se ejecutó sin red de seguridad.
- Queda pendiente decidir si `AcceptNoRestorePoint` debe exigir su propia
  confirmación reforzada (hoy es una opción del contexto, no del diálogo).
