from typing import Any, Optional

from app.models import ExtraVentaModel


def precio_efectivo(
    *,
    costo_unitario: float,
    cantidad: float,
    usar_precio_manual: bool,
    precio_personalizado: Optional[float],
) -> float:
    if usar_precio_manual and precio_personalizado is not None:
        return float(precio_personalizado)
    return float(costo_unitario or 0) * float(cantidad or 1)


def precio_desde_modelo(extra: ExtraVentaModel) -> float:
    return precio_efectivo(
        costo_unitario=float(extra.costo_unitario or 0),
        cantidad=float(extra.cantidad or 1),
        usar_precio_manual=bool(extra.usar_precio_manual),
        precio_personalizado=(
            float(extra.precio_personalizado)
            if extra.precio_personalizado is not None
            else None
        ),
    )


def sincronizar_precio_guardado(extra: ExtraVentaModel) -> None:
    """Mantiene la columna precio alineada con el precio efectivo (ventas/POS)."""
    extra.precio = precio_desde_modelo(extra)


def extra_a_catalogo(extra: ExtraVentaModel) -> dict[str, Any]:
    return {
        "id_extra": extra.id_extra,
        "nombre": extra.nombre,
        "unidad": extra.unidad,
        "cantidad": float(extra.cantidad or 1),
        "costo_unitario": float(extra.costo_unitario or 0),
        "usar_precio_manual": bool(extra.usar_precio_manual),
        "precio_personalizado": (
            float(extra.precio_personalizado)
            if extra.precio_personalizado is not None
            else None
        ),
        "precio": precio_desde_modelo(extra),
        "tipo": extra.tipo,
        "activo": extra.activo,
        "id_insumo_origen": extra.id_insumo_origen,
    }
