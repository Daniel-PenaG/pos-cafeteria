from app.utils.timezone_mx import now_utc_naive, isoformat_utc, segundos_desde

from sqlalchemy.orm import Session, joinedload

from app.models.models import (
    PedidoModel,
    DetallePedidoModel,
    ProductoModel,
    ClienteModel,
)
from app.schemas.pedido import PedidoLineaCreate
from app.schemas.ventas import VentaCreate, DetalleVentaItem
from app.services.extras_validacion_service import (
    validar_extras_producto,
    extras_json_desde_normalizados,
    parsear_extras_json,
    extras_linea_desde_json,
)
from app.services.promocion_service import calcular_linea, calcular_combo
from app.services.promocion_ticket_service import recalcular_lineas_ticket
from app.services.venta_service import registrar_venta, MESA_PARA_LLEVAR
from app.exceptions import DatosInvalidosException, RecursoNoEncontradoException


def _line_key(id_producto: int, extras: list, id_promocion, comentario: str | None = None) -> str:
    ids = sorted([e.id_extra for e in extras])
    base = f"{id_producto}-{id_promocion or 'np'}-{'-'.join(map(str, ids))}"
    com = (comentario or "").strip().lower()[:50]
    if com:
        return f"{base}-c:{com}"[:120]
    return base[:120]


def _parse_extras(extras_json: str | None) -> list:
    return parsear_extras_json(extras_json)


def _detalle_a_dict(d: DetallePedidoModel) -> dict:
    extras = _parse_extras(d.extras_json)
    cant = float(d.cantidad)
    lista = float(d.cantidad_lista or 0)
    prep_secs = None
    if d.en_comanda and d.fecha_envio_comanda and lista < cant:
        prep_secs = segundos_desde(d.fecha_envio_comanda)
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
        "comentario": d.comentario,
        "line_key": d.line_key,
        "fecha_envio_comanda": isoformat_utc(d.fecha_envio_comanda),
        "fecha_listo_comanda": isoformat_utc(d.fecha_listo_comanda),
        "segundos_preparacion": prep_secs,
    }


def _pedido_a_dict(p: PedidoModel, promo_resumen: dict | None = None) -> dict:
    lineas = [_detalle_a_dict(d) for d in p.detalles]
    total = sum(l["cantidad"] * l["precio_unitario"] for l in lineas)
    cliente_nombre = p.cliente.nombre if p.cliente else None
    out = {
        "id_pedido": p.id_pedido,
        "numero_mesa": p.numero_mesa,
        "para_llevar": bool(getattr(p, "para_llevar", False)),
        "estado": p.estado,
        "id_cliente": p.id_cliente,
        "id_usuario": p.id_usuario,
        "id_venta": p.id_venta,
        "fecha_apertura": isoformat_utc(p.fecha_apertura),
        "total": round(total, 2),
        "lineas": lineas,
        "cliente_nombre": cliente_nombre,
    }
    if promo_resumen:
        out["subtotal_normal"] = promo_resumen.get("subtotal_normal")
        out["descuento_promociones"] = promo_resumen.get("descuento_promociones")
        out["resumen_promociones"] = promo_resumen.get("resumen_promociones", [])
    return out


def obtener_pedido_abierto_mesa(
    db: Session, numero_mesa: int, id_usuario: int, para_llevar: bool = False
) -> PedidoModel:
    pedido = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles), joinedload(PedidoModel.cliente))
        .filter(
            PedidoModel.numero_mesa == numero_mesa,
            PedidoModel.estado == "ABIERTO",
            PedidoModel.para_llevar == para_llevar,
        )
        .first()
    )
    if not pedido:
        pedido = PedidoModel(
            numero_mesa=numero_mesa,
            id_usuario=id_usuario,
            estado="ABIERTO",
            para_llevar=para_llevar,
        )
        db.add(pedido)
        db.commit()
        db.refresh(pedido)
    return pedido


def _lineas_desde_pedido(pedido: PedidoModel) -> list:
    lineas = []
    for d in pedido.detalles:
        extras = extras_linea_desde_json(_parse_extras(d.extras_json))
        lineas.append(
            {
                "id_producto": d.id_producto,
                "cantidad": float(d.cantidad),
                "precio_extras": sum(float(e.precio) for e in extras),
                "extras": extras,
                "id_promocion": d.id_promocion,
                "sin_promocion": d.id_promocion is None,
            }
        )
    return lineas


