from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from app.database import get_db
from app.models.models import (
    VentaModel,
    DetalleVentaModel,
    ProductoModel,
    RecetaModel,
    RecetaInsumoModel,
    InsumoModel
)

router = APIRouter(prefix="/reportes", tags=["Reportes"])


# ============================
# REPORTE DE VENTAS POR DÍA
# ============================
@router.get("/ventas-dia")
def ventas_por_dia(fecha: date, db: Session = Depends(get_db)):

    ventas = (
        db.query(VentaModel)
        .filter(func.date(VentaModel.fecha_hora) == fecha)
        .all()
    )

    if not ventas:
        return {
            "fecha": fecha,
            "total_dia": 0,
            "numero_ventas": 0,
            "productos": []
        }

    total_dia = sum(float(v.total) for v in ventas)

    # Productos vendidos
    detalles = (
        db.query(
            DetalleVentaModel.id_producto,
            func.sum(DetalleVentaModel.cantidad).label("cantidad"),
            func.sum(DetalleVentaModel.subtotal).label("subtotal")
        )
        .join(VentaModel, VentaModel.id_venta == DetalleVentaModel.id_venta)
        .filter(func.date(VentaModel.fecha_hora) == fecha)
        .group_by(DetalleVentaModel.id_producto)
        .all()
    )

    productos = []
    for d in detalles:
        producto = db.query(ProductoModel).filter(ProductoModel.id_producto == d.id_producto).first()

        # Buscar receta para calcular costo
        receta = db.query(RecetaModel).filter(
            RecetaModel.id_producto == producto.id_producto,
            RecetaModel.activo == True
        ).first()

        costo_total = receta.costo_total if receta else 0
        precio_venta = float(producto.precio_venta)
        margen = precio_venta - float(costo_total)

        productos.append({
            "id_producto": producto.id_producto,
            "nombre": producto.nombre,
            "cantidad": float(d.cantidad),
            "subtotal": float(d.subtotal),
            "precio_venta": precio_venta,
            "costo_receta": float(costo_total),
            "margen_unitario": margen,
            "margen_total": margen * float(d.cantidad)
        })

    return {
        "fecha": fecha,
        "total_dia": total_dia,
        "numero_ventas": len(ventas),
        "productos": productos
    }


# ============================
# REPORTE DE CONSUMO DE INSUMOS
# ============================
@router.get("/consumo-insumos")
def consumo_insumos(fecha: date, db: Session = Depends(get_db)):

    detalles = (
        db.query(
            DetalleVentaModel.id_producto,
            func.sum(DetalleVentaModel.cantidad).label("cantidad")
        )
        .join(VentaModel, VentaModel.id_venta == DetalleVentaModel.id_venta)
        .filter(func.date(VentaModel.fecha_hora) == fecha)
        .group_by(DetalleVentaModel.id_producto)
        .all()
    )

    consumo = []

    for d in detalles:
        receta = db.query(RecetaModel).filter(
            RecetaModel.id_producto == d.id_producto,
            RecetaModel.activo == True
        ).first()

        if not receta:
            continue

        receta_insumos = db.query(RecetaInsumoModel).filter(
            RecetaInsumoModel.id_receta == receta.id_receta
        ).all()

        for ri in receta_insumos:
            insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == ri.id_insumo).first()

            cantidad_total = float(ri.cantidad) * float(d.cantidad)

            consumo.append({
                "id_insumo": insumo.id_insumo,
                "nombre": insumo.nombre,
                "unidad": insumo.unidad,
                "cantidad_consumida": cantidad_total,
                "stock_actual": float(insumo.stock_actual),
                "stock_minimo": float(insumo.stock_minimo),
                "alerta": cantidad_total >= float(insumo.stock_actual)
            })

    return {
        "fecha": fecha,
        "consumo": consumo
    }

@router.get("/resumen-dashboard")
def resumen_dashboard(db: Session = Depends(get_db)):
    hoy = date.today()

    total_hoy = (
        db.query(func.coalesce(func.sum(VentaModel.total), 0))
        .filter(func.date(VentaModel.fecha_hora) == hoy)
        .scalar()
    )

    num_ventas_hoy = (
        db.query(func.count(VentaModel.id_venta))
        .filter(func.date(VentaModel.fecha_hora) == hoy)
        .scalar()
    )

    total_general = (
        db.query(func.coalesce(func.sum(VentaModel.total), 0))
        .scalar()
    )

    # Top 5 productos por ventas (histórico)
    top_productos = (
        db.query(
            DetalleVentaModel.id_producto,
            func.sum(DetalleVentaModel.cantidad).label("cantidad"),
            func.sum(DetalleVentaModel.subtotal).label("subtotal"),
        )
        .join(VentaModel, VentaModel.id_venta == DetalleVentaModel.id_venta)
        .group_by(DetalleVentaModel.id_producto)
        .order_by(func.sum(DetalleVentaModel.subtotal).desc())
        .limit(5)
        .all()
    )

    productos_data = []
    for p in top_productos:
        prod = db.query(ProductoModel).filter(ProductoModel.id_producto == p.id_producto).first()
        productos_data.append({
            "id_producto": prod.id_producto,
            "nombre": prod.nombre,
            "cantidad": float(p.cantidad),
            "subtotal": float(p.subtotal),
        })

    return {
        "hoy": str(hoy),
        "total_hoy": float(total_hoy),
        "num_ventas_hoy": int(num_ventas_hoy),
        "total_general": float(total_general),
        "top_productos": productos_data,
    }
