from datetime import datetime, time
import math
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import (
    ProductoModel,
    PromocionModel,
    PromocionProductoModel,
    PromocionCategoriaModel,
    RecetaModel,
)
from app.exceptions import DatosInvalidosException


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


def promocion_vigente(promo: PromocionModel, ahora: Optional[datetime] = None) -> bool:
    if not promo.activa:
        return False
    ahora = ahora or datetime.now()
    if promo.fecha_inicio and ahora < promo.fecha_inicio:
        return False
    if promo.fecha_fin and ahora > promo.fecha_fin:
        return False
    dias = _parse_dias(promo.dias_semana)
    if dias is not None and ahora.weekday() not in dias:
        return False
    h_ini = _parse_hora(promo.hora_inicio)
    h_fin = _parse_hora(promo.hora_fin)
    if h_ini or h_fin:
        t = ahora.time()
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


def listar_aplicables(
    db: Session, producto: ProductoModel, ahora: Optional[datetime] = None
) -> List[PromocionModel]:
    promos = db.query(PromocionModel).filter(PromocionModel.activa == True).all()
    resultado = []
    for p in promos:
        if promocion_vigente(p, ahora) and producto_elegible(p, producto):
            resultado.append(p)
    return resultado


def calcular_linea(
    db: Session,
    producto: ProductoModel,
    cantidad: float,
    precio_extras: float = 0,
    id_promocion: Optional[int] = None,
    ahora: Optional[datetime] = None,
) -> dict:
    precio_base = float(producto.precio_venta)
    costo = costo_producto(db, producto.id_producto)
    precio_original_unitario = round(precio_base + precio_extras, 2)

    promo = None
    if id_promocion:
        promo = (
            db.query(PromocionModel).filter(PromocionModel.id_promocion == id_promocion).first()
        )
        if not promo:
            raise DatosInvalidosException("Promoción no encontrada")
        if not promocion_vigente(promo, ahora):
            raise DatosInvalidosException(f"La promoción '{promo.nombre}' no está vigente")
        if not producto_elegible(promo, producto):
            raise DatosInvalidosException(
                f"La promoción '{promo.nombre}' no aplica a este producto"
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
        descuento = round(precio_original_unitario - precio_unitario, 2)
        return {
            "id_promocion": promo.id_promocion,
            "nombre_promocion": promo.nombre,
            "tipo": promo.tipo,
            "precio_base": precio_base,
            "precio_base_promo": precio_base_promo,
            "precio_extras": precio_extras,
            "precio_unitario": precio_unitario,
            "precio_original_unitario": precio_original_unitario,
            "descuento_unitario": max(descuento, 0),
            "costo_unitario": costo,
            "margen_porcentaje": margen,
            "margen_ok": margen_ok,
            "mensaje": mensaje,
        }

    margen = margen_porcentaje(precio_base, costo) if costo > 0 else None
    return {
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
    }
