# Plan de oleadas (cifras medidas)

Generado por `tools/ledger_extract/build_wave_plan.py`. No editar a mano: CI compara el fichero con el generado.

## Tabla por sección

MEDIDO: las cuatro primeras columnas de estado salen de `inventory/ledger/inventory-reconciliation.tsv` (588 líneas); «Mapped cubiertas» cruza esas líneas con `ledger_refs` de las 39 capacidades; «pending upstream» cuenta las filas `pending` de `upstream-capability-map.tsv` con `section_guess` igual a esa sección.

| § | Título | Líneas | Mapped | Mapped-To-App | EVO-Exclusive | Absent-At-Pin | Informative | Mapped cubiertas | Mapped sin cubrir | Trabajo (medido) | Pending upstream |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Limpieza y eliminación de componentes | 29 | 3 | 0 | 1 | 23 | 2 | 3 | 0 | 24 | 0 |
| 2 | Debloat de Windows | 42 | 17 | 0 | 0 | 23 | 2 | 17 | 0 | 23 | 3 |
| 3 | Telemetría y privacidad | 42 | 6 | 0 | 0 | 34 | 2 | 6 | 0 | 34 | 32 |
| 4 | Optimización de servicios | 26 | 9 | 0 | 0 | 14 | 3 | 0 | 9 | 23 | 7 |
| 5 | Optimización CPU y rendimiento | 28 | 7 | 0 | 0 | 18 | 3 | 1 | 6 | 24 | 13 |
| 6 | Optimización gaming | 32 | 6 | 0 | 11 | 12 | 3 | 0 | 6 | 29 | 0 |
| 7 | Memoria y aplicaciones en segundo plano | 29 | 7 | 0 | 10 | 10 | 2 | 1 | 6 | 26 | 4 |
| 8 | Administración de inicio y apagado | 21 | 4 | 0 | 0 | 15 | 2 | 0 | 4 | 19 | 12 |
| 9 | Registro de Windows y configuración del sistema | 58 | 28 | 0 | 0 | 28 | 2 | 6 | 22 | 50 | 8 |
| 10 | Explorador de archivos e interfaz | 48 | 25 | 0 | 0 | 21 | 2 | 9 | 16 | 37 | 91 |
| 11 | Red y conectividad | 26 | 4 | 0 | 0 | 20 | 2 | 0 | 4 | 24 | 16 |
| 12 | Windows Update y mantenimiento | 28 | 5 | 0 | 0 | 21 | 2 | 0 | 5 | 26 | 8 |
| 13 | Seguridad y protección | 25 | 9 | 0 | 0 | 13 | 3 | 1 | 8 | 21 | 15 |
| 14 | Reparación y diagnóstico | 29 | 13 | 0 | 0 | 14 | 2 | 3 | 10 | 24 | 10 |
| 15 | Administración de aplicaciones | 32 | 1 | 5 | 0 | 23 | 3 | 0 | 6 | 29 | 35 |
| 16 | Funciones de instalación y administración avanzada | 44 | 5 | 0 | 0 | 35 | 4 | 0 | 5 | 40 | 2 |
| 17 | Capacidades adicionales que no debemos perder | 49 | 0 | 0 | 15 | 2 | 32 | 0 | 0 | 17 | 0 |
| **Σ** | **17 secciones** | **588** | **149** | **5** | **37** | **326** | **71** | **47** | **107** | **470** | **256** |

Pendientes upstream **sin sección**: 129. Son los ítems cuya categoría está marcada `mixed` en `inventory/partition/category-section-map.tsv`; el reparto por ítem es trabajo del paso siguiente, no se inventa aquí.

## Orden propuesto de oleadas

PROPUESTA (no medida): el orden y los motivos son del agente; las cifras de cada fila son las de la tabla de arriba.

| Oleada | § | Trabajo medido | Motivo de la posición |
|---|---|---|---|
| W1 | 1 Limpieza y eliminación de componentes | 24 | Base de limpieza: 24 unidades de trabajo y ya tiene 3/3 Mapped cubiertas. Va primero porque las demás oleadas reutilizan su motor de borrado. |
| W2 | 2 Debloat de Windows | 23 | Debloat es el núcleo del producto y ya está 17/17. Continúa con 10 y 9. |
| W3 | 10 Explorador de archivos e interfaz | 37 | Explorador e interfaz: 25 Mapped de 48 líneas, el bloque más grande de upstream (92 ítems con sección). Depende de las políticas de 2. |
| W4 | 9 Registro de Windows y configuración del sistema | 50 | Registro y configuración: 28 Mapped, casi el mismo tamaño que 10 y sin dependencias; buen candidato a oleada paralela. |
| W5 | 3 Telemetría y privacidad | 34 | Telemetría: 6/6 Mapped cubiertas; el resto (34 Absent-At-Pin) son los ajustes de privacidad finos, que necesitan el motor de 2. |
| W6 | 4 Optimización de servicios | 23 | Servicios: alto riesgo por servicio, 9 Mapped. Después de 3 para no duplicar DiagTrack. |
| W7 | 12 Windows Update y mantenimiento | 26 | Windows Update: 5 Mapped y 21 Absent-At-Pin; toca el mismo DISM de 1 y 14, así que va después de ellas. |
| W8 | 14 Reparación y diagnóstico | 24 | Reparación y diagnóstico: 13 Mapped; sus comandos comparten ejecutor con 1. |
| W9 | 13 Seguridad y protección | 21 | Seguridad: 9 Mapped y riesgo alto; después de 4 y 12, que ya tocan servicios y directivas del sistema. |
| W10 | 11 Red y conectividad | 24 | Red: 4 Mapped y 20 Absent-At-Pin; aislada, puede ir en cualquier momento. |
| W11 | 5 Optimización CPU y rendimiento | 24 | Rendimiento: 7 Mapped, 1 cubierta; toca energía y programas, poco acoplado. |
| W12 | 7 Memoria y aplicaciones en segundo plano | 26 | Memoria y segundo plano: 10 EVO-Exclusive propios; necesita 6 resuelto antes (mismo objeto: apps en segundo plano). |
| W13 | 6 Optimización gaming | 29 | Gaming: 11 EVO-Exclusive propios y 12 Absent-At-Pin; depende de 7. |
| W14 | 8 Administración de inicio y apagado | 19 | Inicio y apagado: 4 Mapped, riesgo alto (arranque). Va tarde. |
| W15 | 15 Administración de aplicaciones | 29 | Administración de aplicaciones: 5 Mapped-To-App y 23 Absent-At-Pin; depende del instalador (16). |
| W16 | 16 Funciones de instalación y administración avanzada | 40 | Funciones de instalación: 35 Absent-At-Pin, casi todo tooling propio; sólo tiene sentido con 15 cerrada. |
| W17 | 17 Capacidades adicionales que no debemos perder | 17 | Capacidades adicionales: 32 cabeceras informativas y 15 EVO-Exclusive; es un cajón de requisitos, se cierra al final. |

## Cómo leer las cifras

- «Trabajo» = Mapped sin cubrir + EVO-Exclusive + Absent-At-Pin. No cuenta las líneas informativas.
- «Pending upstream» no se suma con «Trabajo»: miden universos distintos (ítems de upstream frente a líneas del inventario).
- Los ítems `mixed` no aparecen en ninguna sección porque su categoría no permite asignarlos sin mirarlos uno a uno.
