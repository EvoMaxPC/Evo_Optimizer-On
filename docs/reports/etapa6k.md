# Informe ETAPA 6-K — Corregir rollback automático del motor y repetir verificaciones de la 6-I

## Rama y commits (todos subidos a origin; HEAD final en origin)

- Rama: `arena/ab2d6de7-evo-optimizer-on`.
- Push 1 (6-K): `f2afe43126ec0818dc9704563330a2113229250b` (marca de índice `rollbackStartIndex` + `Skip()` en EngineCoordinator; tests nuevos del motor y del ViewModel) → CI falló (el test nuevo del motor seguía dando ValorX=1).
- Push 2 (6-K): `7431c0127e9304729c22fd6091729adbec4a443d` (opción B: journal LOCAL aislado por ejecución; volcadura al journal del contexto solo si tuvo éxito) → **CI verde en todos los workflows**.
- HEAD final (origin y local): `7431c0127e9304729c22fd6091729adbec4a443d` (40 chars).
- PR #1: draft:true, merged:false, head `7431c0127e9304729c22fd6091729adbec4a443d`.
- Pushes de código usados en 6-K: 2 (de hasta 4 permitidos). Push final de docs (etapa6k, etapa6i corregido, PRUEBA_EN_VM) pendiente al cerrar este informe.

## PASO 0 — Sincronización y archivos basura

- `git remote -v`: `origin https://github.com/EvoMaxPC/Evo_Optimizador-On (fetch/push)` (slug correcto: `EvoMaxPC/Evo_Optimizador-On`).
- `git fetch origin`, `git checkout arena/ab2d6de7-evo-optimizer-on`, `git merge --ff-only origin/arena/ab2d6de7-evo-optimizer-on`: fast-forward desde `402af190` (initial commit) a `f956019f47fc8005bcdbdbca8048fceea22e4b2d`.
- `git rev-parse HEAD`: `f956019f47fc8005bcdbdbca8048fceea22e4b2d` (antes de los pushes de 6-K).
- `git status --short`: limpio tras `git checkout -- README.md` y `git clean -fd`.
- `git ls-files | grep -E '[ ;>]|2>/dev/null'`: **vacío** (sin archivos basura).
- `git ls-files docs/reports docs/PRUEBA_EN_VM.md`: `etapa6h.md`, `etapa6i.md`, `PRUEBA_EN_VM.md` presentes en origin.
- La rama local no tenía commits propios sin subir.

## PASO 1 — Verificaciones que la 6-J no pudo hacer

### 1b) Error literal del push 5 de la 6-I (commit `267c68759bdee739d5e3b5cc4ffcc8033e8a687e`, run `46109799778` de ci-report):

```
Evo.Engine.Tests.UndoUsesContextJournalTests.RollbackAutomatico_No_Afecta_Otra_Capacidad (Evo.Engine.Tests): Assert.True() Failure
Expected: True
Actual:   False
   at Evo.Engine.Tests.UndoUsesContextJournalTests.cs:line 108
```

Línea 108 era `Assert.True(summaryA.Succeeded >= 1)`. Falló porque el contrato pasado tenía `restore: RestoreLevel.SessionUndo` con el `risk` por defecto (`RiskLevel.Medium`), y `ValidateReversibility` exige `Restore >= MinimumRestore(risk)` donde `MinimumRestore(Medium) = RestoreLevel.RestorePoint(2)`; como `SessionUndo(1) < RestorePoint(2)`, la validación rechazó la capacidad y `Succeeded` quedó en 0.

### Contrato por defecto de `TestHarness.Contract`

```csharp
public static CapabilityContract Contract(
    IEnumerable<CapabilityAction> actions,
    string id = "test.capability",
    RiskLevel risk = RiskLevel.Medium,           // default: Medium
    PrivilegeLevel privilege = PrivilegeLevel.User,
    RestoreLevel restore = RestoreLevel.RestorePoint,   // default: RestorePoint
    ConfirmationType? confirmation = null,      // default: MinimumConfirmation(risk)
    ...
)
```