def recalcular_promociones_pedido(db: Session, pedido: PedidoModel) -> dict:
    """Recalcula promociones ticket y actualiza líneas del pedido abierto."""
    if pedido.estado != "ABIERTO" or not pedido.detalles:
        return {"lineas": [], "resumen_promociones": [], "subtotal_normal": 0.0, "descuento_promociones": 0.0, "total": 0.0}

    recalc = recalcular_lineas_ticket(db, _lineas_desde_pedido(pedido))
    for detalle, calc in zip(pedido.detalles, recalc["lineas"]):
        detalle.precio_unitario = calc["precio_unitario"]
        detalle.precio_original = calc.get("precio_original")
        detalle.descuento_unitario = calc.get("descuento_unitario")
        detalle.id_promocion = calc.get("id_promocion")
        detalle.nombre_promocion = calc.get("nombre_promocion")
    db.commit()
    return recalc


def pedido_respuesta(db: Session, pedido: PedidoModel) -> dict:
    resumen = recalcular_promociones_pedido(db, pedido)
    db.refresh(pedido)
    return _pedido_a_dict(pedido, resumen)


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
    sin_promo = data.id_promocion is None
    calculo = calcular_linea(
        db, producto, float(data.cantidad), precio_extras, data.id_promocion,
        sin_promocion=sin_promo,
    )
    if not calculo["margen_ok"]:
        raise DatosInvalidosException(calculo["mensaje"] or "Margen insuficiente")

    extras_normalizados = validar_extras_producto(db, data.id_producto, data.extras)

    esperado = calculo["precio_unitario"]
    if abs(float(data.precio_unitario) - esperado) > 0.02:
        raise DatosInvalidosException(
            f"Precio inválido. Esperado: {esperado:.2f}, recibido: {data.precio_unitario:.2f}"
        )

    comentario = (data.comentario or "").strip() or None
    key = _line_key(data.id_producto, data.extras, data.id_promocion, comentario)
    existente = (
        db.query(DetallePedidoModel)
        .filter(DetallePedidoModel.id_pedido == pedido.id_pedido, DetallePedidoModel.line_key == key)
        .first()
    )

    extras_json = extras_json_desde_normalizados(extras_normalizados)

    ahora = now_utc_naive()
    if existente and existente.en_comanda and not data.enviar_comanda:
        existente = None
        key = f"{key}-n{int(ahora.timestamp() * 1000)}"[:120]
    elif existente:
        existente.cantidad = float(existente.cantidad) + float(data.cantidad)
        if data.enviar_comanda:
            existente.en_comanda = True
            existente.fecha_envio_comanda = ahora
            if float(existente.cantidad_lista or 0) < float(existente.cantidad):
                existente.fecha_listo_comanda = None
        db.commit()
        db.refresh(existente)
        recalcular_promociones_pedido(db, pedido)
        db.refresh(existente)
        return existente

    # Evita duplicados por doble envío concurrente
    existente = (
        db.query(DetallePedidoModel)
        .filter(DetallePedidoModel.id_pedido == pedido.id_pedido, DetallePedidoModel.line_key == key)
        .first()
    )
    if existente and not (existente.en_comanda and not data.enviar_comanda):
        existente.cantidad = float(existente.cantidad) + float(data.cantidad)
        if data.enviar_comanda:
            existente.en_comanda = True
            existente.fecha_envio_comanda = ahora
            if float(existente.cantidad_lista or 0) < float(existente.cantidad):
                existente.fecha_listo_comanda = None
        db.commit()
        db.refresh(existente)
        recalcular_promociones_pedido(db, pedido)
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
        comentario=comentario,
    )
    db.add(detalle)
    db.commit()
    db.refresh(detalle)
    recalcular_promociones_pedido(db, pedido)
    db.refresh(detalle)
    return detalle


