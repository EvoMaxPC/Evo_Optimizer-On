# Plan de oleadas (cifras medidas)

Generado por `tools/ledger_extract/build_wave_plan.py`. No editar a mano: CI compara el fichero con el generado.

## Tabla por sección

MEDIDO: las cuatro primeras columnas de estado salen de `inventory/ledger/inventory-reconciliation.tsv` (588 líneas); «Mapped cubiertas» cruza esas líneas con `ledger_refs` de las 101 capacidades del catálogo; «pending upstream» cuenta las filas `pending` de `upstream-capability-map.tsv` con `section_guess` igual a esa sección.

| § | Título | Líneas | Mapped | Mapped-To-App | EVO-Exclusive | Absent-At-Pin | Informative | Mapped cubiertas | Mapped sin cubrir | Trabajo (medido) | Pending upstream |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Limpieza y eliminación de componentes | 29 | 3 | 0 | 1 | 23 | 2 | 3 | 0 | 24 | 2 |
| 2 | Debloat de Windows | 42 | 17 | 0 | 0 | 23 | 2 | 17 | 0 | 23 | 5 |
| 3 | Telemetría y privacidad | 42 | 6 | 0 | 0 | 34 | 2 | 6 | 0 | 34 | 35 |
| 4 | Optimización de servicios | 26 | 13 | 0 | 0 | 10 | 3 | 13 | 0 | 10 | 1 |
| 5 | Optimización CPU y rendimiento | 28 | 7 | 0 | 0 | 18 | 3 | 3 | 4 | 22 | 20 |
| 6 | Optimización gaming | 32 | 6 | 0 | 11 | 12 | 3 | 2 | 4 | 27 | 1 |
| 7 | Memoria y aplicaciones en segundo plano | 29 | 7 | 0 | 10 | 10 | 2 | 3 | 4 | 24 | 3 |
| 8 | Administración de inicio y apagado | 21 | 4 | 0 | 0 | 15 | 2 | 1 | 3 | 18 | 16 |
| 9 | Registro de Windows y configuración del sistema | 58 | 31 | 0 | 0 | 25 | 2 | 31 | 0 | 25 | 3 |
| 10 | Explorador de archivos e interfaz | 48 | 29 | 0 | 0 | 17 | 2 | 29 | 0 | 17 | 98 |
| 11 | Red y conectividad | 26 | 4 | 0 | 0 | 20 | 2 | 0 | 4 | 24 | 26 |
| 12 | Windows Update y mantenimiento | 28 | 5 | 0 | 0 | 21 | 2 | 1 | 4 | 25 | 17 |
| 13 | Seguridad y protección | 25 | 9 | 0 | 0 | 13 | 3 | 2 | 7 | 20 | 16 |
| 14 | Reparación y diagnóstico | 29 | 13 | 0 | 0 | 14 | 2 | 3 | 10 | 24 | 14 |
| 15 | Administración de aplicaciones | 32 | 1 | 5 | 0 | 23 | 3 | 0 | 6 | 29 | 44 |
| 16 | Funciones de instalación y administración avanzada | 44 | 5 | 0 | 0 | 35 | 4 | 0 | 5 | 40 | 7 |
| 17 | Capacidades adicionales que no debemos perder | 49 | 0 | 0 | 15 | 2 | 32 | 0 | 0 | 17 | 0 |
| **Σ** | **17 secciones** | **588** | **160** | **5** | **37** | **315** | **71** | **114** | **51** | **403** | **308** |

Pendientes upstream **sin sección**: 18. Desde el paso 8d la sección sale también de `inventory/partition/item-section-map.tsv` (435 filas, regla y evidencia escritas). Lo que queda sin sección no tiene efecto propio: entradas de navegación, presets, paneles heredados y scripts cuyo efecto no está medido en el pin.

## Orden propuesto de oleadas

PROPUESTA (no medida): el orden y los motivos son del agente; las cifras de cada fila son las de la tabla de arriba.

