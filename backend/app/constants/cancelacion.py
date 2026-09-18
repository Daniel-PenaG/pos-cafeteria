"""Motivos y estados de cancelación de líneas de pedido."""

ESTADO_ACTIVA = "ACTIVA"
ESTADO_CANCELADA = "CANCELADA"

MOTIVO_DUPLICADO = "Producto duplicado"
MOTIVO_CAPTURA = "Error de captura"
MOTIVO_CLIENTE = "Cambio solicitado por cliente"
MOTIVO_NO_DISPONIBLE = "Producto no disponible"
MOTIVO_OTRO = "Otro"

MOTIVOS_CANCELACION = [
    MOTIVO_DUPLICADO,
    MOTIVO_CAPTURA,
    MOTIVO_CLIENTE,
    MOTIVO_NO_DISPONIBLE,
    MOTIVO_OTRO,
]

AVISO_CANCELADO = "CANCELADO"
AVISO_CANCELAR_UNIDAD = "CANCELAR_UNIDAD"
AVISO_CAMBIO_CANTIDAD = "CAMBIO_CANTIDAD"

MSG_ENVIADA = "El producto ya fue enviado a comandera. Registra una cancelación."
MSG_SIN_PERMISO = "No tienes permiso para cancelar productos enviados."
MSG_COBRADO = "El pedido ya fue cobrado y no puede modificarse."
MSG_STALE = "La cantidad cambió en otro dispositivo. Actualiza el pedido."
MSG_COMANDA_STALE = "La línea cambió en otro dispositivo. Actualiza la comandera."
MSG_NEGATIVA = "La cantidad no puede ser negativa"
MSG_LINEA_CANCELADA = "La línea ya está cancelada"


def aviso_cancelacion(cantidad_anterior: float, cantidad_nueva: float, cantidad_cancelada: float) -> tuple[str, str]:
    if cantidad_nueva <= 0:
        return AVISO_CANCELADO, "CANCELADO"
    if float(cantidad_cancelada) == 1:
        if float(cantidad_anterior) == 2:
            return AVISO_CAMBIO_CANTIDAD, "CANTIDAD CAMBIÓ DE 2 A 1"
        return AVISO_CANCELAR_UNIDAD, "CANCELAR 1 UNIDAD"
    ant = int(cantidad_anterior) if float(cantidad_anterior).is_integer() else cantidad_anterior
    nueva = int(cantidad_nueva) if float(cantidad_nueva).is_integer() else cantidad_nueva
    return AVISO_CAMBIO_CANTIDAD, f"CANTIDAD CAMBIÓ DE {ant} A {nueva}"
