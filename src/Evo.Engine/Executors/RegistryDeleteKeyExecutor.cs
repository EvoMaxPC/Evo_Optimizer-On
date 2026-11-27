using Evo.Core.Actions;
using Evo.Core.System;
using Evo.Engine.Execution;
using Evo.Engine.Undo;
using Microsoft.Win32;

namespace Evo.Engine.Executors;

/// <summary>
/// Límites de la instantánea de un subárbol del registro (ADR-0005). Si se
/// superan, el motor ABORTA sin borrar: una clave enorme no se borra a ciegas.
/// </summary>
public sealed record RegistrySnapshotLimits
{
    /// <summary>Profundidad máxima de subclaves (0 = sólo la clave pedida).</summary>
    public int MaxDepth { get; init; } = 16;

    /// <summary>Valores totales admitidos en la instantánea.</summary>
    public int MaxValues { get; init; } = 4096;

    /// <summary>Subclaves totales admitidas en la instantánea.</summary>
    public int MaxKeys { get; init; } = 1024;

    public static RegistrySnapshotLimits Default { get; } = new();
}

/// <summary>
/// Excepcion propia lanzada por <see cref="TakeSnapshot"/> cuando el recorrido
/// supera un limite de <see cref="RegistrySnapshotLimits"/> (profundidad,
/// valores o claves). El executor la captura por separado de las fallas del
/// lector para informar exactamente que limite se excedio, sin confundirla
/// con un error de lectura del arbol.
/// </summary>
internal sealed class SnapshotLimitExceededException : Exception
{
    public SnapshotLimitExceededException(string message) : base(message) { }
}

/// <summary>
/// Borra una clave completa del registro con deshacer exacto (paso 11).
/// </summary>
/// <remarks>
/// Orden fail-closed, sólo en <see cref="ExecutionMode.Execute"/> cuando hay
/// algo que borrar:
/// <list type="number">
///   <item>si la clave no existe → no-op registrado (deshacer no crea nada);</item>
///   <item>si el accesor no implementa <see cref="IRegistryTreeReader"/> → falla
///   sin borrar;</item>
///   <item>se toma la instantánea completa (valores con tipo y datos, subclaves
///   recursivamente); si lanza o supera <see cref="RegistrySnapshotLimits"/> →
///   falla sin borrar;</item>
///   <item>sólo entonces se borra la clave y se guarda la instantánea en el
///   diario.</item>
/// </list>
/// En DryRun y Audit no se muta nada y no se toma instantánea del sistema: se
/// informa de lo que se borraría.
/// </remarks>
public sealed class RegistryDeleteKeyExecutor : IActionExecutor
{
    private readonly RegistrySnapshotLimits _limits;

    public RegistryDeleteKeyExecutor(RegistrySnapshotLimits? limits = null)
    {
        _limits = limits ?? RegistrySnapshotLimits.Default;
    }

    public ActionKind Kind => ActionKind.RegistryDeleteKey;

    public Task<ActionResult> ExecuteAsync(CapabilityAction action, ActionContext context)
    {
        ArgumentNullException.ThrowIfNull(action);
        ArgumentNullException.ThrowIfNull(context);

        if (action is not RegistryDeleteKeyAction deleteAction)
        {
            return Task.FromResult(ActionResult.Fail(action.Key, "Acción no es de borrado de clave."));
        }

        var hive = RegistryActionExecutor.Map(deleteAction.Hive);

        if (!context.Registry.KeyExists(hive, deleteAction.KeyPath))
        {
            // No-op: no se borra nada y el deshacer no debe crear la clave.
            return Task.FromResult(ActionResult.Ok(
                action.Key, "absent", "absent", false, Describe(deleteAction)));
        }

        if (!context.Mutates)
        {
            return Task.FromResult(ActionResult.Ok(
                action.Key,
                "present",
                $"would-delete: {deleteAction.Hive}\\{deleteAction.KeyPath} " +
                $"(recursive={deleteAction.Recursive.ToString().ToLowerInvariant()})",
                false,
                Describe(deleteAction)));
        }

        if (context.Registry is not IRegistryTreeReader reader)
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                "El accesor de registro no sabe enumerar el árbol: no se puede tomar la " +
                "instantánea previa, así que no se borra (fail-closed).",
                "present",
                Describe(deleteAction)));
        }

        if (context.Registry is not IRegistryKeyCreator)
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                "El accesor de registro no sabe crear claves: no se puede deshacer el borrado, " +
                "así que no se borra (fail-closed).",
                "present",
                Describe(deleteAction)));
        }

        RegistryKeySnapshot snapshot;
        try
        {
            snapshot = TakeSnapshot(reader, hive, deleteAction.KeyPath, _limits);
        }
        catch (OperationCanceledException)
        {
            // Nunca se traga una cancelación: la deja propagar al coordinador,
            // que la trata como cancelación honesta (H1).
            throw;
        }
        catch (SnapshotLimitExceededException ex)
    {
        // Límite de snapshot excedido: se informa el límite concreto y no se
        // borra (fail-closed). No se envuelve en el mensaje genérico del
        // lector para distinguirlo de una falla de lectura del árbol.
        return Task.FromResult(ActionResult.Fail(
            action.Key,
            ex.Message + " No se borra (fail-closed).",
            "present",
            Describe(deleteAction)));
    }
