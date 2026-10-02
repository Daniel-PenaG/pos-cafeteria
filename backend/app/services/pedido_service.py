import hashlib
import json
import time

from app.utils.timezone_mx import now_utc_naive, isoformat_utc, segundos_desde

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, joinedload

from app.models.models import (
    PedidoModel,
    DetallePedidoModel,
    PedidoOperacionModel,
    ProductoModel,
    ClienteModel,
    PromocionModel,
    UsuarioModel,
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
from app.exceptions import (
    ConflictoOperacionException,
    DatosInvalidosException,
    RecalculoTotalException,
    RecursoNoEncontradoException,
)


def _line_key(id_producto: int, extras: list, id_promocion, comentario: str | None = None, modo: str = "A") -> str:
    ids = sorted([e.id_extra for e in extras])
    base = f"{id_producto}-{modo}-{id_promocion or 'np'}-{'-'.join(map(str, ids))}"
    com = (comentario or "").strip().lower()[:50]
    if com:
        return f"{base}-c:{com}"[:120]
    return base[:120]


def modo_promocion_detalle(detalle: DetallePedidoModel) -> str:
    """AUTOMATICA, SELECCIONADA, PRECIO_NORMAL o LEGACY.

    LEGACY: la columna sin_promocion no existía. No adopta una promoción nueva.
    Un id_promocion ya guardado se trata como SELECCIONADA.
    """
    flag = getattr(detalle, "sin_promocion", None)
    if flag is True:
        return "PRECIO_NORMAL"
    if flag is False:
        return "SELECCIONADA" if detalle.id_promocion else "AUTOMATICA"
    if detalle.id_promocion:
        return "SELECCIONADA"
    return "LEGACY"


def _subtotal_guardado(detalle: DetallePedidoModel):
    from decimal import Decimal
    from app.services.promocion_service import dinero

    guardado = getattr(detalle, "subtotal", None)
    if guardado is not None:
        return dinero(guardado)
    return dinero(dinero(detalle.precio_unitario) * Decimal(str(detalle.cantidad or 0)))


def _parse_extras(extras_json: str | None) -> list:
    return parsear_extras_json(extras_json)


def _detalle_a_dict(d: DetallePedidoModel, calc: dict | None = None) -> dict:
    from app.services.promocion_service import dinero

    extras = _parse_extras(d.extras_json)
    cant = float(d.cantidad)
    lista = float(d.cantidad_lista or 0)
    prep_secs = None
    if d.en_comanda and d.fecha_envio_comanda and lista < cant:
        prep_secs = segundos_desde(d.fecha_envio_comanda)
    subtotal = _subtotal_guardado(d)
    desglose = []
    aplicaciones = 0
    unidades_normales = 0
    if calc and dinero(calc.get("subtotal") or 0) == subtotal:
        desglose = calc.get("desglose") or []
        aplicaciones = int(calc.get("aplicaciones") or 0)
        unidades_normales = calc.get("unidades_normales") or 0
    modo = modo_promocion_detalle(d)
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
        "nombre_promocion": d.nombre_promocion or None,
        "sin_promocion": True if d.sin_promocion is True else False if d.sin_promocion is False else None,
        "modo_promocion": modo,
        "subtotal": float(subtotal),
        "desglose": desglose,
        "aplicaciones": aplicaciones,
        "unidades_normales": unidades_normales,
        "extras": extras,
        "en_comanda": bool(d.en_comanda),
        "comentario": d.comentario,
        "line_key": d.line_key,
        "fecha_envio_comanda": isoformat_utc(d.fecha_envio_comanda),
        "fecha_listo_comanda": isoformat_utc(d.fecha_listo_comanda),
        "segundos_preparacion": prep_secs,
        "estado_linea": getattr(d, "estado_linea", None) or "ACTIVA",
        "cantidad_cancelada": float(getattr(d, "cantidad_cancelada", 0) or 0),
    }


