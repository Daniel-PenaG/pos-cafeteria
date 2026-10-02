"""Promociones a nivel ticket (varias líneas / unidades elegibles)."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models import ProductoModel, PromocionModel
from decimal import Decimal

from app.services.promocion_service import (
    promocion_vigente,
    producto_elegible,
    es_promo_paquete,
    calcular_linea,
    costo_producto,
    es_promo_ticket,
    TIPOS_TICKET,
    dinero,
    presentar_importes,
    _margen_insuficiente,
    _distribuir_precio_combo,
    _productos_combo,
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
        if (
            linea.get("es_paquete")
            or linea.get("precio_resuelto")
            or linea.get("sin_promocion")
            or linea.get("forzar_promo_linea")
        ):
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


def _aplicar_promo_unidades(unidades: List[dict], promo: PromocionModel, db: Session | None = None) -> float:
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
        if precio_bundle >= base_bundle - 0.001:
            continue
        if db is not None:
            costo_bundle = sum(
                (Decimal(str(costo_producto(db, u["id_producto"]))) for u in bundle),
                Decimal("0"),
            )
            if _margen_insuficiente(promo, dinero(precio_bundle), dinero(costo_bundle)):
                continue
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
            u["cantidad_requerida"] = n_req

    return _round2(descuento)


def _simular_ticket_promos(
    unidades: List[dict], promos: List[PromocionModel], db: Session | None = None
) -> tuple[List[dict], float, List[dict]]:
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
        desc = _aplicar_promo_unidades(copia, promo, db)
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
        d = _aplicar_promo_unidades(mejor_unidades, promo, db)
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
        "valor_promocion": calc.get("valor_promocion"),
        "promocion_aplicaciones": calc.get("promocion_aplicaciones") or 0,
        "aplicaciones": calc.get("aplicaciones") or 0,
        "unidades_normales": calc.get("unidades_normales") or 0,
        "subtotal": calc.get("subtotal"),
        "total_linea": calc.get("total_linea"),
        "desglose": calc.get("desglose") or [],
        "cantidad_requerida": calc.get("cantidad_requerida"),
        "costo_unitario": calc["costo_unitario"],
        "margen_ok": calc["margen_ok"],
        "mensaje": calc.get("mensaje"),
    }


def _resolver_paquetes(db: Session, trabajo: List[dict], ahora) -> None:
    """Aplica un paquete solo si están todos los productos. Si falta uno, precio normal."""
    from collections import defaultdict

    grupos: dict[int, list[int]] = defaultdict(list)
    for i, item in enumerate(trabajo):
        if item.get("es_paquete") and item.get("id_promocion"):
            grupos[int(item["id_promocion"])].append(i)

    for id_promo, indices in grupos.items():
        promo = (
            db.query(PromocionModel)
            .options(joinedload(PromocionModel.productos))
            .filter(PromocionModel.id_promocion == id_promo)
            .first()
        )

        def _soltar():
            for i in indices:
                trabajo[i]["es_paquete"] = False
                trabajo[i]["id_promocion"] = None
                trabajo[i]["sin_promocion"] = True

        if not promo or not es_promo_paquete(promo) or not promocion_vigente(promo, ahora):
            _soltar()
            continue
        productos = _productos_combo(db, promo)
        requeridos = [p.id_producto for p in productos]
        if len(requeridos) < 2:
            _soltar()
            continue
        cantidades: dict[int, int] = defaultdict(int)
        for i in indices:
            pid = int(trabajo[i]["id_producto"])
            if pid in requeridos:
                cantidades[pid] += int(float(trabajo[i]["cantidad"]))
        if any(cantidades[pid] < 1 for pid in requeridos):
            _soltar()
            continue
        aplicaciones = min(cantidades[pid] for pid in requeridos)
        if promo.limite_usos_por_ticket is not None:
            aplicaciones = min(aplicaciones, int(promo.limite_usos_por_ticket))
        if aplicaciones < 1:
            _soltar()
            continue
        precio_paquete = dinero(promo.valor) * aplicaciones
        costo = sum((Decimal(str(costo_producto(db, pid))) for pid in requeridos), Decimal("0"))
        costo *= aplicaciones
        if _margen_insuficiente(promo, precio_paquete, dinero(costo)):
            _soltar()
            continue
        bases = [float(p.precio_venta) for p in productos]
        shares = _distribuir_precio_combo(bases, float(precio_paquete))
        share_por_producto = {pid: dinero(share) for pid, share in zip(requeridos, shares)}
        consumido: dict[int, int] = defaultdict(int)
        porciones = []
        for i in indices:
            item = trabajo[i]
            pid = int(item["id_producto"])
            cant = int(float(item["cantidad"]))
            if pid not in share_por_producto or cant < 1:
                item["es_paquete"] = False
                item["id_promocion"] = None
                continue
            en_paquete = max(0, min(cant, aplicaciones - consumido[pid]))
            consumido[pid] += en_paquete
            sobrantes = cant - en_paquete
            normal = dinero(float(item["_producto"].precio_venta) + _precio_extras_linea(item))
            if en_paquete <= 0 or aplicaciones < 1:
                dinero_paq = dinero(0)
            else:
                dinero_paq = dinero(
                    share_por_producto[pid] * Decimal(en_paquete) / Decimal(aplicaciones)
                )
            porciones.append((item, dinero_paq, normal, sobrantes, en_paquete, cant, pid))
        if porciones:
            suma_paq = sum((p[1] for p in porciones), Decimal("0"))
            delta = dinero(precio_paquete - suma_paq)
            if delta != 0:
                item, paq, normal, sobrantes, en_paquete, cant, pid = porciones[-1]
                porciones[-1] = (item, dinero(paq + delta), normal, sobrantes, en_paquete, cant, pid)
        for item, dinero_paq, normal, sobrantes, en_paquete, cant, pid in porciones:
            subtotal = dinero(dinero_paq + normal * Decimal(sobrantes))
            partes = []
            if en_paquete:
                partes.append({"etiqueta": promo.nombre, "importe": float(dinero_paq)})
            if sobrantes:
                partes.append({
                    "etiqueta": f"{sobrantes} a precio normal",
                    "importe": float(dinero(normal * Decimal(sobrantes))),
                })
            if not partes:
                partes = [{"etiqueta": "Precio normal", "importe": float(subtotal)}]
            item.update(
                {
                    "es_paquete": False,
                    "precio_resuelto": True,
                    "precio_original": float(normal),
                    "precio_original_unitario": float(normal),
                    "id_promocion": promo.id_promocion if en_paquete else None,
                    "nombre_promocion": promo.nombre if en_paquete else None,
                    "tipo_promocion": promo.tipo if en_paquete else None,
                    "valor_promocion": float(promo.valor) if en_paquete else None,
                    "promocion_aplicaciones": aplicaciones if en_paquete else 0,
                    "aplicaciones": 1 if en_paquete else 0,
                    "unidades_normales": sobrantes,
                    "margen_ok": True,
                    "mensaje": None,
                    "costo_unitario": costo_producto(db, pid),
                    "subtotal": float(subtotal),
                    "total_linea": float(subtotal),
                }
            )
            presentar_importes(
                item,
                cantidad=cant,
                precio_normal=normal,
                aplicaciones=1 if en_paquete and sobrantes else 0,
                unidades_normales=sobrantes if en_paquete else 0,
                cantidad_requerida=1 if en_paquete and sobrantes else None,
                valor_paquete=dinero_paq if en_paquete and sobrantes else None,
            )
            item["desglose"] = partes
            item["precio_original"] = float(normal)


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

    _resolver_paquetes(db, trabajo, ahora)
    promos_ticket = listar_promos_ticket(db, ahora)
    unidades = _expandir_unidades(trabajo, db)
    unidades, desc_ticket, resumen = _simular_ticket_promos(unidades, promos_ticket, db)

    for li, item in enumerate(trabajo):
        if item.get("precio_resuelto"):
            continue

        units_line = [u for u in unidades if u["line_index"] == li]
        if units_line:
            precio_orig = units_line[0]["precio_full"]
            total_line = _round2(sum(u["precio_final"] for u in units_line))
            cant = len(units_line)
            promo_ids = {u["id_promocion"] for u in units_line if u["id_promocion"]}
            promo_id = promo_ids.pop() if len(promo_ids) == 1 else None
            if promo_id:
                promo_ref = next(u for u in units_line if u["id_promocion"] == promo_id)
                marcadas = sum(1 for u in units_line if u["id_promocion"] == promo_id)
                n_req = max(1, int(promo_ref.get("cantidad_requerida") or 1))
                aplicaciones = marcadas // n_req
                sobrantes = cant - marcadas
                precio_paquete = promo_ref.get("valor_promocion")
                if promo_ref.get("tipo_promocion") == "DESCUENTO_FIJO":
                    precio_paquete = dinero(
                        Decimal(str(precio_orig)) * n_req - dinero(precio_paquete or 0)
                    )
                item.update(
                    {
                        "precio_original": precio_orig,
                        "precio_original_unitario": precio_orig,
                        "id_promocion": promo_id,
                        "nombre_promocion": promo_ref.get("nombre_promocion"),
                        "tipo_promocion": promo_ref.get("tipo_promocion"),
                        "valor_promocion": promo_ref.get("valor_promocion"),
                        "promocion_aplicaciones": aplicaciones,
                        "aplicaciones": aplicaciones,
                        "unidades_normales": sobrantes,
                        "margen_ok": True,
                        "mensaje": None,
                        "costo_unitario": costo_producto(db, item["id_producto"]),
                        "subtotal": total_line,
                        "total_linea": total_line,
                    }
                )
                presentar_importes(
                    item,
                    cantidad=cant,
                    precio_normal=precio_orig,
                    aplicaciones=aplicaciones,
                    unidades_normales=sobrantes,
                    cantidad_requerida=n_req,
                    valor_paquete=precio_paquete,
                )
                continue

        if item.get("precio_unitario") is not None and item.get("subtotal") is not None:
            continue

        producto = item["_producto"]
        if not producto:
            continue
        precio_extras = _precio_extras_linea(item)
        sin_promo = bool(item.get("sin_promocion"))
        id_calc = None if sin_promo else item.get("id_promocion")
        if id_calc and not item.get("forzar_promo_linea"):
            promo_linea = (
                db.query(PromocionModel)
                .options(joinedload(PromocionModel.productos))
                .filter(PromocionModel.id_promocion == id_calc)
                .first()
            )
            if (
                not promo_linea
                or es_promo_paquete(promo_linea)
                or es_promo_ticket(promo_linea)
                or not promocion_vigente(promo_linea, ahora)
            ):
                id_calc = None
        elif id_calc and item.get("forzar_promo_linea"):
            promo_linea = (
                db.query(PromocionModel)
                .options(joinedload(PromocionModel.productos))
                .filter(PromocionModel.id_promocion == id_calc)
                .first()
            )
            if (
                not promo_linea
                or not promocion_vigente(promo_linea, ahora)
                or es_promo_paquete(promo_linea)
            ):
                id_calc = None
                sin_promo = True
        calc = calcular_linea(
            db, producto, float(item["cantidad"]), precio_extras,
            id_calc, ahora=ahora, sin_promocion=sin_promo,
        )
        item.update(_calc_a_linea(calc))
        if calc.get("subtotal") is not None:
            item["subtotal"] = calc["subtotal"]
            item["total_linea"] = calc["subtotal"]
            item["aplicaciones"] = calc.get("aplicaciones") or 0
            item["unidades_normales"] = calc.get("unidades_normales") or 0
            item["promocion_aplicaciones"] = calc.get("promocion_aplicaciones") or 0

    total = Decimal("0")
    normal_total = Decimal("0")
    for linea in trabajo:
        if linea.get("subtotal") is not None:
            total += dinero(linea["subtotal"])
        else:
            total += dinero(linea.get("cantidad") or 0) * dinero(linea.get("precio_unitario") or 0)
    for item in trabajo:
        if item.get("_producto"):
            pe = _precio_extras_linea(item)
            normal_total += dinero(float(item["_producto"].precio_venta) + pe) * dinero(item["cantidad"])
    total = dinero(total)
    normal_total = dinero(normal_total)
    descuento = dinero(max(Decimal("0"), normal_total - total))

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
        "subtotal_normal": float(normal_total),
        "descuento_promociones": float(descuento),
        "total": float(total),
    }
