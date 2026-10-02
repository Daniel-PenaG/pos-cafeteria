from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from app.utils.timezone_mx import filtro_dia_mx, filtro_mes_mx, filtro_anio_mx, MX, now_utc_naive
import math
from typing import List, Optional

from sqlalchemy import and_, extract, func
from sqlalchemy.orm import Session, joinedload

from app.models import (
    ProductoModel,
    PromocionModel,
    PromocionProductoModel,
    PromocionCategoriaModel,
    RecetaModel,
    DetalleVentaModel,
    VentaModel,
)
from app.exceptions import DatosInvalidosException

TIPOS_TICKET = frozenset({"CANTIDAD_PRECIO", "DESCUENTO_FIJO"})


def es_promo_ticket(promo: PromocionModel) -> bool:
    return promo.tipo in TIPOS_TICKET


def _parse_hora(texto: Optional[str]) -> Optional[time]:
    if not texto or not texto.strip():
        return None
    partes = texto.strip().split(":")
    if len(partes) != 2:
        raise DatosInvalidosException("Hora inválida (use HH:MM)")
    return time(int(partes[0]), int(partes[1]))


def _parse_dias(texto: Optional[str]) -> Optional[set[int]]:
    if not texto or not texto.strip():
        return None
    return {int(d.strip()) for d in texto.split(",") if d.strip() != ""}


