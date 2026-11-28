# Reglas del borrador de conciliación (paso 4e)

Generador: `tools/ledger_extract/build_conciliacion.py` →
`inventory/ledger/conciliacion-borrador.tsv`.

**Este fichero no decide nada.** La columna `estado_propuesto` es una
*propuesta*; la palabra `Mapped` no aparece como valor en ninguna celda. El
responsable revisa y decide.

## Entrada

`docs/requirements/INVENTARIO_USUARIO.md`, **solo lectura**. Se normaliza igual
que `count_inventory.py`: `html.unescape` + `strip`, y a los títulos se les quita
la viñeta `- `. El fichero crudo no se modifica.

- 17 secciones, **588 líneas no vacías** (mismo conteo que
  `inventario-usuario-conteo.tsv`; comprobado en los tests).
- `fuente_declarada` = el modo vigente de `count_inventory.py` línea a línea
  (`winutil` / `atlas` / `evo` / `general`), aplicando sus reglas (d) y (e).

## Normalización de etiquetas

```
html.unescape -> NFD -> quitar diacríticos -> minúsculas
-> todo lo que no sea [a-z0-9] pasa a un espacio -> colapsar espacios
```

Vocabulario vacío documentado en `GENERIC` (palabras que aparecen en casi todas
las líneas: `windows`, `ajustes`, `activar`, `desactivar`, `permitir`…). Un token
de menos de 3 caracteres tampoco cuenta.

## Reglas, en orden (gana la primera que casa)

| regla | definición | confianza | estado propuesto |
|---|---|---|---|
| **R1** | la etiqueta normalizada del texto **es igual** a la etiqueta normalizada de un candidato | `alta` | `propuesto-mapped` |
| **R2** | el texto normalizado es **subcadena contigua** de la etiqueta normalizada, con **≥ 2 tokens** y **al menos un token discriminante** | `alta` si hay 1 candidato, `media` si hay varios | `propuesto-mapped` |
| **R3** | el texto (normalizado, como palabra completa) menciona un `target` o `name` literal de `atlas-effects.tsv`, `atlas-tweak-ops.tsv` o `winutil-tweak-ops.tsv` | `media` si ≤ 2 candidatos, `baja` si más | `propuesto-mapped` |
| **R4** | ninguna de las anteriores | `ninguna` | `sin-evidencia` |

### Umbrales (fijados antes de mirar resultados, no ajustados después)

- **R2 exige ≥ 2 tokens.** Con 1 token, «Storage.» casaría con
  «Configure Storage Sense».
- **`DF_MAX = 10`**: un token presente en más de 10 etiquetas del conjunto de
  candidatos no discrimina. Se exige que al menos un token esté en ≤ 10.
- **R2 es contigüidad, no conjuntos de tokens.** La primera versión comparaba
  conjuntos y aceptaba «Install Software.» → `WPFTweaksRazerBlock`
  («Razer Software Auto-Install - Disable»): mismos tokens, ningún significado
  común. Se corrigió el criterio, no el umbral.
- **R3 ignora targets de menos de 4 caracteres y genéricos** (`1`, `0`, `true`,
  `hklm`, `set-itemproperty`…) porque casan con cualquier texto.

## Candidatos

De estos TSV, en este orden: `winutil-items.tsv`, `winutil-apps.tsv`,
`atlas-toggles.tsv`, `atlas-tweak-files.tsv`, `atlas-manifest.tsv`. Máximo 5 por
línea, separados por `|`. Para `atlas-tweak-files.tsv` (que no tiene columna
`label`) la etiqueta es el nombre del `.psd1` sin extensión.

`atlas-effects` y `winutil-tweak-ops` **no** son fuente de etiquetas: solo
aportan *targets* para R3 (son operaciones, no objetos con nombre legible).

## Resultado medido

```
filas                 : 588 (esperado 588)
por regla             : R1 96 · R2 65 · R3 67 · R4 360
por confianza         : alta 134 · media 94 · ninguna 360
por estado propuesto  : propuesto-mapped 228 · sin-evidencia 360
por fuente declarada  : atlas 271 · evo 22 · general 98 · winutil 197
```

## Límites conocidos

- R3 puede señalar una operación concreta (`winutil:tweak-op:…:service:1`) en vez
  del tweak que la contiene; es evidencia del objeto, no del ajuste.
- Un texto que nombra dos objetos distintos produce varios candidatos y baja a
  `media`.
- `ninguna` **no** significa «no existe»: significa «con estas reglas y estos
  ledgers no hay evidencia». Ver REQ-002.
