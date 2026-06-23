from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.database import get_db
from app.models.models import PedidoModel, DetallePedidoModel, ClienteModel
from app.schemas.pedido import (
    Pedido,
    PedidoResumen,
    PedidoLineaCreate,
    PedidoLineaUpdate,
    PedidoClienteUpdate,
    PedidoCobrar,
    DetallePedidoLinea,
)
from app.schemas.ventas import VentaResponse
from app.services.pedido_service import (
    obtener_pedido_abierto_mesa,
    agregar_linea_pedido,
    cobrar_pedido,
    _pedido_a_dict,
    _detalle_a_dict,
)
from app.services.promocion_service import calcular_linea
from app.models import ProductoModel
from app.exceptions import DatosInvalidosException, RecursoNoEncontradoException

router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


@router.get("/activos", response_model=List[PedidoResumen])
def listar_pedidos_activos(db: Session = Depends(get_db)):
    pedidos = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles))
        .filter(PedidoModel.estado == "ABIERTO")
        .order_by(PedidoModel.numero_mesa)
        .all()
    )
    res = []
    for p in pedidos:
        total = sum(float(d.cantidad) * float(d.precio_unitario) for d in p.detalles)
        pendientes = sum(
            1
            for d in p.detalles
            if d.en_comanda and float(d.cantidad_lista or 0) < float(d.cantidad)
        )
        res.append(
            {
                "id_pedido": p.id_pedido,
                "numero_mesa": p.numero_mesa,
                "total": round(total, 2),
                "num_lineas": len(p.detalles),
                "pendientes_comanda": pendientes,
            }
        )
    return res


@router.get("/mesa/{numero_mesa}", response_model=Pedido)
def obtener_pedido_mesa(numero_mesa: int, id_usuario: int, db: Session = Depends(get_db)):
    if numero_mesa < 1:
        raise DatosInvalidosException("Mesa inválida")
    pedido = obtener_pedido_abierto_mesa(db, numero_mesa, id_usuario)
    pedido = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles), joinedload(PedidoModel.cliente))
        .filter(PedidoModel.id_pedido == pedido.id_pedido)
        .first()
    )
    return _pedido_a_dict(pedido)


@router.post("/mesa/{numero_mesa}/lineas", response_model=DetallePedidoLinea)
def agregar_linea(
    numero_mesa: int,
    data: PedidoLineaCreate,
    id_usuario: int,
    db: Session = Depends(get_db),
):
    pedido = obtener_pedido_abierto_mesa(db, numero_mesa, id_usuario)
    detalle = agregar_linea_pedido(db, pedido, data)
    return _detalle_a_dict(detalle)


@router.patch("/lineas/{id_detalle_pedido}", response_model=DetallePedidoLinea)
def actualizar_linea(id_detalle_pedido: int, data: PedidoLineaUpdate, db: Session = Depends(get_db)):
    detalle = db.query(DetallePedidoModel).filter(DetallePedidoModel.id_detalle_pedido == id_detalle_pedido).first()
    if not detalle:
        raise RecursoNoEncontradoException("Línea no encontrada")
    pedido = db.query(PedidoModel).filter(PedidoModel.id_pedido == detalle.id_pedido).first()
    if pedido.estado != "ABIERTO":
        raise DatosInvalidosException("Pedido cerrado")

    if data.cantidad < 1:
        raise DatosInvalidosException("Cantidad inválida")

    if detalle.id_promocion:
        producto = db.query(ProductoModel).filter(ProductoModel.id_producto == detalle.id_producto).first()
        import json
        extras = json.loads(detalle.extras_json) if detalle.extras_json else []
        precio_extras = sum(float(e.get("precio", 0)) for e in extras)
        calc = calcular_linea(db, producto, float(data.cantidad), precio_extras, detalle.id_promocion)
        if not calc["margen_ok"]:
            raise DatosInvalidosException(calc["mensaje"] or "Cantidad no válida para promoción")
        detalle.precio_unitario = calc["precio_unitario"]
        detalle.precio_original = calc["precio_original_unitario"]
        detalle.descuento_unitario = calc["descuento_unitario"]

    if float(data.cantidad) < float(detalle.cantidad_lista or 0):
        detalle.cantidad_lista = data.cantidad

    detalle.cantidad = data.cantidad
    db.commit()
    db.refresh(detalle)
    return _detalle_a_dict(detalle)


@router.delete("/lineas/{id_detalle_pedido}")
def eliminar_linea(id_detalle_pedido: int, db: Session = Depends(get_db)):
    detalle = db.query(DetallePedidoModel).filter(DetallePedidoModel.id_detalle_pedido == id_detalle_pedido).first()
    if not detalle:
        raise RecursoNoEncontradoException("Línea no encontrada")
    pedido = db.query(PedidoModel).filter(PedidoModel.id_pedido == detalle.id_pedido).first()
    if pedido.estado != "ABIERTO":
        raise DatosInvalidosException("Pedido cerrado")
    db.delete(detalle)
    db.commit()
    return {"ok": True}


@router.put("/{id_pedido}/cliente", response_model=Pedido)
def asignar_cliente(id_pedido: int, data: PedidoClienteUpdate, db: Session = Depends(get_db)):
    pedido = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles), joinedload(PedidoModel.cliente))
        .filter(PedidoModel.id_pedido == id_pedido)
        .first()
    )
    if not pedido:
        raise RecursoNoEncontradoException("Pedido no encontrado")
    if pedido.estado != "ABIERTO":
        raise DatosInvalidosException("Pedido cerrado")

    if data.id_cliente:
        cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == data.id_cliente).first()
        if not cliente:
            raise RecursoNoEncontradoException("Cliente no encontrado")
        pedido.id_cliente = data.id_cliente
    else:
        pedido.id_cliente = None

    db.commit()
    db.refresh(pedido)
    return _pedido_a_dict(pedido)


@router.post("/{id_pedido}/cobrar", response_model=VentaResponse)
def cobrar(id_pedido: int, data: PedidoCobrar, db: Session = Depends(get_db)):
    pedido = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles))
        .filter(PedidoModel.id_pedido == id_pedido)
        .first()
    )
    if not pedido:
        raise RecursoNoEncontradoException("Pedido no encontrado")

    if data.id_cliente:
        cliente = db.query(ClienteModel).filter(
            ClienteModel.id_cliente == data.id_cliente, ClienteModel.activo == True
        ).first()
        if not cliente:
            raise RecursoNoEncontradoException("Cliente no encontrado o inactivo")
        pedido.id_cliente = data.id_cliente
    else:
        pedido.id_cliente = None

    db.flush()
    return cobrar_pedido(db, pedido, data.id_usuario, data.forma_pago)
