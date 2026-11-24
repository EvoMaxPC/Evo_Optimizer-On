# ADR-0003 — Reversibilidad declarada y restauración mínima

- **Estado**: aceptado (paso 8b)
- **Sustituye**: la regla del paso 6 «`RestoreLevel.None` exige `Risk >= High`» de `CapabilityRules`
- **Contexto de código**: `src/Evo.Core/Enums/Primitives.cs` (`Reversibility`),
  `src/Evo.Core/Models/{CapabilityContract,CapabilityRules}.cs`,
  `src/Evo.Catalog/{Model/CapabilityDefinition.cs,CatalogValidator.cs}`

## Contexto

La regla del paso 6 mezclaba dos cosas distintas en una sola condición: *cuánto se
puede deshacer* y *cuánto hay que avisar*. Decía «si no restauras nada, el riesgo
tiene que ser alto», lo que permitía dos errores simétricos:

1. Una limpieza trivial e irreversible (borrar temporales, volcar dumps) tenía que
   declararse `High` para pasar el validador. El aviso quedaba inflado.
2. Una operación de riesgo medio que sí se puede deshacer no estaba obligada a
   declarar cómo se deshace: bastaba con poner `RestorePoint` y no había ninguna
   comprobación de que la restauración declarada fuese coherente con el efecto.

Además, el catálogo no distinguía «no hay nada que restaurar porque no se cambia
estado persistente» de «no hay nada que restaurar porque el cambio es
irrecuperable». Son dos situaciones con confirmaciones muy distintas.

## Decisión

Se añade un enum obligatorio `Reversibility` con tres miembros y una tabla de
compatibilidad en `CapabilityRules.ValidateReversibility`:

| `Reversibility` | `Restore` exigido | `Risk` permitido | `Confirmation` mínima |
| --- | --- | --- | --- |
| `Reversible` | `>= SessionUndo` **y** `>=` el mínimo por riesgo | cualquiera | mínimo por riesgo |
| `NothingToRestore` | exactamente `None` | `<= Medium` | mínimo por riesgo |
| `Irreversible` | exactamente `None` | `>= High` | `>= SummaryAndRestorePoint` |

Reglas derivadas:

- **`Reversible ⇒ Restore >= SessionUndo`**. Si el efecto toca estado persistente
  y se declara reversible, tiene que existir al menos un diario de deshacer de
  sesión. `RestorePoint` insinúa un punto de restauración del sistema, así que
  para `High`/`Critical` se sigue exigiendo `RestorePoint` o `FullBackup`.
- **`NothingToRestore ⇒ Restore = None` sólo con `Risk <= Medium`**. Es el caso de
  borrar ficheros efímeros: no queda estado que revertir y el daño máximo está
  acotado. Si el riesgo sube a `High`, la única salida honesta es declararse
  `Irreversible` y asumir la confirmación fuerte.
- **`Irreversible ⇒ Restore = None`, `Risk >= High` y `Confirmation >= Summary`**.
  Un cambio irrecuperable no puede venderse con un clic. Con `Risk = Critical` se
  mantiene la exigencia del paso 6: `Confirmation = TypeOperationName`.
- La comprobación es un **error de catálogo** (`R-RISK`) y no un aviso: un
  catálogo incoherente no debe cargarse.

El campo es obligatorio en el JSON (`reversibility`), se sitúa justo después de
`restore` y su ausencia produce `R-RISK` con el nombre del campo en el mensaje.
`CapabilityDefinition.Reversibility` es `Reversibility?` en el DTO y
`ToContract()` aplica `Reversible` por defecto **sólo** para no romper dobles de
test; el validador nunca ve el valor por defecto.

## Justificación

- Separar las dos dimensiones hace que el aviso al usuario sea proporcional al
  daño real, no al capricho de quien escribe el catálogo.
- La tabla es comprobable sin ejecutar Windows: es una función pura sobre tres
  enums, y por eso se puede cubrir con tests unitarios en Linux/Windows.
- `Irreversible` obliga a declarar en `provenance` qué se pierde; el campo pasa a
  ser la fuente de verdad para el texto de confirmación de la UI.

## Consecuencias

- Reclasificación de las 24 capacidades de la oleada 1 más
  `cleanup.winsxs.resetbase`: 4 `NothingToRestore`, 9 `Irreversible`,
  12 `Reversible` (una de ellas, `privacy.ceip.tasks`, baja de
  `Medium/RestorePoint` a `Low/SessionUndo`).
- `cleanup.winsxs.resetbase` nace como capacidad aparte de
  `cleanup.winsxs.component` porque `/ResetBase` elimina los componentes
  sustituidos y hace imposible desinstalar actualizaciones; ambas se declaran
  mutuamente en `conflictsWith`.
- Tests: `tests/Evo.Core.Tests/ReversibilityTests.cs` (13 casos, incluido el
  mínimo por riesgo y la tabla completa de aceptación/rechazo) y la comprobación
  de que `Enum.GetNames<Reversibility>()` no cambia de tamaño sin test.
- Cambios de `Risk`/`Restore`/`Confirmation` respecto al paso 8: ver
  `docs/reports/paso8b.md`, tabla T2. Ningún cambio sube el riesgo sin bajar el
  `Restore` correspondiente.
