from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.models import (
    VentaModel, DetalleVentaModel,
    ProductoModel, RecetaModel, InsumoModel,
    MovimientoInventarioModel
)
from app.schemas.ventas import VentaCreate, VentaResponse

router = APIRouter(prefix="/ventas", tags=["Ventas"])

# ============================
# REGISTRAR VENTA
# ============================
@router.post("/", response_model=VentaResponse)
def registrar_venta(data: VentaCreate, db: Session = Depends(get_db)):

    total_venta = 0

    # 1. Validar stock antes de vender
    for item in data.detalles:
        producto = db.query(ProductoModel).filter(ProductoModel.id_producto == item.id_producto).first()
        if not producto:
            raise HTTPException(status_code=404, detail=f"Producto {item.id_producto} no existe")

        recetas = db.query(RecetaModel).filter(RecetaModel.id_producto == item.id_producto).all()

        for receta in recetas:
            insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == receta.id_insumo).first()
            cantidad_necesaria = float(receta.cantidad_por_producto) * float(item.cantidad)

            if insumo.stock_actual < cantidad_necesaria:
                raise HTTPException(
                    status_code=400,
                    detail=f"No hay suficiente {insumo.nombre}. Necesario: {cantidad_necesaria}, Disponible: {insumo.stock_actual}"
                )

        total_venta += float(producto.precio_venta) * item.cantidad

    # 2. Crear venta
    venta = VentaModel(
        fecha_hora=datetime.now(),
        id_usuario=data.id_usuario,
        total=total_venta,
        forma_pago=data.forma_pago
    )
    db.add(venta)
    db.commit()
    db.refresh(venta)

    # 3. Registrar detalle y descontar inventario
    for item in data.detalles:
        producto = db.query(ProductoModel).filter(ProductoModel.id_producto == item.id_producto).first()

        detalle = DetalleVentaModel(
            id_venta=venta.id_venta,
            id_producto=item.id_producto,
            cantidad=item.cantidad,
            precio_unitario=producto.precio_venta,
            subtotal=float(producto.precio_venta) * item.cantidad
        )
        db.add(detalle)

        # Descontar inventario según receta
        recetas = db.query(RecetaModel).filter(RecetaModel.id_producto == item.id_producto).all()

        for receta in recetas:
            insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == receta.id_insumo).first()
            cantidad_necesaria = float(receta.cantidad_por_producto) * float(item.cantidad)


            insumo.stock_actual = float(insumo.stock_actual) - float(cantidad_necesaria)


            movimiento = MovimientoInventarioModel(
                id_insumo=insumo.id_insumo,
                tipo="SALIDA",
                cantidad=cantidad_necesaria,
                motivo="VENTA",
                referencia=f"Venta {venta.id_venta}",
                fecha_hora=datetime.now()
            )
            db.add(movimiento)

    db.commit()

    return VentaResponse(id_venta=venta.id_venta, total=total_venta)
