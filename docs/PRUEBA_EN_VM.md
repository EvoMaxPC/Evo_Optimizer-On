# Prueba de EVO Clean en una VM con Windows 11

Esta guía es para un usuario que no es desarrollador. Le permite bajar, instalar y probar la aplicación EVO Clean en una máquina virtual (VM) con Windows 11.

---

## 1. Dónde bajar el archivo

1. Entre al repositorio en GitHub: **EvoMaxPC/Evo_Optimizer-On**.
2. Vaya a la pestaña **Actions** (Acciones).
3. Busque la corrida más reciente del workflow llamado **release-exe**.
4. En el panel derecho de esa corrida, busque la sección **Artifacts** (Artefactos).
5. Descargue **EvoClean-preview-win-x64.zip**.

También puede bajarlo desde la pestaña **Releases**, buscando el pre-release en borrador llamado `preview-<numero_de_corrida>`.

---

## 2. Verificar el archivo (SHA-256)

Junto al ZIP se encuentra un archivo llamado `EvoClean-preview-win-x64.zip.sha256`. Sirve para confirmar que el ZIP no se corrompiu al descargar.

En PowerShell de Windows:

```powershell
Get-FileHash -Algorithm SHA256 EvoClean-preview-win-x64.zip
```

Compare el resultado con el contenido del archivo `.sha256`. Deben coincidir.

---

## 3. Antes de instalar: hacer un snapshot de la VM

**Importante:** esta aplicación puede modificar el registro de Windows, servicios y archivos del sistema. Antes de descomprimir o ejecutar nada:

1. Tome un **snapshot** (punto de control) de su VM con Windows 11.
2. Así podrá volver al estado original después de probar.

---

## 4. Instalación y ejecución

1. Descomprima `EvoClean-preview-win-x64.zip` en una carpeta de la VM.
2. Dentro de la carpeta descomprimida verá `Evo.App.exe` y una subcarpeta llamada `catalog/`.
3. Haga clic derecho sobre `Evo.App.exe` y elija **Ejecutar como administrador**.
   - Algunas capacidades requieren privilegios de administrador. Si no lo ejecuta como administrador, esas capacidades se muestran pero no se pueden aplicar.

### Qué debe ver al abrir

- Arriba: la detección de Windows (build, UBR, edición y tipo de instalación). Si Windows no es compatible (por ejemplo, Windows Server o un build desconocido), aparece un mensaje **"Windows no compatible"** y no se puede aplicar nada.
- El centro: 17 secciones del inventario de usuario con sus capacidades (nombre, descripción, riesgo, privilegio, estado).
- Abajo: el área de resultados (texto de lo que cambió, omitió, falló o se deshizo).

---

## 5. Qué probar primero

Siga este orden:

1. **Simular (DryRun):** Haga clic en el botón **Simular** de una capacidad. Esto no cambia nada del sistema; solo muestra qué haría.
2. **Aplicar:** Haga clic en **Aplicar** de una capacidad **Safe** (riesgo bajo). Se aplicará el cambio y aparecerá un registro en el área de resultados.
3. **Deshacer:** Haga clic en **Deshacer** para revertir lo aplicado en la sesión.

---

## 6. Qué NO está disponible todavía

Estas funcionalidades existen en el diseño pero **no están habilitadas** en esta versión preliminar:

- **Capacidades Críticas:** están bloqueadas (requieren respaldo completo).
- **Punto de restauración:** no disponible todavía en esta versión. En producción la aplicación funciona **fail-closed**: si una capacidad exige punto de restauración y no hay servicio disponible, no se aplica nada (no muta el sistema).
- **Confirmación real:** al aplicar una capacidad que la requiera se muestra un cuadro de diálogo de Windows (`MessageBox`) con nombre, riesgo y resumen de las acciones; si el usuario elige "No", la operación se cancela.
- **Tareas programadas y comandos externos:** se indican como "no disponible todavía" (el ejecutor devuelve error sin ejecutar nada real).
- **TrustedInstaller:** no disponible.

---

## 7. Cómo volver al estado original

Si algo salió mal o desea empezar de nuevo:

1. Restaure el **snapshot** de la VM que tomó en el paso 3.
2. La VM volverá al estado exacto antes de instalar EVO Clean.

---

## 8. Qué datos devolver

Después de probar, envíe:

1. Una **captura de pantalla** de la ventana principal de EVO Clean.
2. El **texto del área de resultados** (copie y pegue lo que aparece abajo en la ventana).

Eso permite verificar que la detección de Windows, las 17 secciones y las acciones de Simular / Aplicar / Deshacer funcionan correctamente.
