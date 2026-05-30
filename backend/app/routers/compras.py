from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.models import (
    CompraModel,
    DetalleCompraModel,
    InsumoModel,
    MovimientoInventarioModel
)
from app.schemas.compra import CompraCreate, CompraResponse

router = APIRouter(prefix="/compras", tags=["Compras"])


@router.post("/", response_model=CompraResponse)
def registrar_compra(data: CompraCreate, db: Session = Depends(get_db)):

    if not data.detalles or len(data.detalles) == 0:
        raise HTTPException(status_code=400, detail="La compra debe tener insumos")

    total = 0

    # Calcular total
    for item in data.detalles:
        subtotal = float(item.cantidad) * float(item.costo_unitario)
        total += subtotal

    compra = CompraModel(
        fecha_hora=datetime.now(),
        proveedor=data.proveedor,
        total=total
    )

    db.add(compra)
    db.commit()
    db.refresh(compra)

    # Guardar detalles y aumentar inventario
    for item in data.detalles:
        insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == item.id_insumo).first()
        if not insumo:
            raise HTTPException(status_code=404, detail=f"Insumo {item.id_insumo} no existe")

        subtotal = float(item.cantidad) * float(item.costo_unitario)

        detalle = DetalleCompraModel(
            id_compra=compra.id_compra,
            id_insumo=item.id_insumo,
            cantidad=item.cantidad,
            costo_unitario=item.costo_unitario,
            subtotal=subtotal
        )
        db.add(detalle)

        # Aumentar stock
        insumo.stock_actual = float(insumo.stock_actual) + float(item.cantidad)

        # Registrar movimiento
        mov = MovimientoInventarioModel(
            id_insumo=item.id_insumo,
            tipo="ENTRADA",
            cantidad=item.cantidad,
            motivo="COMPRA",
            referencia=f"COMPRA {compra.id_compra}",
            fecha_hora=datetime.now()
        )
        db.add(mov)

    db.commit()
    db.refresh(compra)

    return compra
