"""Reportes avanzados de promociones."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from app.models import (
    PromocionModel,
    DetalleVentaModel,
    VentaModel,
)
from app.utils.timezone_mx import (
    filtro_rango_mx,
    fecha_mx_desde_utc_naive,
    datetime_mx_desde_utc_naive,
)


def _round2(n: float) -> float:
    return round(float(n), 2)


def _safe_div(a: float, b: float) -> float:
    return _round2(a / b) if b else 0.0


def _parse_hora(texto: Optional[str]) -> Optional[time]:
    if not texto:
        return None
    h, m = texto.split(":")
    return time(int(h), int(m))


def _venta_en_ventana_promo(venta: VentaModel, promo: PromocionModel) -> bool:
    dt = datetime_mx_desde_utc_naive(venta.fecha_hora)
    if promo.dias_semana:
        dias = {int(x.strip()) for x in promo.dias_semana.split(",") if x.strip()}
        if dt.weekday() not in dias:
            return False
    h_ini = _parse_hora(promo.hora_inicio)
    h_fin = _parse_hora(promo.hora_fin)
    if h_ini or h_fin:
        t = dt.time()
        if h_ini and h_fin:
            if h_ini <= h_fin:
                if not (h_ini <= t <= h_fin):
                    return False
            elif not (t >= h_ini or t <= h_fin):
                return False
        elif h_ini and t < h_ini:
            return False
        elif h_fin and t > h_fin:
            return False
    return True


def rendimiento_promociones_rango(db: Session, fecha_inicio: date, fecha_fin: date) -> dict:
    filas_q = (
        db.query(
            DetalleVentaModel.id_promocion,
            func.coalesce(DetalleVentaModel.nombre_promocion, PromocionModel.nombre).label("nombre"),
            func.coalesce(func.sum(DetalleVentaModel.cantidad), 0),
            func.count(distinct(DetalleVentaModel.id_venta)),
            func.coalesce(func.sum(DetalleVentaModel.subtotal), 0),
            func.coalesce(
                func.sum(DetalleVentaModel.descuento_unitario * DetalleVentaModel.cantidad), 0
            ),
        )
        .join(VentaModel, VentaModel.id_venta == DetalleVentaModel.id_venta)
        .outerjoin(PromocionModel, PromocionModel.id_promocion == DetalleVentaModel.id_promocion)
        .filter(
            DetalleVentaModel.id_promocion.isnot(None),
            *filtro_rango_mx(VentaModel.fecha_hora, fecha_inicio, fecha_fin),
        )
        .group_by(DetalleVentaModel.id_promocion, DetalleVentaModel.nombre_promocion, PromocionModel.nombre)
        .all()
    )

    promociones = []
    for r in filas_q:
        usos = int(float(r[2]))
        tickets = int(r[3] or 0)
        venta = _round2(float(r[4]))
        desc = _round2(float(r[5]))
        promociones.append(
            {
                "id_promocion": r[0],
                "nombre": r[1],
                "usos": usos,
                "tickets_con_promocion": tickets,
                "venta_generada": venta,
                "descuento_otorgado": desc,
                "ticket_promedio": _safe_div(venta, tickets),
                "unidades_asociadas": usos,
            }
        )

    return {
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "promociones": sorted(promociones, key=lambda x: -x["venta_generada"]),
    }


def detalle_promocion(
    db: Session, id_promocion: int, fecha_inicio: date, fecha_fin: date
) -> dict:
    promo = db.query(PromocionModel).filter(PromocionModel.id_promocion == id_promocion).first()
    if not promo:
        return {"error": "Promoción no encontrada"}

    detalles = (
        db.query(DetalleVentaModel, VentaModel)
        .join(VentaModel, VentaModel.id_venta == DetalleVentaModel.id_venta)
        .filter(
            DetalleVentaModel.id_promocion == id_promocion,
            *filtro_rango_mx(VentaModel.fecha_hora, fecha_inicio, fecha_fin),
        )
        .all()
    )

    usos = sum(float(d.cantidad) for d, _ in detalles)
    venta = sum(float(d.subtotal) for d, _ in detalles)
    desc = sum(float(d.descuento_unitario or 0) * float(d.cantidad) for d, _ in detalles)
    tickets = len({v.id_venta for d, v in detalles})

    por_dia: dict[str, dict] = defaultdict(lambda: {"usos": 0, "tickets": set(), "venta": 0.0, "descuento": 0.0})
    for d, v in detalles:
        dia = str(fecha_mx_desde_utc_naive(v.fecha_hora))
        por_dia[dia]["usos"] += float(d.cantidad)
        por_dia[dia]["tickets"].add(v.id_venta)
        por_dia[dia]["venta"] += float(d.subtotal)
        por_dia[dia]["descuento"] += float(d.descuento_unitario or 0) * float(d.cantidad)

    desglose = []
    for dia in sorted(por_dia.keys()):
        p = por_dia[dia]
        desglose.append(
            {
                "fecha": dia,
                "usos": int(p["usos"]),
                "tickets": len(p["tickets"]),
                "venta": _round2(p["venta"]),
                "descuento": _round2(p["descuento"]),
            }
        )

    return {
        "promocion": {
            "id_promocion": promo.id_promocion,
            "nombre": promo.nombre,
            "descripcion": promo.descripcion,
            "tipo": promo.tipo,
            "activa": promo.activa,
            "fecha_inicio": promo.fecha_inicio,
            "fecha_fin": promo.fecha_fin,
            "hora_inicio": promo.hora_inicio,
            "hora_fin": promo.hora_fin,
            "dias_semana": promo.dias_semana,
            "cantidad_requerida": promo.cantidad_requerida,
            "valor": float(promo.valor),
            "acumulable": bool(promo.acumulable),
        },
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "resultados": {
            "usos_totales": int(usos),
            "tickets_con_promocion": tickets,
            "venta_generada": _round2(venta),
            "descuento_otorgado": _round2(desc),
            "ticket_promedio": _safe_div(venta, tickets),
            "unidades_vendidas": int(usos),
        },
        "desglose_dias": desglose,
    }


def _metricas_ventana(
    db: Session,
    promo: PromocionModel,
    fecha_inicio: date,
    fecha_fin: date,
    solo_con_promo: bool = False,
) -> dict:
    ventas = (
        db.query(VentaModel)
        .filter(*filtro_rango_mx(VentaModel.fecha_hora, fecha_inicio, fecha_fin))
        .all()
    )
    ventas_filtradas = [v for v in ventas if _venta_en_ventana_promo(v, promo)]
    if not ventas_filtradas:
        return {
            "venta_promedio": 0.0,
            "tickets_promedio": 0.0,
            "ticket_promedio": 0.0,
            "unidades_promedio": 0.0,
            "dias_analizados": 0,
        }

    dias = len({fecha_mx_desde_utc_naive(v.fecha_hora) for v in ventas_filtradas})
    venta_ids = [v.id_venta for v in ventas_filtradas]

    if solo_con_promo:
        venta_ids_promo = {
            r[0]
            for r in db.query(DetalleVentaModel.id_venta)
            .filter(
                DetalleVentaModel.id_venta.in_(venta_ids),
                DetalleVentaModel.id_promocion == promo.id_promocion,
            )
            .distinct()
            .all()
        }
        ventas_filtradas = [v for v in ventas_filtradas if v.id_venta in venta_ids_promo]
        venta_ids = [v.id_venta for v in ventas_filtradas]

    venta_total = sum(float(v.total) for v in ventas_filtradas)
    tickets = len(ventas_filtradas)
    unidades = (
        db.query(func.coalesce(func.sum(DetalleVentaModel.cantidad), 0))
        .filter(DetalleVentaModel.id_venta.in_(venta_ids))
        .scalar()
        if venta_ids
        else 0
    )

    return {
        "venta_promedio": _safe_div(venta_total, dias),
        "tickets_promedio": _safe_div(tickets, dias),
        "ticket_promedio": _safe_div(venta_total, tickets),
        "unidades_promedio": _safe_div(float(unidades or 0), dias),
        "dias_analizados": dias,
        "venta_total": _round2(venta_total),
        "tickets": tickets,
    }


def comparar_promocion_periodos(
    db: Session,
    id_promocion: int,
    fecha_inicio_antes: date,
    fecha_fin_antes: date,
    fecha_inicio_durante: date,
    fecha_fin_durante: date,
) -> dict:
    promo = db.query(PromocionModel).filter(PromocionModel.id_promocion == id_promocion).first()
    if not promo:
        return {"error": "Promoción no encontrada"}

    antes = _metricas_ventana(db, promo, fecha_inicio_antes, fecha_fin_antes, solo_con_promo=False)
    durante = _metricas_ventana(db, promo, fecha_inicio_durante, fecha_fin_durante, solo_con_promo=False)

    def _var(a, b):
        if a == 0:
            return None if b == 0 else 100.0
        return _round2((b - a) / a * 100)

    return {
        "promocion": {"id_promocion": promo.id_promocion, "nombre": promo.nombre},
        "ventana": {
            "dias_semana": promo.dias_semana,
            "hora_inicio": promo.hora_inicio,
            "hora_fin": promo.hora_fin,
        },
        "periodo_antes": {
            "fecha_inicio": fecha_inicio_antes,
            "fecha_fin": fecha_fin_antes,
            **antes,
        },
        "periodo_durante": {
            "fecha_inicio": fecha_inicio_durante,
            "fecha_fin": fecha_fin_durante,
            **durante,
        },
        "variacion_pct": {
            "venta_promedio": _var(antes["venta_promedio"], durante["venta_promedio"]),
            "tickets_promedio": _var(antes["tickets_promedio"], durante["tickets_promedio"]),
            "ticket_promedio": _var(antes["ticket_promedio"], durante["ticket_promedio"]),
            "unidades_promedio": _var(antes["unidades_promedio"], durante["unidades_promedio"]),
        },
    }
