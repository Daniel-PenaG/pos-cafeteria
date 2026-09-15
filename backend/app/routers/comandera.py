from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_
from typing import List
from app.database import get_db
from app.models.models import DetallePedidoModel, PedidoModel, UsuarioModel
from app.schemas.pedido import ComandaLinea, ComandaMarcarListo
from app.services.cancelacion_service import (
    cancelaciones_pendientes_comandera,
    marcar_cancelacion_vista,
    marcar_linea_comanda_listo,
)
from app.services.pedido_service import _parse_extras
from app.utils.deps import get_current_user
from app.utils.permisos import require_module
from app.utils.timezone_mx import isoformat_utc, segundos_desde

router = APIRouter(
    prefix="/comandera",
    tags=["Comandera"],
    dependencies=[Depends(require_module("/comandera"))],
)


def _pedido_visible_en_comandera(pedido: PedidoModel) -> bool:
    """Productos pendientes: ABIERTO, o para llevar COBRADO aún en preparación."""
    if pedido.estado == "CANCELADO":
        return False
    if pedido.estado == "ABIERTO":
        return True
    if pedido.estado == "COBRADO" and bool(getattr(pedido, "para_llevar", False)):
        return True
    return False


def _pedido_permite_marcar_listo(pedido: PedidoModel) -> bool:
    return _pedido_visible_en_comandera(pedido)


def _linea_comanda(detalle: DetallePedidoModel, pedido: PedidoModel) -> dict:
    cant = float(detalle.cantidad)
    lista = float(detalle.cantidad_lista or 0)
    return {
        "id_detalle_pedido": detalle.id_detalle_pedido,
        "id_pedido": detalle.id_pedido,
        "numero_mesa": pedido.numero_mesa,
        "para_llevar": bool(getattr(pedido, "para_llevar", False)),
        "nombre_producto": detalle.nombre_producto,
        "cantidad": cant,
        "cantidad_lista": lista,
        "cantidad_pendiente": max(0, cant - lista),
        "extras": _parse_extras(detalle.extras_json),
        "nombre_promocion": detalle.nombre_promocion,
        "comentario": detalle.comentario,
        "fecha_envio_comanda": isoformat_utc(detalle.fecha_envio_comanda),
        "segundos_en_preparacion": segundos_desde(detalle.fecha_envio_comanda),
        "tipo": "PENDIENTE",
        "estado_pedido": pedido.estado,
        "cuenta_cobrada": pedido.estado == "COBRADO",
    }


@router.get("/pendientes", response_model=List[ComandaLinea])
def listar_pendientes(db: Session = Depends(get_db)):
    lineas = (
        db.query(DetallePedidoModel)
        .join(PedidoModel)
        .options(joinedload(DetallePedidoModel.pedido))
        .filter(
            DetallePedidoModel.en_comanda == True,
            PedidoModel.estado != "CANCELADO",
            or_(
                PedidoModel.estado == "ABIERTO",
                and_(PedidoModel.estado == "COBRADO", PedidoModel.para_llevar == True),
            ),
        )
        .order_by(DetallePedidoModel.fecha_envio_comanda.asc())
        .all()
    )
    res = []
    for d in lineas:
        cant = float(d.cantidad)
        lista = float(d.cantidad_lista or 0)
        pendiente = cant - lista
        if pendiente <= 0:
            continue
        if getattr(d, "estado_linea", "ACTIVA") == "CANCELADA":
            continue
        res.append(_linea_comanda(d, d.pedido))
    for c in cancelaciones_pendientes_comandera(db):
        pedido = c.pedido
        if not pedido:
            continue
        det = c.detalle
        res.append(
            {
                "id_detalle_pedido": c.id_detalle_pedido,
                "id_pedido": c.id_pedido,
                "numero_mesa": pedido.numero_mesa,
                "para_llevar": bool(getattr(pedido, "para_llevar", False)),
                "nombre_producto": det.nombre_producto if det else "Producto",
                "cantidad": float(c.cantidad_anterior),
                "cantidad_lista": 0,
                "cantidad_pendiente": float(c.cantidad),
                "extras": _parse_extras(det.extras_json) if det else [],
                "nombre_promocion": det.nombre_promocion if det else None,
                "comentario": det.comentario if det else None,
                "fecha_envio_comanda": isoformat_utc(c.fecha_hora),
                "segundos_en_preparacion": segundos_desde(c.fecha_hora),
                "tipo": "CANCELACION",
                "aviso": c.aviso,
                "aviso_texto": c.aviso_texto,
                "cantidad_anterior": float(c.cantidad_anterior),
                "cantidad_nueva": float(c.cantidad_nueva),
                "id_cancelacion": c.id_cancelacion,
                "vista_comandera": bool(c.vista_comandera),
                "estado_pedido": pedido.estado,
                "cuenta_cobrada": pedido.estado == "COBRADO",
            }
        )
    return res


@router.post("/lineas/{id_detalle_pedido}/listo", response_model=ComandaLinea)
def marcar_listo(id_detalle_pedido: int, data: ComandaMarcarListo, db: Session = Depends(get_db)):
    detalle = marcar_linea_comanda_listo(
        db,
        id_detalle=id_detalle_pedido,
        cantidad=data.cantidad,
        cantidad_actual=data.cantidad_actual,
        cantidad_lista_actual=data.cantidad_lista_actual,
        pedido_permite_listo=_pedido_permite_marcar_listo,
    )
    return _linea_comanda(detalle, detalle.pedido)


@router.post("/cancelaciones/{id_cancelacion}/visto")
def marcar_cancelacion_atendida(
    id_cancelacion: int,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    return marcar_cancelacion_vista(db, id_cancelacion=id_cancelacion, current=current)
