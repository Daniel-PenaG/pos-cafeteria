"""Permisos de acción independientes de módulos (sincronizar con permissions.js)."""

COBRAR_DESDE_COMANDERA = "COBRAR_DESDE_COMANDERA"
CANCELAR_PRODUCTO_EN_COMANDA = "CANCELAR_PRODUCTO_EN_COMANDA"
ABRIR_CAJA = "ABRIR_CAJA"
REGISTRAR_MOVIMIENTO_CAJA = "REGISTRAR_MOVIMIENTO_CAJA"
CERRAR_CAJA = "CERRAR_CAJA"
REVISAR_CIERRE_CAJA = "REVISAR_CIERRE_CAJA"
ANULAR_CIERRE_CAJA = "ANULAR_CIERRE_CAJA"
FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS = "FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS"
TESORERIA_VER = "TESORERIA_VER"
TESORERIA_TRASPASAR = "TESORERIA_TRASPASAR"
TESORERIA_REGISTRAR_GASTO = "TESORERIA_REGISTRAR_GASTO"
TESORERIA_APORTAR = "TESORERIA_APORTAR"
TESORERIA_RETIRAR = "TESORERIA_RETIRAR"
TESORERIA_CONCILIAR = "TESORERIA_CONCILIAR"
TESORERIA_AJUSTAR = "TESORERIA_AJUSTAR"
TESORERIA_REVERTIR = "TESORERIA_REVERTIR"
TESORERIA_ACTIVAR = "TESORERIA_ACTIVAR"

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
    {
        "codigo": ABRIR_CAJA,
        "label": "Abrir caja",
        "descripcion": "Permite abrir una sesión de caja con fondo inicial.",
    },
    {
        "codigo": REGISTRAR_MOVIMIENTO_CAJA,
        "label": "Registrar movimiento de caja",
        "descripcion": "Permite entradas, retiros, gastos de caja y devoluciones.",
    },
    {
        "codigo": CERRAR_CAJA,
        "label": "Cerrar caja",
        "descripcion": "Permite iniciar arqueo y cerrar la propia sesión de caja.",
    },
    {
        "codigo": REVISAR_CIERRE_CAJA,
        "label": "Revisar cierre de caja",
        "descripcion": "Permite marcar un cierre como revisado (administración).",
    },
    {
        "codigo": ANULAR_CIERRE_CAJA,
        "label": "Anular cierre de caja",
        "descripcion": "Permite anular una sesión de caja con motivo.",
    },
    {
        "codigo": FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS,
        "label": "Forzar cierre con pedidos abiertos",
        "descripcion": "Permite cerrar caja dejando pedidos ABIERTOS. No cobra ni cancela.",
    },
    {"codigo": TESORERIA_VER, "label": "Ver tesorería", "descripcion": "Consulta saldos y movimientos."},
    {"codigo": TESORERIA_TRASPASAR, "label": "Traspasar", "descripcion": "Mueve dinero entre ubicaciones."},
    {"codigo": TESORERIA_REGISTRAR_GASTO, "label": "Registrar gasto de tesorería", "descripcion": "Registra un gasto pagado desde una cuenta."},
    {"codigo": TESORERIA_APORTAR, "label": "Aportar", "descripcion": "Registra aportación del propietario."},
    {"codigo": TESORERIA_RETIRAR, "label": "Retirar", "descripcion": "Registra retiro del propietario."},
    {"codigo": TESORERIA_CONCILIAR, "label": "Conciliar", "descripcion": "Registra una conciliación sin ajustar sola."},
    {"codigo": TESORERIA_AJUSTAR, "label": "Ajustar tesorería", "descripcion": "Confirma sobrante o faltante."},
    {"codigo": TESORERIA_REVERTIR, "label": "Revertir tesorería", "descripcion": "Crea la reversa de una operación."},
    {"codigo": TESORERIA_ACTIVAR, "label": "Activar tesorería", "descripcion": "Activa el libro con saldos iniciales."},
]

ALL_ACCIONES = [a["codigo"] for a in ACCIONES_CATALOGO]

# ADMIN tiene todas. CAJERO cobra desde Ventas (módulo), no necesita COBRAR_DESDE_COMANDERA.
# COCINA no opera caja.
ROLE_DEFAULT_ACCIONES = {
    "ADMIN": list(ALL_ACCIONES),
    "CAJERO": [
        ABRIR_CAJA,
        REGISTRAR_MOVIMIENTO_CAJA,
        CERRAR_CAJA,
        TESORERIA_VER,
        TESORERIA_REGISTRAR_GASTO,
    ],
    "COCINA": [],
}

ORIGEN_VENTAS = "VENTAS"
ORIGEN_COMANDERA = "COMANDERA"
ORIGENES_COBRO = (ORIGEN_VENTAS, ORIGEN_COMANDERA)