- `RestoreLevel` por defecto: **RestorePoint**.
- `ConfirmationType` por defecto: **MinimumConfirmation(Medium) = Summary**.
- El test usa `TestHarness.Create()` → `FakeRestorePointService { Available = true }` (por defecto `restorePointAvailable = true`). Sí hay un fake de punto de restauración, y con `RestorePoint` disponible el motor lo crea y pasa.
- El test del punto B de la 6-I **no cubre** el contrato real de la app (`Safe`, `SessionUndo`, `Confirmation.None`): con `RestorePoint` sí se invoca el punto de restauración, cosa que el contrato real de Safe no exige (`RequiresRestorePoint(SessionUndo, None) = false`).
- El test nuevo del paso 2c de esta etapa **sí cubre** el contrato real: `risk: RiskLevel.Safe`, `restore: RestoreLevel.SessionUndo`, `confirmation: ConfirmationType.None`. `FakeRestorePointService` no se invoca (no se necesita punto).

## PASO 2 — Defecto del rollback automático (EngineCoordinator.cs)

### 2a) Código real con números de línea (versión ANTES de la corrección, HEAD `f956019f4`):

```csharp
        var journal = template.Journal ?? new UndoJournal();
        if (restorePointId is not null)
        {
            journal.RestorePointId = restorePointId;
        }

        var context = template with { Mode = mode, Journal = journal, CapabilityId = plan.Capability.Id };
        ...
        var rollbackEntries = journal.Entries.ToList();
        ...
        bool doRollback = mode == ExecutionMode.Execute &&
                          rollbackEntries.Count > 0 &&
                          (failed || canceled);

        if (doRollback)
        {
            var undoContext = new UndoContext(
                template.Registry, template.Services, template.Tasks,
                template.Processes, template.Commands);
            rollbackReport = await journal.RollbackAsync(undoContext).ConfigureAwait(false);
        }
```

Y `UndoJournal.RollbackAsync` itera sobre **todo** `_entries` (no sobre `rollbackEntries`):

```csharp
        for (var index = _entries.Count - 1; index >= 0; index--)
        {
            var entry = _entries[index];
            ...
        }
```

### Confirmación del defecto (SÍ hay defecto)

**Confirmado con el código.** `rollbackEntries = journal.Entries.ToList()` captura TODAS las entradas del journal compartido, y `journal.RollbackAsync(...)` las revierte todas LIFO. Si la capacidad X ya se aplicó con éxito (entrada e1 en J_X) y se vuelve a ejecutar X fallando en la 2ª acción (entrada e2), el rollback revierte **ambas** (e2 y e1), haciendo que el valor de X vuelva al estado de ANTES de la primera ejecución en vez de quedarse en el estado tras la primera ejecución exitosa.

### 2b) Corrección mínima (opción B: journal local aislado por ejecución)

**Elección:** journal local de ejecución (`executionJournal`) para el rollback automático; el journal del contexto (`contextJournal` = el del ViewModel) solo recibe las entradas de ejecuciones exitosas. Motivo: `UndoJournal.RollbackAsync` no soporta revertir solo un subconjunto (itera todo `_entries`), así que el aislamiento debe hacerse separando los diarios antes de llamar a `RollbackAsync`. `RollbackAsync` público (Deshacer de la app) sigue revirtiendo TODAS las entradas del journal de la capacidad (no se tocó `UndoJournal.cs`).

**Cambio en `src/Evo.Engine/EngineCoordinator.cs`:**

ANTES (líneas ~348-356):
```csharp
        var journal = template.Journal ?? new UndoJournal();
        if (restorePointId is not null)
        {
            journal.RestorePointId = restorePointId;
        }

        var context = template with { Mode = mode, Journal = journal, CapabilityId = plan.Capability.Id };
```

DESPUÉS:
```csharp
        // Usa el diario del contexto (pasado por el llamante/ViewModel) para
        // el deshacer manual (ETAPA 6-H). Para el rollback automático se usa
        // un journal LOCAL de esta ejecución, así el deshacer automático de
        // una ejecución fallida no toca las entradas de ejecuciones previas
        // exitosas de la misma capacidad (ETAPA 6-K).
        var contextJournal = template.Journal ?? new UndoJournal();
        var executionJournal = new UndoJournal();
        if (restorePointId is not null)
        {
            executionJournal.RestorePointId = restorePointId;
        }

        var context = template with { Mode = mode, Journal = executionJournal, CapabilityId = plan.Capability.Id };
```

ANTES (líneas ~398-410):
```csharp
        var rollbackEntries = journal.Entries.ToList();
        ...
        rollbackReport = await journal.RollbackAsync(undoContext).ConfigureAwait(false);
```

