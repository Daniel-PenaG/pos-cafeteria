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
)
from app.services.pedido_service import _parse_extras
from app.exceptions import RecursoNoEncontradoException, DatosInvalidosException
from app.utils.deps import get_current_user
from app.utils.permisos import require_module
from app.utils.timezone_mx import isoformat_utc, now_utc_naive, segundos_desde

router = APIRouter(
    prefix="/comandera",
    tags=["Comandera"],
    dependencies=[Depends(require_module("/comandera"))],
)


def _pedido_visible_en_comandera(pedido: PedidoModel) -> bool:
    """Pedidos ABIERTO o para llevar COBRADO con preparación pendiente."""
    if pedido.estado == "CANCELADO":
        return False
    if pedido.estado == "ABIERTO":
        return True
    if pedido.estado == "COBRADO" and bool(getattr(pedido, "para_llevar", False)):
        return True
    return False


def _pedido_permite_marcar_listo(pedido: PedidoModel) -> bool:
    return _pedido_visible_en_comandera(pedido)


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
        res.append(
            {
                "id_detalle_pedido": d.id_detalle_pedido,
                "id_pedido": d.id_pedido,
                "numero_mesa": d.pedido.numero_mesa,
                "para_llevar": bool(getattr(d.pedido, "para_llevar", False)),
                "nombre_producto": d.nombre_producto,
                "cantidad": cant,
                "cantidad_lista": lista,
                "cantidad_pendiente": pendiente,
                "extras": _parse_extras(d.extras_json),
                "nombre_promocion": d.nombre_promocion,
                "comentario": d.comentario,
                "fecha_envio_comanda": isoformat_utc(d.fecha_envio_comanda),
                "segundos_en_preparacion": segundos_desde(d.fecha_envio_comanda),
                "tipo": "PENDIENTE",
            }
        )
    for c in cancelaciones_pendientes_comandera(db):
        pedido = c.pedido
        if not pedido or not _pedido_visible_en_comandera(pedido):
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
            }
        )
    return res


@router.post("/lineas/{id_detalle_pedido}/listo", response_model=ComandaLinea)
def marcar_listo(id_detalle_pedido: int, data: ComandaMarcarListo, db: Session = Depends(get_db)):
    detalle = (
        db.query(DetallePedidoModel)
        .options(joinedload(DetallePedidoModel.pedido))
        .filter(DetallePedidoModel.id_detalle_pedido == id_detalle_pedido)
        .first()
    )
    if not detalle:
        raise RecursoNoEncontradoException("Línea no encontrada")
    if not _pedido_permite_marcar_listo(detalle.pedido):
        raise DatosInvalidosException("Pedido ya cerrado")

    cant = float(detalle.cantidad)
    lista = float(detalle.cantidad_lista or 0)
    pendiente = cant - lista
    if pendiente <= 0:
        raise DatosInvalidosException("Esta línea ya está completa en comanda")

    avanzar = min(float(data.cantidad), pendiente)
    if avanzar <= 0:
        raise DatosInvalidosException("Cantidad inválida")

    detalle.cantidad_lista = lista + avanzar
    if float(detalle.cantidad_lista) >= cant:
        detalle.fecha_listo_comanda = now_utc_naive()
    db.commit()
    db.refresh(detalle)

    lista = float(detalle.cantidad_lista)
    return {
        "id_detalle_pedido": detalle.id_detalle_pedido,
        "id_pedido": detalle.id_pedido,
        "numero_mesa": detalle.pedido.numero_mesa,
        "para_llevar": bool(getattr(detalle.pedido, "para_llevar", False)),
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
    }


@router.post("/cancelaciones/{id_cancelacion}/visto")
def marcar_cancelacion_atendida(
    id_cancelacion: int,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    return marcar_cancelacion_vista(db, id_cancelacion=id_cancelacion, current=current)
