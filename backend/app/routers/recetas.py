from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List

from app.database import get_db
from app.models import (
    RecetaModel, 
    RecetaInsumoModel, 
    ProductoModel,
)
from app.schemas.receta import (
    RecetaCreate, 
    RecetaUpdate,
    RecetaResponse,
)
from app.services import RecetaService

router = APIRouter(prefix="/recetas", tags=["Recetas"])


# ============================
# LISTAR TODAS LAS RECETAS
# ============================
@router.get("/", response_model=List[RecetaResponse])
def listar_recetas(db: Session = Depends(get_db)):
    """Obtiene la lista de todas las recetas"""
    recetas = db.query(RecetaModel).all()
    
    resultado = []
    for receta in recetas:
        insumos_detalle = RecetaService.construir_lista_insumos_detalle(receta, db)
        
        producto = db.query(ProductoModel).filter(
            ProductoModel.id_producto == receta.id_producto
        ).first()
        
        resultado.append(RecetaResponse(
            id_receta=receta.id_receta,
            id_producto=receta.id_producto,
            nombre=receta.nombre,
            descripcion=receta.descripcion,
            activo=receta.activo,
            costo_total=float(receta.costo_total or 0),
            insumos=insumos_detalle,
            precio_venta_producto=float(producto.precio_venta or 0) if producto else 0
        ))
    
    return resultado


# ============================
# OBTENER UNA RECETA POR ID
# ============================
@router.get("/{id_receta}", response_model=RecetaResponse)
def obtener_receta(id_receta: int, db: Session = Depends(get_db)):
    """Obtiene una receta específica por su ID"""
    receta = db.query(RecetaModel).filter(
        RecetaModel.id_receta == id_receta
    ).first()
    
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    
    insumos_detalle = RecetaService.construir_lista_insumos_detalle(receta, db)
    
    producto = db.query(ProductoModel).filter(
        ProductoModel.id_producto == receta.id_producto
    ).first()
    
    return RecetaResponse(
        id_receta=receta.id_receta,
        id_producto=receta.id_producto,
        nombre=receta.nombre,
        descripcion=receta.descripcion,
        activo=receta.activo,
        costo_total=float(receta.costo_total or 0),
        insumos=insumos_detalle,
        precio_venta_producto=float(producto.precio_venta or 0) if producto else 0
    )


# ============================
# CREAR RECETA
# ============================
@router.post("/", response_model=RecetaResponse, status_code=201)
def crear_receta(data: RecetaCreate, db: Session = Depends(get_db)):
    """
    Crea una nueva receta con sus insumos.
    
    El flujo es:
    1. Validar que el producto existe
    2. Validar que cada insumo existe y cantidad > 0
    3. Calcular costo total de la receta
    4. Obtener margen de ganancia desde configuracion
    5. Calcular precio_venta = costo_total * (1 + margen)
    6. Guardar receta, insumos y actualizar producto
    """
    try:
        # Validar producto
        producto = RecetaService.validar_producto(data.id_producto, db)
        
        # Validar y calcular costo total de insumos
        costo_total = RecetaService.calcular_costo_total(data.insumos, db)
        
        # Obtener margen y gastos fijos, luego calcular precio
        margen, gastos_fijos = RecetaService.obtener_configuracion(db)
        precio_venta = RecetaService.calcular_precio_venta(costo_total, margen, gastos_fijos)
        
        # Crear receta
        receta = RecetaModel(
            id_producto=data.id_producto,
            nombre=data.nombre,
            descripcion=data.descripcion,
            activo=data.activo,
            costo_total=costo_total
        )
        
        db.add(receta)
        db.flush()
        
        # Agregar insumos
        for insumo_item in data.insumos:
            receta_insumo = RecetaInsumoModel(
                id_receta=receta.id_receta,
                id_insumo=insumo_item.id_insumo,
                cantidad=insumo_item.cantidad
            )
            db.add(receta_insumo)
        
        # Actualizar precio del producto
        producto.precio_venta = precio_venta
        
        db.commit()
        db.refresh(receta)
        
        # Construir respuesta
        insumos_detalle = RecetaService.construir_lista_insumos_detalle(receta, db)
        
        return RecetaResponse(
            id_receta=receta.id_receta,
            id_producto=receta.id_producto,
            nombre=receta.nombre,
            descripcion=receta.descripcion,
            activo=receta.activo,
            costo_total=float(receta.costo_total or 0),
            insumos=insumos_detalle,
            precio_venta_producto=float(producto.precio_venta or 0)
        )
    
    except IntegrityError as e:
        db.rollback()
        error_detail = str(e.orig) if hasattr(e, 'orig') else str(e)
        print(f"[DEBUG] IntegrityError: {error_detail}")
        raise HTTPException(
            status_code=400,
            detail=f"Error de BD: {error_detail}"
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"[DEBUG] Exception: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
        )