DESPUÉS:
```csharp
        var rollbackEntries = executionJournal.Entries.ToList();
        ...
        rollbackReport = await executionJournal.RollbackAsync(undoContext).ConfigureAwait(false);
```

Y en el bloque final de éxito (`if (mode == ExecutionMode.Execute)`), las entradas de `executionJournal` se vuelcan a `contextJournal` (ViewModel) y a `Journal` (coordinador) solo si la ejecución terminó sin fallo:

```csharp
            foreach (var entry in executionJournal.Entries)
            {
                contextJournal.Add(entry);
                Journal.Add(entry);
            }
```

**DESVIACIÓN declarada:** se modificó `src/Evo.Engine/EngineCoordinator.cs` (una sección de `ExecuteAsync`). Permitido por 6-K: "src/Evo.Engine (solo el defecto del paso 2)".

### 2c) Test nuevo del motor que fallaba con el código viejo y pasa con el nuevo

`tests/Evo.Engine.Tests/UndoUsesContextJournalTests.cs` — `RollbackAutomatico_No_Revierte_EjecucionPreviaExitosa` (línea ~211):

```csharp
        // 1ª ejecución: Set DWord ValorX 1→99, éxito.
        ... summary1.Succeeded >= 1; ValorX == 99; Assert.Single(journalJ.Entries);

        // 2ª ejecución con el MISMO journal J: Set DWord (éxito) + comando que falla.
        harness.Commands.Throw("explode.exe --now");
        ... summary2.Succeeded == 1; summary2.Failed == 1;

        // CON LA CORRECCIÓN: ValorX == 99 (NO 1, lo que daba el código viejo).
        Assert.Equal(99, ValorX);
        // J conserva exactamente la entrada de la 1ª ejecución.
        Assert.Single(journalJ.Entries);
```

**Traza a mano del código VIEJO:**
- Antes de la 2ª ejecución: J = [e1: ValorX 1→99] (ValorX == 99).
- 2ª ejecución: e2: ValorX 99→99 (Set DWord, éxito), luego comando falla.
- `rollbackEntries = [e1, e2]`; `RollbackAsync` LIFO → deshace e2 (ValorX queda 99) y luego deshace e1 (ValorX vuelve a **1**). ← BUG.

**Con la corrección (journal local):** `executionJournal` solo tiene e2 en la 2ª ejecución; el rollback revierte solo e2. ValorX se queda en **99** y `journalJ` (el del contexto/ViewModel) conserva solo e1.

Contrato real de la app: `Safe` / `SessionUndo` / `Confirmation.None` (no requiere punto de restauración, `FakeRestorePointService` no se invoca).

### 2d) Todos los tests de Engine siguen pasando

Confirmado por CI: Evo.Engine.Tests **135/134 passed** (134 previos + 1 nuevo), 0 fallos, en ambos runners.

### 2e) Test del ViewModel (registro falso, ViewModel real)

`tests/Evo.App.Tests/UndoTests.cs` — `DespuesDeAplicar_SegundoAplicarFalla_DeshacerReviertePrimera` (línea 281):

```csharp
        // 1ª aplicación: éxito → ValorX = 42.
        var applied1 = vm.Apply(cap);  // HasResults, ValorX == 42

        // 2ª aplicación: SetValue lanza (ThrowOnSetValueCall = 1).
        registry.ResetSetValueCounter();
        registry.ThrowOnSetValueCall = 1;
        var applied2 = vm.Apply(cap);  // no lanza (EngineCoordinator captura OCE)
        // ValorX sigue en 42 (la 2ª aplicación no mutó).
        Assert.Equal(42, ValorX);

        // Deshacer X revierte la 1ª aplicación: estado original (valor ausente).
        var undone = vm.Undo(cap.Id);
        Assert.True(undone.HasResults);
        Assert.Contains("Se deshizo: 1 cambio(s) de cap.x", undone.ResultsText);
        Assert.DoesNotContain("DryRun", undone.ResultsText);
        Assert.Null(ValorX);
```

## PASO 3 — CI y evidencia (HEAD final de código `7431c0127e9304729c22fd6091729adbec4a443d`)

