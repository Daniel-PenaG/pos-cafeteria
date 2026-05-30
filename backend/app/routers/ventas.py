import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from app.database import get_db
from app.models import (
    ProductoModel,
    RecetaModel,
    RecetaInsumoModel,
    InsumoModel,
    VentaModel,
    DetalleVentaModel,
    MovimientoInventarioModel,
    UsuarioModel,
)
from app.schemas.ventas import VentaCreate, VentaResponse, ExtraVenta
from app.services.extras_venta_service import extras_para_producto, extras_para_categoria
from app.exceptions import (
    RecursoNoEncontradoException,
    DatosInvalidosException,
    StockInsuficienteException,
)

router = APIRouter(prefix="/ventas", tags=["Ventas"])


@router.get("/extras", response_model=List[ExtraVenta])
def listar_extras_venta(
    id_producto: Optional[int] = None,
    id_categoria: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Extras permitidos según la categoría del producto (configurados en Extras de venta)."""
    if id_producto:
        return extras_para_producto(db, id_producto)
    if id_categoria:
        return extras_para_categoria(db, id_categoria)
    raise DatosInvalidosException("Indica id_producto o id_categoria")


# ============================
# REGISTRAR VENTA
# ============================
@router.post("/", response_model=VentaResponse)
def registrar_venta(data: VentaCreate, db: Session = Depends(get_db)):

    # Validar usuario
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id_usuario == data.id_usuario).first()
    if not usuario:
        raise RecursoNoEncontradoException("Usuario no encontrado")

    if not data.detalles or len(data.detalles) == 0:
        raise DatosInvalidosException("La venta debe tener al menos un producto")

    if not data.numero_mesa or data.numero_mesa < 1:
        raise DatosInvalidosException("Selecciona un número de mesa válido")

    # Validar forma de pago
    if not data.forma_pago or data.forma_pago.strip() == "":
        raise DatosInvalidosException("Forma de pago requerida")

    total_calculado = 0

    # 1) Validar productos y calcular total
    for item in data.detalles:
        # Validar cantidad positiva
        if item.cantidad <= 0:
            raise DatosInvalidosException(f"La cantidad debe ser positiva")
        
        # Validar precio positivo
        if item.precio_unitario <= 0:
            raise DatosInvalidosException(f"El precio debe ser positivo")
        
        producto = db.query(ProductoModel).filter(ProductoModel.id_producto == item.id_producto).first()
        if not producto:
            raise RecursoNoEncontradoException(f"Producto {item.id_producto} no encontrado")

        if not producto.activo:
            raise DatosInvalidosException(f"Producto {producto.nombre} no está activo")

        subtotal = float(item.cantidad) * float(item.precio_unitario)
        total_calculado += subtotal

    # 2) VALIDAR STOCK DISPONIBLE antes de crear venta
    for item in data.detalles:
        producto = db.query(ProductoModel).filter(ProductoModel.id_producto == item.id_producto).first()
        
        receta = (
            db.query(RecetaModel)
            .filter(RecetaModel.id_producto == item.id_producto, RecetaModel.activo == True)
            .first()
        )

        if receta:
            receta_insumos = (
                db.query(RecetaInsumoModel)
                .filter(RecetaInsumoModel.id_receta == receta.id_receta)
                .all()
            )

            for ri in receta_insumos:
                insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == ri.id_insumo).first()
                if not insumo:
                    continue

                cantidad_requerida = float(ri.cantidad) * float(item.cantidad)
                stock_disponible = float(insumo.stock_actual)

                if stock_disponible < cantidad_requerida:
                    raise StockInsuficienteException(
                        f"Stock insuficiente de '{insumo.nombre}'. "
                        f"Disponible: {stock_disponible}, Requerido: {cantidad_requerida}"
                    )

    # 3) Crear venta
    venta = VentaModel(
        fecha_hora=datetime.now(),
        id_usuario=data.id_usuario,
        numero_mesa=data.numero_mesa,
        total=total_calculado,
        forma_pago=data.forma_pago,
    )
    db.add(venta)
    db.commit()
    db.refresh(venta)

    # 4) Crear detalles + descontar inventario por receta
    for item in data.detalles:
        producto = db.query(ProductoModel).filter(ProductoModel.id_producto == item.id_producto).first()

        extras_json = None
        if item.extras:
            extras_json = json.dumps(
                [
                    {
                        "id_extra": e.id_extra,
                        "nombre": e.nombre,
                        "precio": float(e.precio),
                    }
                    for e in item.extras
                ],
                ensure_ascii=False,
            )

        detalle = DetalleVentaModel(
            id_venta=venta.id_venta,
            id_producto=item.id_producto,
            cantidad=item.cantidad,
            precio_unitario=item.precio_unitario,
            subtotal=float(item.cantidad) * float(item.precio_unitario),
            extras_json=extras_json,
        )
        db.add(detalle)

        # Buscar receta del producto
        receta = (
            db.query(RecetaModel)
            .filter(RecetaModel.id_producto == item.id_producto, RecetaModel.activo == True)
            .first()
        )

        if receta:
            # Por cada insumo de la receta, descontar stock
            receta_insumos = (
                db.query(RecetaInsumoModel)
                .filter(RecetaInsumoModel.id_receta == receta.id_receta)
                .all()
            )

            for ri in receta_insumos:
                insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == ri.id_insumo).first()
                if not insumo:
                    continue

                # cantidad_total = cantidad_por_producto * cantidad_vendida
                cantidad_total = float(ri.cantidad) * float(item.cantidad)

                # Descontar stock
                insumo.stock_actual = float(insumo.stock_actual) - cantidad_total

                # Registrar movimiento de inventario
                mov = MovimientoInventarioModel(
                    id_insumo=insumo.id_insumo,
                    tipo="SALIDA",
                    cantidad=cantidad_total,
                    motivo="VENTA",
                    referencia=f"VENTA {venta.id_venta}",
                    fecha_hora=datetime.now(),
                )
                db.add(mov)

    db.commit()
    db.refresh(venta)

    # Construir respuesta
    return VentaResponse(
        id_venta=venta.id_venta,
        fecha_hora=venta.fecha_hora,
        id_usuario=venta.id_usuario,
        numero_mesa=int(venta.numero_mesa),
        total=float(venta.total),
        forma_pago=venta.forma_pago,
    )
