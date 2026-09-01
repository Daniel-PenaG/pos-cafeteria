"""Pruebas de integración: registrar_venta y flujos de cobro."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.exceptions import DatosInvalidosException
from app.models.models import (
    DetalleVentaModel,
    ExtraVentaModel,
    InsumoModel,
    MovimientoInventarioModel,
    PedidoModel,
    VentaModel,
)
from app.schemas.pedido import PedidoLineaCreate
from app.schemas.ventas import DetalleVentaItem, ExtraVentaLinea, VentaCreate
from app.services.pedido_service import (
    agregar_linea_pedido,
    cobrar_pedido,
    confirmar_comanda_pedido,
    obtener_pedido_abierto_mesa,
    recalcular_promociones_pedido,
)
from app.services.promocion_ticket_service import recalcular_lineas_ticket
from app.services.venta_service import MESA_PARA_LLEVAR, registrar_venta
from app.services.extras_precio import precio_desde_modelo
from tests.promo_seed import crear_promo, promo_vigente_siempre


def _extra_linea(db, refs):
    model = db.get(ExtraVentaModel, refs.id_extra_leche)
    precio = float(precio_desde_modelo(model))
    return ExtraVentaLinea(
        id_extra=refs.id_extra_leche,
        nombre="Extra Leche",
        precio=precio,
        id_insumo=refs.id_insumo_leche,
        cantidad_insumo=0.1,
    )


def _lineas_desde_recalc(db, items):
    """Recalcula ticket completo y devuelve DetalleVentaItem por línea."""
    entrada = []
    for id_producto, cantidad, id_promocion, extras in items:
        entrada.append(
            {
                "id_producto": id_producto,
                "cantidad": cantidad,
                "precio_extras": sum(e.precio for e in (extras or [])),
                "extras": extras or [],
                "id_promocion": id_promocion,
            }
        )
    recalc = recalcular_lineas_ticket(db, entrada)
    out = []
    for calc, (id_producto, cantidad, _, extras) in zip(recalc["lineas"], items):
        out.append(
            DetalleVentaItem(
                id_producto=id_producto,
                cantidad=cantidad,
                precio_unitario=calc["precio_unitario"],
                precio_original=calc.get("precio_original"),
                id_promocion=calc.get("id_promocion"),
                extras=extras or [],
            )
        )
    return out


def _linea(db, id_producto, cantidad, id_promocion=None, extras=None):
    return _lineas_desde_recalc(
        db, [(id_producto, cantidad, id_promocion, extras)]
    )[0]


def _venta(db, refs, detalles, **kwargs):
    data = VentaCreate(
        id_usuario=refs.id_usuario,
        numero_mesa=kwargs.get("numero_mesa", 5),
        forma_pago=kwargs.get("forma_pago", "EFECTIVO"),
        id_cliente=kwargs.get("id_cliente"),
        para_llevar=kwargs.get("para_llevar", False),
        detalles=detalles,
    )
    return registrar_venta(db, data)


def test_venta_normal_varios_productos(db_session, refs):
    detalles = [
        _linea(db_session, refs.id_malteada, 1),
        _linea(db_session, refs.id_cafe, 2),
    ]
    resp = _venta(db_session, refs, detalles)
    assert resp.total == 165.0
    dets = db_session.query(DetalleVentaModel).filter_by(id_venta=resp.id_venta).all()
    assert all(d.id_promocion is None for d in dets)
    assert all(d.nombre_promocion is None for d in dets)


def test_venta_porcentaje(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="20%",
        tipo="PORCENTAJE",
        valor=20,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    det = _linea(db_session, refs.id_malteada, 1, promo.id_promocion)
    resp = _venta(db_session, refs, [det])
    assert resp.total == 52.0
    dv = db_session.query(DetalleVentaModel).filter_by(id_venta=resp.id_venta).one()
    assert dv.id_promocion == promo.id_promocion
    assert float(dv.descuento_unitario) == 13.0


def test_venta_precio_fijo(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Fijo 49",
        tipo="PRECIO_FIJO",
        valor=49,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    det = _linea(db_session, refs.id_malteada, 1, promo.id_promocion)
    resp = _venta(db_session, refs, [det])
    assert resp.total == 49.0


def test_venta_dos_x_uno(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="2x1",
        tipo="DOS_X_UNO",
        valor=0,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    det = _linea(db_session, refs.id_malteada, 2, promo.id_promocion)
    resp = _venta(db_session, refs, [det])
    assert resp.total == 65.0


def test_venta_cantidad_precio_ticket(db_session, refs):
    crear_promo(
        db_session,
        nombre="2x90",
        tipo="CANTIDAD_PRECIO",
        valor=90,
        cantidad_requerida=2,
        id_categoria=refs.id_cat_bebidas,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    det = _linea(db_session, refs.id_malteada, 2)
    resp = _venta(db_session, refs, [det])
    assert resp.total == 90.0
    dv = db_session.query(DetalleVentaModel).filter_by(id_venta=resp.id_venta).one()
    assert dv.nombre_promocion == "2x90"
    assert dv.tipo_promocion == "CANTIDAD_PRECIO"
    assert float(dv.valor_promocion) == 90.0


def test_venta_cantidad_precio_varias_lineas(db_session, refs):
    crear_promo(
        db_session,
        nombre="2x90",
        tipo="CANTIDAD_PRECIO",
        valor=90,
        cantidad_requerida=2,
        id_categoria=refs.id_cat_bebidas,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    detalles = _lineas_desde_recalc(
        db_session,
        [
            (refs.id_malteada, 1, None, []),
            (refs.id_cafe, 1, None, []),
        ],
    )
    resp = _venta(db_session, refs, detalles)
    assert resp.total == 90.0


def test_venta_con_extras(db_session, refs):
    extras = [_extra_linea(db_session, refs)]
    det = _linea(db_session, refs.id_malteada, 1, extras=extras)
    resp = _venta(db_session, refs, [det])
    assert resp.total == 65.0 + float(precio_desde_modelo(db_session.get(ExtraVentaModel, refs.id_extra_leche)))
    dv = db_session.query(DetalleVentaModel).filter_by(id_venta=resp.id_venta).one()
    assert dv.extras_json is not None
    parsed = json.loads(dv.extras_json)
    assert parsed[0]["nombre"] == "Extra Leche"


def test_inventario_descuenta_una_vez(db_session, refs):
    stock_antes = float(
        db_session.get(InsumoModel, refs.id_insumo_leche).stock_actual
    )
    det = _linea(db_session, refs.id_malteada, 2)
    resp = _venta(db_session, refs, [det])
    stock_despues = float(
        db_session.get(InsumoModel, refs.id_insumo_leche).stock_actual
    )
    movs = (
        db_session.query(MovimientoInventarioModel)
        .filter(MovimientoInventarioModel.referencia == f"VENTA {resp.id_venta}")
        .all()
    )
    assert len(movs) == 1
    assert stock_antes - stock_despues == pytest.approx(0.4, abs=0.001)


def test_inventario_extra(db_session, refs):
    extras = [_extra_linea(db_session, refs)]
    stock_antes = float(
        db_session.get(InsumoModel, refs.id_insumo_leche).stock_actual
    )
    det = _linea(db_session, refs.id_malteada, 1, extras=extras)
    resp = _venta(db_session, refs, [det])
    movs = (
        db_session.query(MovimientoInventarioModel)
        .filter(MovimientoInventarioModel.referencia == f"VENTA {resp.id_venta}")
        .all()
    )
    assert len(movs) == 2
    stock_despues = float(
        db_session.get(InsumoModel, refs.id_insumo_leche).stock_actual
    )
    assert stock_antes - stock_despues == pytest.approx(0.3, abs=0.001)


def test_fidelidad_sobre_total_con_descuento(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="50%",
        tipo="PORCENTAJE",
        valor=50,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    det = _linea(db_session, refs.id_malteada, 1, promo.id_promocion)
    resp = _venta(db_session, refs, [det], id_cliente=refs.id_cliente)
    assert resp.total == 32.5
    assert resp.puntos_generados == 3
    from app.models.models import FidelidadMovimientoModel

    movs = (
        db_session.query(FidelidadMovimientoModel)
        .filter_by(id_cliente=refs.id_cliente)
        .all()
    )
    assert len(movs) == 1
    assert movs[0].puntos == 3


def test_total_igual_suma_subtotales(db_session, refs):
    detalles = [
        _linea(db_session, refs.id_malteada, 2),
        _linea(db_session, refs.id_cafe, 1),
    ]
    resp = _venta(db_session, refs, detalles)
    dets = db_session.query(DetalleVentaModel).filter_by(id_venta=resp.id_venta).all()
    suma = sum(float(d.subtotal) for d in dets)
    assert suma == resp.total


def test_precio_invalido_rechazado(db_session, refs):
    det = DetalleVentaItem(
        id_producto=refs.id_malteada,
        cantidad=1,
        precio_unitario=1.0,
        extras=[],
    )
    with pytest.raises(DatosInvalidosException):
        _venta(db_session, refs, [det])


def test_precio_cero_rechazado(db_session, refs):
    det = DetalleVentaItem(
        id_producto=refs.id_malteada,
        cantidad=1,
        precio_unitario=0,
        extras=[],
    )
    with pytest.raises(DatosInvalidosException):
        _venta(db_session, refs, [det])


def test_para_llevar_mesa_99(db_session, refs):
    crear_promo(
        db_session,
        nombre="20%",
        tipo="PORCENTAJE",
        valor=20,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    recalc = recalcular_lineas_ticket(
        db_session,
        [{"id_producto": refs.id_malteada, "cantidad": 1, "precio_extras": 0, "extras": []}],
    )
    det = DetalleVentaItem(
        id_producto=refs.id_malteada,
        cantidad=1,
        precio_unitario=recalc["lineas"][0]["precio_unitario"],
        extras=[],
    )
    resp = _venta(
        db_session,
        refs,
        [det],
        numero_mesa=MESA_PARA_LLEVAR,
        para_llevar=True,
    )
    venta = db_session.get(VentaModel, resp.id_venta)
    assert venta.para_llevar is True
    assert venta.numero_mesa == MESA_PARA_LLEVAR
    assert resp.total == 52.0


def test_flujo_mesa_cobro(db_session, refs):
    crear_promo(
        db_session,
        nombre="20%",
        tipo="PORCENTAJE",
        valor=20,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = obtener_pedido_abierto_mesa(db_session, 3, refs.id_usuario)
    recalc = recalcular_lineas_ticket(
        db_session,
        [{"id_producto": refs.id_malteada, "cantidad": 1, "precio_extras": 0, "extras": []}],
    )
    calc = recalc["lineas"][0]
    agregar_linea_pedido(
        db_session,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_malteada,
            cantidad=1,
            precio_unitario=calc["precio_unitario"],
            id_promocion=calc.get("id_promocion"),
            extras=[],
            enviar_comanda=False,
        ),
    )
    confirmar_comanda_pedido(db_session, pedido)
    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "TARJETA")
    db_session.refresh(pedido)
    assert pedido.estado == "COBRADO"
    assert pedido.id_venta == resp.id_venta
    assert resp.total == 52.0
    assert resp.forma_pago == "TARJETA"
    pedido2 = (
        db_session.query(PedidoModel)
        .filter(PedidoModel.numero_mesa == 3, PedidoModel.estado == "ABIERTO")
        .first()
    )
    assert pedido2 is None or pedido2.id_pedido != pedido.id_pedido


def test_doble_cobro_rechazado(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 7, refs.id_usuario)
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
        ),
    )
    cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    with pytest.raises(DatosInvalidosException):
        cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")


def test_snapshots_inmutables_tras_cambio_promo(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Promo Snap",
        tipo="PORCENTAJE",
        valor=10,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    det = _linea(db_session, refs.id_malteada, 1, promo.id_promocion)
    resp = _venta(db_session, refs, [det])
    dv = db_session.query(DetalleVentaModel).filter_by(id_venta=resp.id_venta).one()
    assert dv.nombre_promocion == "Promo Snap"
    assert float(dv.precio_original) == 65.0
    assert float(dv.costo_unitario_snapshot) == 13.0
    assert dv.tipo_promocion == "PORCENTAJE"
