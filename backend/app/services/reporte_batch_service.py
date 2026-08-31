"""Consultas agrupadas para reportes (evita N+1)."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import (
    DetalleVentaModel,
    ProductoModel,
    PromocionModel,
    RecetaModel,
)


def unidades_por_venta_map(db: Session, venta_ids: Iterable[int]) -> Dict[int, float]:
    ids = list(venta_ids)
    if not ids:
        return {}
    filas = (
        db.query(
            DetalleVentaModel.id_venta,
            func.coalesce(func.sum(DetalleVentaModel.cantidad), 0),
        )
        .filter(DetalleVentaModel.id_venta.in_(ids))
        .group_by(DetalleVentaModel.id_venta)
        .all()
    )
    return {int(r[0]): float(r[1]) for r in filas}


def sum_unidades(unidades_map: Dict[int, float], venta_ids: Iterable[int]) -> float:
    return float(sum(unidades_map.get(int(vid), 0.0) for vid in venta_ids))


def metricas_promociones_batch(db: Session, venta_ids: List[int]) -> dict:
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
    venta_por_promociones = round(sum(float(r[3]) for r in filas), 2)

    return {
        "promociones_utilizadas": promociones_utilizadas,
        "venta_por_promociones": venta_por_promociones,
        "promociones_detalle": [
            {
                "id_promocion": r[0],
                "nombre": r[1],
                "cantidad": int(float(r[2])),
                "importe": round(float(r[3]), 2),
                "descuento_total": round(float(r[4]), 2),
            }
            for r in filas
        ],
    }


def productos_vendidos_batch(db: Session, venta_ids: List[int]) -> list:
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
    if not detalles:
        return []

    ids_producto = [d.id_producto for d in detalles]
    productos_map = {
        p.id_producto: p
        for p in db.query(ProductoModel).filter(ProductoModel.id_producto.in_(ids_producto)).all()
    }
    recetas_map = {
        r.id_producto: r
        for r in db.query(RecetaModel)
        .filter(RecetaModel.id_producto.in_(ids_producto), RecetaModel.activo == True)
        .all()
    }

    productos = []
    for d in detalles:
        producto = productos_map.get(d.id_producto)
        if not producto:
            continue
        receta = recetas_map.get(producto.id_producto)
        costo_total = float(receta.costo_total) if receta and receta.costo_total else 0.0
        precio_venta = float(producto.precio_venta)
        margen = precio_venta - costo_total
        cantidad = float(d.cantidad)
        productos.append(
            {
                "id_producto": producto.id_producto,
                "nombre": producto.nombre,
                "cantidad": cantidad,
                "subtotal": float(d.subtotal),
                "precio_venta": precio_venta,
                "costo_receta": costo_total,
                "margen_unitario": margen,
                "margen_total": margen * cantidad,
            }
        )

    productos.sort(key=lambda p: (-p["cantidad"], -p["subtotal"]))
    return productos


def desglose_diario_batch(db: Session, ventas_por_dia: dict) -> list:
    """ventas_por_dia: date -> list[VentaModel]"""
    if not ventas_por_dia:
        return []

    all_ids = [v.id_venta for grupo in ventas_por_dia.values() for v in grupo]
    unidades_map = unidades_por_venta_map(db, all_ids)

    promo_por_venta: dict[int, dict] = defaultdict(
        lambda: {"usos": 0.0, "venta": 0.0}
    )
    if all_ids:
        filas_promo = (
            db.query(
                DetalleVentaModel.id_venta,
                func.coalesce(func.sum(DetalleVentaModel.cantidad), 0),
                func.coalesce(func.sum(DetalleVentaModel.subtotal), 0),
            )
            .filter(
                DetalleVentaModel.id_venta.in_(all_ids),
                DetalleVentaModel.id_promocion.isnot(None),
            )
            .group_by(DetalleVentaModel.id_venta)
            .all()
        )
        for vid, usos, venta in filas_promo:
            promo_por_venta[int(vid)] = {"usos": float(usos), "venta": float(venta)}

    filas = []
    for dia in sorted(ventas_por_dia.keys()):
        grupo = ventas_por_dia[dia]
        venta_ids = [v.id_venta for v in grupo]
        numero_tickets = len(grupo)
        venta_total = round(sum(float(v.total) for v in grupo), 2)
        unidades = round(sum_unidades(unidades_map, venta_ids), 2)
        prom_usos = int(sum(promo_por_venta[vid]["usos"] for vid in venta_ids))
        prom_venta = round(sum(promo_por_venta[vid]["venta"] for vid in venta_ids), 2)
        filas.append(
            {
                "fecha": str(dia),
                "venta_total": venta_total,
                "total": venta_total,
                "numero_tickets": numero_tickets,
                "numero_ventas": numero_tickets,
                "ticket_promedio": round(venta_total / numero_tickets, 2) if numero_tickets else 0.0,
                "unidades_vendidas": unidades,
                "productos_por_ticket": round(unidades / numero_tickets, 2) if numero_tickets else 0.0,
                "promociones_utilizadas": prom_usos,
                "venta_por_promociones": prom_venta,
            }
        )
    return filas
