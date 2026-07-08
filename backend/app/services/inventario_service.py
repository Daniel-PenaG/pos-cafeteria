"""Utilidades de inventario por ubicación (bodega / cafetería)."""

from app.models.models import InsumoModel, MovimientoInventarioModel
from datetime import datetime
from sqlalchemy.orm import Session

from app.exceptions import DatosInvalidosException, StockInsuficienteException


def sync_stock_total(insumo: InsumoModel) -> None:
    """Mantiene stock_actual = bodega + cafetería (compatibilidad)."""
    insumo.stock_actual = float(insumo.stock_bodega or 0) + float(insumo.stock_cafeteria or 0)


def traspaso_bodega_a_cafeteria(
    db: Session,
    insumo: InsumoModel,
    cantidad: float,
) -> InsumoModel:
    if cantidad <= 0:
        raise DatosInvalidosException("La cantidad debe ser mayor a 0")

    disponible = float(insumo.stock_bodega or 0)
    if disponible < cantidad:
        raise StockInsuficienteException(
            f"Stock insuficiente en bodega de '{insumo.nombre}'. "
            f"Disponible: {disponible}, solicitado: {cantidad}"
        )

    insumo.stock_bodega = disponible - cantidad
    insumo.stock_cafeteria = float(insumo.stock_cafeteria or 0) + cantidad
    sync_stock_total(insumo)

    mov = MovimientoInventarioModel(
        id_insumo=insumo.id_insumo,
        tipo="TRASPASO",
        cantidad=cantidad,
        motivo="BODEGA_A_CAFETERIA",
        referencia=f"TRASPASO {cantidad} {insumo.unidad}",
        fecha_hora=datetime.now(),
    )
    db.add(mov)
    return insumo