def _total_lineas(lineas: list) -> float:
    from decimal import Decimal
    from app.services.promocion_service import dinero

    total = Decimal("0")
    for linea in lineas:
        if linea.get("cantidad", 0) <= 0:
            continue
        if linea.get("subtotal") is not None:
            total += dinero(linea["subtotal"])
        else:
            total += dinero(linea["cantidad"]) * dinero(linea["precio_unitario"])
    return float(dinero(total))


def _pedido_a_dict(p: PedidoModel, promo_resumen: dict | None = None) -> dict:
    calcs = iter((promo_resumen or {}).get("lineas") or [])
    lineas = []
    for detalle in p.detalles:
        calc = next(calcs, None) if _linea_participa_en_ticket(detalle) else None
        lineas.append(_detalle_a_dict(detalle, calc))
    total = _total_lineas(lineas)
    cliente_nombre = p.cliente.nombre if p.cliente else None
    out = {
        "id_pedido": p.id_pedido,
        "numero_mesa": p.numero_mesa,
        "para_llevar": bool(getattr(p, "para_llevar", False)),
        "estado": p.estado,
        "id_cliente": p.id_cliente,
        "cliente_puntos_saldo": int(p.cliente.puntos_saldo or 0) if p.cliente else None,
        "cliente_activo": bool(p.cliente.activo) if p.cliente else None,
        "id_usuario": p.id_usuario,
        "id_venta": p.id_venta,
        "fecha_apertura": isoformat_utc(p.fecha_apertura),
        "total": round(total, 2),
        "lineas": lineas,
        "cliente_nombre": cliente_nombre,
        "cliente_telefono": p.cliente.telefono if p.cliente else None,
        "sin_pedido": False,
    }
    if promo_resumen:
        out["subtotal_normal"] = promo_resumen.get("subtotal_normal")
        out["descuento_promociones"] = promo_resumen.get("descuento_promociones")
        out["resumen_promociones"] = promo_resumen.get("resumen_promociones", [])
    return out


def buscar_pedido_abierto_mesa(
    db: Session, numero_mesa: int, para_llevar: bool = False
) -> PedidoModel | None:
    """Consulta un pedido abierto. No crea ni escribe."""
    return (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles), joinedload(PedidoModel.cliente))
        .filter(
            PedidoModel.numero_mesa == numero_mesa,
            PedidoModel.estado == "ABIERTO",
            PedidoModel.para_llevar == para_llevar,
        )
        .first()
    )


def pedido_vacio_mesa(numero_mesa: int, id_usuario: int, para_llevar: bool = False) -> dict:
    """Respuesta compatible cuando la mesa aún no tiene pedido."""
    return {
        "id_pedido": None,
        "numero_mesa": numero_mesa,
        "para_llevar": para_llevar,
        "estado": "SIN_PEDIDO",
        "id_cliente": None,
        "id_usuario": id_usuario,
        "id_venta": None,
        "fecha_apertura": None,
        "total": 0.0,
        "lineas": [],
        "cliente_nombre": None,
        "subtotal_normal": 0.0,
        "descuento_promociones": 0.0,
        "resumen_promociones": [],
        "sin_pedido": True,
    }


def crear_pedido_abierto(
    db: Session, numero_mesa: int, id_usuario: int, para_llevar: bool = False
) -> PedidoModel:
    """Crea pedido en la sesión actual sin commit (transacción del caller)."""
    pedido = PedidoModel(
        numero_mesa=numero_mesa,
        id_usuario=id_usuario,
        estado="ABIERTO",
        para_llevar=para_llevar,
        fecha_apertura=now_utc_naive(),
    )
    db.add(pedido)
    db.flush()
    return pedido