# ============================
# ACTUALIZAR RECETA
# ============================
@router.put("/{id_receta}", response_model=RecetaResponse)
def actualizar_receta(
    id_receta: int,
    data: RecetaUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza una receta existente.
    Si se actualizan los insumos, recalcula el costo y precio.
    """
    try:
        receta = db.query(RecetaModel).filter(
            RecetaModel.id_receta == id_receta
        ).first()
        
        if not receta:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        
        # Actualizar campos simples
        if data.nombre is not None:
            receta.nombre = data.nombre
        
        if data.descripcion is not None:
            receta.descripcion = data.descripcion
        
        if data.activo is not None:
            receta.activo = data.activo
        
        # Si se actualizan insumos
        if data.insumos is not None:
            costo_total = RecetaService.calcular_costo_total(data.insumos, db)
            receta.costo_total = costo_total
            
            margen, gastos_fijos = RecetaService.obtener_configuracion(db)
            precio_venta = RecetaService.calcular_precio_venta(costo_total, margen, gastos_fijos)
            
            producto = db.query(ProductoModel).filter(
                ProductoModel.id_producto == receta.id_producto
            ).first()
            
            if producto:
                producto.precio_venta = precio_venta
            
            # Eliminar insumos anteriores
            db.query(RecetaInsumoModel).filter(
                RecetaInsumoModel.id_receta == id_receta
            ).delete()
            
            # Agregar nuevos insumos
            for insumo_item in data.insumos:
                receta_insumo = RecetaInsumoModel(
                    id_receta=id_receta,
                    id_insumo=insumo_item.id_insumo,
                    cantidad=insumo_item.cantidad
                )
                db.add(receta_insumo)
        
        db.commit()
        db.refresh(receta)
        
        # Construir respuesta
        insumos_detalle = RecetaService.construir_lista_insumos_detalle(receta, db)
        
        producto = db.query(ProductoModel).filter(
            ProductoModel.id_producto == receta.id_producto
        ).first()
        
        return RecetaResponse(
            id_receta=receta.id_receta,
            id_producto=receta.id_producto,
            nombre=receta.nombre,
            descripcion=receta.descripcion,
            activo=receta.activo,
            costo_total=float(receta.costo_total or 0),
            insumos=insumos_detalle,
            precio_venta_producto=float(producto.precio_venta or 0) if producto else 0
        )
    
    except IntegrityError as e:
        db.rollback()
        error_detail = str(e.orig) if hasattr(e, 'orig') else str(e)
        print(f"[DEBUG] IntegrityError en actualizar: {error_detail}")
        raise HTTPException(
            status_code=400,
            detail=f"Error de BD: {error_detail}"
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"[DEBUG] Exception en actualizar: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
        )


# ============================
# ELIMINAR RECETA
# ============================
@router.delete("/{id_receta}", status_code=204)
def eliminar_receta(id_receta: int, db: Session = Depends(get_db)):
    """
    Elimina una receta.
    Los insumos asociados se eliminan automáticamente por cascada.
    """
    try:
        receta = db.query(RecetaModel).filter(
            RecetaModel.id_receta == id_receta
        ).first()
        
        if not receta:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        
        db.delete(receta)
        db.commit()
        
        return None
    
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar la receta: {str(e)}"
        )

