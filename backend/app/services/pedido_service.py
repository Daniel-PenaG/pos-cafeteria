from app.utils.timezone_mx import now_utc_naive, isoformat_utc, segundos_desde

from sqlalchemy.orm import Session, joinedload

from app.models.models import (
    PedidoModel,
    DetallePedidoModel,
    ProductoModel,
    ClienteModel,
    PromocionModel,
)
from app.schemas.pedido import PedidoLineaCreate
from app.schemas.ventas import VentaCreate, DetalleVentaItem
from app.services.extras_validacion_service import (
    validar_extras_producto,
    extras_json_desde_normalizados,
    parsear_extras_json,
    extras_linea_desde_json,
)
from app.services.promocion_service import calcular_linea, calcular_combo, es_promo_paquete
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


def _lineas_desde_pedido(db: Session, pedido: PedidoModel) -> list:
    lineas = []
    promo_cache: dict[int, PromocionModel] = {}
    for d in pedido.detalles:
        extras = extras_linea_desde_json(_parse_extras(d.extras_json))
        id_promo = d.id_promocion
        sin_promo = id_promo is None
        if id_promo:
            if id_promo not in promo_cache:
                promo_cache[id_promo] = (
                    db.query(PromocionModel)
                    .filter(PromocionModel.id_promocion == id_promo)
                    .first()
                )
            if promo_cache[id_promo] and es_promo_paquete(promo_cache[id_promo]):
                id_promo = None
                sin_promo = True
        lineas.append(
            {
                "id_producto": d.id_producto,
                "cantidad": float(d.cantidad),
                "precio_extras": sum(float(e.precio) for e in extras),
                "extras": extras,
                "id_promocion": id_promo,
                "sin_promocion": sin_promo,
            }
        )
    return lineas


def _aplicar_recalc_a_detalles(pedido: PedidoModel, recalc: dict) -> None:
    for detalle, calc in zip(pedido.detalles, recalc["lineas"]):
        detalle.precio_unitario = calc["precio_unitario"]
        detalle.precio_original = calc.get("precio_original")
        detalle.descuento_unitario = calc.get("descuento_unitario")
        detalle.id_promocion = calc.get("id_promocion")
        detalle.nombre_promocion = calc.get("nombre_promocion")


def _recalcular_promociones_sin_commit(db: Session, pedido: PedidoModel) -> dict:
    """Recalcula promociones ticket en memoria/sesión sin commit."""
    if pedido.estado != "ABIERTO" or not pedido.detalles:
        return {
            "lineas": [],
            "resumen_promociones": [],
            "subtotal_normal": 0.0,
            "descuento_promociones": 0.0,
            "total": 0.0,
        }
    recalc = recalcular_lineas_ticket(db, _lineas_desde_pedido(db, pedido))
    _aplicar_recalc_a_detalles(pedido, recalc)
    return recalc


def recalcular_promociones_pedido(db: Session, pedido: PedidoModel) -> dict:
    """Recalcula promociones ticket y persiste (mutaciones explícitas)."""
    recalc = _recalcular_promociones_sin_commit(db, pedido)
    if pedido.estado == "ABIERTO" and pedido.detalles:
        db.commit()
    return recalc


def _pedido_a_dict_con_recalc_en_lectura(pedido: PedidoModel, recalc: dict) -> dict:
    """Construye respuesta GET sin persistir precios recalculados."""
    lineas = []
    for detalle, calc in zip(pedido.detalles, recalc.get("lineas", [])):
        d = _detalle_a_dict(detalle)
        d["precio_unitario"] = calc["precio_unitario"]
        d["precio_original"] = calc.get("precio_original")
        d["descuento_unitario"] = calc.get("descuento_unitario")
        d["id_promocion"] = calc.get("id_promocion")
        d["nombre_promocion"] = calc.get("nombre_promocion")
        lineas.append(d)
    total = sum(l["cantidad"] * l["precio_unitario"] for l in lineas)
    cliente_nombre = pedido.cliente.nombre if pedido.cliente else None
    return {
        "id_pedido": pedido.id_pedido,
        "numero_mesa": pedido.numero_mesa,
        "para_llevar": bool(getattr(pedido, "para_llevar", False)),
        "estado": pedido.estado,
        "id_cliente": pedido.id_cliente,
        "id_usuario": pedido.id_usuario,
        "id_venta": pedido.id_venta,
        "fecha_apertura": isoformat_utc(pedido.fecha_apertura),
        "total": round(total, 2),
        "lineas": lineas,
        "cliente_nombre": cliente_nombre,
        "subtotal_normal": recalc.get("subtotal_normal"),
        "descuento_promociones": recalc.get("descuento_promociones"),
        "resumen_promociones": recalc.get("resumen_promociones", []),
    }