def agregar_linea_combo(
    db: Session,
    pedido: PedidoModel,
    data: PedidoLineaCreate,
    nombre_promocion: str,
    precio_original: float,
    descuento_unitario: float,
) -> DetallePedidoModel:
    if pedido.estado != "ABIERTO":
        raise DatosInvalidosException("El pedido ya está cerrado")

    producto = db.query(ProductoModel).filter(ProductoModel.id_producto == data.id_producto).first()
    if not producto:
        raise RecursoNoEncontradoException("Producto no encontrado")
    if not producto.activo:
        raise DatosInvalidosException(f"Producto {producto.nombre} no está activo")

    extras_normalizados = validar_extras_producto(db, data.id_producto, data.extras)
    comentario = (data.comentario or "").strip() or None
    key = _line_key(data.id_producto, data.extras, data.id_promocion, comentario)
    extras_json = extras_json_desde_normalizados(extras_normalizados)
    ahora = now_utc_naive()

    existente = (
        db.query(DetallePedidoModel)
        .filter(DetallePedidoModel.id_pedido == pedido.id_pedido, DetallePedidoModel.line_key == key)
        .first()
    )
    if existente and existente.en_comanda and not data.enviar_comanda:
        existente = None
        key = f"{key}-n{int(ahora.timestamp() * 1000)}"[:120]
    elif existente:
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
        precio_unitario=float(data.precio_unitario),
        precio_original=precio_original,
        descuento_unitario=descuento_unitario,
        id_promocion=data.id_promocion,
        nombre_promocion=nombre_promocion,
        extras_json=extras_json,
        en_comanda=data.enviar_comanda,
        fecha_envio_comanda=ahora if data.enviar_comanda else None,
        line_key=key,
        comentario=comentario,
    )
    db.add(detalle)
    db.commit()
    db.refresh(detalle)
    return detalle


def agregar_combo_pedido(
    db: Session,
    pedido: PedidoModel,
    id_promocion: int,
    cantidad: float = 1,
    enviar_comanda: bool = False,
) -> list:
    combo = calcular_combo(db, id_promocion, cantidad)
    detalles = []
    for item in combo["items"]:
        data = PedidoLineaCreate(
            id_producto=item["id_producto"],
            cantidad=item["cantidad"],
            precio_unitario=item["precio_unitario"],
            precio_original=item["precio_original"],
            id_promocion=id_promocion,
            extras=[],
            enviar_comanda=enviar_comanda,
        )
        detalles.append(
            agregar_linea_combo(
                db,
                pedido,
                data,
                combo["nombre_promocion"],
                item["precio_original"],
                item["descuento_unitario"],
            )
        )
    return detalles


def confirmar_comanda_pedido(db: Session, pedido: PedidoModel) -> int:
    if pedido.estado != "ABIERTO":
        raise DatosInvalidosException("El pedido ya está cerrado")
    if getattr(pedido, "para_llevar", False):
        raise DatosInvalidosException("Los pedidos para llevar no usan comanda")

    ahora = now_utc_naive()
    enviadas = 0
    for detalle in pedido.detalles:
        if detalle.en_comanda:
            continue
        detalle.en_comanda = True
        detalle.fecha_envio_comanda = ahora
        detalle.fecha_listo_comanda = None
        enviadas += 1

    if enviadas == 0:
        raise DatosInvalidosException("No hay productos pendientes de confirmar")

    db.commit()
    return enviadas


def cobrar_pedido(db: Session, pedido: PedidoModel, id_usuario: int, forma_pago: str):
    if pedido.estado != "ABIERTO":
        raise DatosInvalidosException("El pedido ya fue cobrado o cancelado")
    if not pedido.detalles:
        raise DatosInvalidosException("El pedido no tiene productos")

    detalles_venta = []
    for d in pedido.detalles:
        extras = extras_linea_desde_json(_parse_extras(d.extras_json))
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
        para_llevar=bool(getattr(pedido, "para_llevar", False)),
        detalles=detalles_venta,
    )
    resp = registrar_venta(db, venta_data)
    pedido.estado = "COBRADO"
    pedido.id_venta = resp.id_venta
    pedido.fecha_cierre = now_utc_naive()
    db.commit()
    return resp


def listar_pedidos_activos_resumen(db: Session) -> list:
    pedidos = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles), joinedload(PedidoModel.cliente))
        .filter(PedidoModel.estado == "ABIERTO")
        .order_by(PedidoModel.numero_mesa)
        .all()
    )
    res = []
    for p in pedidos:
        if not p.detalles:
            continue
        lineas = [_detalle_a_dict(d) for d in p.detalles]
        total = sum(l["cantidad"] * l["precio_unitario"] for l in lineas)
        pendientes = sum(
            1
            for l in lineas
            if l["en_comanda"] and l["cantidad_pendiente"] > 0
        )
        res.append(
            {
                "id_pedido": p.id_pedido,
                "numero_mesa": p.numero_mesa,
                "para_llevar": bool(getattr(p, "para_llevar", False)),
                "total": round(total, 2),
                "num_lineas": len(lineas),
                "pendientes_comanda": pendientes,
                "fecha_apertura": isoformat_utc(p.fecha_apertura),
                "segundos_activa": segundos_desde(p.fecha_apertura) or 0,
                "cliente_nombre": p.cliente.nombre if p.cliente else None,
                "lineas": lineas,
            }
        )
    return res
