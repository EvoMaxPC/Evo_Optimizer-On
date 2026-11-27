# Informe ETAPA 6-D — Paso 2b (estructura .NET, commit de referencia 550cfb01)

## Commit de referencia

- Commit: `550cfb01e3ba61f5291644eb39e42e517e72cd93` (rama `arena/ab2d6de7-evo-optimizer-on`, presente en origin).
- Commit base para diff: `ed6457e94f2f9b63696dfdb1e43106fc02cb3406`.

## Tabla de CI del commit 550cfb01 (conclusiones leídas con `gh api`)

| Run id | Workflow | Evento | head_sha (40 chars) | Conclusión |
|---|---|---|---|---|
| 45976059323 | dotnet-ci | push | 550cfb01e3ba61f5291644eb39e42e517e72cd93 | success |
| 45976068136 | dotnet-ci | pull_request | 550cfb01e3ba61f5291644eb39e42e517e72cd93 | success |
| 45976059146 | ledger-verify | push | 550cfb01e3ba61f5291644eb39e42e517e72cd93 | success |

No hay run release-exe para este commit en la salida de `gh api` (no se relanzó o no aparece en el historial consultado).

## test-per-project.txt literal de cada runner (de ci-report)

**NO VERIFICADO.** La rama `ci-report` en origen solo conserva los runs más recientes (carpetas `runs/45989551832` en adelante). El run `45976059323` (commit `550cfb01`) ya fue rotado de `ci-report`, por lo que no existe `runs/45976059323-dotnet-windows-2025/test-per-project.txt` ni `runs/45976059323-dotnet-windows-11-arm/test-per-project.txt` para pegar literalmente. No se inventan cifras.

## Diff de src/ entre el commit base y el commit de referencia

```
 git diff --stat ed6457e94f2f9b63696dfdb1e43106fc02cb3406..550cfb01e3ba61f5291644eb39e42e517e72cd93 -- src/
```

Resultado (10 archivos, 211 insertions, 102 deletions):

```
 src/Evo.Core/System/IProcessAccessor.cs            |   3 -
 src/Evo.Core/System/ITaskAccessor.cs               |   6 ++
 src/Evo.Engine/EngineCoordinator.cs                |   4 +-
 src/Evo.Engine/Execution/ExecutionModels.cs        |   3 +-
 src/Evo.Engine/Executors/ProcessActionExecutor.cs  |  29 ++++--
 src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs | 112 +++++++++++++++------
 src/Evo.Engine/Executors/TaskCreateExecutor.cs     |  46 ++++--
 src/Evo.Engine/Undo/UndoJournal.cs                 |  61 ++++++++---
 src/Evo.Testing/FakeProcessAccessor.cs             |   24 +----
 src/Evo.Testing/FakeTaskAccessor.cs                |   25 +++--
10 files changed, 211 insertions(+), 102 deletions(-)
```

## Diff literal de src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs

Entre `ed6457e94f2f9b63696dfdb1e43106fc02cb3406` y `550cfb01e3ba61f5291644eb39e42e517e72cd93`:

```
diff --git a/src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs b/src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs
index 5226f35f..2f5922b4 100644
--- a/src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs
+++ b/src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs
@@ -24,6 +24,18 @@
+internal sealed class SnapshotLimitExceededException : Exception
+{
+    public SnapshotLimitExceededException(string message) : base(message) { }
+}
@@ -94,10 +106,20 @@
+        if (context.Registry is not IRegistryKeyCreator)
+        {
+            return Task.FromResult(ActionResult.Fail(
+                action.Key,
+                "El accesor de registro no sabe crear claves: no se puede deshacer el borrado, "
+                "así que no se borra (fail-closed).",
+                "present",
+                Describe(deleteAction)));
+        }
+        snapshot = TakeSnapshot(reader, hive, deleteAction.KeyPath, _limits);
@@ -105,7 +127,18 @@
-        catch (Exception ex) when (ex is not OutOfMemoryException)
+        catch (SnapshotLimitExceededException ex)
+    {
+        return Task.FromResult(ActionResult.Fail(
+            action.Key,
+            ex.Message + " No se borra (fail-closed).",
+            "present",
+            Describe(deleteAction)));
+    }
+catch (Exception ex) when (ex is not OutOfMemoryException)
@@ -172,16 +205,37 @@
+    public static RegistryKeySnapshot TakeSnapshot(
+        IRegistryTreeReader reader, RegistryHive hive, string keyPath,
+        RegistrySnapshotLimits? limits = null)
+    {
+        int totalKeys = 1;
+        int totalValues = 0;
+        int maxDepthReached = 0;
+        if (lim is not null && depth > lim.MaxDepth)
+        {
+            throw new SnapshotLimitExceededException(...);
+        }
+        totalValues++; if (lim is not null && totalValues > lim.MaxValues) throw ...;
+        totalKeys++; if (lim is not null && totalKeys > lim.MaxKeys) throw ...;
+        if (lim is not null && maxDepthReached > lim.MaxDepth) throw ...;
+        return new RegistryKeySnapshot(root);
+    }
@@ -250,12 +308,6 @@
-    public bool Truncated { get; init; }
-    public string? TruncationMessage { get; init; }
```

Cambios clave: se agregó `SnapshotLimitExceededException`, puerta fail-closed cuando `context.Registry` no es `IRegistryKeyCreator` (no se borra si no se puede deshacer), `TakeSnapshot` acepta `RegistrySnapshotLimits` y aborta temprano por profundidad/valores/claves, y se removieron `Truncated`/`TruncationMessage` de `RegistryKeySnapshot`.
