# Rangos de build — capacidades con `supportedBuilds` incompleto

Fecha: 2026-11-24 (reloj del agente, UTC).
Pins: Atlas `ec3c4058ad0ebd5289a4d07f2af5d6c86e8d455f`,
WinUtil `70c23c80641d7370532af2f619b2842658600842`.
Catálogo: 39 capacidades, 28 `Implemented` y 11 `Specified`.

## Método

Comprobación en dos pasos sobre `catalog/capabilities/*.json`:

1. Se leen todas las capacidades y se agrupa por la tupla exacta de
   `supportedBuilds` (sin asumir orden ni normalizar).
2. Se comparan con el conjunto completo del catálogo,
   `{19045, 22631, 26100, 26200}`, y se contrasta cada excepción con su
   `provenance` y con las líneas citadas del pin.

Resultado del paso 1 — sólo hay tres grupos:

| `supportedBuilds` | Capacidades |
| --- | --- |
| `[19045, 22631, 26100, 26200]` | 37 |
| `[26100, 26200]` | 1 |
| `[22631, 26100, 26200]` | 1 |

Es decir: **2 capacidades** no cubren las cuatro builds. Son las dos que el
paso 8d deja documentadas y testeadas
(`test_las_capacidades_con_rango_incompleto_lo_justifican`, que fija el conjunto
exacto y falla si aparece una tercera).

## Capacidad 1 — `debloat.windows.ai.recall`

- `state`: `Specified`
- `supportedBuilds`: `[26100, 26200]`
- Falta: **19045** (y 22631 sí está, pero el objeto real —Recall— no existe
  antes de 24H2).

Evidencia:

| Fichero:línea | Qué dice | Qué fija |
| --- | --- | --- |
| `Toggles/General/Recall.psd1:14-16` | `AllowRecallEnablement=0` con la nota de que aplica a **24H2 26100.3915+** | Suelo en 26100 para la política de Recall |
| `Toggles/General/Recall.psd1` (claves `WindowsAI`) | Las claves viven bajo `HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsAI` | La rama de política `WindowsAI` no existe antes de 24H2 |
| `Toggles/General/Recall.ps1` (rama `Enable`) | Borra las claves anteriores | La reversión es por política, no por paquete |

**NO VERIFICADO**: el rango de las acciones de Click To Do y del agente de
Configuración que esta capacidad agrupa; y si `WindowsAI\DisableAIDataAnalysis`
tiene efecto en 26100 RTM frente a 26100.3915+. El pin sólo fecha el suelo de
`AllowRecallEnablement`; no fecha las demás.

Motivo de no ampliar: 19045 no tiene Recall; declararlo ahí produciría una
capacidad que se ofrece donde no aplica.

## Capacidad 2 — `debloat.copilot.remove`

- `state`: `Specified` (cambiada en el paso 8d; antes `Implemented`)
- `supportedBuilds`: `[22631, 26100, 26200]`
- Falta: **19045**.

Evidencia:

| Fichero:línea | Qué dice | Qué fija |
| --- | --- | --- |
| `Tweaks/qol/taskbar/disable-copilot.psd1:6` | `RemoveMicrosoftCopilotApp` es **25H2+** y sólo lo honran Enterprise y Education | La política de desinstalación es 26200+ |
| `Tweaks/qol/taskbar/disable-copilot.psd1:9` | `RemoveMicrosoftCopilotApp = 1` | Acción 1 |
| `Toggles/General/Copilot.psd1:13-14` | `Disable`: `RemoveMicrosoftCopilotApp=1` (HKLM) y `ShowCopilotButton=0` (HKCU) | Acciones 1 y 3 |
| `Toggles/General/Copilot.ps1:42` | `Enable` borra la política | Reversible por política |
| `Toggles/General/Copilot.ps1:52` | `$legacyTaskbarAvailable = ($Toggle.WindowsBuild -lt 26100 …)` | El botón de barra de tareas sólo se toca por debajo de 26100 |
| `Toggles/General/Copilot.ps1:18,59` | `Microsoft.Copilot*` / `Get-AppxPackage -Name Microsoft.Copilot` | El paquete es el objeto |
| `Toggles/General/Copilot.ps1:71` | `install --id 9NHT9RB2F4HD --source msstore` | Reinstalación desde Store |

**NO VERIFICADO**: el rango **por acción**. El pin fija el suelo 25H2+ de la
política y el uso del botón por debajo de 26100, pero no fija qué acción tiene
efecto en 22631 ni en 26100. El campo `provenance` lo dice literalmente
(`RANGO NO VERIFICADO`), y por eso la capacidad baja a `Specified`.

**22631 en el pin**: aparece en `tests/Atlas.AiFeatureToggles.Tests.ps1:127,161`
como build de ejemplo y en `app/src/services/windows_release.rs:390,416,424`
como build no soportada para probar transiciones. **No** hay guarda de build en
el `.psd1` ni en el `.ps1` de Copilot. Se mantiene porque 22631 es la build
donde Copilot existe como botón de barra de tareas, pero la evidencia es
indirecta y así queda marcada.

Motivo de no ampliar: 19045 no aparece en el pin en relación con Copilot. La
política de desinstalación del paquete no existe allí; el botón sí, pero
declararlo sería inventar el rango.

## Qué haría falta para cerrar estos rangos

1. Ejecutar en VM 19045, 22631, 26100 y 26200 las tres acciones por separado y
   comprobar el estado resultante (política presente, paquete presente, botón
   presente).
2. Leer el valor de `DisplayVersion`/UBR en cada build para fijar el suelo de
   `26100.3915+`.
3. Con eso, o se amplía `supportedBuilds` con evidencia, o se parte cada
   capacidad en una por acción (política vs. paquete vs. botón), que es lo que
   ADR-0003 ya permite con `Irreversible`.

Ninguno de los tres pasos se puede hacer en CI: son observaciones sobre una
máquina Windows real.