catch (Exception ex) when (ex is not OutOfMemoryException)
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                $"No se pudo tomar la instantánea de '{deleteAction.KeyPath}': {ex.Message}. " +
                "No se borra (fail-closed).",
                "present",
                Describe(deleteAction)));
        }

        var tooBig = snapshot.Exceeds(_limits);
        if (tooBig is not null)
        {
            return Task.FromResult(ActionResult.Fail(
                action.Key,
                $"La instantánea de '{deleteAction.KeyPath}' supera el límite " +
                $"({tooBig}): no se borra (fail-closed).",
                "present",
                Describe(deleteAction)));
        }

        var deleted = context.Registry.DeleteKey(hive, deleteAction.KeyPath, deleteAction.Recursive);

        context.Journal.Add(new RegistryDeleteKeyUndoEntry
        {
            CapabilityId = context.CapabilityId,
            ActionKey = action.Key,
            Description = Describe(deleteAction),
            PreviousState = snapshot.Summary(),
            Hive = hive,
            KeyPath = deleteAction.KeyPath,
            Recursive = deleteAction.Recursive,
            ExistedBefore = true,
            Snapshot = snapshot,
        });

        return Task.FromResult(ActionResult.Ok(
            action.Key,
            snapshot.Summary(),
            deleted ? "deleted" : "deleted-nothing",
            true,
            Describe(deleteAction)));
    }

    public string? ReadCurrentState(CapabilityAction action, ActionContext context)
    {
        if (action is not RegistryDeleteKeyAction deleteAction)
        {
            return null;
        }

        var hive = RegistryActionExecutor.Map(deleteAction.Hive);
        if (!context.Registry.KeyExists(hive, deleteAction.KeyPath))
        {
            return "absent";
        }

        if (context.Registry is not IRegistryTreeReader reader)
        {
            return "present (sin lector de árbol)";
        }

        var snapshot = TakeSnapshot(reader, hive, deleteAction.KeyPath);
        return snapshot.Summary();
    }

    /// <summary>Instantánea recursiva del subárbol (valores, tipos y subclaves).</summary>
    /// <param name="reader">Lector del árbol de claves del registro.</param>
    /// <param name="hive">Colmena del registro (HKLM, HKCU, etc.).</param>
    /// <param name="keyPath">Ruta de la clave a instantanear.</param>
    /// <param name="limits">Límites opcionales. Si se exceden durante el recorrido,
    /// se lanza <see cref="SnapshotLimitExceededException"/> y se deja de leer.</param>
    public static RegistryKeySnapshot TakeSnapshot(
        IRegistryTreeReader reader, RegistryHive hive, string keyPath,
        RegistrySnapshotLimits? limits = null)
    {
        ArgumentNullException.ThrowIfNull(reader);

        var kinds = reader as IRegistryKindReader;
        var lim = limits;

        // Contadores acumulativos durante el recorrido para abortar temprano.
        int totalKeys = 1; // la raíz cuenta como clave
        int totalValues = 0;
        int maxDepthReached = 0;

        RegistryKeyNode Walk(string path, int depth)
        {
            maxDepthReached = Math.Max(maxDepthReached, depth);

            // Aborto temprano por profundidad: si ya estamos por encima del límite,
            // no seguimos leyendo este nodo ni sus hijos.
            if (lim is not null && depth > lim.MaxDepth)
            {
                throw new SnapshotLimitExceededException(
                    $"Límite de profundidad excedido: {depth} > {lim.MaxDepth}");
            }

            var values = new List<RegistryValueSnapshot>();
            foreach (var name in reader.GetValueNames(hive, path))
            {
                var value = reader is IRegistryAccessor accessor
                    ? accessor.GetValue(hive, path, name)
                    : null;
                var kind = kinds is null ? RegistryValueKind.Unknown : kinds.GetKind(hive, path, name);
                values.Add(new RegistryValueSnapshot(name, value, kind));
                totalValues++;
                if (lim is not null && totalValues > lim.MaxValues)
                {
                    throw new SnapshotLimitExceededException(
                        $"Límite de valores excedido: {totalValues} > {lim.MaxValues}");
                }
            }

            var children = new List<RegistryKeyNode>();
            // Tope duro de recursión del propio recorrido: los límites de tamaño
            // se comprueban durante el recorrido, pero un árbol patológico no debe
            // poder colgar el recorrido.
            IReadOnlyList<string> childNames = depth >= 64
                ? Array.Empty<string>()
                : reader.GetSubKeyNames(hive, path);

            foreach (var child in childNames.OrderBy(c => c, StringComparer.OrdinalIgnoreCase))
            {
                totalKeys++;
                if (lim is not null && totalKeys > lim.MaxKeys)
                {
                    throw new SnapshotLimitExceededException(
                        $"Límite de claves excedido: {totalKeys} > {lim.MaxKeys}");
                }

                children.Add(Walk($"{path}\\{child}", depth + 1));
            }

            return new RegistryKeyNode(path, values, children);
        }

        var root = Walk(keyPath, 0);

        // Comprobación final de profundidad (Deepest) por si el límite de
        // profundidad se excede sin haber entrado a un nodo hijo adicional.
        if (lim is not null && maxDepthReached > lim.MaxDepth)
        {
            throw new SnapshotLimitExceededException(
                $"Límite de profundidad excedido: {maxDepthReached} > {lim.MaxDepth}");
        }

        return new RegistryKeySnapshot(root);
    }

    private static string Describe(RegistryDeleteKeyAction action) =>
        $"Borrar clave {action.Hive}\\{action.KeyPath}" +
        (action.Recursive ? " (con subárbol)" : string.Empty);
}

