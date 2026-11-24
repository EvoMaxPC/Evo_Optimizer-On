# ADR-0002 — Datos de Atlas y GPL-3.0 en el catálogo de EVO

- **Estado**: **Propuesto** (no aceptado; la decisión es del responsable)
- **Fecha**: 2026-11-23
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

**PENDIENTE DEL RESPONSABLE.** Este ADR queda en estado **Propuesto**. No se
modifica el ledger, no se incorporan datos de Atlas y el estado actual
(solo hechos) se mantiene hasta que haya decisión escrita.

## Consecuencias de no decidir

El ledger sigue siendo suficiente para medir cobertura y trazabilidad, pero **no
para ejecutar los ajustes**: el motor no puede aplicar nada sin una de las tres
opciones resuelta.
