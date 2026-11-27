namespace Evo.App;

/// <summary>Títulos exactos de las 17 secciones del inventario de usuario.</summary>
/// <remarks>
/// Coinciden con <c>docs/requirements/INVENTARIO_USUARIO.md</c> y con el
/// catálogo de capacidades (<c>catalog/capabilities/section*.json</c>).
/// </remarks>
public static partial class SectionTitles
{
    private static readonly Dictionary<string, string> _titles = new(StringComparer.OrdinalIgnoreCase)
    {
        ["1"] = "LIMPIEZA Y ELIMINACIÓN DE COMPONENTES",
        ["2"] = "DEBLOAT DE WINDOWS",
        ["3"] = "TELEMETRÍA Y PRIVACIDAD",
        ["4"] = "OPTIMIZACIÓN DE SERVICIOS",
        ["5"] = "OPTIMIZACIÓN DE CPU Y RENDIMIENTO",
        ["6"] = "OPTIMIZACIÓN GAMING",
        ["7"] = "MEMORIA Y APLICACIONES EN SEGUNDO PLANO",
        ["8"] = "ADMINISTRACIÓN DE INICIO Y APAGADO",
        ["9"] = "REGISTRO DE WINDOWS Y CONFIGURACIÓN DEL SISTEMA",
        ["10"] = "EXPLORADOR DE ARCHIVOS E INTERFAZ",
        ["11"] = "RED Y CONECTIVIDAD",
        ["12"] = "WINDOWS UPDATE Y MANTENIMIENTO",
        ["13"] = "SEGURIDAD Y PROTECCIÓN",
        ["14"] = "REPARACIÓN Y DIAGNÓSTICO",
        ["15"] = "ADMINISTRACIÓN DE APLICACIONES",
        ["16"] = "FUNCIONES DE INSTALACIÓN Y ADMINISTRACIÓN AVANZADA",
        ["17"] = "CAPACIDADES ADICIONALES QUE NO DEBEMOS PERDER",
    };

    /// <summary>Obtiene el título de una sección por su identificador (cadena).</summary>
    public static string this[string sectionId] => _titles[sectionId];

    /// <summary>Identificadores de sección ordenados (1-17).</summary>
    public static IReadOnlyList<string> Ids => _titles.Keys.OrderBy(int.Parse).ToList();
}
