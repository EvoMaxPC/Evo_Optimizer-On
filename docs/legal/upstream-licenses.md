# Licencias de upstream en los pines fijados

Medido en los checkouts de `/tmp/upstream/` con el pin de cada repo. No se
juzga compatibilidad: solo se transcribe lo que dicen los ficheros.

| repo | pin | LICENSE | líneas |
|---|---|---|---|
| `AtlasOS/Atlas` | `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f` | `LICENSE` (raíz) | 674 |
| `ChrisTitusTech/winutil` | `70c23c80641d7370532af2f619b2842658600842` | `LICENSE` | 21 |

## WinUtil — MIT

Encabezado literal (4 primeras líneas no vacías):

```
MIT License

Copyright (c) 2022 CT Tech Group LLC
```

Licencia permisiva MIT estándar. **No hay cláusula de "o posterior"**: es MIT
tal cual.

## Atlas — GPL v3

Encabezado literal del `LICENSE` de la raíz:

```
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.
```

Existe además un `package/Executables/AtlasModules/LICENSE` con el **mismo
texto GPLv3** (35 149 B).

### ¿GPL-3.0 *solo* o *3.0 o posterior*?

Comando:

```
cd /tmp/upstream/atlas
git grep -n -i "any later version\|GPL-3.0-only\|GPL-3.0-or-later\|SPDX-License-Identifier"
```

Resultado (conteo por fichero, `git grep -c -i "any later version"`):

| fichero | coincidencias |
|---|---:|
| `LICENSE` | 3 |
| `package/Executables/AtlasModules/LICENSE` | 3 |
| `app/licenses/THIRD-PARTY-NOTICES.txt` | 2 |

Las 3 coincidencias de cada `LICENSE` son **texto plantilla de la GPL**, no una
declaración del proyecto:

- línea 572: `Public License "or any later version" applies to it, you have the`
- línea 574: `version or of any later version published by the Free Software`
- línea 640: `(at your option) any later version.` (apéndice "How to Apply")

Ninguna cabecera de fichero de Atlas declara `or later`. `git grep -l
"SPDX-License-Identifier:"` devuelve **1 solo fichero**,
`app/licenses/THIRD-PARTY-NOTICES.txt`, con **34** identificadores, **todos
`Unicode-3.0`** (dependencias, no Atlas).

La declaración explícita del proyecto está en el manifiesto de Cargo:

```
$ git grep -n "^license" -- '*.toml'
app/Cargo.toml:8:license = "GPL-3.0-only"
services/reports-mcp/Cargo.toml:5:license = "GPL-3.0-only"
app/vendor/accesskit_windows/Cargo.toml:33:license = "MIT OR Apache-2.0"
app/vendor/gpui-pre-windows/Cargo.toml:25:license = "Apache-2.0"
app/vendor/gpui-pre/Cargo.toml:33:license = "Apache-2.0"
```

**Conclusión: `GPL-3.0-only`** (no "o posterior"), según `app/Cargo.toml` línea
8 y la ausencia de cualquier "or later" declarativo en cabeceras. Cinco
ejemplos usados: los tres pasajes de `LICENSE` y las dos declaraciones
`GPL-3.0-only` de los `Cargo.toml`.

## Ficheros de Atlas con licencia propia distinta

`app/licenses/` contiene el inventario de licencias de las **dependencias**, no
de Atlas:

| fichero | contenido |
|---|---|
| `dependency-inventory.json` | 391 paquetes con su campo `license`; `unresolved: 0` |
| `THIRD-PARTY-NOTICES.txt` | avisos de terceros (34 SPDX `Unicode-3.0`) |
| `GPUI-input-APACHE-2.0.txt` | licencia Apache-2.0 de una dependencia |
| `supplements.json` | 34 suplementos (paquetes con licencia fuera del inventario general) |
| `supplemental/` | un directorio por paquete suplementado (accesskit, lyon, fluent-langneg…) |
| `README.md` | explica el procedimiento de generación |

Distribución de licencias declaradas en `dependency-inventory.json` (391
paquetes, top 8): `MIT OR Apache-2.0` 192 · `MIT` 54 · `Apache-2.0 OR MIT` 36 ·
`Unicode-3.0` 34 · `MIT/Apache-2.0` 13 · `Apache-2.0` 13 · `BSD-3-Clause` 8 ·
`Unlicense OR MIT` 6.

**No se juzga compatibilidad**, según el encargo. Nótese solo que Atlas
vendoriza `app/vendor/gpui-pre*` (Apache-2.0) y `accesskit_windows`
(MIT OR Apache-2.0), que en la partición son `reference`, no `extract`.
