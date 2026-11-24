# Rangos de build — capacidades con `supportedBuilds` incompleto

Generado por `tools/ledger_extract/build_build_ranges_report.py` a partir de `catalog/capabilities/*.json`. No editar a mano: CI compara el fichero con el generado.

Catálogo: **68** capacidades, 57 `Implemented` y 11 `Specified`.

## Método

Se agrupa por la tupla exacta de `supportedBuilds` (sin normalizar ni reordenar) y se contrasta cada grupo incompleto con la `provenance` de la capacidad, que cita el pin y la razón del recorte.

## Grupos medidos

| `supportedBuilds` | Capacidades |
|---|---:|
| `[19045, 22631, 26100, 26200]` | 61 |
| `[22631, 26100, 26200]` | 6 |
| `[26100, 26200]` | 1 |

Con las cuatro builds del catálogo: **61**. Con rango recortado: **7**.

## Capacidades con rango recortado

| Capacidad | `supportedBuilds` | `state` | Motivo (de su `provenance`) |
|---|---|---|---|
| `debloat.copilot.remove` | `[22631, 26100, 26200]` | Specified | el pin NO declara un numero de build para la politica mas alla de 25H2+ (que en este pin es 26200, app/src/services/windows_release.rs:48); 26100 aparece en el pin como la build a partir de la cual NO hay boton de barra de tareas y 22631 solo como build de ejemplo en pruebas (tests/Atlas.AiFeatureToggles.Tests.ps1:127,161) |
| `debloat.windows.ai.recall` | `[26100, 26200]` | Specified | NO VERIFICADO: 24H2+ por la política WindowsAI; el rango de ClickToDo y SettingsAgent es NO VERIFICADO (sin MinBuild/MaxBuild ni guardas en el pin), de ahí State=Specified |
| `explorer.gallery.hide` | `[22631, 26100, 26200]` | Implemented | la Galería del Explorador es una carpeta de Windows 11 (su CLSID {e88865ea-...} no existe en 19045) |
| `explorer.home.hide` | `[22631, 26100, 26200]` | Implemented | la carpeta Inicio (CLSID {f874310e-...}) y LaunchTo son de Windows 11; 19045 no se declara |
| `ui.context-menu.classic` | `[22631, 26100, 26200]` | Implemented | el CLSID {86ca1aa0-34aa-4e8b-a509-50c905bae2a2} es el del menú contextual de Windows 11; Windows 10 no lo usa |
| `ui.taskbar.end-task` | `[22631, 26100, 26200]` | Implemented | TaskbarEndTask no existe en Windows 10 ni en 22000/22621 sin la actualización que lo introdujo; se limita a las builds del catálogo que lo leen (22631, 26100 y 26200) |
| `ui.taskbar.icons-centered` | `[22631, 26100, 26200]` | Implemented | TaskbarAl (centrado de iconos de la barra) sólo existe en Windows 11; en 19045 la clave se escribe pero Explorer no la lee, así que la capacidad no se ofrece ahí |

## Qué comprueba CI

- `tests/test_paso9.py` exige que TODA capacidad declare `supportedBuilds` explícito y que las cinco de la sección 10 sin 19045 sean exactamente las que no tienen efecto en Windows 10.
- La nota `Builds:` de la procedencia es obligatoria para cada capacidad recortada (lo comprueban los xUnit y el test de Python).