def pedido_respuesta_lectura(db: Session, pedido: PedidoModel) -> dict:
    """GET de pedido: recalcula para mostrar totales sin escribir en BD."""
    if pedido.estado == "ABIERTO" and pedido.detalles:
        recalc = recalcular_lineas_ticket(db, _lineas_desde_pedido(db, pedido))
        return _pedido_a_dict_con_recalc_en_lectura(pedido, recalc)
    return _pedido_a_dict(pedido)


def pedido_respuesta(db: Session, pedido: PedidoModel, promo_resumen: dict | None = None) -> dict:
    if promo_resumen is not None:
        db.refresh(pedido)
        return _pedido_a_dict(pedido, promo_resumen)
    resumen = recalcular_promociones_pedido(db, pedido)
    db.refresh(pedido)
    return _pedido_a_dict(pedido, resumen)


def _reload_pedido(db: Session, pedido: PedidoModel) -> PedidoModel:
    return (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles), joinedload(PedidoModel.cliente))
        .filter(PedidoModel.id_pedido == pedido.id_pedido)
        .first()
    )


def agregar_linea_pedido(
    db: Session, pedido: PedidoModel, data: PedidoLineaCreate, nombre_promocion: str | None = None
) -> DetallePedidoModel:
    _, detalle = agregar_linea_pedido_con_respuesta(db, pedido, data, nombre_promocion)
    return detalle


def agregar_linea_pedido_con_respuesta(
    db: Session, pedido: PedidoModel, data: PedidoLineaCreate, nombre_promocion: str | None = None
) -> tuple[dict, DetallePedidoModel]:
    """Inserta/actualiza línea, recalcula promociones y hace un único commit."""
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
    extras_json = extras_json_desde_normalizados(extras_normalizados)
    ahora = now_utc_naive()

    try:
        existente = (
            db.query(DetallePedidoModel)
            .filter(DetallePedidoModel.id_pedido == pedido.id_pedido, DetallePedidoModel.line_key == key)
            .first()
        )

        if existente and existente.en_comanda and not data.enviar_comanda:
            existente = None
            key = f"{key}-n{int(ahora.timestamp() * 1000)}"[:120]

        detalle: DetallePedidoModel
        if existente:
            existente.cantidad = float(existente.cantidad) + float(data.cantidad)
            if data.enviar_comanda:
                existente.en_comanda = True
                existente.fecha_envio_comanda = ahora
                if float(existente.cantidad_lista or 0) < float(existente.cantidad):
                    existente.fecha_listo_comanda = None
            detalle = existente
        else:
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

        db.flush()
        detalle_id = detalle.id_detalle_pedido
        recalc = _recalcular_promociones_sin_commit(db, pedido)
        db.commit()
        pedido = _reload_pedido(db, pedido)
        detalle = next(d for d in pedido.detalles if d.id_detalle_pedido == detalle_id)
        return pedido_respuesta(db, pedido, recalc), detalle
    except Exception:
        db.rollback()
        raise


def agregar_linea_combo(
    db: Session,
    pedido: PedidoModel,
    data: PedidoLineaCreate,
    nombre_promocion: str,
    precio_original: float,
    descuento_unitario: float,
) -> DetallePedidoModel:
    """Inserta línea de combo sin commit (commit en agregar_combo_pedido)."""
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
    db.flush()
    return detalle


def agregar_combo_pedido(
    db: Session,
    pedido: PedidoModel,
    id_promocion: int,
    cantidad: float = 1,
    enviar_comanda: bool = False,
) -> dict:
    try:
        combo = calcular_combo(db, id_promocion, cantidad)
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
            agregar_linea_combo(
                db,
                pedido,
                data,
                combo["nombre_promocion"],
                item["precio_original"],
                item["descuento_unitario"],
            )
        recalc = _recalcular_promociones_sin_commit(db, pedido)
        db.commit()
        pedido = _reload_pedido(db, pedido)
        return pedido_respuesta(db, pedido, recalc)
    except Exception:
        db.rollback()
        raise


def confirmar_comanda_pedido(db: Session, pedido: PedidoModel) -> int:
    if pedido.estado != "ABIERTO":
        raise DatosInvalidosException("El pedido ya está cerrado")

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
    from app.utils.forma_pago import normalizar_forma_pago

    forma_pago = normalizar_forma_pago(forma_pago)
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
        id_pedido=pedido.id_pedido,
        detalles=detalles_venta,
    )
    return registrar_venta(db, venta_data)


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
