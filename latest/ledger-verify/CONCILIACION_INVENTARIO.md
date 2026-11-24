# Conciliación del inventario del responsable

Generado por `tools/ledger_extract/build_final_reconciliation.py`.
Fuente: `docs/requirements/INVENTARIO_USUARIO.md` (solo lectura,
sha256 `0b6aeaef…f709`). **No se modifica el inventario.**

Total: **588** líneas no vacías.

## Estados

| estado | líneas | qué significa |
|---|---:|---|
| `Mapped` | 152 | existe como tweak/toggle/servicio/clave en el pin, con id |
| `Mapped-To-App` | 5 | entrada de `winutil-apps.tsv` (sección 15) |
| `EVO-Exclusive` | 37 | requisito propio de EVO |
| `Absent-At-Pin` | 323 | nombrado en el inventario, no existe en el pin |
| `Informative-Header` | 71 | encabezado, nota o cabecera de tabla |

## Tabla 17 × 5

| sección | título | Mapped | Mapped-To-App | EVO-Exclusive | Absent-At-Pin | Informative-Header | total |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | LIMPIEZA Y ELIMINACIÓN DE COMPONENTES | 3 | 0 | 1 | 23 | 2 | 29 |
| 2 | DEBLOAT DE WINDOWS | 17 | 0 | 0 | 23 | 2 | 42 |
| 3 | TELEMETRÍA Y PRIVACIDAD | 6 | 0 | 0 | 34 | 2 | 42 |
| 4 | OPTIMIZACIÓN DE SERVICIOS | 9 | 0 | 0 | 14 | 3 | 26 |
| 5 | OPTIMIZACIÓN DE CPU Y RENDIMIENTO | 7 | 0 | 0 | 18 | 3 | 28 |
| 6 | OPTIMIZACIÓN GAMING | 6 | 0 | 11 | 12 | 3 | 32 |
| 7 | MEMORIA Y APLICACIONES EN SEGUNDO PLANO | 7 | 0 | 10 | 10 | 2 | 29 |
| 8 | ADMINISTRACIÓN DE INICIO Y APAGADO | 4 | 0 | 0 | 15 | 2 | 21 |
| 9 | REGISTRO DE WINDOWS Y CONFIGURACIÓN DEL SIST | 27 | 0 | 0 | 29 | 2 | 58 |
| 10 | EXPLORADOR DE ARCHIVOS E INTERFAZ | 29 | 0 | 0 | 17 | 2 | 48 |
| 11 | RED Y CONECTIVIDAD | 4 | 0 | 0 | 20 | 2 | 26 |
| 12 | WINDOWS UPDATE Y MANTENIMIENTO | 5 | 0 | 0 | 21 | 2 | 28 |
| 13 | SEGURIDAD Y PROTECCIÓN | 9 | 0 | 0 | 13 | 3 | 25 |
| 14 | REPARACIÓN Y DIAGNÓSTICO | 13 | 0 | 0 | 14 | 2 | 29 |
| 15 | ADMINISTRACIÓN DE APLICACIONES | 1 | 5 | 0 | 23 | 3 | 32 |
| 16 | FUNCIONES DE INSTALACIÓN Y ADMINISTRACIÓN AV | 5 | 0 | 0 | 35 | 4 | 44 |
| 17 | CAPACIDADES ADICIONALES QUE NO DEBEMOS PERDE | 0 | 0 | 15 | 2 | 32 | 49 |
| **Σ** | | 152 | 5 | 37 | 323 | 71 | **588** |

## Reglas aplicadas

1. `Informative-Header`: encabezados de sección, encabezados de modo
   (`WinUtil`/`AtlasOS`), notas metodológicas y referencias
   bibliográficas.
2. `EVO-Exclusive`: todo el bloque que abre `EVO CLEAN` o
   `Capacidad EVO a desarrollar:` y cierra con la nota «Estas últimas
   capacidades…» o el siguiente encabezado de modo.
3. `Absent-At-Pin`: la sonda de `seccion16-17-probe.tsv` da `atlas=0` o
   patrón dudoso, o el texto cae en la lista de funcionalidades que en
   el pin no existen como código ejecutable.
4. `Mapped-To-App`: sección 15 y candidato `winutil:catalog-entry:*`.
5. `Mapped`: regla R1/R2/R3 del paso 4e con candidato presente en los
   ledgers; se añaden dos reglas propias: `apps_in_text()` (nombre de
   producto de `winutil-apps.tsv`, ≥4 caracteres, con límites de
   palabra) y `service_index()` (servicios de `winutil-tweak-ops.tsv`
   cruzados con `value_name` de `atlas-tweak-ops.tsv`).
6. `Absent-At-Pin` (resto): sin candidato y sin ser requisito EVO.
7. Sección 17: la tabla está aplanada en el inventario (una celda por
   línea). La primera celda de cada fila es la `Funcionalidad` y se
   clasifica como requisito (`EVO-Exclusive`, o `Absent-At-Pin` para
   las tres que ningún pin implementa: perfiles y presets, instalación
   de ISO, creación de USB); las celdas `Sí`/`No` y las cabeceras
   `Funcionalidad`/`WinUtil`/`AtlasOS` son `Informative-Header`;
   `No como motor propio` es `Absent-At-Pin`.

## Límites

- `Absent-At-Pin` **no** afirma que la funcionalidad no exista en
  Windows: solo que no hay código/parser en el pin medido.
- `Mapped` usa la coincidencia de etiquetas del paso 4e; su precisión
  está auditada en `docs/reports/paso4e.md`.
