"""Orden global de bloqueo del cobro.

1. Sesión de caja, si el cajero tiene una.
2. Pedido.
3. Detalles, por id_detalle_pedido.
4. Cliente, si el cobro queda asociado a uno.

La idempotencia, la venta, los pagos y los movimientos van después.
Cancelar no entra aquí: solo toma pedido y detalle.
Cerrar caja solo toma la sesión.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.constants.caja import ESTADO_ABIERTA, MSG_CAJA_CERRANDO, MSG_SIN_CAJA
from app.exceptions import ConflictoOperacionException, DatosInvalidosException
from app.models.models import ClienteModel
from app.services.caja_service import (
    caja_requerida_para_cobrar,
    lock_sesion,
    sesion_activa_usuario,
)


def bloquear_sesion_de_cobro(db: Session, id_usuario: int) -> int | None:
    activa = sesion_activa_usuario(db, id_usuario)
    if not activa:
        if caja_requerida_para_cobrar():
            raise DatosInvalidosException(MSG_SIN_CAJA)
        return None
    locked = lock_sesion(db, activa.id_sesion_caja)
    if not locked or locked.estado != ESTADO_ABIERTA:
        raise ConflictoOperacionException(MSG_CAJA_CERRANDO)
    return locked.id_sesion_caja


def bloquear_cliente_cobro(db: Session, id_cliente: int) -> tuple[ClienteModel | None, int | None]:
    """Lee el saldo y después toma la fila. Si cambió al esperar, el caller distingue 409 de 422."""
    saldo_visto = (
        db.query(ClienteModel.puntos_saldo)
        .filter(ClienteModel.id_cliente == id_cliente)
        .scalar()
    )
    q = db.query(ClienteModel).filter(
        ClienteModel.id_cliente == id_cliente,
        ClienteModel.activo == True,
    )
    if db.bind.dialect.name != "sqlite":
        q = q.with_for_update()
    cliente = q.first()
    visto = int(saldo_visto) if saldo_visto is not None else None
    return cliente, visto
