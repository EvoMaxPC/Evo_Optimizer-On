# ADR-0005 — Expresividad del motor: claves, tareas y servicios

- **Estado**: Propuesto (paso 11)
- **Decide**: qué operaciones del pin puede aplicar el motor sin romper ADR-0003
  (reversibilidad honesta) y cómo se deshacen exactamente
- **Contexto de código**: `src/Evo.Core/Actions/CapabilityAction.cs`
  (`RegistryDeleteKey`, `TaskCreate`), `src/Evo.Core/Actions/ConcreteActions.cs`
  (`RegistryDeleteKeyAction`, `TaskCreateAction`),
  `src/Evo.Core/System/IRegistryAccessor.cs` (`IRegistryTreeReader`,
  `IRegistryKeyCreator`), `src/Evo.Core/System/ITaskAccessor.cs`
  (`CreateTask`, `DeleteTask`, `TaskDefinition`),
  `src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs`,
  `src/Evo.Engine/Executors/TaskCreateExecutor.cs`,
  `src/Evo.Engine/Executors/ServiceActionExecutor.cs`,
  `src/Evo.Engine/Undo/UndoJournal.cs`,
  `src/Evo.Testing/FakeRegistryAccessor.cs`, `src/Evo.Testing/FakeTaskAccessor.cs`
- **Sustituye**: los huecos de expresividad declarados en `docs/reports/paso10.md`
  (`DeleteKey` omitido, tarea `AutoRegBackup` no expresable, `w32tm`/`lfsvc` sin
  acción de servicio)

## Contexto

Hasta el paso 10 el motor tenía cinco tipos de acción y una regla tácita: **sólo
se declara lo que se sabe deshacer**. Eso dejó tres huecos escritos y medidos:

1. **Borrado de clave completa.** Atlas usa `Operation = 'DeleteKey'` (por
   ejemplo, `Toggles/Interface/Home.psd1`). El motor sólo sabía borrar *valores*,
   así que esas líneas se omitían y se declaraban en la descripción.
2. **Crear una tarea.** `WPFFeatureRegBackup` registra la tarea `AutoRegBackup`
   con `Register-ScheduledTask`. El motor sólo sabía habilitar o deshabilitar una
   tarea **existente**.
3. **Arrancar o parar un servicio.** El enum `ServiceOperation` ya tenía `Start`
   y `Stop`, pero ninguna capacidad los usaba y el deshacer sólo restauraba el
   estado cuando la operación no era `SetStartupType` (caso que nunca se daba).

Los tres huecos afectan a capacidades ya publicadas: `explorer.home.hide`,
`system.registry-backup.enable`, `system.time.ntp-servers` y
`system.location.consent-deny`.

## Decisión

### 1. Dos acciones nuevas, con contrato cerrado

- **`registryDeleteKey`** (`RegistryDeleteKeyAction`): `hive`, `keyPath`,
  `recursive` (por defecto `false`, que es lo que hace el pin), `order`,
  `description`. El discriminador JSON es exactamente `registryDeleteKey`.
- **`taskCreate`** (`TaskCreateAction`): `taskPath`, `taskName`, `execute`,
  `arguments`, `trigger` (`Daily` | `OnLogon`), `triggerAt` (`HH:mm` con
  `Daily`), `userId` (`System` en el pin), `runLevel` (`Highest` | `Limited`),
  `taskDescription`, `overwrite` (por defecto `false`).

Las acciones **no** llevan `line`: la línea del pin va en la `provenance` de la
capacidad, como en las oleadas 2 y 3 (`CapabilityAction` es polimórfica y su
contrato se mantiene cerrado; el cargador estricto ignora propiedades
desconocidas, pero el generador no las escribe).

### 2. Borrado de clave: instantánea antes de borrar (fail-closed)

En `ExecutionMode.Execute` y sólo si la clave existe, el ejecutor:

1. exige que el accesor implemente `IRegistryTreeReader` (subclaves y valores);
   si no, **falla sin borrar**;
2. toma una instantánea recursiva (`RegistryKeySnapshot`: valores con su
   `RegistryValueKind` y su dato, subclaves, ramas vacías);
3. si la instantánea lanza o supera `RegistrySnapshotLimits`
   (profundidad 16, 4096 valores, 1024 claves), **falla sin borrar**;
