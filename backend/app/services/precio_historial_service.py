"""Sugiere y restaura precio_venta desde el historial de ventas/pedidos."""
from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import DetallePedidoModel, DetalleVentaModel, ProductoModel


def _dinero(value) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        d = Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return None
    if d <= 0:
        return None
    return d


def _precio_base_linea(precio_original, precio_unitario) -> Optional[Decimal]:
    """Precio de catálogo de la línea (antes de promo si existe original)."""
    original = _dinero(precio_original)
    if original is not None:
        return original
    return _dinero(precio_unitario)


def _score_menu(precio: Decimal) -> tuple:
    """Prioriza precios de menú típicos (enteros o .50) frente a recálculos raros."""
    cents = int(precio * 100) % 100
    redondo = 0 if cents in (0, 50) else 1
    return (redondo, -float(precio))


def sugerir_precio_desde_historial(
    db: Session,
    producto: ProductoModel,
    *,
    min_apariciones: int = 2,
) -> Optional[dict]:
    """
    Elige el precio histórico más plausible distinto del actual.

    Si el recálculo por receta contaminó ventas recientes, el precio actual suele
    ser el más frecuente; en ese caso se toma el segundo más común (o el más
    'de menú' entre los no actuales).
    """
    actual = _dinero(producto.precio_venta)
    contador: Counter = Counter()

    for row in (
        db.query(DetalleVentaModel.precio_original, DetalleVentaModel.precio_unitario)
        .filter(DetalleVentaModel.id_producto == producto.id_producto)
        .all()
    ):
        p = _precio_base_linea(row.precio_original, row.precio_unitario)
        if p is not None:
            contador[p] += 1

    for row in (
        db.query(
            DetallePedidoModel.precio_original,
            DetallePedidoModel.precio_unitario,
        )
        .filter(
            DetallePedidoModel.id_producto == producto.id_producto,
            DetallePedidoModel.estado_linea != "CANCELADA",
        )
        .all()
    ):
        p = _precio_base_linea(row.precio_original, row.precio_unitario)
        if p is not None:
            contador[p] += 1

    if not contador:
        return None

    candidatos = [
        (precio, n)
        for precio, n in contador.items()
        if n >= min_apariciones and (actual is None or precio != actual)
    ]
    if not candidatos:
        # Sin umbral: cualquier precio distinto al actual
        candidatos = [
            (precio, n)
            for precio, n in contador.items()
            if actual is None or precio != actual
        ]
    if not candidatos:
        return None

    candidatos.sort(key=lambda item: (-item[1], _score_menu(item[0])))
    sugerido, apariciones = candidatos[0]
    if actual is not None and sugerido == actual:
        return None

    return {
        "id_producto": producto.id_producto,
        "nombre": producto.nombre,
        "precio_actual": float(actual) if actual is not None else None,
        "precio_sugerido": float(sugerido),
        "apariciones": int(apariciones),
        "muestras": int(sum(contador.values())),
    }


def previsualizar_restauracion_precios(db: Session) -> list[dict]:
    productos = (
        db.query(ProductoModel)
        .filter(ProductoModel.activo == True)  # noqa: E712
        .order_by(ProductoModel.nombre)
        .all()
    )
    out = []
    for producto in productos:
        sug = sugerir_precio_desde_historial(db, producto)
        if sug:
            out.append(sug)
    return out


def restaurar_precios_desde_historial(db: Session) -> dict:
    cambios = []
    for sug in previsualizar_restauracion_precios(db):
        producto = (
            db.query(ProductoModel)
            .filter(ProductoModel.id_producto == sug["id_producto"])
            .first()
        )
        if not producto:
            continue
        producto.precio_venta = Decimal(str(sug["precio_sugerido"]))
        cambios.append(sug)
    if cambios:
        db.commit()
    return {
        "actualizados": len(cambios),
        "cambios": cambios,
    }
