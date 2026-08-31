"""Promociones a nivel ticket (varias líneas / unidades elegibles)."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models import ProductoModel, PromocionModel
from app.services.promocion_service import (
    promocion_vigente,
    producto_elegible,
    es_promo_paquete,
    calcular_linea,
    costo_producto,
    es_promo_ticket,
    TIPOS_TICKET,
)


def _round2(n: float) -> float:
    return round(float(n), 2)


def listar_promos_ticket(db: Session, ahora: Optional[datetime] = None) -> List[PromocionModel]:
    promos = (
        db.query(PromocionModel)
        .options(
            joinedload(PromocionModel.productos),
            joinedload(PromocionModel.categorias),
        )
        .filter(PromocionModel.activa == True, PromocionModel.tipo.in_(list(TIPOS_TICKET)))
        .all()
    )
    return [p for p in promos if promocion_vigente(p, ahora)]


def _precio_extras_linea(linea: dict) -> float:
    if linea.get("precio_extras") is not None:
        return float(linea["precio_extras"])
    return sum(float(e.get("precio", 0)) for e in (linea.get("extras") or []))


def _linea_es_paquete(db: Session, linea: dict) -> bool:
    id_promo = linea.get("id_promocion")
    if not id_promo:
        return False
    promo = (
        db.query(PromocionModel)
        .options(joinedload(PromocionModel.productos))
        .filter(PromocionModel.id_promocion == id_promo)
        .first()
    )
    return bool(promo and es_promo_paquete(promo))


def _expandir_unidades(lineas: List[dict], db: Session) -> List[dict]:
    unidades: List[dict] = []
    for li, linea in enumerate(lineas):
        if linea.get("es_paquete"):
            continue
        producto = linea.get("_producto") or db.query(ProductoModel).filter(
            ProductoModel.id_producto == linea["id_producto"]
        ).first()
        if not producto:
            continue
        precio_extras = _precio_extras_linea(linea)
        precio_full = _round2(float(producto.precio_venta) + precio_extras)
        cantidad = int(float(linea["cantidad"]))
        for _ in range(cantidad):
            unidades.append(
                {
                    "line_index": li,
                    "id_producto": linea["id_producto"],
                    "precio_full": precio_full,
                    "precio_final": precio_full,
                    "id_promocion": None,
                    "nombre_promocion": None,
                    "tipo_promocion": None,
                    "valor_promocion": None,
                    "_producto": producto,
                }
            )
    return unidades


def _aplicar_promo_unidades(unidades: List[dict], promo: PromocionModel) -> float:
    """Marca unidades elegibles con precio de promo. Retorna descuento total generado."""
    elegibles = [
        u for u in unidades
        if u["id_promocion"] is None and producto_elegible(promo, u["_producto"])
    ]
    n_req = max(1, int(promo.cantidad_requerida or 2))
    limite = promo.limite_usos_por_ticket
    max_bundles = len(elegibles) // n_req
    if limite is not None:
        max_bundles = min(max_bundles, int(limite))

    descuento = 0.0
    cursor = 0
    for _ in range(max_bundles):
        bundle = elegibles[cursor : cursor + n_req]
        cursor += n_req
        base_bundle = sum(u["precio_full"] for u in bundle)
        if promo.tipo == "CANTIDAD_PRECIO":
            precio_bundle = float(promo.valor)
        else:
            precio_bundle = max(0.0, base_bundle - float(promo.valor))
        descuento += base_bundle - precio_bundle

        restante = precio_bundle
        for i, u in enumerate(bundle):
            if i == len(bundle) - 1:
                share = _round2(restante)
            else:
                share = (
                    _round2(precio_bundle * (u["precio_full"] / base_bundle))
                    if base_bundle > 0
                    else _round2(precio_bundle / n_req)
                )
                restante -= share
            u["precio_final"] = share
            u["id_promocion"] = promo.id_promocion
            u["nombre_promocion"] = promo.nombre
            u["tipo_promocion"] = promo.tipo
            u["valor_promocion"] = float(promo.valor)

    return _round2(descuento)


def _simular_ticket_promos(unidades: List[dict], promos: List[PromocionModel]) -> tuple[List[dict], float, List[dict]]:
    """
    Decide promos ticket (no acumulables: elige la de mayor descuento).
    Promos acumulables se aplican después sobre unidades restantes.
    """
    if not unidades or not promos:
        return unidades, 0.0, []

    no_acum = [p for p in promos if not p.acumulable]
    acum = [p for p in promos if p.acumulable]

    mejor_unidades = deepcopy(unidades)
    mejor_desc = 0.0
    mejor_promo: Optional[PromocionModel] = None

    for promo in no_acum:
        copia = deepcopy(unidades)
        desc = _aplicar_promo_unidades(copia, promo)
        if desc > mejor_desc:
            mejor_desc = desc
            mejor_unidades = copia
            mejor_promo = promo

    resumen: List[dict] = []
    if mejor_promo and mejor_desc > 0:
        n_req = max(1, int(mejor_promo.cantidad_requerida or 2))
        usos = sum(1 for u in mejor_unidades if u["id_promocion"] == mejor_promo.id_promocion) // n_req
        resumen.append(
            {
                "id_promocion": mejor_promo.id_promocion,
                "nombre": mejor_promo.nombre,
                "tipo": mejor_promo.tipo,
                "aplicaciones": usos,
                "descuento": mejor_desc,
            }
        )
    else:
        mejor_unidades = deepcopy(unidades)

    desc_acum = 0.0
    for promo in acum:
        d = _aplicar_promo_unidades(mejor_unidades, promo)
        if d > 0:
            desc_acum += d
            n_req = max(1, int(promo.cantidad_requerida or 2))
            usos = sum(1 for u in mejor_unidades if u["id_promocion"] == promo.id_promocion) // n_req
            resumen.append(
                {
                    "id_promocion": promo.id_promocion,
                    "nombre": promo.nombre,
                    "tipo": promo.tipo,
                    "aplicaciones": usos,
                    "descuento": d,
                }
            )

    return mejor_unidades, _round2(mejor_desc + desc_acum), resumen


def _calc_a_linea(calc: dict) -> dict:
    return {
        "precio_unitario": calc["precio_unitario"],
        "precio_original": calc["precio_original_unitario"],
        "descuento_unitario": calc["descuento_unitario"],
        "id_promocion": calc["id_promocion"],
        "nombre_promocion": calc.get("nombre_promocion"),
        "tipo_promocion": calc.get("tipo"),
        "valor_promocion": None,
        "promocion_aplicaciones": 0,
        "costo_unitario": calc["costo_unitario"],
        "margen_ok": calc["margen_ok"],
        "mensaje": calc.get("mensaje"),
    }


def recalcular_lineas_ticket(
    db: Session,
    lineas: List[dict],
    ahora: Optional[datetime] = None,
) -> dict:
    if not lineas:
        return {
            "lineas": [],
            "resumen_promociones": [],
            "subtotal_normal": 0.0,
            "descuento_promociones": 0.0,
            "total": 0.0,
        }

    trabajo: List[dict] = []
    subtotal_normal = 0.0
    for linea in lineas:
        item = dict(linea)
        item["es_paquete"] = _linea_es_paquete(db, item)
        producto = db.query(ProductoModel).filter(
            ProductoModel.id_producto == item["id_producto"]
        ).first()
        item["_producto"] = producto
        if producto:
            pe = _precio_extras_linea(item)
            item["precio_extras"] = pe
            subtotal_normal += (float(producto.precio_venta) + pe) * float(item["cantidad"])
        trabajo.append(item)

    promos_ticket = listar_promos_ticket(db, ahora)
    unidades = _expandir_unidades(trabajo, db)
    unidades, desc_ticket, resumen = _simular_ticket_promos(unidades, promos_ticket)

    for item in trabajo:
        if item.get("es_paquete"):
            producto = item["_producto"]
            precio_extras = _precio_extras_linea(item)
            calc = calcular_linea(
                db, producto, float(item["cantidad"]), precio_extras,
                item.get("id_promocion"), ahora=ahora,
            )
            item.update(_calc_a_linea(calc))
            continue

        li = trabajo.index(item)
        units_line = [u for u in unidades if u["line_index"] == li]
        if units_line:
            precio_orig = units_line[0]["precio_full"]
            total_line = sum(u["precio_final"] for u in units_line)
            cant = len(units_line)
            promo_ids = {u["id_promocion"] for u in units_line if u["id_promocion"]}
            promo_id = promo_ids.pop() if len(promo_ids) == 1 else None
            unitario = _round2(total_line / cant)
            item.update(
                {
                    "precio_unitario": unitario,
                    "precio_original": precio_orig,
                    "descuento_unitario": _round2(max(0, precio_orig - unitario)),
                    "id_promocion": promo_id,
                    "nombre_promocion": next((u["nombre_promocion"] for u in units_line if u["nombre_promocion"]), None),
                    "tipo_promocion": next((u["tipo_promocion"] for u in units_line if u["tipo_promocion"]), None),
                    "valor_promocion": next((u["valor_promocion"] for u in units_line if u["valor_promocion"] is not None), None),
                    "promocion_aplicaciones": 0,
                    "margen_ok": True,
                    "mensaje": None,
                    "costo_unitario": costo_producto(db, item["id_producto"]),
                }
            )
            if promo_id:
                continue

        if item.get("precio_unitario") is not None:
            continue

        producto = item["_producto"]
        if not producto:
            continue
        precio_extras = _precio_extras_linea(item)
        sin_promo = bool(item.get("sin_promocion"))
        calc = calcular_linea(
            db, producto, float(item["cantidad"]), precio_extras,
            None if sin_promo else item.get("id_promocion"),
            ahora=ahora, sin_promocion=sin_promo,
        )
        item.update(_calc_a_linea(calc))

    total = sum(float(l["cantidad"]) * float(l.get("precio_unitario", 0)) for l in trabajo)
    descuento = _round2(max(0, subtotal_normal - total))

    out_lineas = []
    for item in trabajo:
        out = {
            k: v for k, v in item.items()
            if not k.startswith("_") and k not in ("es_paquete",)
        }
        out_lineas.append(out)

    return {
        "lineas": out_lineas,
        "resumen_promociones": resumen,
        "subtotal_normal": _round2(subtotal_normal),
        "descuento_promociones": descuento,
        "total": _round2(total),
    }
