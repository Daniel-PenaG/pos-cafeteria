"""Rutas de módulos del frontend (deben coincidir con permissions.js)."""

MODULOS_CATALOGO = [
    {"path": "/dashboard", "label": "Dashboard", "grupo": "Inicio"},
    {"path": "/categorias", "label": "Categorías", "grupo": "Catálogo"},
    {"path": "/productos", "label": "Productos", "grupo": "Catálogo"},
    {"path": "/insumos", "label": "Insumos", "grupo": "Catálogo"},
    {"path": "/recetas", "label": "Recetas", "grupo": "Catálogo"},
    {"path": "/ventas", "label": "Ventas", "grupo": "Operación"},
    {"path": "/ventas-para-llevar", "label": "Para llevar", "grupo": "Operación"},
    {"path": "/comandera", "label": "Comandera", "grupo": "Operación"},
    {"path": "/clientes", "label": "Clientes", "grupo": "Operación"},
    {"path": "/promociones", "label": "Promociones", "grupo": "Operación"},
    {"path": "/extras-venta", "label": "Extras de venta", "grupo": "Operación"},
    {"path": "/para-llevar", "label": "Productos para llevar", "grupo": "Operación"},
    {"path": "/compras", "label": "Compras", "grupo": "Operación"},
    {"path": "/gastos", "label": "Gastos", "grupo": "Operación"},
    {"path": "/cierre-caja", "label": "Cierre de caja", "grupo": "Operación"},
    {"path": "/reportes", "label": "Reportes", "grupo": "Administración"},
    {"path": "/cuentas-cajero", "label": "Cuentas por cajero", "grupo": "Administración"},
    {"path": "/cierres-dia", "label": "Cierres del día", "grupo": "Administración"},
    {"path": "/usuarios", "label": "Usuarios", "grupo": "Administración"},
]

ALL_MODULE_PATHS = [m["path"] for m in MODULOS_CATALOGO]

ROLE_DEFAULT_MODULES = {
    "ADMIN": ALL_MODULE_PATHS,
    "CAJERO": [
        "/dashboard",
        "/ventas",
        "/ventas-para-llevar",
        "/comandera",
        "/clientes",
        "/cierre-caja",
    ],
    "COCINA": ["/comandera"],
}