def obtener_pedido_abierto_mesa(
    db: Session, numero_mesa: int, id_usuario: int, para_llevar: bool = False
) -> PedidoModel:
    """Obtiene el pedido abierto o lo crea en sesión sin commit.

    GET no debe usar esta función: usar buscar_pedido_abierto_mesa.
    Si otra transacción crea el único ABIERTO de la mesa, se reutiliza.
    """
    for _ in range(20):
        db.expire_all()
        pedido = buscar_pedido_abierto_mesa(db, numero_mesa, para_llevar=para_llevar)
        if pedido:
            return pedido
        try:
            # Sin SAVEPOINT: en SQLite begin_nested + RELEASE puede dejar el INSERT
            # persistido y un rollback posterior no borra el pedido vacío.
            return crear_pedido_abierto(db, numero_mesa, id_usuario, para_llevar=para_llevar)
        except (IntegrityError, OperationalError):
            db.rollback()
            time.sleep(0.05)
    db.expire_all()
    pedido = buscar_pedido_abierto_mesa(db, numero_mesa, para_llevar=para_llevar)
    if pedido:
        return pedido
    raise DatosInvalidosException("No se pudo abrir el pedido de la mesa. Reintenta.")


def _normalizar_operation_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = str(raw).strip()
    return key[:64] if key else None


def _canon_extras(extras) -> list:
    out = []
    for e in extras or []:
        extra = e.model_dump() if hasattr(e, "model_dump") else dict(e)
        out.append(
            {
                "id_extra": extra.get("id_extra"),
                "precio": round(float(extra.get("precio") or 0), 2),
            }
        )
    return sorted(out, key=lambda x: (x["id_extra"] is None, x["id_extra"]))


def huella_operacion_linea(pedido: PedidoModel, data) -> str:
    payload = {
        "tipo": "linea",
        "numero_mesa": pedido.numero_mesa,
        "para_llevar": bool(getattr(pedido, "para_llevar", False)),
        "id_producto": data.id_producto,
        "cantidad": float(data.cantidad),
        "precio_unitario": round(float(data.precio_unitario), 2),
        "id_promocion": data.id_promocion,
        "comentario": (data.comentario or "").strip() or None,
        "enviar_comanda": bool(data.enviar_comanda),
        "extras": _canon_extras(data.extras),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def huella_operacion_combo(
    pedido: PedidoModel, id_promocion: int, cantidad: float, enviar_comanda: bool
) -> str:
    payload = {
        "tipo": "combo",
        "numero_mesa": pedido.numero_mesa,
        "para_llevar": bool(getattr(pedido, "para_llevar", False)),
        "id_promocion": id_promocion,
        "cantidad": float(cantidad),
        "enviar_comanda": bool(enviar_comanda),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cargar_operacion(db: Session, operation_id: str) -> PedidoOperacionModel | None:
    return (
        db.query(PedidoOperacionModel)
        .filter(PedidoOperacionModel.operation_id == operation_id)
        .first()
    )


def _pedido_de_operacion(db: Session, op: PedidoOperacionModel) -> PedidoModel | None:
    return (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles), joinedload(PedidoModel.cliente))
        .filter(PedidoModel.id_pedido == op.id_pedido)
        .first()
    )


def _detalle_de_operacion(db: Session, op: PedidoOperacionModel) -> DetallePedidoModel | None:
    if not op.id_detalle_pedido:
        return None
    return db.get(DetallePedidoModel, op.id_detalle_pedido)


def _asegurar_huella(op: PedidoOperacionModel, payload_hash: str, tipo: str) -> None:
    if (op.payload_hash or "") != payload_hash or op.tipo != tipo:
        raise ConflictoOperacionException(
            "Esta clave de operación ya se usó con otro producto, combo, mesa o datos"
        )


def _replay_operacion(
    db: Session, operation_id: str, payload_hash: str | None = None, tipo: str | None = None
) -> tuple[dict, DetallePedidoModel | None] | None:
    op = _cargar_operacion(db, operation_id)
    if not op:
        return None
    if payload_hash is not None or tipo is not None:
        _asegurar_huella(op, payload_hash or op.payload_hash, tipo or op.tipo)
    pedido = _pedido_de_operacion(db, op)
    if not pedido:
        return None
    return pedido_respuesta_lectura(db, pedido), _detalle_de_operacion(db, op)


def _registrar_operacion(
    db: Session,
    operation_id: str,
    id_pedido: int,
    tipo: str,
    payload_hash: str,
) -> PedidoOperacionModel:
    op = PedidoOperacionModel(
        operation_id=operation_id,
        id_pedido=id_pedido,
        tipo=tipo,
        payload_hash=payload_hash,
        fecha=now_utc_naive(),
    )
    db.add(op)
    db.flush()
    return op


