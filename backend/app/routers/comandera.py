from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List
from datetime import datetime

from app.database import get_db
from app.models.models import DetallePedidoModel, PedidoModel
from app.schemas.pedido import ComandaLinea, ComandaMarcarListo, _segundos_transcurridos
from app.services.pedido_service import _parse_extras
from app.exceptions import RecursoNoEncontradoException, DatosInvalidosException

router = APIRouter(prefix="/comandera", tags=["Comandera"])


@router.get("/pendientes", response_model=List[ComandaLinea])
def listar_pendientes(db: Session = Depends(get_db)):
    lineas = (
        db.query(DetallePedidoModel)
        .join(PedidoModel)
        .options(joinedload(DetallePedidoModel.pedido))
        .filter(
            PedidoModel.estado == "ABIERTO",
            DetallePedidoModel.en_comanda == True,
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
        res.append(
            {
                "id_detalle_pedido": d.id_detalle_pedido,
                "id_pedido": d.id_pedido,
                "numero_mesa": d.pedido.numero_mesa,
                "nombre_producto": d.nombre_producto,
                "cantidad": cant,
                "cantidad_lista": lista,
                "cantidad_pendiente": pendiente,
                "extras": _parse_extras(d.extras_json),
                "nombre_promocion": d.nombre_promocion,
                "fecha_envio_comanda": d.fecha_envio_comanda,
                "segundos_en_preparacion": _segundos_transcurridos(d.fecha_envio_comanda),
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
    if detalle.pedido.estado != "ABIERTO":
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
        detalle.fecha_listo_comanda = datetime.now()
    db.commit()
    db.refresh(detalle)

    lista = float(detalle.cantidad_lista)
    return {
        "id_detalle_pedido": detalle.id_detalle_pedido,
        "id_pedido": detalle.id_pedido,
        "numero_mesa": detalle.pedido.numero_mesa,
        "nombre_producto": detalle.nombre_producto,
        "cantidad": cant,
        "cantidad_lista": lista,
        "cantidad_pendiente": max(0, cant - lista),
        "extras": _parse_extras(detalle.extras_json),
        "nombre_promocion": detalle.nombre_promocion,
        "fecha_envio_comanda": detalle.fecha_envio_comanda,
        "segundos_en_preparacion": _segundos_transcurridos(detalle.fecha_envio_comanda),
    }
