ETAPA 0 — REVALIDAR HALLAZGOS DE AUDITORÍA DEL MOTOR (SOLO LECTURA) [PARTE 3/5]

Rama: `arena/ab2d6de7-evo-optimizer-on` (base `402af190` de main). HEAD = `908f6ad`. Reglas ETAPA 0: SOLO LECTURA, sin commits/pushes, sin `gh pr ready`, sin merge, sin `git push --force`.

---

### HALLADIZO H4 — TaskCreateUndoEntry no guarda la TaskDefinition completa

`TaskCreateUndoEntry` guarda solo `ExistedBefore` y `WasEnabled` (+ `TaskPath`/`TaskName`/`PreviousState`, líneas 208-216), NO la `TaskDefinition` completa. `ITaskAccessor` (líneas 4-22) expone `Exists`, `IsTaskEnabled`, `EnableTask`, `DisableTask`, `CreateTask`, `DeleteTask` — NO expone lectura de la definición previa (no hay `GetTaskDescription`/`GetTaskDefinition`).

Función completa — `TaskCreateUndoEntry` (`src/Evo.Engine/Undo/UndoJournal.cs`, `nl -ba`):

```
   206    public sealed record TaskCreateUndoEntry : UndoJournalEntry
   207    {
   208        public required string TaskPath { get; init; }
   209

   210        public required string TaskName { get; init; }

   212        /// <summary>True si la tarea ya existía antes (se restaura, no se borra).</summary>
   213        public required bool ExistedBefore { get; init; }

   215        /// <summary>Estado previo de la tarea si ya existía.</summary>
   216        public required bool WasEnabled { get; init; }

   218        public override void Restore(IUndoContext context)
   219        {
   220            ArgumentNullException.ThrowIfNull(context);

   222            if (context.DryRun)
   223            {
   224                return;
   225            }

   227            if (!ExistedBefore)
   228            {
   229                context.Tasks.DeleteTask(TaskPath, TaskName);
   230                return;
   231            }

   233            if (WasEnabled)
   234            {
   235                context.Tasks.EnableTask(TaskPath, TaskName);
   236            }
   237            else
   238            {
   239                context.Tasks.DisableTask(TaskPath, TaskName);
   240            }
   241        }
   242    }
```

Función completa — `ITaskAccessor` (`src/Evo.Core/System/ITaskAccessor.cs`, `nl -ba`):

```
     4    public interface ITaskAccessor
     5    {
     6        bool Exists(string taskPath, string taskName);
     7

     8        bool IsTaskEnabled(string taskPath, string taskName);
     9

    10        void EnableTask(string taskPath, string taskName);
    11

    12        void DisableTask(string taskPath, string taskName);
    12

    14        /// <summary>
    15        /// Crea (o sobrescribe, si <paramref name="definition"/> ya existe y el
    16        /// accesor lo admite) una tarea programada (paso 11, ADR-0005).
    17        /// </summary>
    18        void CreateTask(TaskDefinition definition);
    19

    20        /// <summary>Borra la tarea; devuelve true si existía.</summary>
    21        bool DeleteTask(string taskPath, string taskName);
    22    }
```

Veredicto: **CONFIRMADO** — `src/Evo.Engine/Undo/UndoJournal.cs:206-242`; `src/Evo.Core/System/ITaskAccessor.cs:4-22`.

Tests hoy para H4: **NINGUNO test específico del hallazgo** (ningún test afirma que `TaskCreateUndoEntry` NO almacena `TaskDefinition` completa). Hay tests de comportamiento de `TaskCreate` en `Wave4EngineTests` (líneas 276, 303, 322, 344, 368) que cubren crear/deshacer, pero no verifican la ausencia de la definición en el undo entry.

---

### HALLADIZO H5 — RegistryDeleteKeyExecutor: comprueba IRegistryTreeReader, no IRegistryKeyCreator antes de borrar

Línea 87: comprueba `IRegistryTreeReader` (fail-closed si no lo implementa), NO comprueba `IRegistryKeyCreator` antes de borrar. La restauración de claves vacías anidadas SÍ ocurre en `UndoJournal.RestoreNode` (líneas 153-168: llama a `creator.EnsureKey` por nodo, luego valores, luego hijos recursivamente). Límites: profundidad en recorrido (`depth>=64` → sin subclaves, línea 192-194); tamaño (`MaxValues`/`MaxKeys`/`MaxDepth`) se comprueba DESPUÉS sobre la instantánea ya tomada (línea 112-121).

