from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.models import (
    CompraModel,
    DetalleCompraModel,
    InsumoModel,
    MovimientoInventarioModel,
    UsuarioModel,
)
from app.schemas.compra import CompraCreate, CompraResponse
from app.utils.deps import get_current_user, require_admin
from app.utils.permisos import require_module

router = APIRouter(
    prefix="/compras",
    tags=["Compras"],
    dependencies=[Depends(require_admin), Depends(require_module("/compras"))],
)


@router.post("/", response_model=CompraResponse)
def registrar_compra(
    data: CompraCreate,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):

    if not data.detalles or len(data.detalles) == 0:
        raise HTTPException(status_code=400, detail="La compra debe tener insumos")

    total = 0

    # Calcular total
    for item in data.detalles:
        subtotal = float(item.cantidad) * float(item.costo_unitario)
        total += subtotal

    estado = (data.estado_pago or "PAGADO").strip().upper()
    compra = CompraModel(
        fecha_hora=datetime.now(),
        proveedor=data.proveedor,
        total=total,
        estado_pago=estado if estado in ("PAGADO", "PENDIENTE") else "PAGADO",
    )

    db.add(compra)
    db.flush()

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

    from app.services.tesoreria_service import TIPO_COMPRA, registrar_salida_origen, tesoreria_activa

    if tesoreria_activa(db) and compra.estado_pago == "PAGADO":
        if not data.codigo_cuenta:
            raise HTTPException(status_code=422, detail="Indica la cuenta desde la que se paga la compra")
        registrar_salida_origen(
            db,
            usuario=current,
            codigo_cuenta=data.codigo_cuenta,
            importe=total,
            tipo=TIPO_COMPRA,
            concepto=f"Compra {compra.id_compra}",
            operation_id=data.operation_id or f"tesoreria-compra-{compra.id_compra}",
            origen_tipo="COMPRA",
            origen_id=int(compra.id_compra),
        )

    db.commit()
    db.refresh(compra)

    return compra