def _linea_participa_en_ticket(d: DetallePedidoModel) -> bool:
    from sqlalchemy import inspect as sa_inspect

    if sa_inspect(d).deleted:
        return False
    if float(d.cantidad or 0) <= 0:
        return False
    if getattr(d, "estado_linea", "ACTIVA") == "CANCELADA":
        return False
    return True


def _lineas_desde_pedido(db: Session, pedido: PedidoModel) -> list:
    lineas = []
    promo_cache: dict[int, PromocionModel] = {}
    for d in pedido.detalles:
        if not _linea_participa_en_ticket(d):
            continue
        extras = extras_linea_desde_json(_parse_extras(d.extras_json))
        modo = modo_promocion_detalle(d)
        id_promo = d.id_promocion
        sin_promo = modo in ("PRECIO_NORMAL", "LEGACY")
        forzar = modo == "SELECCIONADA" and bool(id_promo)
        if forzar and id_promo:
            if id_promo not in promo_cache:
                promo_cache[id_promo] = (
                    db.query(PromocionModel)
                    .filter(PromocionModel.id_promocion == id_promo)
                    .first()
                )
            promo = promo_cache[id_promo]
            if not promo:
                forzar = False
                id_promo = None
                sin_promo = True
        elif modo == "AUTOMATICA":
            id_promo = None
            sin_promo = False
            forzar = False
        lineas.append(
            {
                "id_detalle_pedido": d.id_detalle_pedido,
                "id_producto": d.id_producto,
                "cantidad": float(d.cantidad),
                "precio_extras": sum(float(e.precio) for e in extras),
                "extras": extras,
                "id_promocion": None if sin_promo else id_promo,
                "sin_promocion": sin_promo,
                "forzar_promo_linea": forzar,
                "comentario": d.comentario,
            }
        )
    return lineas


def _aplicar_recalc_a_detalles(pedido: PedidoModel, recalc: dict) -> None:
    from app.services.promocion_service import dinero

    activos = [d for d in pedido.detalles if _linea_participa_en_ticket(d)]
    for detalle, calc in zip(activos, recalc.get("lineas") or []):
        modo = modo_promocion_detalle(detalle)
        detalle.precio_unitario = calc["precio_unitario"]
        detalle.precio_original = calc.get("precio_original") or calc.get("precio_original_unitario")
        detalle.descuento_unitario = calc.get("descuento_unitario") or 0
        detalle.subtotal = dinero(calc.get("subtotal") if calc.get("subtotal") is not None else 0)
        if modo == "PRECIO_NORMAL":
            detalle.sin_promocion = True
            detalle.id_promocion = None
            detalle.nombre_promocion = None
        elif modo == "LEGACY":
            detalle.sin_promocion = None
            detalle.id_promocion = None
            detalle.nombre_promocion = None
        elif modo == "AUTOMATICA":
            detalle.sin_promocion = False
            detalle.id_promocion = None
            detalle.nombre_promocion = calc.get("nombre_promocion")
        else:
            detalle.sin_promocion = False
            if calc.get("nombre_promocion"):
                detalle.nombre_promocion = calc.get("nombre_promocion")
            elif not calc.get("id_promocion"):
                detalle.nombre_promocion = None


def _recalcular_promociones_sin_commit(db: Session, pedido: PedidoModel) -> dict:
    """Recalcula promociones ticket en memoria/sesión sin commit."""
    vacio = {
        "lineas": [],
        "resumen_promociones": [],
        "subtotal_normal": 0.0,
        "descuento_promociones": 0.0,
        "total": 0.0,
    }
    if pedido.estado != "ABIERTO" or not pedido.detalles:
        return vacio
    if not any(_linea_participa_en_ticket(d) for d in pedido.detalles):
        return vacio
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
    """GET: muestra el subtotal guardado. Si el recálculo cambia el dinero, avisa."""
    from app.services.promocion_service import dinero

    base = _pedido_a_dict(pedido, recalc)
    guardado = dinero(base["total"])
    recalculado = dinero(recalc.get("total") or 0)
    if guardado != recalculado:
        base = _pedido_a_dict(pedido, None)
        base["aviso_recalculo"] = (
            f"El total guardado es ${guardado} y al recalcular promociones "
            f"o vigencia quedaría ${recalculado}. Confirma antes de cobrar."
        )
        base["total_recalculado"] = float(recalculado)
    return base


