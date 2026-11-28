# Contrato de trabajo: EVO CLEAN
1. Alcance: optimizador EXCLUSIVO para Windows 10 22H2 y Windows 11
   23H2/24H2/25H2/26H2. C# / .NET 10 LTS (net10.0-windows) definido en una única
   propiedad central. UI WPF. Licencia GPLv3.
2. Requisitos maestros
   - REQ-000: cobertura 100% de WinUtil + AtlasOS + capacidades EVO. Nada se
     descarta por avanzado, experimental, privilegiado o de riesgo alto.
   - REQ-001: incorporar != ejecutar. Cada operación tiene control propio,
     requisitos, compatibilidad, privilegio mínimo, confirmación según riesgo
     y restauración cuando proceda.
   - REQ-002: nunca inventar datos; lo no verificado se marca NO VERIFICADO.
   - REQ-003: las versiones de Windows viven en datos (catalog/windows-releases.json).
     Un build desconocido NUNCA es compatible. Windows Server NO es objetivo.
   - REQ-004: el motor accede al sistema solo mediante interfaces (dry-run,
     simulación, tests con fakes, reversión verificable).
   - REQ-005: trazabilidad total: cada fichero de upstream queda clasificado;
     ninguno se ignora en silencio.
   - REQ-006: no hay deuda oculta: desviaciones y suposiciones se declaran.
3. Entorno del agente: Linux sin .NET ni PowerShell. Python 3.11 con pytest,
   jsonschema y pyyaml (pip --break-system-packages). Todo build o test de
   .NET/PowerShell ocurre en GitHub Actions. Los runners hosted de Windows
   pueden ser Windows Server: sirven para compilar y para tests unitarios y
   de integración en claves sandbox, no para validar AppX/Store/Explorer.
   Windows 10 22H2 y los tweaks de shell se validan en VM del responsable.
4. Lectura de resultados de CI: método estándar = rama ci-report vía git:
   `git fetch origin ci-report` y `git show FETCH_HEAD:<ruta>`.
   [ERRATA-EVO-001] `git fetch origin ci-report` NO crea `origin/ci-report`
   (verificado: `fatal: invalid object name 'origin/ci-report'`). Para usar el
   nombre remoto, refspec explícito:
   `git fetch origin ci-report:refs/remotes/origin/ci-report`.
   `gh run view --log` NO funciona (CDN bloqueado: `results-receiver.actions.githubusercontent.com`).
   Estado por job: `gh api .../actions/runs/<id>/jobs`.
   Salida del agente limitada a 20.000 caracteres: informes cortos y detalle en
   docs/reports/.
5. Licencias: el repo es GPLv3. WinUtil es MIT (atribución en
   THIRD_PARTY_NOTICES.md). El inventario guarda metadatos, claves y hashes,
   no cuerpos de código. Copiar código de upstream requiere un ADR.
6. Convenciones: Conventional Commits, ADRs breves en docs/adr/, trabajar en la
   rama actual, no hacer merge a main sin aprobación.
7. Formato de informe: resumen; archivos; comandos con salida real; resultados
   de tests; criterios CUMPLIDO/NO CUMPLIDO/NO VERIFICADO con evidencia;
   desviaciones; datos asumidos; riesgos; preguntas abiertas; commit.

## Erratas

### ERRATA-EVO-003: hallazgos sobre la matriz de runners

Medido en el run `45267030334`, commit `49bfc3f`. Evidencia literal en
`inventory/raw/ci-reports/`.

- `windows-11-arm` = Windows 11 Enterprise 25H2, build 26200,
  `InstallationType=Client`, ARM64, explorer corriendo, Store presente
  (`22609.1401.13.0`). **Único runner cliente real.**
- `windows-latest` = `windows-2025` = Windows Server 2025 Datacenter, build 26100
  (misma imagen `win25-vs2026`). `ServerDatacenter` **no** es un cliente
  Windows 11.
- `ProductName` no es un detector fiable (reporta `Windows 10 Enterprise` para un
  kernel build 26200). La detección exige `CurrentBuildNumber` +
  `InstallationType=Client`.

### ERRATA-EVO-004: formato real del inventario y regla de conteo

- El inventario del responsable usa encabezados `- TÍTULO EN MAYÚSCULAS`
  (**17 secciones**), no `1. Título`. El regex `^[0-9]{1,2}\.\s+[A-ZÁÉÍÓÚÑ]`
  casa **0** líneas de ese texto. `count_inventory.py` acepta
  `--heading-style bullet` (por defecto, formato real) y `numeric` (regex pedido).
- Convención de conteo: una sub-cabecera `WinUtil`/`AtlasOS`/`EVO CLEAN…`
  **cuenta como línea no vacía de su propio cubo** y las líneas siguientes
  heredan ese cubo hasta la próxima sub-cabecera o el próximo encabezado de
  sección (que reinicia a `general`).
- Verificado también que una viñeta **sangrada** (`  - X`) no debe abrir sección;
  se corrigió el bug de `strip()` que la aceptaba.
- **Corrección (ERRATA-EVO-005):** en el primer cálculo se atribuyó `general=2`
  a la "tabla aplanada" de la sección 17. Era **falso**: fue un fallo de
  implementación (no se aplicaban las reglas de notas ni la excepción de la
  sección 17). Corregido; hoy `general=56` con la sección 17 al 100 % general.

### ERRATA-EVO-005: el texto del inventario atravesó el canal transformado

El texto del inventario atravesó el canal del mensaje con transformaciones: los
17 títulos llegaron como viñetas `- TÍTULO` y `&` llegó como `&amp;`.
`INVENTARIO_USUARIO.md` es **byte-idéntico a lo recibido por el agente**, no
necesariamente al original del responsable. Los extractores normalizan
(`html.unescape`, quitar la viñeta de título) **sin modificar el fichero crudo**.

Consecuencias medidas en este repo:

- El regex de encabezado pedido (`^[0-9]{1,2}\.\s+[A-ZÁÉÍÓÚÑ]`) casa 0 líneas;
  por eso el estilo por defecto es `bullet`.
- `&amp;amp;` aparece **0** veces en el fichero; lo que hay es `&amp;` en
  `O&amp;O ShutUp10++` (1 ocurrencia, línea 87). `html.unescape` aplica **un**
  nivel: `&amp;amp;` -> `&amp;`, nunca `&amp;amp;` -> `&`.
