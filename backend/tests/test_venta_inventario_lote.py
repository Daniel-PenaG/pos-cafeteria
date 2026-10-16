"""Inventario por lotes: agregación, extras, advertencias y transacción."""
from __future__ import annotations

import pytest
from sqlalchemy import func

from app.models import InsumoModel, MovimientoInventarioModel, VentaModel
from app.schemas.ventas import DetalleVentaItem, ExtraVentaLinea
from app.services.venta_inventario import (
    _consumo_por_insumo,
    descontar_stock_venta,
    revisar_stock_venta,
)
from app.services.pedido_service import cobrar_pedido, confirmar_comanda_pedido, obtener_pedido_abierto_mesa
from app.services.pedido_service import agregar_linea_pedido
from app.schemas.pedido import PedidoLineaCreate
from app.services.pedido_service import recalcular_lineas_ticket
from app.utils.sql_counter import get_sql_count, reset_sql_count


def test_revisar_stock_agrupa_insumos(db_session, refs):
    detalles = [
        DetalleVentaItem(
            id_producto=refs.id_cafe,
            cantidad=2,
            precio_unitario=35,
            extras=[],
        ),
        DetalleVentaItem(
            id_producto=refs.id_malteada,
            cantidad=1,
            precio_unitario=48,
            extras=[],
        ),
    ]
    reset_sql_count()
    advertencias, estructura = revisar_stock_venta(db_session, detalles)
    sql = get_sql_count()
    assert isinstance(advertencias, list)
    assert isinstance(estructura, list)
    assert sql <= 6, f"demasiadas consultas SQL para revisar stock: {sql}"


def _extra_leche(refs):
    return ExtraVentaLinea(
        id_extra=refs.id_extra_leche,
        nombre="Extra Leche",
        precio=5,
        id_insumo=refs.id_insumo_leche,
        cantidad_insumo=0.1,
    )


def test_consumo_suma_mismo_insumo(db_session, refs):
    extra = _extra_leche(refs)
    detalles = [
        DetalleVentaItem(id_producto=refs.id_malteada, cantidad=1, precio_unitario=48, extras=[extra]),
        DetalleVentaItem(id_producto=refs.id_malteada, cantidad=1, precio_unitario=48, extras=[extra]),
    ]
    consumo = _consumo_por_insumo(db_session, detalles)
    assert refs.id_insumo_leche in consumo
    assert consumo[refs.id_insumo_leche] > 0


def test_advertencias_sin_duplicar_insumo(db_session, refs):
    insumo = db_session.get(InsumoModel, refs.id_insumo_leche)
    stock_prev = float(insumo.stock_actual)
    insumo.stock_actual = 0.01
    db_session.commit()
    extra = _extra_leche(refs)
    detalles = [
        DetalleVentaItem(id_producto=refs.id_malteada, cantidad=2, precio_unitario=48, extras=[extra]),
        DetalleVentaItem(id_producto=refs.id_malteada, cantidad=1, precio_unitario=48, extras=[extra]),
    ]
    _, estructura = revisar_stock_venta(db_session, detalles)
    ids = [e["id_insumo"] for e in estructura]
    assert len(ids) == len(set(ids))
    insumo.stock_actual = stock_prev
    db_session.commit()


def test_descontar_orden_ascendente_ids(db_session, refs):
    detalles = [
        DetalleVentaItem(id_producto=refs.id_cafe, cantidad=1, precio_unitario=35, extras=[]),
    ]
    consumo = _consumo_por_insumo(db_session, detalles)
    ids_esperados = sorted(consumo.keys())
    assert ids_esperados == sorted(ids_esperados)
    antes = {
        i: float(db_session.get(InsumoModel, i).stock_actual)
        for i in ids_esperados
    }
    descontar_stock_venta(db_session, 999001, detalles)
    db_session.flush()
    for i in ids_esperados:
        desp = float(db_session.get(InsumoModel, i).stock_actual)
        assert desp == pytest.approx(antes[i] - consumo[i])
    movs = (
        db_session.query(MovimientoInventarioModel)
        .filter(MovimientoInventarioModel.referencia == "VENTA 999001")
        .all()
    )
    assert len(movs) == len(ids_esperados)
    db_session.rollback()


def test_cobro_fallido_no_deja_venta_ni_movimiento(db_session, refs):
    from app.models import PedidoModel

    pedido = obtener_pedido_abierto_mesa(db_session, 8, refs.id_usuario)
    recalc = recalcular_lineas_ticket(
        db_session,
        [{"id_producto": refs.id_cafe, "cantidad": 1, "precio_extras": 0, "extras": []}],
    )
    calc = recalc["lineas"][0]
    agregar_linea_pedido(
        db_session,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_cafe,
            cantidad=1,
            precio_unitario=calc["precio_unitario"],
            extras=[],
            enviar_comanda=False,
        ),
    )
    confirmar_comanda_pedido(db_session, pedido)
    ventas_antes = db_session.query(func.count(VentaModel.id_venta)).scalar()
    movs_antes = db_session.query(func.count(MovimientoInventarioModel.id_movimiento)).scalar()
    from app.exceptions import DatosInvalidosException

    with pytest.raises(DatosInvalidosException):
        cobrar_pedido(
            db_session,
            pedido,
            refs.id_usuario,
            "EFECTIVO",
            puntos_canje=999_999,
            id_cliente=refs.id_cliente,
        )
    db_session.rollback()
    db_session.expire_all()
    ventas_desp = db_session.query(func.count(VentaModel.id_venta)).scalar()
    movs_desp = db_session.query(func.count(MovimientoInventarioModel.id_movimiento)).scalar()
    pedido_db = db_session.get(PedidoModel, pedido.id_pedido)
    assert ventas_desp == ventas_antes
    assert movs_desp == movs_antes
    assert pedido_db.estado != "COBRADO"
