from typing import List

from sqlalchemy.orm import Session

from app.models import CategoriaExtraModel, ExtraVentaModel, ProductoModel
from app.schemas.ventas import ExtraVenta
from app.services.extras_precio import precio_desde_modelo


def extras_para_categoria(db: Session, id_categoria: int) -> List[ExtraVenta]:
    enlaces = (
        db.query(CategoriaExtraModel.id_extra)
        .filter(CategoriaExtraModel.id_categoria == id_categoria)
        .all()
    )
    if not enlaces:
        return []

    ids = [e[0] for e in enlaces]
    extras = (
        db.query(ExtraVentaModel)
        .filter(
            ExtraVentaModel.id_extra.in_(ids),
            ExtraVentaModel.activo == True,
        )
        .order_by(ExtraVentaModel.tipo, ExtraVentaModel.nombre)
        .all()
    )
    return [
        ExtraVenta(
            id_extra=e.id_extra,
            nombre=e.nombre,
            precio=precio_desde_modelo(e),
            tipo=e.tipo,
            activo=e.activo,
        )
        for e in extras
    ]


def extras_para_producto(db: Session, id_producto: int) -> List[ExtraVenta]:
    producto = (
        db.query(ProductoModel).filter(ProductoModel.id_producto == id_producto).first()
    )
    if not producto:
        return []
    return extras_para_categoria(db, producto.id_categoria)
