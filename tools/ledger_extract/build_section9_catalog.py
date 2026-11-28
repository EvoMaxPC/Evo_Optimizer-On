#!/usr/bin/env python3
"""Genera `catalog/capabilities/section9_system_registry.json` (paso 10, oleada 3).

Los VALORES de cada acción no se escriben a mano: se leen del pin fijado
(WinUtil `70c23c8…` en `config/tweaks.json` y `config/feature.json`; Atlas
`ec3c4058…` en `package/Executables/AtlasModules/Toggles/` y `Scripts/Tweaks/`)
y la provenance cita fichero y línea. Si el pin no está en `/tmp/upstream`, el
script falla con un mensaje claro: no se inventa ningún literal.

Alcance de la sección 9 (REGISTRO DE WINDOWS Y CONFIGURACIÓN DEL SISTEMA):

- Las líneas del inventario conciliado que ninguna capacidad cubría todavía y
  que el pin SÍ implementa (hibernación, ubicación, servicios, modo de juego,
  aceleración del ratón, S0/S3, mitigaciones, atajos de teclado, visibilidad de
  páginas de Configuración).
- Los ítems de upstream que `item-section-map.tsv` asigna a la sección 9 y que
  son de registro (control de fallos, WPBT, retardo de menús, servidores NTP,
  información OEM, copia de seguridad del registro, UTC, indexación).
- Cuando el pin hace además algo que NO es de registro (servicios, scripts,
  tareas programadas), no se calla: se dice en la descripción, se anota en la
  provenance y, si el efecto completo no cabe en el motor, la capacidad queda en
  `State=Specified`.

Salida determinista: orden por id, LF, UTF-8 sin BOM, 3 espacios de sangría.

Uso:
    python3 tools/ledger_extract/build_section9_catalog.py
    python3 tools/ledger_extract/build_section9_catalog.py --check
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Se reutiliza el parseo ya probado de la oleada 2 (mismo pin, mismas reglas):
# troceo de `@{ … }`, estados de los .psd1 de Toggles, normalización de literales
# y de rutas.
import build_section10_catalog as b10  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "catalog" / "capabilities" / "section9_system_registry.json"
UPSTREAM = b10.UPSTREAM
WINUTIL_TWEAKS = b10.WINUTIL_TWEAKS
WINUTIL_FEATURES = UPSTREAM / "winutil" / "config" / "feature.json"
ATLAS_TOGGLES = b10.ATLAS_TOGGLES
ATLAS_TWEAKS = b10.ATLAS_TWEAKS

WINUTIL_PIN = b10.WINUTIL_PIN
ATLAS_PIN = b10.ATLAS_PIN
DEFAULT_BUILDS = b10.DEFAULT_BUILDS
W_TWEAKS: dict = b10.W_TWEAKS
W_FEATURES: dict = (
    json.loads(WINUTIL_FEATURES.read_text(encoding="utf-8"), strict=False)
    if WINUTIL_FEATURES.is_file() else {}
)

CONFIRM = {"Safe": "None", "Low": "SimpleClick", "Medium": "Summary",
           "High": "SummaryAndRestorePoint", "Critical": "TypeOperationName"}
# ADR-0003: con Reversibility=Reversible el mínimo de restauración depende del
# riesgo (Low -> SessionUndo, Medium/High -> RestorePoint). Las capacidades de
# esta sección que tocan estado de máquina (HKLM) y piden Medium/High van con
# RestorePoint: el motor crea el punto antes de escribir y además guarda el valor
# previo. Las de HKCU van con SessionUndo.
RESTORE = {"Safe": "SessionUndo", "Low": "SessionUndo",
           "Medium": "RestorePoint", "High": "RestorePoint",
           "Critical": "FullBackup"}

HIVES = {"HKLM": "LocalMachine", "HKCU": "CurrentUser",
         "HKCR": "ClassesRoot", "HKU": "Users"}

# --------------------------------------------------------------- especificación
# Cada entrada:
#   id, name, desc, risk, security, build_note
#   winutil     tweak de `config/tweaks.json` (se toma `Value`, que es el valor
#               que WinUtil escribe)
#   services    True si el tweak declara `service` (se emiten ServiceActions)
#   feature     entrada de `config/feature.json` cuyos literales están en el
#               `InvokeScript` (se leen con `script_props`)
#   atlas_toggle (ruta dentro de Toggles, estado) del pin
#   atlas_tweak ruta dentro de Scripts/Tweaks (con .psd1)
#   static_key/static_value_variable  script del pin con clave y valor literales
#   omit        lo que el pin hace y NO se declara (se escribe, no se calla)
#   state       "Implemented" por defecto
WINUTIL_SPECS = [
    dict(id="system.game-mode.enable", winutil="WPFToggleGameMode",
         name="Activar el modo de juego de Windows",
         desc="Pone AllowAutoGameMode=1 y AutoGameModeEnabled=1 en HKCU\\Software\\"
              "Microsoft\\GameBar. El modo de juego evita que Windows reparta recursos "
              "de CPU y GPU entre segundo plano y juego mientras uno está en primer "
              "plano. Es una preferencia por usuario y ya suele estar activa.",
         risk="Safe", security="Neutral",
         build_note="claves de HKCU presentes en 19045 y en las tres builds de Windows 11"),
    dict(id="system.mouse-acceleration.enable", winutil="WPFToggleMouseAcceleration",
         name="Activar la aceleración del puntero del ratón",
         desc="Pone MouseSpeed='1' y MouseThreshold1='6' / MouseThreshold2='10' en "
              "HKCU\\Control Panel\\Mouse. La casilla encendida del pin ACTIVA la "
              "aceleración (es el valor por defecto de Windows); el catálogo declara el "
              "efecto tal y como está medido en la fuente, sin invertir su significado. "
              "Sólo escribe valores de la sesión del usuario.",
         risk="Safe", security="Neutral",
         build_note="claves de HKCU/Control Panel estables desde Windows 10 1507"),
    dict(id="system.sleep.s0-network-keep", winutil="WPFToggleStandbyFix",
         name="Mantener la red durante el reposo moderno (S0)",
         desc="Pone ACSettingIndex=1 en la directiva de energía del adaptador de red "
              "(HKCU\\SOFTWARE\\Policies\\Microsoft\\Power\\PowerSettings\\f15576e8-…). "
              "Evita que la conexión se caiga al entrar en reposo moderno (S0). No "
              "cambia el modelo de reposo del equipo.",
         risk="Safe", security="Neutral",
         build_note="la directiva por GUID existe en 19045 y en las tres de Windows 11"),
    dict(id="system.sleep.s3-enable", winutil="WPFToggleS3Sleep",
         name="Usar el reposo S3 clásico",
         desc="Pone PlatformAoAcOverride=0 en HKLM\\SYSTEM\\CurrentControlSet\\Control\\"
              "Power. Fuerza el modelo de reposo clásico (S3) en equipos que soportan "
              "reposo moderno (S0). Cambia cómo duerme el equipo y puede afectar a la "
              "reanudación en portátiles modernos, por eso el riesgo no es Safe.",
         risk="Medium", security="Neutral",
         build_note="el valor existe en 19045 y en las tres de Windows 11 a partir de 2004"),
    dict(id="system.time.utc-rtc", winutil="WPFTweaksUTC",
         name="Guardar el reloj del hardware en UTC",
         desc="Pone RealTimeIsUniversal=1 (QWord) en HKLM\\SYSTEM\\CurrentControlSet\\"
              "Control\\TimeZoneInformation. Windows pasa a interpretar el reloj de la "
              "placa como UTC, que es lo que esperan Linux y otros sistemas en un equipo "
              "con arranque dual. En un equipo de un solo sistema no hace falta.",
         risk="Low", security="Neutral",
         build_note="valor documentado y presente en 19045 y en Windows 11"),
    dict(id="system.registry-backup.enable", winutil="WPFFeatureRegBackup",
         feature=True, task=True,
         name="Reactivar la copia de seguridad diaria del registro",
         desc="Pone EnablePeriodicBackup=1 y BackupCount=2 en HKLM\\SYSTEM\\"
              "CurrentControlSet\\Control\\Session Manager\\Configuration Manager, que es "
              "lo que Microsoft desactivó por defecto en Windows 10 1803, y crea la tarea "
              "programada AutoRegBackup que ejecuta `schtasks /run /i /tn "
              "\\Microsoft\\Windows\\Registry\\RegIdleBackup` todos los días a las 00:30 "
              "como SYSTEM (paso 11). Deshacer: se restauran los dos valores previos y se "
              "BORRA la tarea creada; si ya existía, se devuelve a su estado anterior en "
              "vez de borrarla.",
         # R3 (paso 12): la capacidad instala una tarea que se ejecuta como SYSTEM
         # con privilegios altos. Eso no puede declararse `Safe` ni sin
         # confirmacion: minimo Risk=Low y Confirmation=SimpleClick, aunque los dos
         # valores de registro por si solos serian inofensivos.
         risk="Low", security="Improves",
         r2_reason=(
             "MEJORA la capacidad de recuperacion: con la copia periodica del registro "
             "activa hay una copia diaria que Windows no tenia desde 1803, y una clave "
             "danada deja de ser una reinstalacion. No reduce ninguna proteccion."),
         r3_reason=(
             "crea la tarea programada AutoRegBackup que se ejecuta como SYSTEM con "
             "privilegios altos (config/feature.json WPFFeatureRegBackup: "
             "Register-ScheduledTask -User 'System'; reg_backup_task_actions lee "
             "UserId='System', RunLevel='Highest'). R3 exige minimo Risk=Low y "
             "Confirmation=SimpleClick para cualquier capacidad que instale algo "
             "persistente con privilegios altos; con Risk=Safe seria None."),
         r1_gap=(
             "la tarea del pin se registra SIN `-RunLevel`: "
             "`Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "
             "'AutoRegBackup' -Description 'Create System Registry Backups' -User 'System'` "
             "(config/feature.json, WPFFeatureRegBackup), es decir con el nivel por "
             "defecto (Limited). La capacidad la declara con RunLevel=Highest porque sin "
             "nivel elevado la tarea no puede leer HKLM, y eso es una desviacion MEDIDA "
             "del pin, no una copia. Se suman dos efectos del script que la capacidad no "
             "declara: el `-Argument '/run /i /tn ...'` con `/i`, que hace que `schtasks` "
             "dispare la copia al crear la tarea, y que el pin no comprueba si "
             "RegIdleBackup existe. Por eso State=Specified."),
         build_note="los valores son los mismos desde 1803; la tarea existe en todas"),
    dict(id="system.services.manual-profile", winutil="WPFTweaksServices", services=True,
         name="Pasar a manual o desactivar los servicios del perfil de WinUtil",
         desc="Ajusta el tipo de inicio de cinco servicios: CscService (Desactivado), "
              "DiagTrack (Desactivado), MapsBroker (Manual), StorSvc (Manual) y "
              "SharedAccess (Manual). Desactivar DiagTrack reduce la telemetría; "
              "desactivar CscService quita el cliente de archivos sin conexión y "
              "SharedAccess en Manual puede impedir compartir la conexión a Internet. Se "
              "puede deshacer porque el motor guarda el tipo de inicio previo.",
         risk="Low", security="Improves",
         r2_reason=(
             "MEJORA la privacidad y la superficie de ataque: desactivar DiagTrack corta "
             "la telemetria de diagnostico y deja tres servicios que no se pueden "
             "arrancar por si solos (CscService y SharedAccess en Desactivado). El coste "
             "se declara en la descripcion: se pierde el cliente de archivos sin conexion "
             "y puede romperse el uso compartido de conexion."),
         build_note="los cinco servicios existen en 19045 y en Windows 11"),
    dict(id="system.search-indexing.disable", winutil="WPFTweaksDisableSearchIndexing",
         services=True,
         name="Desactivar la indización de búsqueda de Windows",
         desc="Pone el servicio WSearch en Desactivado y lo detiene si estaba corriendo. "
              "La búsqueda del Explorador y del menú Inicio deja de usar el índice y "
              "pasa a recorrer las carpetas: menos actividad de disco en reposo y "
              "resultados más lentos en bibliotecas grandes.",
         risk="Low", security="Neutral",
         stop_service=True,
         build_note="WSearch existe en 19045 y en Windows 11"),
]

WINUTIL_REGISTRY_SPECS = [
    dict(id="system.tray.battery-percentage",
         winutil_tweak="WPFToggleBatteryPercentage",
         inventario_linea=278,
         name="Mostrar el porcentaje de bateria en la bandeja del sistema",
         desc="Pone IsBatteryPercentageEnabled=1 en HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced (DWord), como el tweak WPFToggleBatteryPercentage de WinUtil. Muestra el porcentaje numerico de bateria junto al icono de bateria en la bandeja del sistema. Reversible.",
         risk="Safe", security="Neutral",
         build_note="la clave existe en 19045 y Windows 11"),
]

ATLAS_TOGGLE_SPECS = [
    dict(id="system.hibernation.hide", atlas_toggle=("General/Hibernation.psd1", "Disable"),
         name="Ocultar la opción Hibernar del menú de energía",
         desc="Pone ShowHibernateOption=0 en HKLM\\SOFTWARE\\Microsoft\\Windows\\"
              "CurrentVersion\\Explorer\\FlyoutMenuSettings: la entrada «Hibernar» deja "
              "de aparecer en el menú de energía.",
         risk="Low", security="Neutral",
         r1_gap=(
             "el pin declara ademas MachineAction Set-AtlasHibernationPowerState "
             "(General/Hibernation.psd1:15 y :25), que ejecuta "
             "`powercfg /h off` y `powercfg /h on` (Hibernation.ps1): apaga o enciende la "
             "HIBERNACION de verdad, no solo la entrada del menu. Es un cambio que "
             "PERSISTE (hiberfil.sys desaparece o vuelve) y el motor no tiene accion de "
             "energia, asi que no se declara. Ocultar la opcion del menu y desactivar la "
             "hibernacion son dos efectos distintos: por eso State=Specified."),
         builds=[22631, 26100, 26200],
         build_note="la clave FlyoutMenuSettings (menú de energía de Windows 11) existe "
                    "desde 22631; en 19045 Windows no la lee y la entrada del menú no "
                    "cambia, por eso NO se declara 19045"),
    dict(id="system.location.consent-deny", atlas_toggle=("General/Location.psd1", "Disable"),
         location_services=True,
         name="Denegar el acceso a la ubicación",
         desc="Pone Value='Deny' en el ConsentStore de ubicación (HKLM) y "
              "ShowGlobalPrompts=0 en el mismo ConsentStore del usuario, y APAGA los dos "
              "servicios de ubicación: lfsvc y MapsBroker pasan a Desactivado y se "
              "detienen (paso 11). Quita el permiso global de ubicación: las aplicaciones "
              "dejan de poder pedirla. Deshacer: valores previos y, para cada servicio, "
              "tipo de inicio y estado de ejecución anteriores.",
         risk="Low", security="Improves",
         r2_reason=(
             "MEJORA la privacidad: sin el consentimiento global ninguna aplicacion "
             "puede pedir la ubicacion, y los dos servicios que la sirven quedan "
             "desactivados y detenidos. No reduce ninguna proteccion de seguridad: quita "
             "una capacidad del sistema, no una defensa."),
         r1_gap=(
             "el pin declara ademas MachineAction Disable-AtlasLocation "
             "(General/Location.psd1:6) y ese script, ADEMAS de los dos servicios ya "
             "declarados, escribe la politica de Buscar mi dispositivo: "
             "AllowFindMyDevice=0 y LocationSyncEnabled=0 bajo "
             "HKLM\\SOFTWARE\\Policies\\Microsoft\\FindMyDevice "
             "(Atlas.Privacy/Domain/Location.ps1:8, :116-119) y oculta las paginas "
             "privacy-location y findmydevice (:122-123). Son valores que PERSISTEN y no "
             "se declaran: la politica de Find My Device no es 'denegar la ubicacion' y "
             "ocultar paginas de Configuracion es otro efecto. Por eso State=Specified."),
         build_note="ConsentStore de ubicación presente en 19045 y en Windows 11"),
    dict(id="system.mitigations.disable", atlas_toggle=("Security/Mitigations.psd1", "Disable"),
         name="Desactivar las mitigaciones del kernel",
         desc="Escribe FeatureSettingsOverride=3, FeatureSettingsOverrideMask=3, "
              "DisableExceptionChainValidation=1 y ProtectionMode=0 bajo HKLM\\SYSTEM: "
              "desactiva mitigaciones del kernel (SEHOP, validación del árbol de "
              "excepciones) para ganar rendimiento. REDUCE de forma real la protección "
              "frente a exploits y exige reinicio; por eso el riesgo es High y la "
              "confirmación pide resumen y punto de restauración.",
         risk="High", security="Reduces",
         r1_gap=(
             "el pin declara ademas MachineAction Disable-AtlasMitigations "
             "(Security/Mitigations.psd1:21), que hace tres cosas que no son valores de "
             "registro y no se declaran: `Set-ProcessMitigation -System -Disable CFG` "
             "sobre la proteccion de flujo de control del sistema y `-Enable CFG` sobre "
             "valorant, valorant-win64-shipping, vgtray y vgc (Mitigations.ps1:48-53), y "
             "`bcdedit /set nx OptIn`, que cambia el arranque (Mitigations.ps1:54-56). "
             "Las dos ultimas escriben el binario MitigationOptions/"
             "MitigationAuditOptions con un relleno 0x22 (Mitigations.ps1:57), que si "
             "esta declarado si el pin lo escribiera en el .psd1, pero aqui lo escribe el "
             "script, con un tamano que depende de lo que haya. Por eso State=Specified."),
         build_note="los cuatro valores existen en 19045 y en Windows 11"),
    dict(id="system.keyboard-shortcuts.disable", atlas_toggle=("Interface/KeyboardShortcuts.psd1",
                                                              "Disable"),
         name="Desactivar los atajos de cambio de idioma del teclado",
         desc="Pone Hotkey='3', 'Language Hotkey'='3' y 'Layout Hotkey'='3' en "
              "HKCU\\Keyboard Layout\\Toggle. Desactiva Alt+Shift y Ctrl+Shift para "
              "cambiar de idioma o de distribución; Win+Space y el resto de métodos de "
              "entrada siguen funcionando. Atlas requiere cerrar sesión para que el "
              "cambio se note; el motor no puede forzarlo.",
         risk="Safe", security="Neutral",
         build_note="la clave Keyboard Layout\\Toggle existe en 19045 y en Windows 11",
         extra_ledgers=["atlas:manifest:qol/set-keyboard-switching"]),
]

ATLAS_TWEAK_SPECS = [
    dict(id="system.error-reporting.crash-control", atlas_tweak="qol/system/crash-control-qol.psd1",
         name="Configurar el control de fallos (pantalla azul y volcados)",
         desc="Deja la pantalla azul en pantalla sin reiniciar (AutoReboot=0), fija un "
              "volcado pequeño de 256 KiB (CrashDumpEnabled=3), conserva el registro del "
              "evento (LogEvent=1), muestra los parámetros del fallo (DisplayParameters=1) "
              "y apaga el volcado de StorageTelemetry. REDUCE el diagnóstico: sigue "
              "quedando un minidump analizable, pero ya no hay volcado completo de memoria "
              "y el equipo se queda detenido en la pantalla azul hasta que alguien lo "
              "reinicie.",
         risk="Medium", security="Reduces",
         build_note="CrashControl existe en 19045 y en Windows 11; el volcado pequeño "
                    "es el modo 3 desde Windows 8"),
    dict(id="system.error-reporting.wpbt-disable", atlas_tweak="qol/system/disable-wpbt.psd1",
         name="Impedir la ejecución del programa WPBT del firmware",
         desc="Pone DisableWpbtExecution=1 en HKLM\\SYSTEM\\CurrentControlSet\\Control\\"
              "Session Manager. WPBT permite que el firmware ejecute un binario en cada "
              "arranque; el propio pin avisa de que Microsoft no documenta este valor. "
              "Evita software OEM que se reinstala solo, a costa de una función del "
              "firmware: se declara Medium porque cambia el arranque, no Safe.",
         risk="Medium", security="Improves",
         r2_reason=(
             "MEJORA la seguridad: WPBT permite que el firmware ejecute un binario en "
             "cada arranque, y es el mecanismo con el que el software OEM se reinstala "
             "solo despues de que el usuario lo quite. Bloquearlo cierra esa via de "
             "persistencia; el coste (una funcion del firmware) esta en la descripcion y "
             "es la razon de que el riesgo sea Medium."),
         build_note="el valor se lee en el arranque de 19045 y de Windows 11"),
    dict(id="system.menu-delay.disable", atlas_tweak="qol/shell/disable-menu-delay.psd1",
         name="Quitar el retardo de los submenús",
         desc="Pone MenuShowDelay='0' en HKCU\\Control Panel\\Desktop: los submenús se "
              "abren en cuanto el puntero se posa sobre ellos, sin la espera por defecto. "
              "Sólo afecta a la respuesta visual del menú de la sesión.",
         risk="Safe", security="Neutral",
         build_note="MenuShowDelay existe en 19045 y en Windows 11"),
    dict(id="system.time.ntp-servers", atlas_tweak="misc/config-time.psd1",
         ntp_service=True,
         name="Usar los servidores de hora de pool.ntp.org",
         desc="Escribe NtpServer='0.pool.ntp.org 1.pool.ntp.org 2.pool.ntp.org "
              "3.pool.ntp.org' y Type='NTP' en HKLM\\SYSTEM\\CurrentControlSet\\Services\\"
              "W32Time\\Parameters y declara el arranque del servicio w32time (paso 11). "
              "FUERA DE ESTA CAPACIDAD (R1): el pin además ejecuta `w32tm /config /update` y "
              "`w32tm /resync` (config-time.psd1:9-10, bloque `Run`), comandos sin inversa "
              "para los que el motor no tiene acción equivalente (no son registro, servicio "
              "ni tarea); por regla R1 esos comandos quedan fuera de esta capacidad y no se "
              "expresan como acción del catálogo, por lo que la capacidad es Specified y no "
              "Implemented. Los valores de registro y el estado previo de ejecución del "
              "servicio w32time se restauran al deshacer.",
         risk="Low", security="Neutral", state="Specified",
         r1_gap="el pin ejecuta `w32tm /config /update` y `w32tm /resync` "
         "(config-time.psd1:9-10, bloque `Run`), comandos sin inversa para los que el "
         "motor no tiene acción equivalente; R1 (paso 12): quedan fuera de esta capacidad.",
         build_note="W32Time\\Parameters existe en 19045 y en Windows 11"),


    dict(id="system.oem-information.identify", atlas_tweak="misc/config-oem-information.psd1",
         name="Escribir la información OEM del sistema",
         desc="Escribe Manufacturer, SupportURL y SupportPhone en HKLM\\SOFTWARE\\"
              "Microsoft\\Windows\\CurrentVersion\\OEMInformation, los tres valores que "
              "Windows muestra en Información del sistema. Los literales son los del pin "
              "(atribución de Atlas), no una identidad inventada para EVO.",
         risk="Safe", security="Neutral",
         r1_gap="ejecuta `config-oem-information.ps1` (config-oem-information.psd1, "
         "bloque `Script`) que rellena valores dinámicos (versión/modelo de Atlas) no "
         "expresados como acción",
         build_note="OEMInformation existe en 19045 y en Windows 11"),


]

# Capacidades que salen de un `.psd1` de `Scripts/Tweaks/` con una unica entrada
# `Operation = 'AddKey'` (paso 12): crear una clave VACIA es un efecto propio
# —apaga el asistente de ubicacion de red— y el motor ya sabe hacerlo con
# `registryCreateKey`, con deshacer (se borra lo creado). Antes se declaraban
# como hueco; ahora se declaran.
ADDKEY_SPECS = [
    dict(id="system.network.location-wizard.disable",
         atlas_tweak="qol/shell/disable-network-location-wizard.psd1",
         name="Apagar el asistente de ubicacion de red",
         desc="Crea la clave HKLM\\SYSTEM\\CurrentControlSet\\Control\\Network\\"
              "NewNetworkWindowOff. Windows muestra su asistente de ubicacion de red "
              "(el cuadro que pregunta si el equipo debe ser reconocible en una red "
              "nueva) cuando esa clave NO existe; con la clave creada el asistente deja "
              "de aparecer y la red se trata como publica. El pin NO escribe ningun "
              "valor dentro: la clave va vacia. Deshacer: se BORRA la clave creada; si "
              "ya existia, no se toca nada (la accion es un no-op y no se apunta).",
         risk="Low", security="Neutral",
         build_note="NewNetworkWindowOff se lee en 19045 y en Windows 11"),
]

# Capacidad que no sale de un bloque `Registry` sino de un script con clave y
# valor literales: se leen del pin las dos líneas y se comprueba la forma.
STATIC_SCRIPT_SPECS = [
    dict(id="system.settings-page-visibility.hide",
         script="qol/set-hidden-settings-pages.ps1",
         name="Ocultar las páginas de Configuración que Atlas considera rotas",
         desc="Escribe SettingsPageVisibility='hide:recovery;maps;maps-downloadmaps;"
              "privacy;privacy-feedback;privacy-activityhistory;search-permissions;"
              "privacy-general;sync;mobile-devices;mobile-devices-addphone;workplace;"
              "family-group;deviceusage;home' en HKLM\\SOFTWARE\\Microsoft\\Windows\\"
              "CurrentVersion\\Policies\\Explorer. Muchas de esas páginas son las que "
              "usan los ajustes de privacidad: ocultarlas también las hace más difíciles "
              "de encontrar. El valor del pin es una lista COMPLETA: sobrescribe la que "
              "el usuario tuviera, no la amplía (a diferencia de la ayuda incremental de "
              "Atlas, que edita una página por vez). Se puede deshacer porque el motor "
              "guarda el valor previo.",
         risk="Low", security="Neutral",
         build_note="la directiva SettingsPageVisibility existe en 19045 y en Windows 11"),
]


def winutil_registry_actions(tweak: str) -> list[dict]:
    entry = W_TWEAKS.get(tweak)
    if entry is None:
        raise SystemExit(f"el tweak {tweak} no existe en el pin de WinUtil")
    actions = []
    for order, item in enumerate(entry.get("registry") or [], start=1):
        hive, key = b10.split_path(item["Path"])
        actions.append({
            "type": "registry",
            "order": order,
            "description": f"{item['Name']} en {hive}",
            "hive": HIVES[hive],
            "keyPath": key,
            "valueName": item["Name"],
            "value": str(item["Value"]),
            "valueType": item.get("Type", "DWord"),
            "operation": "Set",
        })
    return actions


def winutil_service_actions(tweak: str) -> list[dict]:
    entry = W_TWEAKS.get(tweak)
    if entry is None:
        raise SystemExit(f"el tweak {tweak} no existe en el pin de WinUtil")
    actions = []
    for order, item in enumerate(entry.get("service") or [], start=1):
        actions.append({
            "type": "service",
            "order": order,
            "description": f"{item['Name']} -> {item['StartupType']}",
            "serviceName": item["Name"],
            "operation": "SetStartupType",
            "startupType": item["StartupType"],
        })
    if not actions:
        raise SystemExit(f"el tweak {tweak} no declara servicios en el pin")
    return actions


def stop_service_action(service_name: str, order: int) -> dict:
    """ServiceAction Stop del servicio, con el orden que le toque."""
    return {
        "type": "service",
        "order": order,
        "description": f"{service_name} -> Detener",
        "serviceName": service_name,
        "operation": "Stop",
    }


def script_props(script: str) -> list[dict]:
    """Valores de `New-ItemProperty … -Name 'X' -Type T -Value V` del pin.

    Sólo se aceptan literales (comillas simples y número entero o 'DWord'): si
    aparece una variable en el valor, el script falla en vez de inventar.
    """
    pattern = re.compile(
        r"New-ItemProperty\s+-Path\s+'(HK[A-Z]+):\\\\?([^']+)'\s+"
        r"-Name\s+'([^']+)'\s+-Type\s+(\w+)\s+-Value\s+('[^']*'|\d+)")
    found = []
    for match in pattern.finditer(script):
        hive, key, name, kind, raw = match.groups()
        value = raw[1:-1] if raw.startswith("'") else raw
        found.append({"hive": HIVES[hive], "keyPath": key, "valueName": name,
                      "valueType": kind, "value": value})
    if not found:
        raise SystemExit("el script del pin no declara New-ItemProperty literales")
    return found


def static_script_pair(script: str) -> tuple[str, str, str]:
    """($key de HKLM, $value, ruta relativa) de un script con ambos literales."""
    path = ATLAS_TWEAKS / script
    text = path.read_text(encoding="utf-8", errors="replace")
    key = re.search(r"^\$key\s*=\s*'(HKLM:\\[^']+)'", text, re.M)
    value = re.search(r"^\$value\s*=\s*'([^']+)'", text, re.M)
    if not key or not value:
        raise SystemExit(f"{script}: no se encontraron $key y $value literales en el pin")
    return key.group(1), value.group(1), str(path.relative_to(UPSTREAM / "atlas"))


def line_of(script: str, needle: str) -> int:
    path = ATLAS_TWEAKS / script
    return b10.rel_line(path, needle)


def reg_backup_task_actions() -> list[dict]:
    """Tarea AutoRegBackup tal como la registra el pin (paso 11).

    Los literales (nombre, ejecutable, argumentos, hora, usuario) se leen del
    `InvokeScript` de `feature.json`: `New-ScheduledTaskAction -Execute 'schtasks'
    -Argument '/run /i /tn "\\Microsoft\\Windows\\Registry\\RegIdleBackup"'`,
    `New-ScheduledTaskTrigger -Daily -At 00:30` y
    `Register-ScheduledTask -TaskName 'AutoRegBackup' … -User 'System'`.
    `RunLevel=Highest` porque el pin registra la tarea como SYSTEM.
    """
    entry = W_FEATURES.get("WPFFeatureRegBackup") or {}
    script = entry.get("InvokeScript") or []
    script = script[0] if isinstance(script, list) and script else str(script)
    name = re.search(r"-TaskName\s+'([^']+)'", script)
    execute = re.search(r"New-ScheduledTaskAction\s+-Execute\s+'([^']+)'", script)
    arguments = re.search(r"-Argument\s+'([^']*)'", script)
    at = re.search(r"New-ScheduledTaskTrigger\s+-Daily\s+-At\s+([0-9:]+)", script)
    user = re.search(r"-User\s+'([^']+)'", script)
    description = re.search(r"-Description\s+'([^']+)'", script)
    if not (name and execute and arguments and at and user):
        raise SystemExit("feature.json: no se pudo leer la tarea AutoRegBackup del pin")
    return [{
        "type": "taskCreate",
        "order": 3,
        "description": f"Crear la tarea {name.group(1)} (diaria a las {at.group(1)})",
        "taskPath": "\\",
        "taskName": name.group(1),
        "execute": execute.group(1),
        "arguments": arguments.group(1).replace('\\"', '"'),
        "trigger": "Daily",
        "triggerAt": at.group(1).zfill(5),
        "userId": user.group(1),
        "runLevel": "Highest",
        "taskDescription": description.group(1) if description else "",
        "overwrite": False,
    }]


#: Servicios que el pin apaga con `Invoke-AtlasLocationServiceState` (Location.ps1:
#: `Set-Service -StartupType Disabled` + `Stop()`), con el tipo de inicio y el
#: estado que aplica el estado 'Disable' (StartupType 4 y Status 'Stopped').
LOCATION_SERVICES = ("lfsvc", "MapsBroker")


def location_service_actions(start_order: int) -> list[dict]:
    """Para cada servicio: parar PRIMERO y deshabilitar después.

    El orden importa por el deshacer LIFO del motor: al revertir se deshace en
    orden inverso, así que el tipo de inicio se devuelve ANTES de que se intente
    arrancar el servicio otra vez. Si se declarara al revés (Disabled y luego
    Stop), el rollback arrancaría un servicio todavía deshabilitado y Windows
    fallaría con ERROR_SERVICE_DISABLED. Se aplica igual que el pin: el efecto
    final (parado y deshabilitado) es el mismo.
    """
    actions = []
    for name in LOCATION_SERVICES:
        actions.append({
            "type": "service",
            "order": start_order,
            "description": f"{name}: detener",
            "serviceName": name,
            "operation": "Stop",
        })
        actions.append({
            "type": "service",
            "order": start_order + 1,
            "description": f"{name} -> Disabled",
            "serviceName": name,
            "operation": "SetStartupType",
            "startupType": "Disabled",
        })
        start_order += 2
    return actions


def ntp_service_actions(order: int) -> list[dict]:
    """`Services = @(@{ Name='w32time'; Operation='Start' })` del pin."""
    return [{
        "type": "service",
        "order": order,
        "description": "w32time: iniciar",
        "serviceName": "w32time",
        "operation": "Start",
    }]


ATLAS_PRIVACY_LOCATION = (
    "package/Executables/AtlasModules/Scripts/Modules/Atlas.Privacy/Domain/Location.ps1")


def location_machine_action_line() -> int:
    """Linea del `MachineAction` del estado 'Disable' en el toggle del pin."""
    path = ATLAS_TOGGLES / "General" / "Location.psd1"
    text = path.read_text(encoding="utf-8", errors="replace")
    start = text.find("Name          = 'Disable'")
    index = text.find("MachineAction", max(start, 0))
    return 0 if index < 0 else text.count("\n", 0, index) + 1


def location_service_evidence() -> tuple[int, int, int]:
    """Lineas del pin que demuestran el cambio de servicio (ruta:linea)."""
    path = UPSTREAM / "atlas" / ATLAS_PRIVACY_LOCATION
    text = path.read_text(encoding="utf-8", errors="replace")

    def line_of(needle: str) -> int:
        index = text.find(needle)
        return 0 if index < 0 else text.count("\n", 0, index) + 1

    return (line_of("function Set-AtlasLocationMachineState"),
            line_of("Invoke-AtlasLocationServiceState -Name lfsvc"),
            line_of("Invoke-AtlasLocationServiceState -Name MapsBroker"))


def base(cap_id: str, name: str, desc: str, risk: str, security: str,
         actions: list[dict], builds: list[int] | None, state: str,
         variants: list[str], provenance: str,
         r2_reason: str | None = None, r3_reason: str | None = None) -> dict:
    # R2 (paso 12): `Improves` exige la justificacion ESCRITA en la description.
    # El enum no basta: quien audita tiene que poder leer por que mejora sin
    # abrir el codigo del generador.
    if security == "Improves":
        if not r2_reason:
            raise SystemExit(
                f"{cap_id}: SecurityImpact=Improves exige r2_reason (regla R2 del paso 12)")
        desc = desc.rstrip() + " Por que mejora la seguridad: " + r2_reason
        provenance = provenance.rstrip() + " R2 (paso 12): SecurityImpact=Improves por: " + r2_reason
    # R3 (paso 12): lo que instala algo persistente con privilegios altos no
    # puede ser Safe (ni quedar sin confirmacion). Se comprueba, no se supone.
    if any(a["type"] == "taskCreate" for a in actions):
        if risk == "Safe" or risk == "Low" and r3_reason is None:
            raise SystemExit(
                f"{cap_id}: instala una tarea programada y R3 exige Risk>=Low con motivo")
        if not r3_reason:
            raise SystemExit(f"{cap_id}: R3 exige r3_reason escrito en la provenance")
        provenance = provenance.rstrip() + " R3 (paso 12): Risk=Low y Confirmation=SimpleClick por: " + r3_reason
    return {
        "id": cap_id,
        "name": name,
        "description": desc,
        "sectionId": 9,
        "risk": risk,
        "securityImpact": security,
        # Un servicio se cambia con elevación aunque no haya registro de por medio.
        "privilege": "Admin" if any(a["type"] == "service"
                                    or a.get("hive") in ("LocalMachine", "Users")
                                    for a in actions) else "User",
        "restore": RESTORE[risk],
        "reversibility": "Reversible",
        "confirmation": CONFIRM[risk],
        "state": state,
        "variants": variants,
        "conflictsWith": [],
        "dependsOn": [],
        "supportedBuilds": builds or DEFAULT_BUILDS,
        "provenance": provenance,
        "actions": actions,
    }


def build() -> dict:
    capabilities: list[dict] = []

    # ------------------------------------------------------------------ WinUtil
    for spec in WINUTIL_SPECS:
        if spec.get("feature"):
            entry = W_FEATURES.get(spec["winutil"])
            if entry is None:
                raise SystemExit(f"la entrada {spec['winutil']} no existe en feature.json")
            script = entry.get("InvokeScript") or []
            script = script[0] if isinstance(script, list) and script else str(script)
            values = script_props(script)
            actions = [
                {"type": "registry", "order": i, "description": f"{v['valueName']} en HKLM",
                 "hive": v["hive"], "keyPath": v["keyPath"], "valueName": v["valueName"],
                 "value": v["value"], "valueType": v["valueType"], "operation": "Set"}
                for i, v in enumerate(values, start=1)
            ]
            ledger = f"winutil:feature:{spec['winutil']}"
            task_note = ""
            if spec.get("task"):
                # Paso 11: la tarea se declara como TaskCreateAction, con los
                # literales leidos del propio InvokeScript del pin.
                task_actions = reg_backup_task_actions()
                for offset, task_action in enumerate(task_actions):
                    task_action["order"] = len(actions) + 1 + offset
                actions = actions + task_actions
                tarea = task_actions[0]
                task_note = (
                    " El pin ADEMAS registra la tarea programada "
                    f"{tarea['taskName']} con Register-ScheduledTask (paso 11): se declara "
                    "como accion taskCreate con los literales del InvokeScript "
                    f"(execute={tarea['execute']!r}, arguments={tarea['arguments']!r}, "
                    f"trigger={tarea['trigger']} a las {tarea['triggerAt']}, "
                    f"userId={tarea['userId']!r}, runLevel={tarea['runLevel']}). "
                    "Deshacer: se borra la tarea creada; si ya existia, se restaura su "
                    "estado previo (no se borra). "
                    "Reversibilidad (ADR-0003): Reversible - valores de registro con valor "
                    "previo guardado por el motor + tarea creada que se elimina."
                )
            provenance = (
                f"{WINUTIL_PIN}:config/feature.json#{spec['winutil']} (Type="
                f"{entry.get('Type') or 'sin Type'}). Literales leidos de InvokeScript: "
                + "; ".join(
                    f"{a['valueName']}={a['value']}" if a["type"] == "registry"
                    else f"taskCreate {a['taskName']} ({a['trigger']} {a.get('triggerAt') or ''})".strip()
                    for a in actions)
                + "." + task_note
                + ("" if task_note else
                   " Reversibilidad (ADR-0003): Reversible - valores de registro con valor "
                   "previo guardado por el motor. ")
                + f" Builds: {spec['build_note']}. ledger_refs: {ledger}"
            )
        elif spec.get("services"):
            actions = winutil_service_actions(spec["winutil"])
            if spec.get("stop_service"):
                # Paso 12 (R1): el pin PARA el servicio en su InvokeScript, y solo
                # cambiar el arranque no lo detiene. ServiceAction Stop es la
                # operacion equivalente (el diario guarda el estado previo).
                #
                # ORDEN (ADR-0005 4-bis): primero `Stop` y DESPUES el tipo de
                # inicio, igual que hace el pin (`Stop-Service` y luego
                # `Set-Service -StartupType Disabled`). El diario se deshace en
                # LIFO: asi el deshacer devuelve el arranque ANTES de arrancar el
                # servicio. Al reves, el rollback intenta arrancar un servicio
                # aun deshabilitado y falla con 1058.
                final: list[dict] = []
                for index, action in enumerate(actions):
                    final.append(stop_service_action(action["serviceName"], 2 * index + 1))
                    final.append(dict(action, order=2 * index + 2))
                actions = final
            provenance = (
                f"{WINUTIL_PIN}:config/tweaks.json#{spec['winutil']}. Servicios y tipos de "
                "inicio tomados de la fuente: "
                + "; ".join(
                    (f"{a['serviceName']}={a['startupType']}" if a["operation"] == "SetStartupType"
                     else f"{a['serviceName']}=Stop")
                    for a in actions)
                + ". Semantica: `StartupType` es lo que WinUtil aplica y `OriginalType` lo "
                  "que restaura su propio deshacer; el motor guarda el tipo previo. "
                  "Reversibilidad (ADR-0003): Reversible - el motor registra el tipo de "
                  "inicio anterior de cada servicio y lo devuelve al deshacer. "
                + f"Builds: {spec['build_note']}. "
                + f"ledger_refs: winutil:tweak:{spec['winutil']}, "
                  "winutil:tweak-op:WPFTweaksServices:service:0"
            )
        else:
            actions = winutil_registry_actions(spec["winutil"])
            entry = W_TWEAKS[spec["winutil"]]
            values = "; ".join(f"{a['valueName']}={a['value']}" for a in actions)
            provenance = (
                f"{WINUTIL_PIN}:config/tweaks.json#{spec['winutil']} (Type="
                f"{entry.get('Type') or 'sin Type'}). Valores tomados de la fuente: "
                f"{values}. Semantica: en un Toggle de WinUtil `Value` es el valor que se "
                "escribe y `OriginalValue` el que restaura su deshacer "
                "(functions/private/Invoke-WinUtilTweaks.ps1:34-46). "
                "Reversibilidad (ADR-0003): Reversible - valores de registro con valor "
                "previo guardado por el motor. "
                + ("Privilegio Admin por escribir en HKLM. "
                   if any(a["hive"] == "LocalMachine" for a in actions) else "")
                + f"Builds: {spec['build_note']}. "
                + f"ledger_refs: winutil:tweak:{spec['winutil']}"
            )
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"], spec["risk"], spec["security"],
            actions, spec.get("builds"), spec.get("state", "Implemented"),
            ["Evo", "WinUtil"], provenance,
            r2_reason=spec.get("r2_reason"), r3_reason=spec.get("r3_reason")))

    # ------------------------------------------------------- Atlas (Toggles)
    for spec in ATLAS_TOGGLE_SPECS:
        relative, state = spec["atlas_toggle"]
        actions, skipped, source = b10.atlas_actions(relative, state)
        # La línea del pin va en la provenance, no en la acción: el contrato de
        # `RegistryAction` es cerrado y no tiene ese campo (lo rechazaría el
        # cargador estricto si se colara como propiedad desconocida).
        lines = sorted({a["line"] for a in actions if a.get("line")}) or [0]
        for action in actions:
            action.pop("line", None)
        if lines == [0]:
            # Los toggles se trocean por estado y el parser no conserva la linea:
            # se cita la linea del bloque `Registry` del estado en el pin.
            located = b10.rel_line(ATLAS_TOGGLES / relative, "Registry")
            lines = [located] if located else [0]
        refs = f"{source}:{lines[0]}" + (f"-{lines[-1]}" if len(lines) > 1 else "")
        blocked = ""
        if skipped:
            blocked = (" No expresable como RegistryAction y por tanto NO aplicado: "
                       + ", ".join(skipped) + " (el motor solo borra valores, no claves).")
        ledgers = [f"atlas:toggle:{Path(relative).stem}"] + spec.get("extra_ledgers", [])
        service_note = ""
        registry_actions = list(actions)
        if spec.get("location_services"):
            actions = actions + location_service_actions(len(actions) + 1)
            machine_line, lfsvc_line, maps_line = location_service_evidence()
            service_note = (
                " El pin ADEMAS ejecuta MachineAction Disable-AtlasLocation "
                f"(Toggles/General/Location.psd1:{location_machine_action_line()}), que llama "
                "a Set-AtlasLocationMachineState (Atlas.Privacy/Domain/Location.ps1:"
                f"{machine_line}) y esta MEDIDO como `Invoke-AtlasLocationServiceState -Name "
                f"lfsvc` / `-Name MapsBroker` ahi mismo "
                f"({ATLAS_PRIVACY_LOCATION}:{lfsvc_line} y "
                f"{ATLAS_PRIVACY_LOCATION}:{maps_line}) → "
                "`Set-Service -StartupType Disabled` + `$service.Stop()` (StartupType 4 y "
                "Status 'Stopped'): el tipo de inicio y el estado de ejecucion SI son "
                "expresables con ServiceAction, asi que desde el paso 11 se declaran. NO se "
                "declara lo demas que hace ese script (politica de Find My Device y ocultar "
                "las paginas de Configuracion), que queda fuera de esta capacidad."
            )
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"], spec["risk"], spec["security"],
            actions, spec.get("builds"), spec.get("state", "Implemented"),
            ["Evo", "Atlas"],
            f"{ATLAS_PIN}:{refs} (estado '{state}'). Valores tomados del bloque Registry "
            "del pin: "
            + "; ".join(
                (f"{a['valueName'] or '(predeterminado)'}={a['value']}"
                 if a["operation"] == "Set" else f"{a['valueName']} (borrado)")
                for a in registry_actions)
            + "." + blocked + service_note
            + " Reversibilidad (ADR-0003): Reversible - valores de registro con valor "
              "previo guardado por el motor."
            + (" Servicios: el diario guarda tipo de inicio y estado de ejecucion "
               "previos de cada uno y los devuelve." if service_note else "")
            + f" Builds: {spec['build_note']}. "
            + "ledger_refs: " + ", ".join(ledgers),
            r2_reason=spec.get("r2_reason"), r3_reason=spec.get("r3_reason")))

    # ------------------------------------------------- Atlas (Scripts/Tweaks)
    for spec in ATLAS_TWEAK_SPECS:
        relative = f"Tweaks/{spec['atlas_tweak']}"
        actions, skipped, source = b10.atlas_actions(relative, None, create_key=True)
        # La línea del pin va en la provenance, no en la acción: el contrato de
        # `RegistryAction` es cerrado y no tiene ese campo (lo rechazaría el
        # cargador estricto si se colara como propiedad desconocida).
        lines = sorted({a["line"] for a in actions if a.get("line")}) or [0]
        for action in actions:
            action.pop("line", None)
        if lines == [0]:
            # Los toggles se trocean por estado y el parser no conserva la linea:
            # se cita la linea del bloque `Registry` del estado en el pin.
            located = b10.rel_line(ATLAS_TOGGLES / relative, "Registry")
            lines = [located] if located else [0]
        refs = f"{source}:{lines[0]}" + (f"-{lines[-1]}" if len(lines) > 1 else "")
        if skipped:
            raise SystemExit(f"{relative}: operaciones no expresables {skipped}")
        omit = spec.get("omit", "")
        service_note = ""
        if spec.get("ntp_service"):
            # `Services = @(@{ Name = 'w32time'; Operation = 'Start' })` del pin.
            actions = actions + ntp_service_actions(len(actions) + 1)
            service_note = (
                " El bloque Services del pin arranca w32time: se declara como "
                "ServiceAction Start (paso 11) y el diario devuelve el estado de "
                "ejecucion previo."
            )
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"], spec["risk"], spec["security"],
            actions, spec.get("builds"), spec.get("state", "Implemented"),
            ["Evo", "Atlas"],
            f"{ATLAS_PIN}:{refs}. Valores tomados del bloque Registry del pin: "
            + "; ".join(f"{a['valueName']}={a['value'] or '(cadena vacia)'}"
                        for a in actions if a["type"] == "registry")
            + "." + service_note
            + (f" El pin ADEMAS hace algo que NO se declara: {omit}. "
               "Queda declarado aqui y no se ejecuta: no hay promesa de deshacer para "
               "un comando." if omit else "")
            + " Reversibilidad (ADR-0003): Reversible - valores de registro con valor "
              "previo guardado por el motor."
            + (" Servicio: el diario guarda el estado de ejecucion previo y lo devuelve."
               if service_note else "")
            + f" Builds: {spec['build_note']}. "
            + "ledger_refs: atlas:manifest:"
            + spec["atlas_tweak"].replace(".psd1", ""),
            r2_reason=spec.get("r2_reason"), r3_reason=spec.get("r3_reason")))

    # --------------------------------------------- WinUtil (registro directo)
    for spec in WINUTIL_REGISTRY_SPECS:
        entry = W_TWEAKS[spec["winutil_tweak"]]
        reg = (entry.get("registry") or [])[0]
        hive, key_path = b10.split_path(reg["Path"])
        actions = [{
            "type": "registry", "order": 1,
            "description": f"{reg['Name']} en {hive}",
            "hive": HIVES[hive], "keyPath": key_path,
            "valueName": reg["Name"],
            "value": reg["Value"],
            "valueType": reg.get("Type", "String"),
            "operation": "Set",
        }]
        provenance = (
            f"{WINUTIL_PIN}:config/tweaks.json:{spec['winutil_tweak']}:registry:0. "
            f"Valor {reg['Value']} ({reg.get('Type','String')}) leido del pin. "
            f"Inventario seccion 9: linea {spec['inventario_linea']} (System Tray Battery Percentage). "
            f"ledger_refs: winutil:tweak:{spec['winutil_tweak']} "
            f"Reversibilidad (ADR-0003): el motor guarda el valor previo del valor de registro y lo restaura al deshacer."
        )
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"],
            spec["risk"], spec["security"], actions, None,
            "Implemented", ["Evo", "WinUtil"], provenance,
            r2_reason=spec.get("r2_reason")))

    # ------------------------------------------- Atlas (clave creada, AddKey)
    for spec in ADDKEY_SPECS:
        relative = f"Tweaks/{spec['atlas_tweak']}"
        actions, skipped, source = b10.atlas_actions(relative, None, create_key=True)
        lines = sorted({a["line"] for a in actions if a.get("line")}) or [0]
        for action in actions:
            action.pop("line", None)
        refs = f"{source}:{lines[0]}" + (f"-{lines[-1]}" if len(lines) > 1 else "")
        if skipped:
            raise SystemExit(f"{relative}: operaciones no expresables {skipped}")
        creadas = [a for a in actions if a["type"] == "registryCreateKey"]
        if len(creadas) != 1:
            raise SystemExit(f"{relative}: se esperaba una sola AddKey")
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"], spec["risk"], spec["security"],
            actions, spec.get("builds"), spec.get("state", "Implemented"),
            ["Evo", "Atlas"],
            f"{ATLAS_PIN}:{refs}. La entrada del pin es una operacion de CLAVE, no de "
            f"valor: `Operation = 'AddKey'` sobre {creadas[0]['hive']}\\"
            f"{creadas[0]['keyPath']}, sin Name ni Data, asi que se declara como "
            "registryCreateKey (paso 12) y la clave se crea VACIA. "
            "Reversibilidad (ADR-0003): Reversible - el motor solo crea la clave si NO "
            "existia y el diario apunta ese hecho; al deshacer la borra. Si ya existia, "
            "la accion es un no-op y el deshacer no toca nada (borrarla destruiria "
            "estado previo). "
            f"Builds: {spec['build_note']}. "
            "ledger_refs: atlas:manifest:"
            + spec["atlas_tweak"].removesuffix(".psd1"),
            r2_reason=spec.get("r2_reason"), r3_reason=spec.get("r3_reason")))

    # --------------------------------------------- Atlas (clave y valor fijos)
    for spec in STATIC_SCRIPT_SPECS:
        key, value, source = static_script_pair(spec["script"])
        hive, key_path = b10.split_path(key)
        actions = [{
            "type": "registry", "order": 1,
            "description": f"SettingsPageVisibility en {hive}",
            "hive": HIVES[hive], "keyPath": key_path,
            "valueName": "SettingsPageVisibility",
            "value": value, "valueType": "String", "operation": "Set",
        }]
        capabilities.append(base(
            spec["id"], spec["name"], spec["desc"], spec["risk"], spec["security"],
            actions, spec.get("builds"), "Implemented", ["Evo", "Atlas"],
            f"{ATLAS_PIN}:{source}:{line_of(spec['script'], '$value')} "
            f"(clave en la linea {line_of(spec['script'], '$key')}). "
            "Valor literal del pin: SettingsPageVisibility='" + value + "'. "
            "Reversibilidad (ADR-0003): Reversible - valores de registro con valor previo "
            "guardado por el motor. "
            f"Builds: {spec['build_note']}. "
            "ledger_refs: atlas:manifest:qol/set-hidden-settings-pages"))

    capabilities.sort(key=lambda c: c["id"])
    # R1 (paso 12): las capacidades cuyo pin hace algo mas que lo declarado pasan
    # a Specified y lo dicen en description Y provenance.
    gaps = {spec["id"]: spec.get("r1_gap")
            for spec in WINUTIL_SPECS + ATLAS_TOGGLE_SPECS + ATLAS_TWEAK_SPECS + WINUTIL_REGISTRY_SPECS
            + ADDKEY_SPECS}
    for capability in capabilities:
        gap = gaps.get(capability["id"])
        if gap:
            b10.apply_r1(capability, {"r1_gap": gap})

    return {
        "metadata": {
            "version": "1.0.0",
            "schemaVersion": 1,
            "provenance": (
                f"Paso 10, seccion 9 (oleada 3). Fuentes: {WINUTIL_PIN}, {ATLAS_PIN}. "
                "Los literales de valor se leen del pin con "
                "tools/ledger_extract/build_section9_catalog.py; ninguno se escribe a mano."
            ),
            "generatedBy": "paso 10 (oleada 3)",
        },
        "capabilities": capabilities,
    }


def dump(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=3, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="no escribe: compara con el fichero y sale 1 si difiere")
    args = parser.parse_args(argv)

    if not WINUTIL_TWEAKS.is_file() or not ATLAS_TOGGLES.is_dir():
        print("falta el pin en /tmp/upstream (ejecuta tools/ledger_extract/fetch_upstream.py)",
              file=sys.stderr)
        return 1

    document = build()
    text = dump(document)
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != text:
            print("section9_system_registry.json NO reproducible: el fichero del disco difiere",
                  file=sys.stderr)
            return 1
        print(f"section9_system_registry.json reproducible: OK "
              f"({len(document['capabilities'])} capacidades)")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"capacidades: {len(document['capabilities'])} | "
          f"acciones: {sum(len(c['actions']) for c in document['capabilities'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
