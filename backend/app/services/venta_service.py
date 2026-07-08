import json
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import (
    ProductoModel,
    RecetaModel,
    RecetaInsumoModel,
    InsumoModel,
    VentaModel,
    DetalleVentaModel,
    MovimientoInventarioModel,
    UsuarioModel,
    ClienteModel,
)
from app.schemas.ventas import VentaCreate, VentaResponse
from app.services.promocion_service import calcular_linea
from app.services.fidelidad_service import obtener_config, calcular_puntos_ganados, acumular_puntos_venta
from app.services.inventario_service import sync_stock_total
from app.exceptions import (
    RecursoNoEncontradoException,
    DatosInvalidosException,
    StockInsuficienteException,
)


def registrar_venta(db: Session, data: VentaCreate) -> VentaResponse:
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id_usuario == data.id_usuario).first()
    if not usuario:
        raise RecursoNoEncontradoException("Usuario no encontrado")

    if not data.detalles or len(data.detalles) == 0:
        raise DatosInvalidosException("La venta debe tener al menos un producto")

    if not data.numero_mesa or data.numero_mesa < 1:
        raise DatosInvalidosException("Selecciona un número de mesa válido")

    if not data.forma_pago or data.forma_pago.strip() == "":
        raise DatosInvalidosException("Forma de pago requerida")

    total_calculado = 0

    for item in data.detalles:
        if item.cantidad <= 0:
            raise DatosInvalidosException("La cantidad debe ser positiva")

        producto = db.query(ProductoModel).filter(ProductoModel.id_producto == item.id_producto).first()
        if not producto:
            raise RecursoNoEncontradoException(f"Producto {item.id_producto} no encontrado")
        if not producto.activo:
            raise DatosInvalidosException(f"Producto {producto.nombre} no está activo")

        precio_extras = sum(float(e.precio) for e in item.extras)
        calculo = calcular_linea(
            db,
            producto,
            float(item.cantidad),
            precio_extras,
            item.id_promocion,
        )
        if not calculo["margen_ok"]:
            raise DatosInvalidosException(calculo["mensaje"] or "Margen insuficiente para la promoción")

        esperado = calculo["precio_unitario"]
        if abs(float(item.precio_unitario) - esperado) > 0.02:
            raise DatosInvalidosException(
                f"Precio inválido para '{producto.nombre}'. "
                f"Esperado: {esperado:.2f}, recibido: {item.precio_unitario:.2f}"
            )
        if item.precio_unitario <= 0:
            raise DatosInvalidosException("El precio debe ser positivo")

        total_calculado += float(item.cantidad) * esperado

    cliente = None
    puntos_generados = 0
    if data.id_cliente:
        cliente = (
            db.query(ClienteModel)
            .filter(ClienteModel.id_cliente == data.id_cliente, ClienteModel.activo == True)
            .first()
        )
        if not cliente:
            raise RecursoNoEncontradoException("Cliente no encontrado o inactivo")
        config_fid = obtener_config(db)
        puntos_generados = calcular_puntos_ganados(total_calculado, config_fid)

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
                stock_disponible = float(insumo.stock_cafeteria or 0)
                if stock_disponible < cantidad_requerida:
                    raise StockInsuficienteException(
                        f"Stock insuficiente en cafetería de '{insumo.nombre}'. "
                        f"Disponible: {stock_disponible}, Requerido: {cantidad_requerida}. "
                        f"Surtir desde bodega si hay existencia."
                    )

    venta = VentaModel(
        fecha_hora=datetime.now(),
        id_usuario=data.id_usuario,
        numero_mesa=data.numero_mesa,
        total=total_calculado,
        forma_pago=data.forma_pago,
        id_cliente=data.id_cliente if cliente else None,
        puntos_generados=puntos_generados,
    )
    db.add(venta)
    db.commit()
    db.refresh(venta)

    for item in data.detalles:
        producto = db.query(ProductoModel).filter(ProductoModel.id_producto == item.id_producto).first()
        extras_json = None
        if item.extras:
            extras_json = json.dumps(
                [
                    {"id_extra": e.id_extra, "nombre": e.nombre, "precio": float(e.precio)}
                    for e in item.extras
                ],
                ensure_ascii=False,
            )
        precio_extras = sum(float(e.precio) for e in item.extras)
        calculo = calcular_linea(
            db, producto, float(item.cantidad), precio_extras, item.id_promocion
        )
        detalle = DetalleVentaModel(
            id_venta=venta.id_venta,
            id_producto=item.id_producto,
            cantidad=item.cantidad,
            precio_unitario=calculo["precio_unitario"],
            subtotal=float(item.cantidad) * float(calculo["precio_unitario"]),
            extras_json=extras_json,
            id_promocion=calculo["id_promocion"],
            precio_original=calculo["precio_original_unitario"],
            descuento_unitario=calculo["descuento_unitario"],
            costo_unitario_snapshot=calculo["costo_unitario"],
        )
        db.add(detalle)

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
                cantidad_total = float(ri.cantidad) * float(item.cantidad)
                insumo.stock_cafeteria = float(insumo.stock_cafeteria or 0) - cantidad_total
                sync_stock_total(insumo)
                mov = MovimientoInventarioModel(
                    id_insumo=insumo.id_insumo,
                    tipo="SALIDA",
                    cantidad=cantidad_total,
                    motivo="VENTA_CAFETERIA",
                    referencia=f"VENTA {venta.id_venta}",
                    fecha_hora=datetime.now(),
                )
                db.add(mov)

    if cliente and puntos_generados > 0:
        acumular_puntos_venta(db, cliente, puntos_generados, venta.id_venta, data.id_usuario)

    db.commit()
    db.refresh(venta)

    cliente_nombre = None
    cliente_puntos_saldo = None
    if cliente:
        db.refresh(cliente)
        cliente_nombre = cliente.nombre
        cliente_puntos_saldo = int(cliente.puntos_saldo)

    return VentaResponse(
        id_venta=venta.id_venta,
        fecha_hora=venta.fecha_hora,
        id_usuario=venta.id_usuario,
        numero_mesa=int(venta.numero_mesa),
        total=float(venta.total),
        forma_pago=venta.forma_pago,
        id_cliente=venta.id_cliente,
        puntos_generados=int(venta.puntos_generados or 0),
        cliente_nombre=cliente_nombre,
        cliente_puntos_saldo=cliente_puntos_saldo,
    )
