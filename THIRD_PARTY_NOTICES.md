# THIRD_PARTY_NOTICES

Este producto (EVO CLEAN) se distribuye bajo **GPL-3.0** (ver `LICENSE`).
Incorpora ideas, datos de configuración y metadatos derivados de los proyectos
listados abajo. Los ficheros de upstream **no** se copian al repositorio
(ver `docs/AGENT_CONTRACT.md` §5): el inventario guarda metadatos, claves y
hashes.

## Resumen de licencias

| Proyecto | Repo | Tipo | Licencia | SHA fijado |
|---|---|---|---|---|
| WinUtil | ChrisTitusTech/winutil | herramienta PowerShell (WPF) | MIT | `70c23c80641d7370532af2f619b2842658600842` |
| AtlasOS | Atlas-OS/Atlas | SO/script de configuración | GPL-3.0 | `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f` |
| EVO CLEAN | EvoMaxPC/Evo_Optimizer-On | este proyecto | GPL-3.0 | — |

Compatibilidad: MIT es compatible con GPL-3.0 en la dirección MIT→GPL (el
código MIT puede incorporarse a un proyecto GPLv3 conservando el aviso).
El código GPL-3.0 de Atlas solo puede incorporarse a este proyecto manteniendo
GPL-3.0, que es el caso.

---

## 1. WinUtil — MIT License

Origen: https://github.com/ChrisTitusTech/winutil · SHA `70c23c80641d7370532af2f619b2842658600842`
Fichero original: `LICENSE` (sha256 `469b54dadfa5c0d0002291e452fcaa32165356d3459e1dee040404db5439fb1c`)

Texto íntegro, sin modificar:

```
MIT License

Copyright (c) 2022 CT Tech Group LLC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 2. AtlasOS — GNU General Public License v3.0

Origen: https://github.com/Atlas-OS/Atlas · SHA `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`
Fichero original: `LICENSE` (sha256 `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`)

Texto íntegro = el fichero `LICENSE` de este repositorio, byte a byte idéntico
al de Atlas (verificado con `sha256sum` y `cmp`, ver `docs/reports/paso1.md`).
Por tanto no se duplica aquí: **`LICENSE` ES el texto GPL-3.0 de Atlas**.
