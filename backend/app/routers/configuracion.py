from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.models import ConfiguracionModel
from app.schemas.configuracion import (
    Configuracion,
    ConfiguracionUpdate,
    ConfiguracionActualizada,
)
from app.services import RecetaService

router = APIRouter(prefix="/configuracion", tags=["Configuración"])


# ============================
# OBTENER CONFIGURACIÓN
# ============================
@router.get("/", response_model=Configuracion)
def obtener_configuracion(db: Session = Depends(get_db)):
    """Obtiene la configuración actual (márgenes, etc.)"""
    config = db.query(ConfiguracionModel).first()
    
    if not config:
        # Si no existe, crear con margen por defecto (15%)
        config = ConfiguracionModel(margen_ganancia=15.0)
        db.add(config)
        db.commit()
        db.refresh(config)
    
    return config


# ============================
# ACTUALIZAR CONFIGURACIÓN
# ============================
@router.put("/", response_model=ConfiguracionActualizada)
def actualizar_configuracion(data: ConfiguracionUpdate, db: Session = Depends(get_db)):
    """Actualiza la configuración y recalcula precios de venta de productos con receta activa."""
    
    # Validar que el margen esté entre 0 y 100
    if data.margen_ganancia < 0 or data.margen_ganancia > 100:
        raise HTTPException(
            status_code=400, 
            detail="El margen debe estar entre 0 y 100"
        )
    
    # Validar que los gastos fijos no sean negativos
    if data.gastos_fijos < 0:
        raise HTTPException(
            status_code=400, 
            detail="Los gastos fijos no pueden ser negativos"
        )
    
    config = db.query(ConfiguracionModel).first()
    
    if not config:
        config = ConfiguracionModel(
            margen_ganancia=data.margen_ganancia,
            gastos_fijos=data.gastos_fijos
        )
        db.add(config)
    else:
        config.margen_ganancia = data.margen_ganancia
        config.gastos_fijos = data.gastos_fijos
        config.fecha_actualizacion = datetime.utcnow()
    
    db.commit()
    db.refresh(config)

    productos_actualizados = 0
    try:
        resultado = RecetaService.actualizar_precios_productos_por_configuracion(
            db,
            margen=float(data.margen_ganancia),
            gastos_fijos=float(data.gastos_fijos),
        )
        db.commit()
        productos_actualizados = resultado.get("productos_precio_actualizados", 0)
    except Exception:
        db.rollback()

    return ConfiguracionActualizada(
        id_configuracion=config.id_configuracion,
        margen_ganancia=float(config.margen_ganancia),
        gastos_fijos=float(config.gastos_fijos),
        fecha_actualizacion=config.fecha_actualizacion,
        productos_precio_actualizados=productos_actualizados,
    )


# ============================
# CALCULAR PRECIO SUGERIDO CON MARGEN
# ============================
@router.post("/calcular-precio")
def calcular_precio_sugerido(costo_unitario: float, db: Session = Depends(get_db)):
    """
    Calcula el precio sugerido de venta aplicando el margen configurado
    Fórmula: precio_venta = costo * (1 + margen/100)
    """
    
    config = db.query(ConfiguracionModel).first()
    margen = config.margen_ganancia if config else 15.0
    
    precio_sugerido = float(costo_unitario) * (1 + float(margen) / 100)
    
    return {
        "costo_unitario": costo_unitario,
        "margen_ganancia": margen,
        "precio_sugerido": round(precio_sugerido, 2)
    }