| Run ID | Workflow | SHA (40 chars) | Evento | Conclusión |
|--------|----------|----------------|--------|------------|
| 46115531463 | dotnet-ci | 7431c0127e9304729c22fd6091729adbec4a443d | pull_request | success |
| 46115527884 | dotnet-ci | 7431c0127e9304729c22fd6091729adbec4a443d | push | success |
| 46115527892 | release-exe | 7431c0127e9304729c22fd6091729adbec4a443d | push | success |
| 46115527891 | ledger-verify | 7431c0127e9304729c22fd6091729adbec4a443d | push | success |

**Ningún run pending.** Como se cambió `src/**`, release-exe sí corrió (run 46115527892, success).

### test-per-project.txt literal (ambos runners)

windows-2025:
```
Evo.App.Tests: total=28 passed=28 failed=0
Evo.Catalog.Tests: total=79 passed=79 failed=0
Evo.Core.Tests: total=34 passed=34 failed=0
Evo.Detection.Tests: total=35 passed=35 failed=0
Evo.Engine.Tests: total=135 passed=135 failed=0
Evo.Windows.Tests: total=14 passed=14 failed=0
```
windows-11-arm: idéntico (28/79/34/35/135/14).
**Total: 325 passed / 0 failed** (>323 ✓).

### Tabla test | línea de test-console.txt | resultado (ambos runners)

| Test | Línea w-2025 | Línea w-11-arm | Resultado |
|------|-------------|---------------|-----------|
| UndoTests.DeshacerSinAplicar_Dice_NoHayNada | 12 | 13 | Passed |
| UndoTests.DeshacerPorCapacidad_A_No_Afecta_A_B | 20 | 20 | Passed |
| UndoTests.DespuesDeAplicar_Deshacer_EliminaValorCreado | 21 | 21 | Passed |
| UndoTests.DosClicsEnDeshacer_ElSegundo_DiceNoHayNada | 22 | 22 | Passed |
| UndoTests.DespuesDeAplicar_SegundoAplicarFalla_DeshacerReviertePrimera | 30 | 23 | Passed |
| Tests.AplicarYDeshacer_Fake_Vuelve_Al_Estado_Original | 31 | 35 | Passed |
| UndoTests.AplicarADosVeces_DeshacerUnaVez_VuelveAlEstadoOriginal | 33 | 24 | Passed |
| UndoTests.Simular_Despues_Aplicar_Y_Deshacer_Vuelve_Al_Estado_Original | 35 | 25 | Passed |
| UndoTests.DespuesDeAplicar_Deshacer_RestauraValorPrevio | 36 | 26 | Passed |
| UndoUsesContextJournalTests.ExecuteAsync_Uses_ContextJournal... | 279 | 281 | Passed |
| UndoUsesContextJournalTests.RollbackAutomatico_No_Revierte_EjecucionPreviaExitosa | 280 | 282 | Passed |
| UndoRealRegistryTest.AplicarYDeshacer_RegistroReal_RevierteValor | 429 | 429 | Passed |

Todos **Passed** en ambos runners (verificado con `grep -n` sobre test-console.txt; números de línea del archivo de log, no del código fuente).

### Artefacto release-exe (run 46115527892, commit `7431c012...`)

```
gh api -i repos/EvoMaxPC/Evo_Optimizador-On/actions/runs/46115527892/artifacts
→ HTTP/2.0 404 Not Found
{"message":"Not Found","status":"404"}
```

El listado de artefactos devuelve **HTTP 404** (no listable con mi token). Según la instrucción, un 404 **no se interpreta como "expirado"**: se reporta como "no listable con mi token". `digest` no disponible → **SHA-256 NO VERIFICADO**. Tamaño no disponible (no se pudo listar el artefacto).

### Estado del PR

```
gh pr view 1 --json isDraft,mergedAt,headRefOid,number
{"headRefOid":"7431c0127e9304729c22fd6091729adbec4a443d","isDraft":true,"mergedAt":null,"number":1}
```
- draft: **true** ✓
- merged: **false** (`mergedAt: null`) ✓
- head: `7431c0127e9304729c22fd6091729adbec4a443d` = HEAD de origin ✓ (coinciden)

## Qué no se probó

- Deshacer por fila y rollback automático con la app abierta en una VM física Windows: sigue pendiente de la prueba del usuario (los tests de Windows corren en los runners de GitHub Actions, no en una VM local).
- SHA-256 del artefacto release-exe (artefacto no listable con mi token; descarga bloqueada en sandbox).
