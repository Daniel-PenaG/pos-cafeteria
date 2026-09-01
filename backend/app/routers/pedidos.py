from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.database import get_db
from app.models.models import PedidoModel, DetallePedidoModel, ClienteModel, PromocionModel
from app.schemas.pedido import (
    Pedido,
    PedidoResumen,
    PedidoLineaCreate,
    PedidoLineaUpdate,
    PedidoClienteUpdate,
    PedidoCobrar,
    ComboPedidoCreate,
    DetallePedidoLinea,
)
from app.schemas.ventas import VentaResponse
from app.services.pedido_service import (
    obtener_pedido_abierto_mesa,
    agregar_linea_pedido,
    agregar_combo_pedido,
    cobrar_pedido,
    confirmar_comanda_pedido,
    listar_pedidos_activos_resumen,
    recalcular_promociones_pedido,
    pedido_respuesta,
    _pedido_a_dict,
    _detalle_a_dict,
)
from app.services.venta_service import MESA_PARA_LLEVAR
from app.services.promocion_service import calcular_linea, es_promo_paquete
from app.models import ProductoModel
from app.exceptions import DatosInvalidosException, RecursoNoEncontradoException
from app.utils.deps import require_admin, require_pos
from app.services.mesas_service import obtener_mesas, agregar_mesa, quitar_mesa, validar_mesa_operacion
from app.schemas.mesas import MesasConfigResponse, MesaAgregarRequest

router = APIRouter(
    prefix="/pedidos",
    tags=["Pedidos"],
    dependencies=[Depends(require_pos)],
)


@router.get("/activos", response_model=List[PedidoResumen])
def listar_pedidos_activos(db: Session = Depends(get_db)):
    return listar_pedidos_activos_resumen(db)


@router.get("/mesas", response_model=MesasConfigResponse)
def listar_mesas_configuradas(db: Session = Depends(get_db)):
    return {"mesas": obtener_mesas(db)}


@router.post("/mesas", response_model=MesasConfigResponse, dependencies=[Depends(require_admin)])
def agregar_mesa_config(data: MesaAgregarRequest, db: Session = Depends(get_db)):
    mesas = agregar_mesa(db, data.numero)
    return {"mesas": mesas}


@router.delete("/mesas/{numero_mesa}", response_model=MesasConfigResponse, dependencies=[Depends(require_admin)])
def quitar_mesa_config(numero_mesa: int, db: Session = Depends(get_db)):
    mesas = quitar_mesa(db, numero_mesa)
    return {"mesas": mesas}


@router.get("/mesa/{numero_mesa}", response_model=Pedido)
def obtener_pedido_mesa(
    numero_mesa: int,
    id_usuario: int,
    para_llevar: bool = False,
    db: Session = Depends(get_db),
):
    if para_llevar:
        if numero_mesa != MESA_PARA_LLEVAR:
            raise DatosInvalidosException("Mesa inválida para venta para llevar")
    else:
        validar_mesa_operacion(db, numero_mesa, para_llevar=False)
    pedido = obtener_pedido_abierto_mesa(db, numero_mesa, id_usuario, para_llevar=para_llevar)
    pedido = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles), joinedload(PedidoModel.cliente))
        .filter(PedidoModel.id_pedido == pedido.id_pedido)
        .first()
    )
    return pedido_respuesta(db, pedido)


@router.post("/mesa/{numero_mesa}/lineas", response_model=DetallePedidoLinea)
def agregar_linea(
    numero_mesa: int,
    data: PedidoLineaCreate,
    id_usuario: int,
    para_llevar: bool = False,
    db: Session = Depends(get_db),
):
    if para_llevar:
        if numero_mesa != MESA_PARA_LLEVAR:
            raise DatosInvalidosException("Mesa inválida para venta para llevar")
    else:
        validar_mesa_operacion(db, numero_mesa, para_llevar=False)
    pedido = obtener_pedido_abierto_mesa(db, numero_mesa, id_usuario, para_llevar=para_llevar)
    detalle = agregar_linea_pedido(db, pedido, data)
    return _detalle_a_dict(detalle)


@router.post("/mesa/{numero_mesa}/combo", response_model=List[DetallePedidoLinea])
def agregar_combo(
    numero_mesa: int,
    data: ComboPedidoCreate,
    id_usuario: int,
    para_llevar: bool = False,
    db: Session = Depends(get_db),
):
    if para_llevar:
        if numero_mesa != MESA_PARA_LLEVAR:
            raise DatosInvalidosException("Mesa inválida para venta para llevar")
    else:
        validar_mesa_operacion(db, numero_mesa, para_llevar=False)
    pedido = obtener_pedido_abierto_mesa(db, numero_mesa, id_usuario, para_llevar=para_llevar)
    detalles = agregar_combo_pedido(
        db, pedido, data.id_promocion, data.cantidad, data.enviar_comanda
    )
    return [_detalle_a_dict(d) for d in detalles]


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
        promo = (
            db.query(PromocionModel)
            .options(joinedload(PromocionModel.productos))
            .filter(PromocionModel.id_promocion == detalle.id_promocion)
            .first()
        )
        if promo and es_promo_paquete(promo):
            raise DatosInvalidosException(
                "No se puede cambiar la cantidad de una línea de paquete; agrega otro paquete"
            )
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
    return pedido_respuesta(db, pedido)


@router.post("/{id_pedido}/confirmar-comanda", response_model=Pedido)
def confirmar_comanda(id_pedido: int, db: Session = Depends(get_db)):
    pedido = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles), joinedload(PedidoModel.cliente))
        .filter(PedidoModel.id_pedido == id_pedido)
        .first()
    )
    if not pedido:
        raise RecursoNoEncontradoException("Pedido no encontrado")
    confirmar_comanda_pedido(db, pedido)
    db.refresh(pedido)
    return pedido_respuesta(db, pedido)


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