4. borra y guarda `RegistryDeleteKeyUndoEntry` con la instantánea.

El deshacer recrea cada clave (también las vacías, vía `IRegistryKeyCreator`),
cada valor con su tipo y su dato, en el orden del árbol. En `DryRun` y `Audit`
no se muta nada y se informa de lo que se borraría. Si la clave no existe, la
acción es un **no-op registrado** y el deshacer no crea nada.

### 3. Creación de tarea: la inversa es borrar la creada

- Si la tarea **no existía**: se crea y el diario la borra
  (`DeleteTask`).
- Si existía y `overwrite = false`: **falla sin tocar nada** (no se pisa una
  tarea ajena en silencio).
- Si existía y `overwrite = true`: se captura el estado previo
  (habilitada/deshabilitada) y el deshacer la devuelve a ese estado, **no** la
  borra.

Una creación que lanza no deja entrada en el diario: no se promete un deshacer
de algo que no se aplicó.

### 4. Servicios: tipo de inicio y estado de ejecución, por separado

- `SetStartupType` cambia **sólo** el tipo: `StatusChanged = false`.
- `Start` / `Stop` cambian **sólo** el estado: `StartupTypeChanged = false`.
- Un fallo al arrancar o al parar devuelve `ActionResult.Fail` y el coordinador
  revierte en LIFO lo ya aplicado de la capacidad.
- El deshacer restaura primero el tipo de inicio y después el estado: al revés,
  arrancar un servicio que quedó `Disabled` falla con `ERROR_SERVICE_DISABLED`.

### 4-bis. El ORDEN de las acciones de servicio es semántico

Como el diario se deshace en **LIFO**, la última acción es la primera en
revertirse. Para dejar un servicio «parado y deshabilitado» con deshacer correcto
hay que declarar **primero la parada y después el tipo de inicio**:

```
Stop(1) → SetStartupType Disabled(2)   → rollback: startup(2), then start(1)   OK
SetStartupType Disabled(1) → Stop(2)   → rollback: stop(2), then startup(1)   arranca
                                         con el servicio aún deshabilitado → 1058
```

`Stop` sobre un servicio ya parado es inocuo, así que el orden elegido no añade
efectos. `location_service_actions()` lo emite así desde el paso 11 y
`FakeServiceAccessor.StartService` imita el 1058 para que el orden equivocado
falle en los tests.

### 5. Lo que NO cambia

- **Comandos y procesos siguen sin inversa.** `CommandUndoEntry.Restore` no hace
  nada, y así se declara. Por eso `w32tm /config /update` y `w32tm /resync` **no
  se ejecutan**: se escriben en la descripción y en la procedencia de
  `system.time.ntp-servers`.
- No se inventan accesores reales de Windows en este paso (REQ-004): las
  interfaces se amplían y los fakes las implementan; el ejecutor real de
  `IRegistryTreeReader` sobre el registro llega con la capa de sistema.
- No se cambia `SecurityImpact` de ninguna capacidad sin evidencia del pin.

## Consecuencias

- **Positivas**: cuatro capacidades cierran su hueco sin bajar la promesa de
  deshacer; los huecos que quedan (crear claves, `AddKey`, comandos) están
  escritos con su motivo.
- **Negativas / límites declarados**:
  - La instantánea se toma **en memoria**: una clave enorme no se borra
    (fail-closed) en vez de intentarlo con riesgo de perder el deshacer.
  - Un borrado recursivo puede borrar la clave padre si se queda vacía (el
    accesor borra la clave y su subárbol, y una clave sin valores no tiene por
    qué sobrevivir); el diario devuelve el subárbol pedido, no la clave padre.
    Medido en `Wave4EngineTests.DeleteKey_RestoresTheWholeSubtreeWithTypesAndData`
    con el fake, que sí se comporta así.
  - Crear una tarea registra la tarea, no valida después que Windows la acepte
    (eso es del accesor real).
- **Pruebas**: `tests/Evo.Engine.Tests/Wave4EngineTests.cs` (ejecutar, deshacer
  exacto, dry-run, clave inexistente, instantánea que falla, límite superado,
  fallo a mitad con reversión, puerta de punto de restauración) y
  `tests/Evo.Catalog.Tests/Wave4CatalogTests.cs` (validador acepta/rechaza).
