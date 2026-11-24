# ADR-0002 — Datos de Atlas y GPL-3.0 en el catálogo de EVO

- **Estado**: **Aceptado — opción C**
- **Fecha**: 2026-11-23 (propuesto) · **aceptado 2026-11-24**
- **Contexto**: el Paso 3b/4a midió la semántica de Atlas sin copiar contenido:
  91 toggles en `Toggles/catalog.json` (grupo, elevación, estados, reinicio) y
  183 `.psd1` en `Scripts/Tweaks` (definiciones de cambio: registro, servicios,
  scripts, tareas). De los `.reg` solo se guardan clave, nombre y tipo, nunca el
  dato. Ambos proyectos son GPLv3 (`LICENSE` de EVO), y Atlas también.
- **Problema**: el catálogo de EVO CLEAN tiene que describir **qué hace** cada
  ajuste (qué clave, qué valor, qué servicio). Esa información *es* el contenido
  de obra de Atlas. Hay que decidir cómo representarla sin comprometer el
  proyecto.

## Restricción que aplica a las tres opciones

Ninguna opción permite copiar cuerpos de script, `.cmd` ni cadenas de comando:
el contrato del proyecto lo prohíbe expresamente y este ADR no lo cambia.

## Opción A — El catálogo guarda solo ids y hashes; el motor lee los datos

El ledger de EVO almacena `item_id`, ruta, sha256 y enumerados. Cuando el motor
necesita el dato (clave/valor de registro), lo lee **en tiempo de ejecución**
del checkout de Atlas fijado por SHA.

- **Riesgo**: dependencia fuerte de la estructura interna de Atlas; si upstream
  renombra un `.psd1`, el motor se rompe en ejecución (no en el build). También
  arrastra el problema de "¿el usuario final tiene Atlas en local?".
- **Coste**: bajo para publicar (no hay que redactar 91 + 183 entradas), alto en
  ingeniería (parser de `.psd1` en el motor, versionado del contrato, tests de
  compatibilidad por SHA).
- **Qué impide**: que EVO CLEAN funcione sin Atlas presente; impide distribuir
  un catálogo autocontenido.
- **Efecto legal**: mínimo, porque no se redistribuye nada derivado.

## Opción B — El catálogo se redacta de forma independiente a partir de hechos

EVO redacta sus propias entradas (qué clave, qué valor, por qué) partiendo de
los hechos medidos, con redacción propia y sin copiar texto de Atlas.

- **Riesgo**: la línea entre "hecho de configuración" y "obra derivada" es
  difusa: un listado de 300 claves de registro con sus valores puede ser
  considerado un extracto sustancial de la base de datos de Atlas (art. 7 y
  directiva 96/9/CE sobre bases de datos, además del copyright).
- **Coste**: medio-alto (redactar y mantener 274 entradas a mano).
- **Qué impide**: no impide nada técnicamente; exige disciplina de autoría y
  revisión.
- **Efecto legal**: el más incierto de los tres sin un abogado. Marcar el origen
  en cada entrada ayuda, pero no elimina el riesgo de "extracción sustancial".

## Opción C — EVO es GPLv3 y puede incorporar datos de Atlas con atribución

Al ser ambos GPLv3, se incorporan los datos (no los scripts) con atribución
explícita, conservando el aviso de licencia y el SHA de Atlas.

- **Riesgo**: obliga a mantener la compatibilidad GPLv3 del catálogo completo
  (incluidas las partes propias que se mezclen en el mismo fichero); complica un
  futuro cambio de licencia o una edición comercial.
- **Coste**: bajo de ingeniería, alto de gobernanza (revisión legal de cada
  incorporación, avisos por fichero, atribución en la UI).
- **Qué impide**: impide relicenciar el catálogo a algo no-GPL sin reescribirlo.
- **Efecto legal**: el más predecible si la atribución es correcta.

## Comparación

| | A (ids+hashes) | B (redacción propia) | C (GPLv3 + atribución) |
|---|---|---|---|
| Distribuye datos de Atlas | no | parcialmente | sí |
| Autocontenido | no | sí | sí |
| Coste de ingeniería | alto | medio | bajo |
| Coste de gobernanza | bajo | medio | alto |
| Riesgo legal residual | bajo | **alto/indeterminado** | bajo con atribución |
| Aceptable hoy sin revisión legal | sí | no | sí, con avisos |

## Recomendación técnica (no vinculante)

**A como estado actual** (es lo que el ledger ya hace: solo ids, enumerados y
hashes) y **C como destino** si el producto necesita datos completos, dejando
**B** descartada por riesgo legal indeterminado.

## Decisión

**ACEPTADA — OPCIÓN C** (2026-11-24, decisión del responsable en esta sesión).

> EVO CLEAN será siempre código abierto bajo GPLv3 y **puede incorporar datos de
> Atlas** (claves de registro, valores, nombres) **con atribución** y el commit
> fijado como origen.

### Consecuencias operativas (obligatorias)

1. **THIRD_PARTY_NOTICES** es obligatorio antes de publicar binarios o catálogo.
   Aún **no creado**: va en la base .NET (ver `docs/reports/paso4c.md`).
2. **Atribución por dato**: cada entrada incorporada lleva su origen explícito
   `atlas@ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f:<ruta>`.
3. **Marca**: prohibido usar el nombre "AtlasOS", sus logos o sus imágenes.
   EVO usa marca propia; en textos se escribe "Atlas" como referencia factual,
   nunca como marca del producto.
4. **Herramientas de terceros** (O&O ShutUp10++, Process Explorer,
   NVCleanstall): **no se redistribuyen**. Solo se invoca el original descargado
   por el usuario.
5. **El ledger actual ya cumple**: `atlas-toggles.tsv`, `atlas-toggle-ops.tsv`,
   `atlas-tweak-ops.tsv` y `atlas-functions.tsv` no llevan cuerpos de código ni
   valores literales, solo metadatos, claves y hashes.
6. **Si en el futuro se cambiara a una licencia no-GPL**, habría que **rehacer
   el catálogo sin datos de Atlas** (opción B del histórico de este ADR). Es
   coste de reescritura completa de las entradas derivadas, no un cambio de
   fichero de licencia.

### Opción elegida frente a las descartadas

- **A (solo ids/hashes)**: descartada por dependencia en tiempo de ejecución del
  checkout de Atlas.
- **B (redacción propia)**: descartada por riesgo legal indeterminado (base de
  datos) y coste de redacción de 274+ entradas.
- **C (GPLv3 + atribución)**: elegida.

## Consecuencias de no decidir

El ledger sigue siendo suficiente para medir cobertura y trazabilidad, pero **no
para ejecutar los ajustes**: el motor no puede aplicar nada sin una de las tres
opciones resuelta.
