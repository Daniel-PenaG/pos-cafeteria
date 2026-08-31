"""Pruebas de transacción atómica en registrar_venta."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.exceptions import DatosInvalidosException
from app.models.models import (
    ClienteModel,
    DetalleVentaModel,
    FidelidadMovimientoModel,
    InsumoModel,
    MovimientoInventarioModel,
    PedidoModel,
    VentaModel,
)
from app.schemas.pedido import PedidoLineaCreate
from app.schemas.ventas import DetalleVentaItem, VentaCreate
from app.services.pedido_service import (
    agregar_linea_pedido,
    cobrar_pedido,
    obtener_pedido_abierto_mesa,
)
from app.services.promocion_ticket_service import recalcular_lineas_ticket
from app.services import venta_service
from app.services.venta_service import registrar_venta


def _venta_simple(db, refs, **kwargs):
    return VentaCreate(
        id_usuario=refs.id_usuario,
        numero_mesa=kwargs.get("numero_mesa", 1),
        forma_pago=kwargs.get("forma_pago", "EFECTIVO"),
        id_cliente=kwargs.get("id_cliente"),
        id_pedido=kwargs.get("id_pedido"),
        detalles=[
            DetalleVentaItem(
                id_producto=refs.id_malteada,
                cantidad=1,
                precio_unitario=65.0,
                extras=[],
            )
        ],
    )


def test_registrar_venta_un_solo_commit(db_session, refs):
    commits = []
    original_commit = db_session.commit

    def tracked_commit():
        commits.append(1)
        original_commit()

    db_session.commit = tracked_commit  # type: ignore[method-assign]
    registrar_venta(db_session, _venta_simple(db_session, refs))
    assert len(commits) == 1


def test_fallo_al_crear_detalle_no_persiste_venta(db_session, refs):
    original_add = db_session.add

    def failing_add(obj):
        if isinstance(obj, DetalleVentaModel):
            raise RuntimeError("fallo simulado detalle")
        original_add(obj)

    db_session.add = failing_add  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="fallo simulado detalle"):
        registrar_venta(db_session, _venta_simple(db_session, refs))

    assert db_session.query(VentaModel).count() == 0
    assert db_session.query(DetalleVentaModel).count() == 0


def test_fallo_inventario_no_persiste_venta_ni_movimiento(db_session, refs):
    with patch.object(venta_service, "_descontar_stock_receta", side_effect=RuntimeError("fallo inventario")):
        with pytest.raises(RuntimeError, match="fallo inventario"):
            registrar_venta(db_session, _venta_simple(db_session, refs))

    assert db_session.query(VentaModel).count() == 0
    assert db_session.query(MovimientoInventarioModel).count() == 0


def test_fallo_fidelidad_no_persiste_venta_ni_puntos(db_session, refs):
    with patch.object(venta_service, "acumular_puntos_venta", side_effect=RuntimeError("fallo fidelidad")):
        with pytest.raises(RuntimeError, match="fallo fidelidad"):
            registrar_venta(
                db_session,
                _venta_simple(db_session, refs, id_cliente=refs.id_cliente),
            )

    assert db_session.query(VentaModel).count() == 0
    assert db_session.query(FidelidadMovimientoModel).count() == 0
    cliente = db_session.get(ClienteModel, refs.id_cliente)
    assert int(cliente.puntos_saldo) == 0


def test_fallo_cerrar_pedido_no_persiste_venta_pedido_abierto(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 4, refs.id_usuario)
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
            extras=[],
        ),
    )
    db_session.refresh(pedido)

    with patch.object(venta_service, "_cerrar_pedido_tras_venta", side_effect=RuntimeError("fallo pedido")):
        with pytest.raises(RuntimeError, match="fallo pedido"):
            registrar_venta(
                db_session,
                _venta_simple(db_session, refs, id_pedido=pedido.id_pedido),
            )

    assert db_session.query(VentaModel).count() == 0
    db_session.refresh(pedido)
    assert pedido.estado == "ABIERTO"
    assert pedido.id_venta is None


def test_reintento_tras_fallo_no_duplica_venta(db_session, refs):
    intentos = {"n": 0}

    def fail_once(*args, **kwargs):
        intentos["n"] += 1
        if intentos["n"] == 1:
            raise RuntimeError("fallo temporal")
        return None

    with patch.object(venta_service, "_descontar_stock_receta", side_effect=fail_once):
        with pytest.raises(RuntimeError):
            registrar_venta(db_session, _venta_simple(db_session, refs))

    assert db_session.query(VentaModel).count() == 0

    resp = registrar_venta(db_session, _venta_simple(db_session, refs))
    assert db_session.query(VentaModel).count() == 1
    assert resp.total == 65.0


def test_cobro_correcto_persiste_venta_detalle_inventario_pedido(db_session, refs):
    stock_antes = float(db_session.get(InsumoModel, refs.id_insumo_leche).stock_actual)
    pedido = obtener_pedido_abierto_mesa(db_session, 6, refs.id_usuario)
    recalc = recalcular_lineas_ticket(
        db_session,
        [{"id_producto": refs.id_malteada, "cantidad": 2, "precio_extras": 0, "extras": []}],
    )
    calc = recalc["lineas"][0]
    agregar_linea_pedido(
        db_session,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_malteada,
            cantidad=2,
            precio_unitario=calc["precio_unitario"],
            extras=[],
        ),
    )
    db_session.refresh(pedido)

    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    db_session.refresh(pedido)

    assert resp.id_venta is not None
    assert pedido.estado == "COBRADO"
    assert pedido.id_venta == resp.id_venta
    assert db_session.query(DetalleVentaModel).filter_by(id_venta=resp.id_venta).count() == 1
    movs = db_session.query(MovimientoInventarioModel).filter_by(referencia=f"VENTA {resp.id_venta}").all()
    assert len(movs) == 1
    stock_despues = float(db_session.get(InsumoModel, refs.id_insumo_leche).stock_actual)
    assert stock_antes - stock_despues == pytest.approx(0.4, abs=0.001)


def test_doble_cobro_pedido_rechazado(db_session, refs):
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
        ),
    )
    cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    db_session.refresh(pedido)

    with pytest.raises(DatosInvalidosException):
        cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")

    assert db_session.query(VentaModel).count() == 1
