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

## Anexo (paso 8c) — las 13 capacidades `Irreversible`, una a una

Tabla **documental**: no reclasifica nada. «Vía de recuperación» dice qué haría
falta para volver al estado anterior, no si EVO puede hacerlo (el motor sólo
revierte lo que tiene en el diario). Cuando el pin no dice nada, la celda dice
**NO VERIFICADO**.

| Capacidad | Por qué es irreversible | ¿Vía de recuperación? | Reversibilidad si se reclasificara |
| --- | --- | --- | --- |
| `cleanup.recycle.bin` | Vacía la papelera (`StateFlags0064=2`): los ficheros borrados no están en ningún otro sitio. | No hay. Sólo recuperación forense del volumen. | Se queda `Irreversible`. |
| `cleanup.winsxs.component` | `dism /StartComponentCleanup` elimina las versiones sustituidas de los componentes; Windows no las reconstruye sin volver a aplicar actualizaciones. | Parcial: Windows Update puede volver a descargar los paquetes, pero la copia local no se regenera. | Se queda `Irreversible`. |
| `cleanup.winsxs.resetbase` | Igual que la anterior **más** `/ResetBase`: marca la línea base y las actualizaciones ya instaladas dejan de poder desinstalarse. | Sólo reinstalar el sistema o restaurar una imagen. | Se queda `Irreversible`. |
| `debloat.appx.consumer` | Desinstala paquetes provisionados y de usuario; los datos locales del usuario se pierden. | Sí para el paquete (Store/winget), **no** para los datos. | Se queda `Irreversible` (la pérdida de datos manda). |
| `debloat.cortana.remove` | Desinstala Cortana; Microsoft la retiró del Store para Windows 11. | Parcial: en Windows 10 vuelve desde el Store; en Windows 11 el paquete ya no está publicado. **NO VERIFICADO** para cada build del rango. | `Reversible` sólo si se acota a las builds donde el paquete sigue disponible. |
| `debloat.onedrive.uninstall` | Ejecuta el desinstalador de OneDrive y deniega el acceso al binario con `icacls /deny`. | Sí: OneDrive se reinstala desde su instalador oficial. El `deny` lo tendría que quitar el usuario (el diario no lo deshace). | Candidata a `Reversible` **si** se modela el `icacls /grant` inverso; hoy no existe. |
| `debloat.copilot.remove` | `Remove-AppxPackage -AllUsers *Copilot*`: el paquete desaparece para todos los usuarios. | Sí en builds ≥ 26100: se reinstala desde la Store (`9NHT9RB2F4HD`, como hace Atlas en `Toggles/General/Copilot.ps1`). En 23H2 el equivalente es un botón de la barra de tareas (`ShowCopilotButton`). | Candidata a `Reversible` con un `UndoAction` que reinstale el paquete; hoy no existe. |
| `debloat.telemetry.appx` | Desinstala paquetes AppX de telemetría de usuario. | Sí: Store/winget, si el paquete sigue publicado. **NO VERIFICADO** cuáles siguen. | Candidata a `Reversible` por la misma razón que Copilot. |
| `debloat.edge.remove` | Borra el binario de Edge. | Sí: `winget install Microsoft.Edge` (es justo el `UndoScript` del pin). | Candidata clara a `Reversible` si se modela la reinstalación. |
| `debloat.explorer.auto-folder-discovery` | Borra las vistas de carpeta guardadas (`Shell\Bags` y `BagMRU`). | No hay copia previa: Windows las vuelve a generar al navegar, no las restaura. | Se queda `Irreversible` (regenerable ≠ restaurable). |
| `debloat.drivers.razer` | Dos valores de política (`SearchOrderConfig=0`, `DisableCoInstallers=1`) **y** un `Remove-Item` sobre `%SystemRoot%\Installer\Razer\*`: borra los instaladores en caché del fabricante. | Los valores de registro se revierten con el diario; los ficheros borrados **no**. Recuperar el instalador exige descargarlo de nuevo. | Se queda `Irreversible` por el borrado de ficheros. Si se quitara el `Remove-Item`, sería `Reversible`. |
| `debloat.drivers.logitech` | `Stop-Process` del asistente de Logitech **y** borrado de su directorio bajo `Program Files`. | No: el directorio borrado no se restaura; habría que reinstalar el software del fabricante. | Se queda `Irreversible` (borrado de ficheros, no sólo políticas). |
| `debloat.network.adobe-blocklist` | Añade (`Add-Content`) la lista de bloqueo de Adobe al fichero `hosts`, descargada de un repositorio de terceros en tiempo de ejecución; el contenido añadido no queda registrado en el diario. | Parcial: se pueden borrar las líneas añadidas, pero la lista del repositorio cambia con el tiempo y el pin no guarda cuáles se añadieron. | **NO VERIFICADO**: con un `UndoAction` que registre las líneas añadidas sería `Reversible`; hoy no existe. |

### Qué sale de esta tabla

- **6 de las 13** son irreversibles sin discusión (papelera, WinSxS ×2, AppX de
  consumidor, vistas de carpeta y —con reservas de build— Cortana).
- **4** tienen una vía de recuperación clara (Edge, Copilot, telemetría AppX,
  OneDrive) y podrían bajar a `Reversible` **cuando exista la acción inversa**
  en el motor. No se hace aquí: sin `UndoAction` implementada, declararlas
  reversibles sería mentir sobre lo que EVO puede hacer.
- **3** (Razer, Logitech, Adobe) se quedan `Irreversible` pero por motivos
  distintos de los que apuntaba el nombre: las dos primeras **borran ficheros**
  (caché de instaladores del fabricante) además de escribir políticas, y la
  tercera añade contenido a `hosts` que nadie registra. Quedan como **NO
  VERIFICADO** en cuanto a qué haría falta para recuperarlas (el pin no lo dice)
  y son las primeras a revisar cuando se prueben en una VM.
