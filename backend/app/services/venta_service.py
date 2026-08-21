import json
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from app.utils.timezone_mx import now_utc_naive

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
    ExtraVentaModel,
)
from app.schemas.ventas import VentaCreate, VentaResponse, ExtraVentaLinea
from app.services.promocion_service import calcular_linea
from app.services.fidelidad_service import obtener_config, calcular_puntos_ganados, acumular_puntos_venta
from app.services.extras_validacion_service import validar_extras_producto
from app.exceptions import (
    RecursoNoEncontradoException,
    DatosInvalidosException,
)

MESA_PARA_LLEVAR = 99


def _resolver_extra_insumo(
    db: Session, extra: ExtraVentaLinea
) -> tuple[int | None, float]:
    if extra.id_insumo:
        return int(extra.id_insumo), float(extra.cantidad_insumo or 1)

    if extra.id_extra:
        model = (
            db.query(ExtraVentaModel)
            .filter(ExtraVentaModel.id_extra == extra.id_extra)
            .first()
        )
        if model and model.id_insumo_origen:
            return int(model.id_insumo_origen), float(model.cantidad or 1)
    return None, 0.0


def _revisar_stock_receta(db: Session, detalles, advertencias: List[str]) -> None:
    for item in detalles:
        receta = (
            db.query(RecetaModel)
            .filter(RecetaModel.id_producto == item.id_producto, RecetaModel.activo == True)
            .first()
        )
        if not receta:
            continue
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
                advertencias.append(
                    f"Stock insuficiente de '{insumo.nombre}'. "
                    f"Disponible: {stock_disponible}, Requerido: {cantidad_requerida}"
                )


def _revisar_stock_extras(db: Session, detalles, advertencias: List[str]) -> None:
    for item in detalles:
        for extra in item.extras:
            id_insumo, cantidad_por_unidad = _resolver_extra_insumo(db, extra)
            if not id_insumo:
                continue
            insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == id_insumo).first()
            if not insumo:
                continue
            cantidad_requerida = cantidad_por_unidad * float(item.cantidad)
            stock_disponible = float(insumo.stock_actual)
            if stock_disponible < cantidad_requerida:
                advertencias.append(
                    f"Stock insuficiente de '{insumo.nombre}' (extra). "
                    f"Disponible: {stock_disponible}, Requerido: {cantidad_requerida}"
                )


def _descontar_stock_receta(db: Session, venta_id: int, detalles) -> None:
    for item in detalles:
        receta = (
            db.query(RecetaModel)
            .filter(RecetaModel.id_producto == item.id_producto, RecetaModel.activo == True)
            .first()
        )
        if not receta:
            continue
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
            insumo.stock_actual = float(insumo.stock_actual) - cantidad_total
            mov = MovimientoInventarioModel(
                id_insumo=insumo.id_insumo,
                tipo="SALIDA",
                cantidad=cantidad_total,
                motivo="VENTA",
                referencia=f"VENTA {venta_id}",
                fecha_hora=now_utc_naive(),
            )
            db.add(mov)


def _descontar_stock_extras(db: Session, venta_id: int, detalles) -> None:
    for item in detalles:
        for extra in item.extras:
            id_insumo, cantidad_por_unidad = _resolver_extra_insumo(db, extra)
            if not id_insumo:
                continue
            insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == id_insumo).first()
            if not insumo:
                continue
            cantidad_total = cantidad_por_unidad * float(item.cantidad)
            insumo.stock_actual = float(insumo.stock_actual) - cantidad_total
            mov = MovimientoInventarioModel(
                id_insumo=insumo.id_insumo,
                tipo="SALIDA",
                cantidad=cantidad_total,
                motivo="VENTA_EXTRA",
                referencia=f"VENTA {venta_id}",
                fecha_hora=now_utc_naive(),
            )
            db.add(mov)


def registrar_venta(db: Session, data: VentaCreate) -> VentaResponse:
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id_usuario == data.id_usuario).first()
    if not usuario:
        raise RecursoNoEncontradoException("Usuario no encontrado")

    if not data.detalles or len(data.detalles) == 0:
        raise DatosInvalidosException("La venta debe tener al menos un producto")

    para_llevar = bool(data.para_llevar)
    if para_llevar:
        if data.numero_mesa != MESA_PARA_LLEVAR:
            raise DatosInvalidosException("Venta para llevar inválida")
    elif not data.numero_mesa or data.numero_mesa < 1:
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

        validar_extras_producto(db, item.id_producto, item.extras)

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

    advertencias_stock: List[str] = []
    _revisar_stock_receta(db, data.detalles, advertencias_stock)
    _revisar_stock_extras(db, data.detalles, advertencias_stock)

    venta = VentaModel(
        fecha_hora=now_utc_naive(),
        id_usuario=data.id_usuario,
        numero_mesa=data.numero_mesa,
        para_llevar=para_llevar,
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
            extras_normalizados = validar_extras_producto(db, item.id_producto, item.extras)
            extras_json = json.dumps(extras_normalizados, ensure_ascii=False)
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

    _descontar_stock_receta(db, venta.id_venta, data.detalles)
    _descontar_stock_extras(db, venta.id_venta, data.detalles)

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
        para_llevar=bool(venta.para_llevar),
        advertencias_stock=advertencias_stock,
    )