def pedido_respuesta_lectura(db: Session, pedido: PedidoModel) -> dict:
    """GET de pedido: recalcula para mostrar totales sin escribir en BD."""
    if pedido.estado == "ABIERTO" and any(_linea_participa_en_ticket(d) for d in (pedido.detalles or [])):
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
    operation_id = _normalizar_operation_id(getattr(data, "operation_id", None))
    payload_hash = huella_operacion_linea(pedido, data) if operation_id else None
    if operation_id:
        replay = _replay_operacion(db, operation_id, payload_hash, "linea")
        if replay is not None:
            return replay

    try:
        if pedido.estado != "ABIERTO":
            raise DatosInvalidosException("El pedido ya está cerrado")

        producto = db.query(ProductoModel).filter(ProductoModel.id_producto == data.id_producto).first()
        if not producto:
            raise RecursoNoEncontradoException("Producto no encontrado")
        if not producto.activo:
            raise DatosInvalidosException(f"Producto {producto.nombre} no está activo")

        precio_extras = sum(float(e.precio) for e in data.extras)
        sin_promo = bool(getattr(data, "sin_promocion", False))
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
        if sin_promo:
            modo = "N"
            id_promo_key = None
        elif data.id_promocion:
            modo = f"S{data.id_promocion}"
            id_promo_key = data.id_promocion
        else:
            modo = "A"
            id_promo_key = None
        key = _line_key(data.id_producto, data.extras, id_promo_key, comentario, modo)
        extras_json = extras_json_desde_normalizados(extras_normalizados)
        ahora = now_utc_naive()

        op = None
        if operation_id:
            try:
                with db.begin_nested():
                    op = _registrar_operacion(
                        db, operation_id, pedido.id_pedido, "linea", payload_hash
                    )
            except IntegrityError:
                replay = _replay_operacion(db, operation_id, payload_hash, "linea")
                if replay is not None:
                    return replay
                raise
        existente = (
            db.query(DetallePedidoModel)
            .filter(DetallePedidoModel.id_pedido == pedido.id_pedido, DetallePedidoModel.line_key == key)
            .first()
        )
        if existente and getattr(existente, "estado_linea", "ACTIVA") == "CANCELADA":
            existente = None
            key = f"{key}-n{int(ahora.timestamp() * 1000)}"[:120]

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
                id_promocion=None if sin_promo or not data.id_promocion else data.id_promocion,
                nombre_promocion=None if sin_promo else (nombre_promocion or calculo.get("nombre_promocion")),
                sin_promocion=True if sin_promo else False,
                subtotal=calculo.get("subtotal"),
                extras_json=extras_json,
                en_comanda=data.enviar_comanda,
                fecha_envio_comanda=ahora if data.enviar_comanda else None,
                line_key=key,
                comentario=comentario,
            )
            db.add(detalle)

        db.flush()
        detalle_id = detalle.id_detalle_pedido
        if op is not None:
            op.id_detalle_pedido = detalle_id
            op.detalle_ids_json = json.dumps([detalle_id])
        recalc = _recalcular_promociones_sin_commit(db, pedido)
        db.commit()
        pedido = _reload_pedido(db, pedido)
        detalle = next(d for d in pedido.detalles if d.id_detalle_pedido == detalle_id)
        return pedido_respuesta(db, pedido, recalc), detalle
    except IntegrityError:
        db.rollback()
        if operation_id:
            replay = _replay_operacion(db, operation_id, payload_hash, "linea")
            if replay is not None:
                return replay
        raise
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
    key = _line_key(
        data.id_producto, data.extras, data.id_promocion, comentario, f"S{data.id_promocion or 0}"
    )
    extras_json = extras_json_desde_normalizados(extras_normalizados)
    ahora = now_utc_naive()

    existente = (
        db.query(DetallePedidoModel)
        .filter(DetallePedidoModel.id_pedido == pedido.id_pedido, DetallePedidoModel.line_key == key)
        .first()
    )
    if existente and getattr(existente, "estado_linea", "ACTIVA") == "CANCELADA":
        existente = None
        key = f"{key}-n{int(ahora.timestamp() * 1000)}"[:120]
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
        sin_promocion=False,
        subtotal=round(float(data.cantidad) * float(data.precio_unitario), 2),
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
    operation_id: str | None = None,
) -> dict:
    operation_id = _normalizar_operation_id(operation_id)
    payload_hash = (
        huella_operacion_combo(pedido, id_promocion, cantidad, enviar_comanda)
        if operation_id
        else None
    )
    if operation_id:
        replay = _replay_operacion(db, operation_id, payload_hash, "combo")
        if replay is not None:
            return replay[0]
    try:
        op = None
        if operation_id:
            try:
                with db.begin_nested():
                    op = _registrar_operacion(
                        db, operation_id, pedido.id_pedido, "combo", payload_hash
                    )
            except IntegrityError:
                replay = _replay_operacion(db, operation_id, payload_hash, "combo")
                if replay is not None:
                    return replay[0]
                raise
        combo = calcular_combo(db, id_promocion, cantidad)
        detalle_ids = []
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
            det = agregar_linea_combo(
                db,
                pedido,
                data,
                combo["nombre_promocion"],
                item["precio_original"],
                item["descuento_unitario"],
            )
            detalle_ids.append(det.id_detalle_pedido)
        if op is not None:
            op.id_detalle_pedido = detalle_ids[0] if detalle_ids else None
            op.detalle_ids_json = json.dumps(detalle_ids)
        recalc = _recalcular_promociones_sin_commit(db, pedido)
        db.commit()
        pedido = _reload_pedido(db, pedido)
        return pedido_respuesta(db, pedido, recalc)
    except IntegrityError:
        db.rollback()
        if operation_id:
            replay = _replay_operacion(db, operation_id, payload_hash, "combo")
            if replay is not None:
                return replay[0]
        raise
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
        if getattr(detalle, "estado_linea", "ACTIVA") == "CANCELADA":
            continue
        if float(detalle.cantidad or 0) <= 0:
            continue
        detalle.en_comanda = True
        detalle.fecha_envio_comanda = ahora
        detalle.fecha_listo_comanda = None
        enviadas += 1

    if enviadas == 0:
        raise DatosInvalidosException("No hay productos pendientes de confirmar")

    db.commit()
    return enviadas