Función completa — comprobación de árbol y límites (`src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs`, `nl -ba`):

```
   87        if (context.Registry is not IRegistryTreeReader reader)
   88        {
   89            return Task.FromResult(ActionResult.Fail(
   90                action.Key,
   91                "El accesor de registro no sabe enumerar el árbol: no se puede tomar la " +
   92                "instantánea previa, así que no se borra (fail-closed).",
   93                "present",
   94                Describe(deleteAction)));
   95        }

   97        RegistryKeySnapshot snapshot;
   98        try
   99        {
   100            snapshot = TakeSnapshot(reader, hive, deleteAction.KeyPath);
   101        }
   102        catch (Exception ex) when (ex is not OutOfMemoryException)
   103        {
   104            return Task.FromResult(ActionResult.Fail(
   105                action.Key,
   106                $"No se pudo tomar la instantánea de '{deleteAction.KeyPath}': {ex.Message}. " +
   107                "No se borra (fail-closed).",
   108                "present",
   109                Describe(deleteAction)));
   110        }

   112        var tooBig = snapshot.Exceeds(_limits);
   113        if (tooBig is not null)
   114        {
   115            return Task.FromResult(ActionResult.Fail(
   116                action.Key,
   117                $"La instantánea de '{deleteAction.KeyPath}' supera el límite " +
   118                $"({tooBig}): no se borra (fail-closed).",
   119                "present",
   120                Describe(deleteAction)));
   121        }
```

Tope de profundidad en recorrido (líneas 189-194):

```
   189            // Tope duro de recursión del propio recorrido: los límites de tamaño
   190            // se comprueban DESPUÉS, sobre la instantánea ya tomada, pero un árbol
   191            // patológico no debe poder colgar el recorrido.
   192            IReadOnlyList<string> childNames = depth >= 64
   193                ? Array.Empty<string>()
   194                : reader.GetSubKeyNames(hive, path);
```

Restauración de claves vacías anidadas — `UndoJournal.RestoreNode` (`src/Evo.Engine/Undo/UndoJournal.cs`, `nl -ba`):

```
   150    private static void RestoreNode(
   151        Evo.Core.System.IRegistryAccessor registry, RegistryHive hive, Executors.RegistryKeyNode node)
   152    {
   153        // Las claves vacías también se recrean: un borrado recursivo se deshace
   154        // con el árbol exacto, incluidas las ramas sin valores.
   155        if (registry is Evo.Core.System.IRegistryKeyCreator creator)
   156        {
   157            creator.EnsureKey(hive, node.Path);
   158        }

   160        foreach (var value in node.Values)
   161        {
   162            registry.SetValue(hive, node.Path, value.Name, value.Value!, value.Kind);
   163        }

   165        foreach (var child in node.Children)
   166        {
   167            RestoreNode(registry, hive, child);
   168        }
   169    }
```

Veredicto: **CONFIRMADO** — `src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs:87` (no comprueba `IRegistryKeyCreator` antes de borrar); `src/Evo.Engine/Undo/UndoJournal.cs:153-168` (restaura claves vacías anidadas SÍ); `src/Evo.Engine/Executors/RegistryDeleteKeyExecutor.cs:112-121,192-194` (límites).

Tests hoy para H5:
- `Wave4EngineTests.DeleteKey_AccessorWithoutTreeReaderAbortsWithoutDeleting` (línea 115) — cubre fail-closed sin `IRegistryTreeReader`.
- `Wave4EngineTests.DeleteKey_RestoresTheWholeSubtreeWithTypesAndData` (línea 34) — cubre restauración de árbol.
- `Wave4EngineTests.DeleteKey_SnapshotOverTheLimitAbortsWithoutDeleting` (línea 155)
- `Wave4EngineTests.DeleteKey_DepthOverTheLimitAbortsBeforeDeleting` (línea 249)

---

FIN PARTE 3/5. Continúa en PARTE 4/5 (H6-H7).