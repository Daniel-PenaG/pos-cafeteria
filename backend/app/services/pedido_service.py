import json
from datetime import datetime
from sqlalchemy.orm import Session, joinedload

from app.models.models import (
    PedidoModel,
    DetallePedidoModel,
    ProductoModel,
    ClienteModel,
)
from app.schemas.pedido import PedidoLineaCreate
from app.schemas.ventas import VentaCreate, DetalleVentaItem, ExtraVentaLinea
from app.services.promocion_service import calcular_linea
from app.services.venta_service import registrar_venta
from app.exceptions import DatosInvalidosException, RecursoNoEncontradoException


def _line_key(id_producto: int, extras: list, id_promocion) -> str:
    ids = sorted([e.id_extra for e in extras])
    return f"{id_producto}-{id_promocion or 'np'}-{'-'.join(map(str, ids))}"


def _parse_extras(extras_json: str | None) -> list:
    if not extras_json:
        return []
    try:
        return json.loads(extras_json)
    except json.JSONDecodeError:
        return []


def _detalle_a_dict(d: DetallePedidoModel) -> dict:
    extras = _parse_extras(d.extras_json)
    cant = float(d.cantidad)
    lista = float(d.cantidad_lista or 0)
    return {
        "id_detalle_pedido": d.id_detalle_pedido,
        "id_producto": d.id_producto,
        "nombre_producto": d.nombre_producto,
        "cantidad": cant,
        "cantidad_lista": lista,
        "cantidad_pendiente": max(0, cant - lista),
        "precio_unitario": float(d.precio_unitario),
        "precio_original": float(d.precio_original) if d.precio_original else None,
        "descuento_unitario": float(d.descuento_unitario) if d.descuento_unitario else None,
        "id_promocion": d.id_promocion,
        "nombre_promocion": d.nombre_promocion,
        "extras": extras,
        "en_comanda": bool(d.en_comanda),
        "line_key": d.line_key,
    }


def _pedido_a_dict(p: PedidoModel) -> dict:
    lineas = [_detalle_a_dict(d) for d in p.detalles]
    total = sum(l["cantidad"] * l["precio_unitario"] for l in lineas)
    cliente_nombre = p.cliente.nombre if p.cliente else None
    return {
        "id_pedido": p.id_pedido,
        "numero_mesa": p.numero_mesa,
        "estado": p.estado,
        "id_cliente": p.id_cliente,
        "id_usuario": p.id_usuario,
        "id_venta": p.id_venta,
        "fecha_apertura": p.fecha_apertura,
        "total": round(total, 2),
        "lineas": lineas,
        "cliente_nombre": cliente_nombre,
    }


def obtener_pedido_abierto_mesa(db: Session, numero_mesa: int, id_usuario: int) -> PedidoModel:
    pedido = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles), joinedload(PedidoModel.cliente))
        .filter(PedidoModel.numero_mesa == numero_mesa, PedidoModel.estado == "ABIERTO")
        .first()
    )
    if not pedido:
        pedido = PedidoModel(numero_mesa=numero_mesa, id_usuario=id_usuario, estado="ABIERTO")
        db.add(pedido)
        db.commit()
        db.refresh(pedido)
    return pedido


def agregar_linea_pedido(
    db: Session, pedido: PedidoModel, data: PedidoLineaCreate, nombre_promocion: str | None = None
) -> DetallePedidoModel:
    if pedido.estado != "ABIERTO":
        raise DatosInvalidosException("El pedido ya está cerrado")

    producto = db.query(ProductoModel).filter(ProductoModel.id_producto == data.id_producto).first()
    if not producto:
        raise RecursoNoEncontradoException("Producto no encontrado")
    if not producto.activo:
        raise DatosInvalidosException(f"Producto {producto.nombre} no está activo")

    precio_extras = sum(float(e.precio) for e in data.extras)
    calculo = calcular_linea(
        db, producto, float(data.cantidad), precio_extras, data.id_promocion
    )
    if not calculo["margen_ok"]:
        raise DatosInvalidosException(calculo["mensaje"] or "Margen insuficiente")

    esperado = calculo["precio_unitario"]
    if abs(float(data.precio_unitario) - esperado) > 0.02:
        raise DatosInvalidosException(
            f"Precio inválido. Esperado: {esperado:.2f}, recibido: {data.precio_unitario:.2f}"
        )

    key = _line_key(data.id_producto, data.extras, data.id_promocion)
    existente = (
        db.query(DetallePedidoModel)
        .filter(DetallePedidoModel.id_pedido == pedido.id_pedido, DetallePedidoModel.line_key == key)
        .first()
    )

    extras_json = None
    if data.extras:
        extras_json = json.dumps(
            [{"id_extra": e.id_extra, "nombre": e.nombre, "precio": float(e.precio)} for e in data.extras],
            ensure_ascii=False,
        )

    ahora = datetime.now()
    if existente:
        existente.cantidad = float(existente.cantidad) + float(data.cantidad)
        if data.enviar_comanda:
            existente.en_comanda = True
            existente.fecha_envio_comanda = ahora
            if float(existente.cantidad_lista or 0) < float(existente.cantidad):
                existente.fecha_listo_comanda = None
        db.commit()
        db.refresh(existente)
        return existente

    detalle = DetallePedidoModel(
        id_pedido=pedido.id_pedido,
        id_producto=data.id_producto,
        nombre_producto=producto.nombre,
        cantidad=data.cantidad,
        cantidad_lista=0,
        precio_unitario=calculo["precio_unitario"],
        precio_original=calculo["precio_original_unitario"],
        descuento_unitario=calculo["descuento_unitario"],
        id_promocion=calculo["id_promocion"],
        nombre_promocion=nombre_promocion or calculo.get("nombre_promocion"),
        extras_json=extras_json,
        en_comanda=data.enviar_comanda,
        fecha_envio_comanda=ahora if data.enviar_comanda else None,
        line_key=key,
    )
    db.add(detalle)
    db.commit()
    db.refresh(detalle)
    return detalle


def cobrar_pedido(db: Session, pedido: PedidoModel, id_usuario: int, forma_pago: str):
    if pedido.estado != "ABIERTO":
        raise DatosInvalidosException("El pedido ya fue cobrado o cancelado")
    if not pedido.detalles:
        raise DatosInvalidosException("El pedido no tiene productos")

    detalles_venta = []
    for d in pedido.detalles:
        extras = [
            ExtraVentaLinea(id_extra=e["id_extra"], nombre=e["nombre"], precio=e["precio"])
            for e in _parse_extras(d.extras_json)
        ]
        detalles_venta.append(
            DetalleVentaItem(
                id_producto=d.id_producto,
                cantidad=float(d.cantidad),
                precio_unitario=float(d.precio_unitario),
                precio_original=float(d.precio_original) if d.precio_original else None,
                id_promocion=d.id_promocion,
                extras=extras,
            )
        )

    venta_data = VentaCreate(
        id_usuario=id_usuario,
        numero_mesa=pedido.numero_mesa,
        forma_pago=forma_pago,
        id_cliente=pedido.id_cliente,
        detalles=detalles_venta,
    )
    resp = registrar_venta(db, venta_data)
    pedido.estado = "COBRADO"
    pedido.id_venta = resp.id_venta
    pedido.fecha_cierre = datetime.now()
    db.commit()
    return resp