def cobrar_pedido(
    db: Session,
    pedido: PedidoModel,
    id_usuario: int,
    forma_pago: str,
    origen_cobro: str | None = None,
    puntos_canje: int = 0,
    operation_id: str | None = None,
    id_cliente: int | None = None,
    desasociar_cliente: bool = False,
    actor: UsuarioModel | None = None,
    auditoria_meta: dict | None = None,
    confirmar_recalculo: bool = False,
):
    """Bloqueos: sesión → pedido → detalles → cliente → idempotencia → venta."""
    from app.constants import auditoria as A
    from app.utils.forma_pago import normalizar_forma_pago
    from app.services.pedido_locks import lock_detalles_de_pedido, lock_pedido
    from app.services.cobro_bloqueos import bloquear_cliente_cobro, bloquear_sesion_de_cobro
    from app.services.auditoria_service import registrar_auditoria
    from app.services.cobro_operacion import (
        huella_cobro,
        lineas_huella,
        reclamar_cobro,
        respuesta_cobro_guardado,
    )
    from app.exceptions import RecursoNoEncontradoException

    forma_pago = normalizar_forma_pago(forma_pago)
    operation_id = _normalizar_operation_id(operation_id)
    sesion_id = bloquear_sesion_de_cobro(db, id_usuario)
    pedido = lock_pedido(db, pedido.id_pedido) or pedido
    detalles_bloqueados = lock_detalles_de_pedido(db, pedido.id_pedido)
    cliente_quitado = None
    if desasociar_cliente:
        cliente_quitado = pedido.id_cliente
        pedido.id_cliente = None
    elif id_cliente:
        pedido.id_cliente = id_cliente
    cliente = None
    saldo_visto = None
    if pedido.id_cliente:
        cliente, saldo_visto = bloquear_cliente_cobro(db, pedido.id_cliente)
        if cliente is None:
            raise RecursoNoEncontradoException("Cliente no encontrado o inactivo")
    if cliente_quitado:
        meta = auditoria_meta or {}
        registrar_auditoria(
            db,
            usuario=actor,
            accion=A.CLIENTE_DESASOCIADO,
            entidad="pedido",
            entidad_id=pedido.id_pedido,
            detalles={
                "id_pedido": pedido.id_pedido,
                "id_cliente": int(cliente_quitado),
            },
            origen=origen_cobro,
            ip=meta.get("ip"),
            user_agent=meta.get("user_agent"),
        )
    if pedido.estado != "ABIERTO":
        if operation_id:
            huella = huella_cobro(
                id_pedido=pedido.id_pedido,
                id_cliente=pedido.id_cliente,
                forma_pago=forma_pago,
                puntos_canje=puntos_canje,
                lineas=lineas_huella([d for d in detalles_bloqueados if float(d.cantidad or 0) > 0]),
            )
            op = reclamar_cobro(db, operation_id, huella, id_usuario, pedido.id_pedido)
            if op.id_venta:
                guardada = respuesta_cobro_guardado(db, operation_id)
                if guardada:
                    return guardada
        raise DatosInvalidosException("El pedido ya fue cobrado o cancelado")
    detalles_activos = [d for d in detalles_bloqueados if float(d.cantidad) > 0]
    if not detalles_activos:
        raise DatosInvalidosException("El pedido no tiene productos")

    from app.services.promocion_service import dinero

    antes = dinero(sum((_subtotal_guardado(d) for d in detalles_activos), dinero(0)))
    _recalcular_promociones_sin_commit(db, pedido)
    detalles_activos = [d for d in pedido.detalles if _linea_participa_en_ticket(d)]
    despues = dinero(sum((_subtotal_guardado(d) for d in detalles_activos), dinero(0)))
    if antes != despues and not confirmar_recalculo:
        db.rollback()
        raise RecalculoTotalException(antes, despues)
    if operation_id:
        huella = huella_cobro(
            id_pedido=pedido.id_pedido,
            id_cliente=pedido.id_cliente,
            forma_pago=forma_pago,
            puntos_canje=puntos_canje,
            lineas=lineas_huella(detalles_activos),
        )
        op = reclamar_cobro(db, operation_id, huella, id_usuario, pedido.id_pedido)
        if op.id_venta:
            guardada = respuesta_cobro_guardado(db, operation_id)
            if guardada:
                return guardada

    detalles_venta = []
    for d in detalles_activos:
        extras = extras_linea_desde_json(_parse_extras(d.extras_json))
        modo = modo_promocion_detalle(d)
        sin_promo = modo in ("PRECIO_NORMAL", "LEGACY")
        detalles_venta.append(
            DetalleVentaItem(
                id_producto=d.id_producto,
                cantidad=float(d.cantidad),
                precio_unitario=float(d.precio_unitario),
                precio_original=float(d.precio_original) if d.precio_original else None,
                id_promocion=None if sin_promo else d.id_promocion,
                sin_promocion=sin_promo,
                forzar_promocion=modo == "SELECCIONADA" and not sin_promo,
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
        origen_cobro=origen_cobro,
        puntos_canje=int(puntos_canje or 0),
        operation_id=operation_id,
        detalles=detalles_venta,
    )
    return registrar_venta(
        db,
        venta_data,
        sesion_ya_bloqueada=True,
        sesion_id_bloqueada=sesion_id,
        cliente_preparado=(cliente, saldo_visto),
    )


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
        total = _total_lineas(lineas)
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
