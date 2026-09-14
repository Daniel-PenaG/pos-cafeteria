from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from app.constants import auditoria as A
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
    buscar_pedido_abierto_mesa,
    pedido_vacio_mesa,
    agregar_linea_pedido_con_respuesta,
    agregar_combo_pedido,
    cobrar_pedido,
    confirmar_comanda_pedido,
    listar_pedidos_activos_resumen,
    pedido_respuesta,
    pedido_respuesta_lectura,
    _detalle_a_dict,
    _line_key,
    _parse_extras,
)
from app.services.venta_service import MESA_PARA_LLEVAR
from app.services.promocion_service import calcular_linea, es_promo_paquete
from app.models import ProductoModel
from app.exceptions import DatosInvalidosException, RecursoNoEncontradoException
from app.models.models import UsuarioModel
from app.services.auditoria_service import registrar_auditoria
from app.utils.cobro_auth import autorizar_cobro
from app.utils.deps import get_current_user, require_admin
from app.utils.identidad import id_usuario_autenticado
from app.utils.permisos import require_module
from app.services.mesas_service import obtener_mesas, agregar_mesa, quitar_mesa, validar_mesa_operacion
from app.schemas.mesas import MesasConfigResponse, MesaAgregarRequest

_mod_ventas = Depends(require_module("/ventas", "/mesas-activas", "/ventas-para-llevar"))

router = APIRouter(
    prefix="/pedidos",
    tags=["Pedidos"],
    dependencies=[Depends(get_current_user)],
)


def _meta(request: Request) -> dict:
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


@router.get("/activos", response_model=List[PedidoResumen], dependencies=[_mod_ventas])
def listar_pedidos_activos(db: Session = Depends(get_db)):
    return listar_pedidos_activos_resumen(db)


@router.get("/mesas", response_model=MesasConfigResponse, dependencies=[_mod_ventas])
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


