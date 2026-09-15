"""Permisos de acción independientes de módulos (sincronizar con permissions.js)."""

COBRAR_DESDE_COMANDERA = "COBRAR_DESDE_COMANDERA"
CANCELAR_PRODUCTO_EN_COMANDA = "CANCELAR_PRODUCTO_EN_COMANDA"

ACCIONES_CATALOGO = [
    {
        "codigo": COBRAR_DESDE_COMANDERA,
        "label": "Cobrar desde Comandera",
        "descripcion": "Permite iniciar el cobro de un pedido abierto desde Comandera.",
    },
    {
        "codigo": CANCELAR_PRODUCTO_EN_COMANDA,
        "label": "Cancelar producto en comandera",
        "descripcion": "Permite cancelar o reducir líneas ya enviadas a cocina. No se concede a COCINA por defecto.",
    },
]

ALL_ACCIONES = [a["codigo"] for a in ACCIONES_CATALOGO]

# ADMIN tiene todas. CAJERO cobra desde Ventas (módulo), no necesita esta acción.
# COCINA no cobra salvo que un ADMIN otorgue esta acción.
ROLE_DEFAULT_ACCIONES = {
    "ADMIN": list(ALL_ACCIONES),
    "CAJERO": [],
    "COCINA": [],
}

ORIGEN_VENTAS = "VENTAS"
ORIGEN_COMANDERA = "COMANDERA"
ORIGENES_COBRO = (ORIGEN_VENTAS, ORIGEN_COMANDERA)
