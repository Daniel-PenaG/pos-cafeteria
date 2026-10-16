"""Inventario por lotes en cobro/venta. Evita N+1 por línea e insumo."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import (
    ExtraVentaModel,
    InsumoModel,
    MovimientoInventarioModel,
    RecetaInsumoModel,
    RecetaModel,
)
from app.schemas.ventas import ExtraVentaLinea
from app.utils.timezone_mx import now_utc_naive


def _resolver_extra_insumo(
    db: Session, extra: ExtraVentaLinea, extras_cache: dict[int, ExtraVentaModel | None]
) -> tuple[int | None, float]:
    if extra.id_insumo:
        return int(extra.id_insumo), float(extra.cantidad_insumo or 1)
    if extra.id_extra:
        model = extras_cache.get(int(extra.id_extra))
        if model is None and extra.id_extra not in extras_cache:
            model = (
                db.query(ExtraVentaModel)
                .filter(ExtraVentaModel.id_extra == extra.id_extra)
                .first()
            )
            extras_cache[int(extra.id_extra)] = model
        if model and model.id_insumo_origen:
            return int(model.id_insumo_origen), float(model.cantidad or 1)
    return None, 0.0


def _consumo_por_insumo(db: Session, detalles) -> dict[int, float]:
    producto_ids = {int(item.id_producto) for item in detalles}
    recetas = (
        db.query(RecetaModel)
        .filter(RecetaModel.id_producto.in_(producto_ids), RecetaModel.activo == True)
        .all()
    )
    receta_por_producto = {r.id_producto: r for r in recetas}
    receta_ids = [r.id_receta for r in recetas]
    ri_por_receta: dict[int, list] = defaultdict(list)
    if receta_ids:
        for ri in (
            db.query(RecetaInsumoModel)
            .filter(RecetaInsumoModel.id_receta.in_(receta_ids))
            .all()
        ):
            ri_por_receta[int(ri.id_receta)].append(ri)

    extra_ids = set()
    for item in detalles:
        for extra in item.extras:
            if extra.id_extra:
                extra_ids.add(int(extra.id_extra))
    extras_cache: dict[int, ExtraVentaModel | None] = {}
    if extra_ids:
        for row in db.query(ExtraVentaModel).filter(ExtraVentaModel.id_extra.in_(extra_ids)).all():
            extras_cache[int(row.id_extra)] = row

    consumo: dict[int, float] = defaultdict(float)
    for item in detalles:
        qty = float(item.cantidad)
        receta = receta_por_producto.get(int(item.id_producto))
        if receta:
            for ri in ri_por_receta.get(int(receta.id_receta), []):
                consumo[int(ri.id_insumo)] += float(ri.cantidad) * qty
        for extra in item.extras:
            id_insumo, por_unidad = _resolver_extra_insumo(db, extra, extras_cache)
            if id_insumo:
                consumo[id_insumo] += por_unidad * qty
    return dict(consumo)


def revisar_stock_venta(db: Session, detalles) -> tuple[list[str], list[dict]]:
    consumo = _consumo_por_insumo(db, detalles)
    if not consumo:
        return [], []
    insumos = {
        int(i.id_insumo): i
        for i in db.query(InsumoModel).filter(InsumoModel.id_insumo.in_(consumo.keys())).all()
    }
    advertencias: list[str] = []
    detalle: list[dict] = []
    for id_insumo, requerido in sorted(consumo.items()):
        insumo = insumos.get(id_insumo)
        if not insumo:
            continue
        disponible = float(insumo.stock_actual)
        if disponible < requerido:
            fila = {
                "id_insumo": id_insumo,
                "nombre": insumo.nombre,
                "disponible": disponible,
                "requerido": requerido,
            }
            detalle.append(fila)
            advertencias.append(
                f"Stock insuficiente de '{insumo.nombre}'. "
                f"Disponible: {disponible}, Requerido: {requerido}"
            )
    return advertencias, detalle


def descontar_stock_venta(db: Session, venta_id: int, detalles) -> None:
    consumo = _consumo_por_insumo(db, detalles)
    if not consumo:
        return
    ids = sorted(consumo.keys())
    q = db.query(InsumoModel).filter(InsumoModel.id_insumo.in_(ids))
    if db.bind is not None and db.bind.dialect.name != "sqlite":
        q = q.with_for_update()
    insumos = {int(i.id_insumo): i for i in q.order_by(InsumoModel.id_insumo.asc()).all()}
    ahora = now_utc_naive()
    ref = f"VENTA {venta_id}"
    for id_insumo in ids:
        insumo = insumos.get(id_insumo)
        if not insumo:
            continue
        cantidad_total = consumo[id_insumo]
        insumo.stock_actual = float(insumo.stock_actual) - cantidad_total
        db.add(
            MovimientoInventarioModel(
                id_insumo=id_insumo,
                tipo="SALIDA",
                cantidad=cantidad_total,
                motivo="VENTA",
                referencia=ref,
                fecha_hora=ahora,
            )
        )