@router.get("/mesa/{numero_mesa}", response_model=Pedido, dependencies=[_mod_ventas])
def obtener_pedido_mesa(
    numero_mesa: int,
    para_llevar: bool = False,
    id_usuario: Optional[int] = None,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    uid = id_usuario_autenticado(db, current, id_usuario, "pedidos.get_mesa")
    if para_llevar:
        if numero_mesa != MESA_PARA_LLEVAR:
            raise DatosInvalidosException("Mesa inválida para venta para llevar")
    else:
        validar_mesa_operacion(db, numero_mesa, para_llevar=False)
    pedido = buscar_pedido_abierto_mesa(db, numero_mesa, para_llevar=para_llevar)
    if not pedido:
        return pedido_vacio_mesa(numero_mesa, uid, para_llevar=para_llevar)
    return pedido_respuesta_lectura(db, pedido)


@router.post("/mesa/{numero_mesa}/lineas", response_model=Pedido, dependencies=[_mod_ventas])
def agregar_linea(
    numero_mesa: int,
    data: PedidoLineaCreate,
    id_usuario: Optional[int] = None,
    para_llevar: bool = False,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    uid = id_usuario_autenticado(db, current, id_usuario, "pedidos.agregar_linea")
    if para_llevar:
        if numero_mesa != MESA_PARA_LLEVAR:
            raise DatosInvalidosException("Mesa inválida para venta para llevar")
    else:
        validar_mesa_operacion(db, numero_mesa, para_llevar=False)
    existia = buscar_pedido_abierto_mesa(db, numero_mesa, para_llevar=para_llevar)
    pedido = obtener_pedido_abierto_mesa(db, numero_mesa, uid, para_llevar=para_llevar)
    if existia is None:
        registrar_auditoria(
            db,
            usuario=current,
            accion=A.PEDIDO_ABIERTO,
            entidad="pedido",
            entidad_id=pedido.id_pedido,
            detalles={"numero_mesa": numero_mesa, "para_llevar": para_llevar},
            origen="VENTAS",
        )
    pedido_resp, _ = agregar_linea_pedido_con_respuesta(db, pedido, data)
    return pedido_resp


@router.post("/mesa/{numero_mesa}/combo", response_model=Pedido, dependencies=[_mod_ventas])
def agregar_combo(
    numero_mesa: int,
    data: ComboPedidoCreate,
    id_usuario: Optional[int] = None,
    para_llevar: bool = False,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    uid = id_usuario_autenticado(db, current, id_usuario, "pedidos.agregar_combo")
    if para_llevar:
        if numero_mesa != MESA_PARA_LLEVAR:
            raise DatosInvalidosException("Mesa inválida para venta para llevar")
    else:
        validar_mesa_operacion(db, numero_mesa, para_llevar=False)
    existia = buscar_pedido_abierto_mesa(db, numero_mesa, para_llevar=para_llevar)
    pedido = obtener_pedido_abierto_mesa(db, numero_mesa, uid, para_llevar=para_llevar)
    if existia is None:
        registrar_auditoria(
            db,
            usuario=current,
            accion=A.PEDIDO_ABIERTO,
            entidad="pedido",
            entidad_id=pedido.id_pedido,
            detalles={"numero_mesa": numero_mesa, "para_llevar": para_llevar},
            origen="VENTAS",
        )
    return agregar_combo_pedido(
        db,
        pedido,
        data.id_promocion,
        data.cantidad,
        data.enviar_comanda,
        operation_id=data.operation_id,
    )


@router.patch("/lineas/{id_detalle_pedido}", response_model=DetallePedidoLinea, dependencies=[_mod_ventas])
def actualizar_linea(id_detalle_pedido: int, data: PedidoLineaUpdate, db: Session = Depends(get_db)):
    detalle = db.query(DetallePedidoModel).filter(DetallePedidoModel.id_detalle_pedido == id_detalle_pedido).first()
    if not detalle:
        raise RecursoNoEncontradoException("Línea no encontrada")
    pedido = db.query(PedidoModel).filter(PedidoModel.id_pedido == detalle.id_pedido).first()
    if pedido.estado != "ABIERTO":
        raise DatosInvalidosException("Pedido cerrado")
    if data.cantidad is None and data.comentario is None:
        raise DatosInvalidosException("Indica cantidad o comentario")

    if data.cantidad is not None:
        if data.cantidad < 1:
            raise DatosInvalidosException("Cantidad inválida")

    if data.comentario is not None:
        comentario = (data.comentario or "").strip() or None
        detalle.comentario = comentario
        extras = _parse_extras(detalle.extras_json)
        class _Extra:
            def __init__(self, e):
                self.id_extra = e.get("id_extra")
        detalle.line_key = _line_key(
            detalle.id_producto,
            [_Extra(e) for e in extras],
            detalle.id_promocion,
            comentario,
        )

    if data.cantidad is None:
        db.commit()
        db.refresh(detalle)
        return _detalle_a_dict(detalle)

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


@router.delete("/lineas/{id_detalle_pedido}", dependencies=[_mod_ventas])
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


@router.put("/{id_pedido}/cliente", response_model=Pedido, dependencies=[_mod_ventas])
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


@router.post("/{id_pedido}/confirmar-comanda", response_model=Pedido, dependencies=[_mod_ventas])
def confirmar_comanda(
    id_pedido: int,
    request: Request,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    pedido = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles), joinedload(PedidoModel.cliente))
        .filter(PedidoModel.id_pedido == id_pedido)
        .first()
    )
    if not pedido:
        raise RecursoNoEncontradoException("Pedido no encontrado")
    enviadas = confirmar_comanda_pedido(db, pedido)
    registrar_auditoria(
        db,
        usuario=current,
        accion=A.COMANDA_ENVIADA,
        entidad="pedido",
        entidad_id=pedido.id_pedido,
        detalles={"lineas": enviadas},
        origen="VENTAS",
        **_meta(request),
    )
    db.commit()
    db.refresh(pedido)
    return pedido_respuesta(db, pedido)


@router.post("/{id_pedido}/cobrar", response_model=VentaResponse)
def cobrar(
    id_pedido: int,
    data: PedidoCobrar,
    request: Request,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    uid = id_usuario_autenticado(db, current, data.id_usuario, "pedidos.cobrar")
    origen = autorizar_cobro(current, data.origen)
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
    venta = cobrar_pedido(db, pedido, uid, data.forma_pago, origen_cobro=origen)
    registrar_auditoria(
        db,
        usuario=current,
        accion=A.COBRO,
        entidad="venta",
        entidad_id=venta.id_venta,
        detalles={"origen": origen, "forma_pago": data.forma_pago, "id_pedido": id_pedido},
        origen=origen,
        **_meta(request),
    )
    db.commit()
    return venta