| Oleada | § | Trabajo medido | Motivo de la posición |
|---|---|---|---|
| W1 | 1 Limpieza y eliminación de componentes | 24 | Base de limpieza: 24 unidades de trabajo y ya tiene 3/3 Mapped cubiertas. Va primero porque las demás oleadas reutilizan su motor de borrado. |
| W2 | 2 Debloat de Windows | 23 | Debloat es el núcleo del producto y ya está 17/17. Continúa con 10 y 9. |
| W3 | 10 Explorador de archivos e interfaz | 17 | Explorador e interfaz: oleada 2, cerrada en el catálogo (29 de 29 líneas Mapped cubiertas). Sigue siendo la sección con más ítems de upstream pendientes: el trabajo que queda es de upstream, no del inventario. |
| W4 | 9 Registro de Windows y configuración del sistema | 25 | Registro y configuración: oleada 3, cerrada en el catálogo (30 de 30 líneas Mapped cubiertas con 18 capacidades). Quedan 3 ítems de upstream pendientes y ninguno es un valor de registro fijo: la indización se aplica como acción de TrustedInstaller, la página de «workplace» se edita de forma incremental (conservando las demás páginas) y el panel de fecha y hora sólo abre timedate.cpl. |
| W5 | 3 Telemetría y privacidad | 34 | Telemetría: 6/6 Mapped cubiertas; el resto (34 Absent-At-Pin) son los ajustes de privacidad finos, que necesitan el motor de 2. |
| W6 | 4 Optimización de servicios | 10 | Servicios: alto riesgo por servicio, 9 Mapped. Después de 3 para no duplicar DiagTrack. |
| W7 | 12 Windows Update y mantenimiento | 25 | Windows Update: 5 Mapped y 21 Absent-At-Pin; toca el mismo DISM de 1 y 14, así que va después de ellas. |
| W8 | 14 Reparación y diagnóstico | 24 | Reparación y diagnóstico: 13 Mapped; sus comandos comparten ejecutor con 1. |
| W9 | 13 Seguridad y protección | 20 | Seguridad: 9 Mapped y riesgo alto; después de 4 y 12, que ya tocan servicios y directivas del sistema. |
| W10 | 11 Red y conectividad | 24 | Red: 4 Mapped y 20 Absent-At-Pin; aislada, puede ir en cualquier momento. |
| W11 | 5 Optimización CPU y rendimiento | 22 | Rendimiento: 7 Mapped, 1 cubierta; toca energía y programas, poco acoplado. |
| W12 | 7 Memoria y aplicaciones en segundo plano | 24 | Memoria y segundo plano: 10 EVO-Exclusive propios; necesita 6 resuelto antes (mismo objeto: apps en segundo plano). |
| W13 | 6 Optimización gaming | 27 | Gaming: 11 EVO-Exclusive propios y 12 Absent-At-Pin; depende de 7. |
| W14 | 8 Administración de inicio y apagado | 18 | Inicio y apagado: 4 Mapped, riesgo alto (arranque). Va tarde. |
| W15 | 15 Administración de aplicaciones | 29 | Administración de aplicaciones: 5 Mapped-To-App y 23 Absent-At-Pin; depende del instalador (16). |
| W16 | 16 Funciones de instalación y administración avanzada | 40 | Funciones de instalación: 35 Absent-At-Pin, casi todo tooling propio; sólo tiene sentido con 15 cerrada. |
| W17 | 17 Capacidades adicionales que no debemos perder | 17 | Capacidades adicionales: 32 cabeceras informativas y 15 EVO-Exclusive; es un cajón de requisitos, se cierra al final. |

## Cómo leer las cifras

- «Trabajo» = Mapped sin cubrir + EVO-Exclusive + Absent-At-Pin. No cuenta las líneas informativas.
- «Pending upstream» no se suma con «Trabajo»: miden universos distintos (ítems de upstream frente a líneas del inventario).
- Desde el paso 8d, los ítems de categorías `mixed` sí aparecen: se reparten por ítem con regla y evidencia en `inventory/partition/item-section-map.tsv`. Los que siguen sin sección son los que no tienen efecto propio (navegación, presets, paneles, scripts sin operación medida).