def _reloj_promo(ahora: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """UTC naive para vigencia, y hora de México para horario y días."""
    if ahora is None:
        return now_utc_naive(), datetime.now(MX)
    if ahora.tzinfo is None:
        utc = ahora.replace(tzinfo=timezone.utc)
    else:
        utc = ahora.astimezone(timezone.utc)
    return utc.replace(tzinfo=None), utc.astimezone(MX)


def promocion_vigente(promo: PromocionModel, ahora: Optional[datetime] = None) -> bool:
    if not promo.activa:
        return False
    ahora_utc, ahora_mx = _reloj_promo(ahora)
    if promo.fecha_inicio and ahora_utc < promo.fecha_inicio:
        return False
    if promo.fecha_fin and ahora_utc > promo.fecha_fin:
        return False
    dias = _parse_dias(promo.dias_semana)
    if dias is not None and ahora_mx.weekday() not in dias:
        return False
    h_ini = _parse_hora(promo.hora_inicio)
    h_fin = _parse_hora(promo.hora_fin)
    if h_ini or h_fin:
        t = ahora_mx.time()
        if h_ini and h_fin:
            if h_ini <= h_fin:
                if not (h_ini <= t <= h_fin):
                    return False
            else:
                if not (t >= h_ini or t <= h_fin):
                    return False
        elif h_ini and t < h_ini:
            return False
        elif h_fin and t > h_fin:
            return False
    return True


def producto_elegible(promo: PromocionModel, producto: ProductoModel) -> bool:
    if promo.aplica_toda_tienda:
        return True
    ids_prod = {p.id_producto for p in promo.productos}
    if producto.id_producto in ids_prod:
        return True
    ids_cat = {c.id_categoria for c in promo.categorias}
    return producto.id_categoria in ids_cat


def costo_producto(db: Session, id_producto: int) -> float:
    receta = (
        db.query(RecetaModel)
        .filter(RecetaModel.id_producto == id_producto, RecetaModel.activo == True)
        .first()
    )
    if not receta or receta.costo_total is None:
        return 0.0
    return float(receta.costo_total)


def aplicar_promo_base(precio_base: float, tipo: str, valor: float, cantidad: float) -> float:
    if tipo == "PORCENTAJE":
        return round(precio_base * (1 - float(valor) / 100), 2)
    if tipo == "PRECIO_FIJO":
        return round(float(valor), 2)
    if tipo == "DOS_X_UNO":
        if cantidad < 2:
            return round(precio_base, 2)
        unidades_pagadas = math.ceil(cantidad / 2)
        total = unidades_pagadas * precio_base
        return round(total / cantidad, 2)
    return round(precio_base, 2)


def margen_porcentaje(precio: float, costo: float) -> Optional[float]:
    if precio <= 0:
        return None
    return round((precio - costo) / precio * 100, 2)


def es_promo_paquete(promo: PromocionModel) -> bool:
    """Combo explícito o precio fijo sobre 2+ productos específicos (paquete)."""
    n = len(promo.productos or [])
    if promo.tipo == "COMBO":
        return n >= 2
    if promo.tipo == "PRECIO_FIJO" and not promo.aplica_toda_tienda:
        return n >= 2
    return False


def listar_promos_ticket_producto(
    db: Session, producto: ProductoModel, ahora: Optional[datetime] = None
) -> List[PromocionModel]:
    promos = (
        db.query(PromocionModel)
        .options(joinedload(PromocionModel.productos), joinedload(PromocionModel.categorias))
        .filter(PromocionModel.activa == True, PromocionModel.tipo.in_(list(TIPOS_TICKET)))
        .all()
    )
    return [
        p for p in promos
        if promocion_vigente(p, ahora) and producto_elegible(p, producto)
    ]


def listar_aplicables(
    db: Session, producto: ProductoModel, ahora: Optional[datetime] = None
) -> List[PromocionModel]:
    promos = (
        db.query(PromocionModel)
        .options(joinedload(PromocionModel.productos), joinedload(PromocionModel.categorias))
        .filter(PromocionModel.activa == True)
        .all()
    )
    resultado = []
    for p in promos:
        if es_promo_paquete(p):
            continue
        if es_promo_ticket(p):
            continue
        if promocion_vigente(p, ahora) and producto_elegible(p, producto):
            resultado.append(p)
    return resultado


def listar_combos_producto(
    db: Session, id_producto: int, ahora: Optional[datetime] = None
) -> List[PromocionModel]:
    producto = (
        db.query(ProductoModel).filter(ProductoModel.id_producto == id_producto).first()
    )
    if not producto:
        return []
    promos = (
        db.query(PromocionModel)
        .options(joinedload(PromocionModel.productos))
        .filter(PromocionModel.activa == True, PromocionModel.tipo.in_(["COMBO", "PRECIO_FIJO"]))
        .all()
    )
    resultado = []
    for p in promos:
        if not es_promo_paquete(p):
            continue
        if not promocion_vigente(p, ahora):
            continue
        ids = {x.id_producto for x in p.productos}
        if producto.id_producto in ids:
            resultado.append(p)
    return resultado


def _productos_combo(db: Session, promo: PromocionModel) -> List[ProductoModel]:
    ids = [x.id_producto for x in promo.productos]
    if not ids:
        return []
    productos = (
        db.query(ProductoModel)
        .filter(ProductoModel.id_producto.in_(ids), ProductoModel.activo == True)
        .all()
    )
    orden = {pid: i for i, pid in enumerate(ids)}
    productos.sort(key=lambda p: orden.get(p.id_producto, 999))
    return productos


def _distribuir_precio_combo(precios_base: List[float], precio_paquete: float) -> List[float]:
    if not precios_base:
        return []
    total_base = sum(precios_base)
    if total_base <= 0:
        n = len(precios_base)
        share = round(precio_paquete / n, 2)
        out = [share] * n
        out[-1] = round(precio_paquete - sum(out[:-1]), 2)
        return out
    asignados = []
    restante = precio_paquete
    for base in precios_base[:-1]:
        parte = round(precio_paquete * (base / total_base), 2)
        asignados.append(parte)
        restante -= parte
    asignados.append(round(restante, 2))
    return asignados


def calcular_combo(
    db: Session, id_promocion: int, cantidad_paquetes: float = 1
) -> dict:
    promo = (
        db.query(PromocionModel)
        .options(joinedload(PromocionModel.productos))
        .filter(PromocionModel.id_promocion == id_promocion)
        .first()
    )
    if not promo:
        raise DatosInvalidosException("Promoción no encontrada")
    if not es_promo_paquete(promo):
        raise DatosInvalidosException("Esta promoción no es un paquete/combo")
    if not promocion_vigente(promo):
        raise DatosInvalidosException(f"La promoción '{promo.nombre}' no está vigente")

    productos = _productos_combo(db, promo)
    if len(productos) < 2:
        raise DatosInvalidosException("El combo no tiene suficientes productos activos")

    cantidad_paquetes = float(cantidad_paquetes)
    precio_paquete = round(float(promo.valor) * cantidad_paquetes, 2)
    bases = [float(p.precio_venta) for p in productos]
    unitarios_combo = _distribuir_precio_combo(bases, precio_paquete)

    items = []
    for prod, precio_asignado, base in zip(productos, unitarios_combo, bases):
        unitario = round(precio_asignado / cantidad_paquetes, 2)
        descuento = round(base - unitario, 2)
        items.append(
            {
                "id_producto": prod.id_producto,
                "nombre": prod.nombre,
                "cantidad": cantidad_paquetes,
                "precio_unitario": unitario,
                "precio_original": round(base, 2),
                "descuento_unitario": max(descuento, 0),
                "id_promocion": promo.id_promocion,
            }
        )

    return {
        "id_promocion": promo.id_promocion,
        "nombre_promocion": promo.nombre,
        "precio_paquete": precio_paquete,
        "items": items,
    }


def combo_a_dict(promo: PromocionModel, db: Session) -> dict:
    productos = _productos_combo(db, promo)
    return {
        "id_promocion": promo.id_promocion,
        "nombre": promo.nombre,
        "tipo": promo.tipo,
        "valor": float(promo.valor),
        "descripcion": promo.descripcion,
        "ids_productos": [p.id_producto for p in productos],
        "productos": [{"id_producto": p.id_producto, "nombre": p.nombre} for p in productos],
    }


def dinero(valor) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def cerrar_unitario(subtotal, cantidad, precio_normal) -> tuple[float, float]:
    """Unitario solo si cantidad × unitario cierra al centavo. Si no, precio normal."""
    sub = dinero(subtotal)
    cant = Decimal(str(cantidad or 0))
    normal = dinero(precio_normal)
    if cant <= 0:
        return float(normal), 0.0
    unit = dinero(sub / cant)
    if dinero(unit * cant) == sub:
        desc = dinero(max(Decimal("0"), normal - unit))
        return float(unit), float(desc)
    return float(normal), 0.0


def armar_desglose(
    *,
    aplicaciones: int,
    unidades_normales,
    cantidad_requerida,
    valor_paquete,
    subtotal,
    nombre: str | None = None,
    tiene_promo: bool = False,
) -> list[dict]:
    """Desglose que suma el subtotal. No usa un promedio redondeado."""
    sub = dinero(subtotal)
    apps = int(aplicaciones or 0)
    sobrantes = Decimal(str(unidades_normales or 0))
    if apps <= 0:
        etiqueta = (nombre or "Promoción") if tiene_promo else "Precio normal"
        return [{"etiqueta": etiqueta, "importe": float(sub)}]
    precio_paquete = dinero(valor_paquete) if valor_paquete is not None else None
    n_req = int(cantidad_requerida or 0)
    if precio_paquete is not None and n_req > 0:
        importe_promo = dinero(precio_paquete * apps)
    else:
        importe_promo = sub
    if importe_promo > sub:
        importe_promo = sub
    importe_normal = dinero(sub - importe_promo)
    if apps == 1:
        etiqueta = "1 promoción"
    else:
        etiqueta = f"{apps} promociones"
    if n_req and precio_paquete is not None:
        etiqueta = f"{etiqueta} ({n_req} por ${precio_paquete})"
    partes = [{"etiqueta": etiqueta, "importe": float(importe_promo)}]
    if sobrantes > 0:
        n = int(sobrantes) if sobrantes == int(sobrantes) else float(sobrantes)
        partes.append({"etiqueta": f"{n} a precio normal", "importe": float(importe_normal)})
    elif importe_normal != 0:
        partes.append({"etiqueta": "Ajuste", "importe": float(importe_normal)})
    return partes


def presentar_importes(
    calc: dict,
    *,
    cantidad,
    precio_normal,
    aplicaciones: int = 0,
    unidades_normales=0,
    cantidad_requerida=None,
    valor_paquete=None,
) -> dict:
    """El subtotal es la autoridad. El unitario no puede producir otro total."""
    bruto = calc.get("subtotal")
    if bruto is None:
        bruto = calc.get("total_linea") or 0
    sub = dinero(bruto)
    unit, desc = cerrar_unitario(sub, cantidad, precio_normal)
    if int(aplicaciones or 0) > 0 and Decimal(str(unidades_normales or 0)) > 0:
        desc = 0.0
    calc["precio_unitario"] = unit
    calc["descuento_unitario"] = desc
    calc["subtotal"] = float(sub)
    calc["total_linea"] = float(sub)
    calc["desglose"] = armar_desglose(
        aplicaciones=int(aplicaciones or 0),
        unidades_normales=unidades_normales or 0,
        cantidad_requerida=cantidad_requerida,
        valor_paquete=valor_paquete,
        subtotal=sub,
        nombre=calc.get("nombre_promocion"),
        tiene_promo=bool(calc.get("id_promocion")),
    )
    return calc


def _linea_sin_promocion(
    precio_base: float,
    precio_extras: float,
    costo: float,
    precio_original_unitario: float,
    cantidad: float = 1,
) -> dict:
    margen = margen_porcentaje(precio_base, costo) if costo > 0 else None
    cant = Decimal(str(cantidad))
    total = dinero(precio_original_unitario) * cant
    total = dinero(total)
    normales = int(cant) if cant == int(cant) else float(cant)
    calc = {
        "id_promocion": None,
        "nombre_promocion": None,
        "tipo": None,
        "precio_base": precio_base,
        "precio_base_promo": precio_base,
        "precio_extras": precio_extras,
        "precio_unitario": precio_original_unitario,
        "precio_original_unitario": precio_original_unitario,
        "descuento_unitario": 0,
        "costo_unitario": costo,
        "margen_porcentaje": margen,
        "margen_ok": True,
        "mensaje": None,
        "aplicaciones": 0,
        "unidades_normales": normales,
        "total_linea": float(total),
        "subtotal": float(total),
        "promocion_aplicaciones": 0,
    }
    return presentar_importes(
        calc,
        cantidad=cant,
        precio_normal=precio_original_unitario,
        aplicaciones=0,
        unidades_normales=normales,
    )


def _margen_insuficiente(promo: PromocionModel, precio: Decimal, costo: Decimal) -> bool:
    if promo.margen_minimo is None or costo <= 0 or precio <= 0:
        return False
    margen = (precio - costo) / precio * Decimal("100")
    return margen < Decimal(str(promo.margen_minimo))


def total_nx_precio(
    precio_normal: Decimal,
    cantidad: int,
    cantidad_requerida: int,
    precio_paquete: Decimal,
) -> tuple[Decimal, int, int]:
    """N unidades por un precio. Lo que no completa el paquete queda a precio normal."""
    requerida = max(1, int(cantidad_requerida))
    cant = max(0, int(cantidad))
    aplicaciones = cant // requerida
    sobrantes = cant % requerida
    total = dinero(precio_paquete) * aplicaciones + dinero(precio_normal) * sobrantes
    return dinero(total), aplicaciones, sobrantes


def _calcular_ticket_en_linea(
    db: Session,
    producto: ProductoModel,
    promo: PromocionModel,
    cantidad: float,
    precio_extras: float,
    precio_base: float,
    costo: float,
    precio_original_unitario: float,
) -> dict:
    """Precio de una línea con promoción N×precio. Cantidad incompleta = precio normal."""
    cant = int(float(cantidad))
    if cant < 1:
        cant = 1
    normal = _linea_sin_promocion(
        precio_base, precio_extras, costo, precio_original_unitario, cant
    )
    precio_normal = dinero(precio_original_unitario)
    n_req = max(1, int(promo.cantidad_requerida or 1))
    if promo.tipo == "CANTIDAD_PRECIO":
        total, aplicaciones, sobrantes = total_nx_precio(
            precio_normal, cant, n_req, dinero(promo.valor)
        )
    elif promo.tipo == "DESCUENTO_FIJO":
        aplicaciones = cant // n_req
        sobrantes = cant % n_req
        base_bundle = precio_normal * n_req
        precio_bundle = max(Decimal("0"), base_bundle - dinero(promo.valor))
        total = dinero(precio_bundle * aplicaciones + precio_normal * sobrantes)
    else:
        return normal
    if aplicaciones < 1 or total >= precio_normal * cant:
        return normal
    costo_promo = dinero(costo) * (aplicaciones * n_req)
    precio_promo = total - precio_normal * sobrantes
    if _margen_insuficiente(promo, precio_promo, costo_promo):
        normal["mensaje"] = (
            f"La promoción '{promo.nombre}' no se aplicó: el margen quedaría "
            "por debajo del mínimo. Se cobra precio normal."
        )
        return normal
    precio_paquete = dinero(promo.valor) if promo.tipo == "CANTIDAD_PRECIO" else dinero(
        max(Decimal("0"), precio_normal * n_req - dinero(promo.valor))
    )
    margen = margen_porcentaje(float(dinero(total / Decimal(cant))), costo) if costo > 0 else None
    calc = {
        "id_promocion": promo.id_promocion,
        "nombre_promocion": promo.nombre,
        "tipo": promo.tipo,
        "precio_base": precio_base,
        "precio_base_promo": precio_base,
        "precio_extras": precio_extras,
        "precio_unitario": precio_original_unitario,
        "precio_original_unitario": precio_original_unitario,
        "descuento_unitario": 0,
        "costo_unitario": costo,
        "margen_porcentaje": margen,
        "margen_ok": True,
        "mensaje": None,
        "aplicaciones": aplicaciones,
        "unidades_normales": sobrantes,
        "total_linea": float(total),
        "subtotal": float(total),
        "promocion_aplicaciones": aplicaciones,
        "valor_promocion": float(promo.valor),
        "cantidad_requerida": n_req,
    }
    return presentar_importes(
        calc,
        cantidad=cant,
        precio_normal=precio_original_unitario,
        aplicaciones=aplicaciones,
        unidades_normales=sobrantes,
        cantidad_requerida=n_req,
        valor_paquete=precio_paquete,
    )


def calcular_linea(
    db: Session,
    producto: ProductoModel,
    cantidad: float,
    precio_extras: float = 0,
    id_promocion: Optional[int] = None,
    ahora: Optional[datetime] = None,
    sin_promocion: bool = False,
) -> dict:
    precio_base = float(producto.precio_venta)
    costo = costo_producto(db, producto.id_producto)
    precio_original_unitario = round(precio_base + precio_extras, 2)

    normal = _linea_sin_promocion(
        precio_base, precio_extras, costo, precio_original_unitario, cantidad
    )
    if sin_promocion:
        return normal

    promo = None
    calc_ticket = normal
    if id_promocion:
        promo = (
            db.query(PromocionModel)
            .options(
                joinedload(PromocionModel.productos),
                joinedload(PromocionModel.categorias),
            )
            .filter(PromocionModel.id_promocion == id_promocion)
            .first()
        )
        if not promo:
            raise DatosInvalidosException("Promoción no encontrada")
        if not promocion_vigente(promo, ahora) or es_promo_paquete(promo):
            return normal
        if not producto_elegible(promo, producto):
            raise DatosInvalidosException(
                f"La promoción '{promo.nombre}' no aplica a este producto"
            )
        if es_promo_ticket(promo):
            return _calcular_ticket_en_linea(
                db, producto, promo, cantidad, precio_extras,
                precio_base, costo, precio_original_unitario,
            )
    else:
        aplicables = listar_aplicables(db, producto, ahora)
        if aplicables:
            promo = min(
                aplicables,
                key=lambda p: aplicar_promo_base(
                    precio_base, p.tipo, float(p.valor), cantidad
                ),
            )
        tickets = [
            p for p in listar_promos_ticket_producto(db, producto, ahora)
            if p.tipo == "CANTIDAD_PRECIO"
        ]
        calc_ticket = normal
        if tickets:
            mejor_ticket = min(
                tickets,
                key=lambda p: _calcular_ticket_en_linea(
                    db, producto, p, cantidad, precio_extras,
                    precio_base, costo, precio_original_unitario,
                )["total_linea"],
            )
            calc_ticket = _calcular_ticket_en_linea(
                db, producto, mejor_ticket, cantidad, precio_extras,
                precio_base, costo, precio_original_unitario,
            )
        if promo is None:
            return calc_ticket if calc_ticket.get("id_promocion") else normal

    if promo:
        precio_base_promo = aplicar_promo_base(
            precio_base, promo.tipo, float(promo.valor), cantidad
        )
        margen = margen_porcentaje(precio_base_promo, costo)
        margen_min = float(promo.margen_minimo) if promo.margen_minimo is not None else None
        margen_ok = True
        mensaje = None
        if costo > 0 and margen is not None and margen_min is not None and margen < margen_min:
            margen_ok = False
            mensaje = (
                f"Margen {margen}% inferior al mínimo {margen_min}% "
                f"para la promoción '{promo.nombre}'"
            )
        precio_unitario = round(precio_base_promo + precio_extras, 2)
        total = dinero(Decimal(str(precio_unitario)) * Decimal(str(cantidad)))
        calc_linea = {
            "id_promocion": promo.id_promocion,
            "nombre_promocion": promo.nombre,
            "tipo": promo.tipo,
            "precio_base": precio_base,
            "precio_base_promo": precio_base_promo,
            "precio_extras": precio_extras,
            "precio_unitario": precio_unitario,
            "precio_original_unitario": precio_original_unitario,
            "descuento_unitario": 0,
            "costo_unitario": costo,
            "margen_porcentaje": margen,
            "margen_ok": margen_ok,
            "mensaje": mensaje,
            "aplicaciones": 0,
            "unidades_normales": 0,
            "total_linea": float(total),
            "subtotal": float(total),
            "promocion_aplicaciones": 0,
        }
        presentar_importes(
            calc_linea,
            cantidad=cantidad,
            precio_normal=precio_original_unitario,
        )
        if id_promocion is None and not margen_ok:
            return normal
        if id_promocion is None and calc_ticket.get("id_promocion"):
            if calc_ticket["total_linea"] < calc_linea["total_linea"]:
                return calc_ticket
        return calc_linea

    return normal


MESES_ES = (
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)


def resumen_promociones_ventas(
    db: Session,
    periodo: Optional[str] = None,
    fecha: Optional[date] = None,
    anio: Optional[int] = None,
    mes: Optional[int] = None,
) -> dict:
    q = (
        db.query(
            PromocionModel.id_promocion,
            PromocionModel.nombre,
            func.coalesce(func.sum(DetalleVentaModel.cantidad), 0),
            func.coalesce(
                func.sum(DetalleVentaModel.descuento_unitario * DetalleVentaModel.cantidad),
                0,
            ),
            func.coalesce(func.sum(DetalleVentaModel.subtotal), 0),
        )
        .join(
            DetalleVentaModel,
            DetalleVentaModel.id_promocion == PromocionModel.id_promocion,
        )
        .join(VentaModel, VentaModel.id_venta == DetalleVentaModel.id_venta)
    )

    periodo_label = "Histórico total"
    if periodo == "dia" and fecha:
        q = q.filter(*filtro_dia_mx(VentaModel.fecha_hora, fecha))
        periodo_label = fecha.isoformat()
    elif periodo == "mes" and anio and mes:
        q = q.filter(*filtro_mes_mx(VentaModel.fecha_hora, anio, mes))
        nombre_mes = MESES_ES[mes] if 1 <= mes <= 12 else str(mes)
        periodo_label = f"{nombre_mes} {anio}"
    elif periodo == "anio" and anio:
        q = q.filter(*filtro_anio_mx(VentaModel.fecha_hora, anio))
        periodo_label = str(anio)

    filas = (
        q.group_by(PromocionModel.id_promocion, PromocionModel.nombre)
        .order_by(
            func.sum(DetalleVentaModel.descuento_unitario * DetalleVentaModel.cantidad).desc()
        )
        .all()
    )
    total_ventas = sum(int(float(r[2])) for r in filas)
    total_desc = sum(float(r[3]) for r in filas)
    total_ingresos = sum(float(r[4]) for r in filas)
    return {
        "total_ventas_con_promo": total_ventas,
        "total_descuento": round(total_desc, 2),
        "total_ingresos_con_promo": round(total_ingresos, 2),
        "periodo_label": periodo_label,
        "promociones_usadas": [
            {
                "id_promocion": r[0],
                "nombre": r[1],
                "usos": int(float(r[2])),
                "descuento_total": round(float(r[3]), 2),
                "ingresos_con_promo": round(float(r[4]), 2),
            }
            for r in filas
        ],
    }
