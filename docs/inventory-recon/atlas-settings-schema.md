# Esquema real de los ajustes de Atlas (GPL-3.0)

SHA fijado `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`. Todo lo de aquí está
medido con los comandos que se indican; no hay suposiciones.

**Límite de licencia.** Solo se recogen rutas, ids, nombres de campo, categorías,
enumerados, tipos y **conteos**. No se transcribe ningún texto de descripción,
ningún cuerpo de script ni ninguna ruta de registro completa de Atlas.

## 1. `package/Executables/AtlasModules/Toggles/catalog.json`

Ruta exacta según `inventory/ledger/atlas-files.tsv`
(`item_id = atlas:config:package/Executables/AtlasModules/Toggles/catalog.json`).
115 595 B.

### Estructura de primer nivel

```json
{"schemaVersion": 1, "toggles": [ ... ]}
```

Dos claves: `schemaVersion` (int, valor 1) y `toggles` (lista).

### Entradas: **91** (`len(data["toggles"])`)

### Campos por entrada (frecuencia sobre 91 y tipos observados)

| campo | frecuencia | tipos |
|---|---:|---|
| `name` | 91 | str (91) |
| `group` | 91 | str (91) |
| `description` | 91 | str (91), 32–288 caracteres |
| `elevation` | 91 | str (91) |
| `noStateRecord` | 91 | bool (91) |
| `menu` | 91 | bool (91) |
| `launcher` | 91 | str (8) · null (83) |
| `warning` | 91 | str (14) · null (77) |
| `states` | 91 | list (91), 1–4 elementos |

Ninguna entrada tiene claves fuera de esas 9.

### Unicidad

`name` es único: **91 distintos / 91**. No hay campo `id` separado; el
identificador es `name`.

### Campos enumerables (valores distintos)

| campo | valores |
|---|---|
| `group` | General 29 · Interface 26 · Boot 8 · Troubleshooting 8 · Security 7 · Services 7 · Advanced 3 · Software 3 |
| `elevation` | Admin 78 · TrustedInstaller 8 · None 5 |
| `noStateRecord` | true 18 · false 73 |
| `menu` | true 8 · false 83 |

### `states` (173 en total)

| campo | frecuencia | tipos / valores |
|---|---:|---|
| `name` | 173 | Disable 73 · Enable 73 · Run 13 · Minimal 2 · y 12 más con 1 |
| `stateValue` | 173 | int 152 · null 21; valores 0 (74), 1 (74), 2 (4) |
| `launcher` | 173 | str 157 · null 16 |
| `reboot` | 173 | null 107 · Recommend 43 · RestartExplorer 14 · Prompt 7 · SignOut 2 |
| `work` | 173 | objeto, ver abajo |
| `menuLabel` | 16 | str |
| `toolboxLauncher` | 11 | str |

### `work` (siempre presente, 7 claves)

| clave | tipos | total |
|---|---|---:|
| `registry` | int (contador) | 303 |
| `services` | int (contador) | 52 |
| `scheduledTasks` | int (contador) | 2 |
| `machineAction` | str 92 · null 81 | 74 valores distintos |
| `userAction` | str 13 · null 160 | — |
| `action` | str 5 · null 168 | — |
| `user` | bool (`true` en 44) | 173 |

### Qué campos son referencias

| campo | referencia a | resolución |
|---|---|---|
| `launcher` (nivel toggle) | fichero bajo `package/Executables/AtlasDesktop/` | 8/8 existen |
| `states[].launcher` | idem | 157/157 existen |
| `states[].toolboxLauncher` | fichero bajo `package/Executables/AtlasModules/Toolbox/` | 11/11 existen |
| `work.machineAction` / `userAction` / `action` | **nombres de función** PowerShell (no rutas) | 74 valores distintos en `machineAction` |
| `name` | id del toggle | — |

**No hay ninguna clave de registro literal en el catálogo**: solo el número de
operaciones de registro que hace cada estado (`work.registry`).

## 2. `.psd1` de `Scripts/Tweaks` — 183 ficheros

No hay PowerShell en el sandbox: los campos se cuentan con regex
`^\s*([A-Za-z_]\w*)\s*=` sobre cada línea.

- 183 ficheros, **2 091 líneas** (mín. 5, máx. 267).
- Frecuencia de claves de primer nivel (suma sobre todos los ficheros):

| clave | apariciones | | clave | apariciones |
|---|---:|---|---|---:|
| `Name` | 190 | | `ParentModes` | 8 |
| `Description` | 182 | | `Tweaks` | 8 |
| `Registry` | 154 | | `Toggle` | 7 |
| `Script` | 23 | | `ScheduledTasks` | 4 |
| `OnUpgrade` | 13 | | `OnRebase` | 4 |
| `Run` | 9 | | `Option` | 4 |
| `Services` | 3 | | `RunAs` | 2 |
| `Arch` | 1 | | | |

`Name` (190) supera el número de ficheros porque algunos `.psd1` declaran varias
entradas; `Description` (182) falta en 1 fichero.

### Por subdirectorio

| subdirectorio | `.psd1` |
|---|---:|
| `qol/` | 101 |
| `privacy/` | 41 |
| `performance/` | 11 |
| `misc/` | 8 |
| `scripts/` | 8 |
| `debloat/` | 5 |
| `networking/` | 5 |
| `security/` | 3 |
| raíz (`Tweaks/`) | 1 |

## 3. Relación entre `catalog.json` y los `.psd1`

- **`catalog.json` no nombra ningún `.psd1`**: 0 de los 91 `name` coincide con
  el nombre de fichero de algún `.psd1` (comprobado por igualdad exacta).
- Los nombres de los `.psd1` sí aparecen mencionados en el código del paquete
  (`*.ps1`/`*.psm1`/`*.cmd`/`*.psd1`): **183/183** tienen al menos una mención.
- El enlace real está en `work.machineAction`: 74 nombres de función distintos,
  p. ej. `Disable-AtlasAdvancedBootOptions`, `Enable-AtlasCbsRetry`,
  `Add-AtlasRunWithPriorityContextMenu`.
- Ejemplos de ids de toggle (máx. 5, solo nombres): `MicrosoftStore`,
  `ProcessExplorer`, `ToggleWindowsUpdates`, `AdvancedBootOptions`,
  `AutomaticRepair`.

**Conclusión medida:** el catálogo es la capa de *presentación y estado*
(grupo, elevación, estados, reinicio); los `.psd1` son la capa de
*definición del cambio* (registro, servicios, scripts, tareas). El puente son
nombres de función, no rutas. **La correspondencia exacta toggle↔`.psd1` no se
puede afirmar con regex: NO VERIFICADA** (exigiría interpretar PowerShell).