/// <summary>Un valor del registro dentro de una instantánea.</summary>
public sealed record RegistryValueSnapshot(string Name, object? Value, RegistryValueKind Kind);

/// <summary>Una clave del registro dentro de una instantánea.</summary>
public sealed record RegistryKeyNode(
    string Path,
    IReadOnlyList<RegistryValueSnapshot> Values,
    IReadOnlyList<RegistryKeyNode> Children);

/// <summary>
/// Instantánea completa de un subárbol: suficiente para recrearlo con los mismos
/// tipos y datos (ADR-0005).
/// </summary>
public sealed record RegistryKeySnapshot(RegistryKeyNode Root)
{
    /// <summary>Número total de valores de la instantánea.</summary>
    public int ValueCount => CountValues(Root);

    /// <summary>Número total de claves de la instantánea (incluida la raíz).</summary>
    public int KeyCount => CountKeys(Root);

    private static int CountValues(RegistryKeyNode node) =>
        node.Values.Count + node.Children.Sum(CountValues);

    private static int CountKeys(RegistryKeyNode node) => 1 + node.Children.Sum(CountKeys);

    /// <summary>Motivo por el que la instantánea no cabe en los límites, o null.</summary>
    public string? Exceeds(RegistrySnapshotLimits limits)
    {
        ArgumentNullException.ThrowIfNull(limits);

        if (Deepest(Root) > limits.MaxDepth)
        {
            return $"profundidad {Deepest(Root)} > {limits.MaxDepth}";
        }

        if (ValueCount > limits.MaxValues)
        {
            return $"{ValueCount} valores > {limits.MaxValues}";
        }

        if (KeyCount > limits.MaxKeys)
        {
            return $"{KeyCount} claves > {limits.MaxKeys}";
        }

        return null;
    }

    private static int Deepest(RegistryKeyNode node) =>
        node.Children.Count == 0 ? 0 : 1 + node.Children.Max(Deepest);

    /// <summary>Resumen legible para el diario y los informes.</summary>
    public string Summary() => $"{KeyCount} claves / {ValueCount} valores";
}
