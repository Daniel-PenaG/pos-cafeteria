"""Métricas de ventas para reportes (tickets, unidades, promociones)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable, List, Optional, Tuple

from calendar import monthrange

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    VentaModel,
    DetalleVentaModel,
    ProductoModel,
    PromocionModel,
    RecetaModel,
)
from app.utils.timezone_mx import (
    filtro_dia_mx,
    filtro_rango_mx,
    filtro_mes_mx,
    filtro_anio_mx,
    fecha_mx_desde_utc_naive,
    datetime_mx_desde_utc_naive,
    contar_dias_semana_en_rango,
)

DIAS_SEMANA: List[Tuple[int, str]] = [
    (0, "Lunes"),
    (1, "Martes"),
    (2, "Miércoles"),
    (3, "Jueves"),
    (4, "Viernes"),
    (5, "Sábado"),
    (6, "Domingo"),
]


def _round2(n: float) -> float:
    return round(float(n), 2)


def _safe_div(num: float, den: float) -> float:
    return _round2(num / den) if den else 0.0


def _unidades_vendidas(db: Session, venta_ids: List[int]) -> float:
    if not venta_ids:
        return 0.0
    total = (
        db.query(func.coalesce(func.sum(DetalleVentaModel.cantidad), 0))
        .filter(DetalleVentaModel.id_venta.in_(venta_ids))
        .scalar()
    )
    return float(total or 0)


def _metricas_promociones(db: Session, venta_ids: List[int]) -> dict:
    if not venta_ids:
        return {
            "promociones_utilizadas": 0,
            "venta_por_promociones": 0.0,
            "promociones_detalle": [],
        }

    filas = (
        db.query(
            PromocionModel.id_promocion,
            PromocionModel.nombre,
            func.coalesce(func.sum(DetalleVentaModel.cantidad), 0),
            func.coalesce(func.sum(DetalleVentaModel.subtotal), 0),
            func.coalesce(
                func.sum(DetalleVentaModel.descuento_unitario * DetalleVentaModel.cantidad),
                0,
            ),
        )
        .join(PromocionModel, PromocionModel.id_promocion == DetalleVentaModel.id_promocion)
        .filter(
            DetalleVentaModel.id_venta.in_(venta_ids),
            DetalleVentaModel.id_promocion.isnot(None),
        )
        .group_by(PromocionModel.id_promocion, PromocionModel.nombre)
        .order_by(func.sum(DetalleVentaModel.subtotal).desc())
        .all()
    )

    promociones_utilizadas = int(sum(float(r[2]) for r in filas))
    venta_por_promociones = _round2(sum(float(r[3]) for r in filas))

    return {
        "promociones_utilizadas": promociones_utilizadas,
        "venta_por_promociones": venta_por_promociones,
        "promociones_detalle": [
            {
                "id_promocion": r[0],
                "nombre": r[1],
                "cantidad": int(float(r[2])),
                "importe": _round2(float(r[3])),
                "descuento_total": _round2(float(r[4])),
            }
            for r in filas
        ],
    }


def _productos_vendidos(db: Session, venta_ids: list[int]):
    if not venta_ids:
        return []

    detalles = (
        db.query(
            DetalleVentaModel.id_producto,
            func.sum(DetalleVentaModel.cantidad).label("cantidad"),
            func.sum(DetalleVentaModel.subtotal).label("subtotal"),
        )
        .filter(DetalleVentaModel.id_venta.in_(venta_ids))
        .group_by(DetalleVentaModel.id_producto)
        .all()
    )

    productos = []
    for d in detalles:
        producto = (
            db.query(ProductoModel).filter(ProductoModel.id_producto == d.id_producto).first()
        )
        if not producto:
            continue

        receta = (
            db.query(RecetaModel)
            .filter(RecetaModel.id_producto == producto.id_producto, RecetaModel.activo == True)
            .first()
        )

        costo_total = receta.costo_total if receta else 0
        precio_venta = float(producto.precio_venta)
        margen = precio_venta - float(costo_total)

        productos.append(
            {
                "id_producto": producto.id_producto,
                "nombre": producto.nombre,
                "cantidad": float(d.cantidad),
                "subtotal": float(d.subtotal),
                "precio_venta": precio_venta,
                "costo_receta": float(costo_total),
                "margen_unitario": margen,
                "margen_total": margen * float(d.cantidad),
            }
        )

    productos.sort(key=lambda p: (-p["cantidad"], -p["subtotal"]))
    return productos


def _metricas_desde_ventas(db: Session, ventas: Iterable[VentaModel]) -> dict:
    ventas_list = list(ventas)
    venta_ids = [v.id_venta for v in ventas_list]
    numero_tickets = len(ventas_list)
    venta_total = _round2(sum(float(v.total) for v in ventas_list))
    unidades = _unidades_vendidas(db, venta_ids)
    promo = _metricas_promociones(db, venta_ids)

    return {
        "numero_tickets": numero_tickets,
        "numero_ventas": numero_tickets,
        "venta_total": venta_total,
        "ticket_promedio": _safe_div(venta_total, numero_tickets),
        "unidades_vendidas": _round2(unidades),
        "productos_por_ticket": _safe_div(unidades, numero_tickets),
        **promo,
    }


def _resumen_vacio(**extra) -> dict:
    base = {
        "numero_tickets": 0,
        "numero_ventas": 0,
        "venta_total": 0.0,
        "ticket_promedio": 0.0,
        "unidades_vendidas": 0.0,
        "productos_por_ticket": 0.0,
        "promociones_utilizadas": 0,
        "venta_por_promociones": 0.0,
        "promociones_detalle": [],
        "productos": [],
    }
    base.update(extra)
    return base


def resumen_ventas_dia(db: Session, fecha: date) -> dict:
    ventas = (
        db.query(VentaModel).filter(*filtro_dia_mx(VentaModel.fecha_hora, fecha)).all()
    )
    if not ventas:
        return _resumen_vacio(fecha=fecha, total_dia=0.0)

    metricas = _metricas_desde_ventas(db, ventas)
    return {
        "fecha": fecha,
        "total_dia": metricas["venta_total"],
        **metricas,
        "productos": _productos_vendidos(db, [v.id_venta for v in ventas]),
    }


def _extremo_filas(filas: list, key: str, mejor: bool = True) -> Optional[dict]:
    candidatos = [f for f in filas if f.get("dias_analizados", 1) > 0]
    if not candidatos:
        return None
    return max(candidatos, key=lambda f: f[key]) if mejor else min(candidatos, key=lambda f: f[key])


def rendimiento_dia_semana(
    db: Session,
    ventas: List[VentaModel],
    fecha_inicio: date,
    fecha_fin: date,
) -> dict:
    """Agrega ventas por día de la semana (MX) con promedios normalizados por ocurrencias en el rango."""
    dias_en_rango = contar_dias_semana_en_rango(fecha_inicio, fecha_fin)
    por_dow: dict[int, list] = defaultdict(list)

    for v in ventas:
        dow = fecha_mx_desde_utc_naive(v.fecha_hora).weekday()
        por_dow[dow].append(v)

    unidades_por_dow: dict[int, float] = {}
    for dow, grupo in por_dow.items():
        unidades_por_dow[dow] = _unidades_vendidas(db, [v.id_venta for v in grupo])

    filas = []
    for dow, nombre in DIAS_SEMANA:
        grupo = por_dow.get(dow, [])
        dias_analizados = dias_en_rango[dow]
        venta_total = sum(float(v.total) for v in grupo)
        tickets_totales = len(grupo)
        unidades_totales = unidades_por_dow.get(dow, 0.0)

        filas.append(
            {
                "dia_semana": dow,
                "dia": nombre,
                "dias_analizados": dias_analizados,
                "venta_total": _round2(venta_total),
                "venta_promedio_dia": _safe_div(venta_total, dias_analizados),
                "tickets_totales": tickets_totales,
                "tickets_promedio_dia": _safe_div(tickets_totales, dias_analizados),
                "ticket_promedio": _safe_div(venta_total, tickets_totales),
                "unidades_promedio_dia": _safe_div(unidades_totales, dias_analizados),
            }
        )

    return {
        "filas": filas,
        "destacados": {
            "mayor_venta_promedio": _extremo_filas(filas, "venta_promedio_dia", True),
            "menor_venta_promedio": _extremo_filas(filas, "venta_promedio_dia", False),
            "mayor_tickets_promedio": _extremo_filas(filas, "tickets_promedio_dia", True),
            "menor_tickets_promedio": _extremo_filas(filas, "tickets_promedio_dia", False),
        },
    }


def ventas_por_hora(db: Session, ventas: List[VentaModel]) -> dict:
    """Agrupa tickets por hora de cierre (zona México)."""
    por_hora: dict[int, list] = defaultdict(list)
    for v in ventas:
        hora = datetime_mx_desde_utc_naive(v.fecha_hora).hour
        por_hora[hora].append(v)

    filas = []
    for h in range(24):
        grupo = por_hora.get(h, [])
        venta_total = sum(float(v.total) for v in grupo)
        tickets = len(grupo)
        filas.append(
            {
                "hora": h,
                "hora_label": f"{h:02d}:00",
                "venta_total": _round2(venta_total),
                "tickets": tickets,
                "ticket_promedio": _safe_div(venta_total, tickets),
            }
        )

    con_actividad = [f for f in filas if f["tickets"] > 0]
    sin_actividad = [f["hora_label"] for f in filas if f["tickets"] == 0]

    poca_actividad: list[str] = []
    if len(con_actividad) >= 2:
        tickets_vals = sorted(f["tickets"] for f in con_actividad)
        idx = max(0, len(tickets_vals) // 4 - 1)
        umbral = tickets_vals[idx]
        poca_actividad = [
            f["hora_label"]
            for f in con_actividad
            if f["tickets"] <= umbral and f["tickets"] < max(tickets_vals)
        ]

    mayor_venta = max(con_actividad, key=lambda f: f["venta_total"]) if con_actividad else None
    mayor_tickets = max(con_actividad, key=lambda f: f["tickets"]) if con_actividad else None

    return {
        "filas": filas,
        "destacados": {
            "hora_mayor_venta": mayor_venta,
            "hora_mayor_tickets": mayor_tickets,
            "horas_sin_actividad": sin_actividad,
            "horas_poca_actividad": poca_actividad,
        },
    }


def analisis_temporal_periodo(
    db: Session,
    ventas: List[VentaModel],
    fecha_inicio: date,
    fecha_fin: date,
) -> dict:
    return {
        "rendimiento_dia_semana": rendimiento_dia_semana(db, ventas, fecha_inicio, fecha_fin),
        "ventas_por_hora": ventas_por_hora(db, ventas),
    }


def _analisis_temporal_vacio(fecha_inicio: date | None = None, fecha_fin: date | None = None) -> dict:
    dias_en_rango = (
        contar_dias_semana_en_rango(fecha_inicio, fecha_fin)
        if fecha_inicio and fecha_fin
        else {i: 0 for i in range(7)}
    )
    filas_semana = []
    for dow, nombre in DIAS_SEMANA:
        filas_semana.append(
            {
                "dia_semana": dow,
                "dia": nombre,
                "dias_analizados": dias_en_rango[dow],
                "venta_total": 0.0,
                "venta_promedio_dia": 0.0,
                "tickets_totales": 0,
                "tickets_promedio_dia": 0.0,
                "ticket_promedio": 0.0,
                "unidades_promedio_dia": 0.0,
            }
        )
    filas_hora = [
        {
            "hora": h,
            "hora_label": f"{h:02d}:00",
            "venta_total": 0.0,
            "tickets": 0,
            "ticket_promedio": 0.0,
        }
        for h in range(24)
    ]
    return {
        "rendimiento_dia_semana": {
            "filas": filas_semana,
            "destacados": {
                "mayor_venta_promedio": None,
                "menor_venta_promedio": None,
                "mayor_tickets_promedio": None,
                "menor_tickets_promedio": None,
            },
        },
        "ventas_por_hora": {
            "filas": filas_hora,
            "destacados": {
                "hora_mayor_venta": None,
                "hora_mayor_tickets": None,
                "horas_sin_actividad": [f"{h:02d}:00" for h in range(24)],
                "horas_poca_actividad": [],
            },
        },
    }


def rango_fechas_mes(anio: int, mes: int) -> tuple[date, date]:
    ultimo = monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo)


def _desglose_diario(db: Session, ventas: List[VentaModel]) -> list:
    por_dia: dict[date, list] = defaultdict(list)
    for v in ventas:
        por_dia[fecha_mx_desde_utc_naive(v.fecha_hora)].append(v)

    filas = []
    for dia in sorted(por_dia.keys()):
        grupo = por_dia[dia]
        m = _metricas_desde_ventas(db, grupo)
        filas.append(
            {
                "fecha": str(dia),
                "venta_total": m["venta_total"],
                "total": m["venta_total"],
                "numero_tickets": m["numero_tickets"],
                "numero_ventas": m["numero_tickets"],
                "ticket_promedio": m["ticket_promedio"],
                "unidades_vendidas": m["unidades_vendidas"],
                "productos_por_ticket": m["productos_por_ticket"],
                "promociones_utilizadas": m["promociones_utilizadas"],
                "venta_por_promociones": m["venta_por_promociones"],
            }
        )
    return filas


def resumen_ventas_rango(db: Session, fecha_inicio: date, fecha_fin: date) -> dict:
    ventas = (
        db.query(VentaModel)
        .filter(*filtro_rango_mx(VentaModel.fecha_hora, fecha_inicio, fecha_fin))
        .all()
    )

    analisis = _analisis_temporal_vacio(fecha_inicio, fecha_fin)
    if not ventas:
        return _resumen_vacio(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            dias_con_ventas=0,
            promedio_venta_diaria=0.0,
            promedio_tickets_diarios=0.0,
            desglose_dias=[],
            **analisis,
        )

    metricas = _metricas_desde_ventas(db, ventas)
    desglose = _desglose_diario(db, ventas)
    dias_con_ventas = len(desglose)
    analisis = analisis_temporal_periodo(db, ventas, fecha_inicio, fecha_fin)

    return {
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "dias_con_ventas": dias_con_ventas,
        "promedio_venta_diaria": _safe_div(metricas["venta_total"], dias_con_ventas),
        "promedio_tickets_diarios": _safe_div(metricas["numero_tickets"], dias_con_ventas),
        **metricas,
        "productos": _productos_vendidos(db, [v.id_venta for v in ventas]),
        "desglose_dias": desglose,
        **analisis,
    }


def _variacion_pct(valor_a: float, valor_b: float) -> Optional[float]:
    if valor_a == 0:
        return None if valor_b == 0 else 100.0
    return _round2((valor_b - valor_a) / valor_a * 100)


def comparar_periodos_ventas(
    db: Session,
    fecha_inicio_a: date,
    fecha_fin_a: date,
    fecha_inicio_b: date,
    fecha_fin_b: date,
) -> dict:
    resumen_a = resumen_ventas_rango(db, fecha_inicio_a, fecha_fin_a)
    resumen_b = resumen_ventas_rango(db, fecha_inicio_b, fecha_fin_b)

    campos = ("venta_total", "numero_tickets", "ticket_promedio", "unidades_vendidas")
    variacion = {
        f"{campo}_pct": _variacion_pct(resumen_a[campo], resumen_b[campo])
        for campo in campos
    }
    variacion["productos_por_ticket_pct"] = _variacion_pct(
        resumen_a["productos_por_ticket"], resumen_b["productos_por_ticket"]
    )

    return {
        "periodo_a": {
            "fecha_inicio": fecha_inicio_a,
            "fecha_fin": fecha_fin_a,
            **{k: resumen_a[k] for k in campos},
            "productos_por_ticket": resumen_a["productos_por_ticket"],
            "promociones_utilizadas": resumen_a["promociones_utilizadas"],
            "venta_por_promociones": resumen_a["venta_por_promociones"],
        },
        "periodo_b": {
            "fecha_inicio": fecha_inicio_b,
            "fecha_fin": fecha_fin_b,
            **{k: resumen_b[k] for k in campos},
            "productos_por_ticket": resumen_b["productos_por_ticket"],
            "promociones_utilizadas": resumen_b["promociones_utilizadas"],
            "venta_por_promociones": resumen_b["venta_por_promociones"],
        },
        "variacion": variacion,
    }


def enriquecer_resumen_mes_anio(db: Session, ventas: List[VentaModel], venta_ids: List[int]) -> dict:
    """Métricas agregadas para reportes mes/año (compatibilidad con endpoints existentes)."""
    if not ventas:
        return _metricas_desde_ventas(db, [])
    return _metricas_desde_ventas(db, ventas)
