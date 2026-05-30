"""
Servicio de lógica de negocio para recetas.
Centraliza cálculos de costos, márgenes y actualización de precios.
"""

from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import (
    RecetaModel,
    RecetaInsumoModel,
    InsumoModel,
    ProductoModel,
    ConfiguracionModel,
)
from app.schemas.receta import RecetaCreate, RecetaInsumoBase, RecetaInsumoDetalle


class RecetaService:
    """Servicio para operaciones relacionadas con recetas"""
    
    @staticmethod
    def obtener_configuracion(db: Session) -> tuple:
        """
        Obtiene el margen de ganancia y gastos fijos de la tabla configuracion.
        Si no existe registro, retorna valores por defecto.
        
        Returns:
            tuple: (margen en porcentaje, gastos_fijos) ej: (15.0, 1000.0)
        """
        config = db.query(ConfiguracionModel).first()
        if config:
            margen = float(config.margen_ganancia) if config.margen_ganancia else 15.0
            gastos = float(config.gastos_fijos) if config.gastos_fijos else 1000.0
            return margen, gastos
        return 15.0, 1000.0
    
    @staticmethod
    def validar_insumo(id_insumo: int, db: Session) -> InsumoModel:
        """
        Valida que un insumo exista en la BD.
        
        Args:
            id_insumo: ID del insumo a validar
            db: Sesión de base de datos
            
        Returns:
            InsumoModel: El insumo si existe
            
        Raises:
            HTTPException: Si el insumo no existe
        """
        insumo = db.query(InsumoModel).filter(
            InsumoModel.id_insumo == id_insumo
        ).first()
        
        if not insumo:
            raise HTTPException(
                status_code=404,
                detail=f"Insumo con ID {id_insumo} no existe"
            )
        
        return insumo
    
    @staticmethod
    def validar_producto(id_producto: int, db: Session) -> ProductoModel:
        """
        Valida que un producto exista en la BD.
        
        Args:
            id_producto: ID del producto a validar
            db: Sesión de base de datos
            
        Returns:
            ProductoModel: El producto si existe
            
        Raises:
            HTTPException: Si el producto no existe
        """
        producto = db.query(ProductoModel).filter(
            ProductoModel.id_producto == id_producto
        ).first()
        
        if not producto:
            raise HTTPException(
                status_code=404,
                detail=f"Producto con ID {id_producto} no existe"
            )
        
        return producto
    
    @staticmethod
    def calcular_costo_total(insumos_data: List[RecetaInsumoBase], db: Session) -> Decimal:
        """
        Calcula el costo total de una receta sumando los costos de sus insumos.
        
        Formula:
            costo_total = suma(cantidad * costo_unitario) para cada insumo
        
        Args:
            insumos_data: Lista de insumos con cantidades
            db: Sesión de base de datos
            
        Returns:
            Decimal: Costo total de la receta
            
        Raises:
            HTTPException: Si algún insumo no existe o cantidad <= 0
        """
        costo_total = Decimal("0")
        
        for item in insumos_data:
            # Validar cantidad > 0
            if item.cantidad <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"La cantidad del insumo {item.id_insumo} debe ser mayor a 0"
                )
            
            # Obtener insumo y validar
            insumo = RecetaService.validar_insumo(item.id_insumo, db)
            
            # Calcular costo parcial
            costo_unitario = Decimal(str(insumo.costo_unitario or 0))
            cantidad = Decimal(str(item.cantidad))
            costo_total += costo_unitario * cantidad
        
        return costo_total
    
    @staticmethod
    def calcular_precio_venta(costo_total: Decimal, margen: float, gastos_fijos: float = 1000.0) -> Decimal:
        """
        Calcula el precio de venta aplicando el margen y distribuye gastos fijos.
        
        Formula:
            precio_venta = (costo_total + gastos_fijos/1000) * (1 + margen/100)
        
        Se asume una venta de 1000 productos por mes, distribuyendo gastos_fijos entre ellos.
        
        Args:
            costo_total: Costo base de la receta
            margen: Margen de ganancia en porcentaje (ej: 15 para 15%)
            gastos_fijos: Gastos fijos mensuales (default 1000)
            
        Returns:
            Decimal: Precio de venta calculado
        """
        # Convertir a Decimal para precisión
        costo_dec = Decimal(str(costo_total))
        margen_dec = Decimal(str(margen))
        gastos_dec = Decimal(str(gastos_fijos))
        
        # Costo total + distribución de gastos fijos (1000 productos/mes)
        costo_con_gastos = costo_dec + (gastos_dec / Decimal("1000"))
        
        # Aplicar margen
        precio_venta = costo_con_gastos * (Decimal("1") + margen_dec / Decimal("100"))
        
        return precio_venta
    
    @staticmethod
    def construir_respuesta_insumo(ri: RecetaInsumoModel, db: Session) -> RecetaInsumoDetalle:
        """
        Construye un detalle de insumo con información completa.
        
        Args:
            ri: Registro de RecetaInsumoModel
            db: Sesión de base de datos
            
        Returns:
            RecetaInsumoDetalle: Detalle completo del insumo
        """
        insumo = db.query(InsumoModel).filter(
            InsumoModel.id_insumo == ri.id_insumo
        ).first()
        
        if not insumo:
            return None
        
        costo_unitario = float(insumo.costo_unitario or 0)
        cantidad = float(ri.cantidad)
        subtotal = cantidad * costo_unitario
        
        return RecetaInsumoDetalle(
            id_insumo=ri.id_insumo,
            nombre_insumo=insumo.nombre,
            cantidad=cantidad,
            costo_unitario=costo_unitario,
            subtotal=subtotal
        )
    
    @staticmethod
    def construir_lista_insumos_detalle(
        receta: RecetaModel,
        db: Session
    ) -> List[RecetaInsumoDetalle]:
        """
        Construye la lista de detalles de insumos para una receta, ordenados alfabéticamente.
        
        Args:
            receta: Modelo de receta
            db: Sesión de base de datos
            
        Returns:
            List[RecetaInsumoDetalle]: Lista de detalles de insumos ordenada alfabéticamente
        """
        insumos_detalle = []
        
        for ri in receta.insumos:
            detalle = RecetaService.construir_respuesta_insumo(ri, db)
            if detalle:
                insumos_detalle.append(detalle)
        
        # Ordenar alfabéticamente por nombre del insumo
        insumos_detalle.sort(key=lambda x: x.nombre_insumo.lower())
        
        return insumos_detalle

    @staticmethod
    def calcular_costo_total_desde_receta(receta: RecetaModel, db: Session) -> Decimal:
        """
        Recalcula el costo de una receta según los costos actuales de sus insumos.
        """
        costo_total = Decimal("0")

        for ri in receta.insumos:
            insumo = db.query(InsumoModel).filter(
                InsumoModel.id_insumo == ri.id_insumo
            ).first()
            if not insumo:
                continue

            costo_unitario = Decimal(str(insumo.costo_unitario or 0))
            cantidad = Decimal(str(ri.cantidad))
            costo_total += costo_unitario * cantidad

        return costo_total

    @staticmethod
    def actualizar_precios_productos_por_configuracion(
        db: Session,
        margen: Optional[float] = None,
        gastos_fijos: Optional[float] = None,
    ) -> dict:
        """
        Recalcula costo y precio de venta de todos los productos con receta activa,
        usando el margen y los gastos fijos indicados (o los de la BD).
        """
        if margen is None or gastos_fijos is None:
            margen, gastos_fijos = RecetaService.obtener_configuracion(db)

        recetas_activas = (
            db.query(RecetaModel)
            .filter(RecetaModel.activo == True)
            .order_by(RecetaModel.id_receta)
            .all()
        )

        productos_actualizados = 0
        productos_vistos: set[int] = set()

        for receta in recetas_activas:
            if receta.id_producto in productos_vistos:
                continue
            productos_vistos.add(receta.id_producto)

            producto = db.query(ProductoModel).filter(
                ProductoModel.id_producto == receta.id_producto
            ).first()
            if not producto:
                continue

            costo_total = RecetaService.calcular_costo_total_desde_receta(receta, db)
            receta.costo_total = costo_total
            precio_venta = RecetaService.calcular_precio_venta(
                costo_total, margen, gastos_fijos
            )
            producto.precio_venta = precio_venta
            productos_actualizados += 1

        return {
            "productos_precio_actualizados": productos_actualizados,
            "recetas_activas": len(recetas_activas),
        }
