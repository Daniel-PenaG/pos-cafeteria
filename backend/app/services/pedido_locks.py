"""Bloqueos de pedido y detalle. Orden fijo: PedidoModel → DetallePedidoModel."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import DetallePedidoModel, PedidoModel


def _for_update(db: Session, query):
    if db.bind.dialect.name != "sqlite":
        return query.with_for_update()
    return query


def lock_pedido(db: Session, id_pedido: int) -> PedidoModel | None:
    q = db.query(PedidoModel).filter(PedidoModel.id_pedido == id_pedido)
    return _for_update(db, q).first()


def lock_detalle(db: Session, id_detalle: int) -> DetallePedidoModel | None:
    q = db.query(DetallePedidoModel).filter(
        DetallePedidoModel.id_detalle_pedido == id_detalle
    )
    return _for_update(db, q).first()


def lock_detalles_de_pedido(db: Session, id_pedido: int) -> list[DetallePedidoModel]:
    q = (
        db.query(DetallePedidoModel)
        .filter(DetallePedidoModel.id_pedido == id_pedido)
        .order_by(DetallePedidoModel.id_detalle_pedido)
    )
    return _for_update(db, q).all()


def lock_pedido_y_detalle(
    db: Session, id_detalle: int
) -> tuple[PedidoModel | None, DetallePedidoModel | None]:
    """Obtiene id_pedido sin bloqueo; luego Pedido y Detalle con FOR UPDATE."""
    peek = (
        db.query(DetallePedidoModel.id_pedido)
        .filter(DetallePedidoModel.id_detalle_pedido == id_detalle)
        .first()
    )
    if not peek:
        return None, None
    pedido = lock_pedido(db, int(peek[0]))
    if not pedido:
        return None, None
    detalle = lock_detalle(db, id_detalle)
    return pedido, detalle
