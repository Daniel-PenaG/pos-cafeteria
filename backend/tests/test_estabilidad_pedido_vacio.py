"""GET no crea pedidos; primer producto es atómico."""
from __future__ import annotations

import pytest

from app.exceptions import DatosInvalidosException, RecursoNoEncontradoException
from app.models.models import PedidoModel, UsuarioModel
from app.routers.pedidos import agregar_linea, obtener_pedido_mesa
from app.schemas.pedido import ExtraLineaPedido, PedidoLineaCreate
from app.services.pedido_service import (
    buscar_pedido_abierto_mesa,
    obtener_pedido_abierto_mesa,
    pedido_vacio_mesa,
)
from tests.test_promociones_integracion import _linea


def _usuario(db_session, refs):
    return db_session.get(UsuarioModel, refs.id_usuario)


def test_buscar_mesa_sin_pedido_no_crea(db_session, refs):
    encontrado = buscar_pedido_abierto_mesa(db_session, 2)
    assert encontrado is None
    assert db_session.query(PedidoModel).filter_by(numero_mesa=2).count() == 0


def test_get_mesa_sin_pedido_respuesta_vacia(db_session, refs):
    resp = obtener_pedido_mesa(2, False, refs.id_usuario, db_session, _usuario(db_session, refs))
    assert resp["sin_pedido"] is True
    assert resp["id_pedido"] is None
    assert resp["lineas"] == []
    assert resp["total"] == 0
    assert db_session.query(PedidoModel).filter_by(numero_mesa=2).count() == 0


def test_producto_invalido_primer_item_no_crea(db_session, refs):
    data = PedidoLineaCreate(
        id_producto=999999,
        cantidad=1,
        precio_unitario=10,
        extras=[],
    )
    with pytest.raises(RecursoNoEncontradoException):
        agregar_linea(3, data, refs.id_usuario, False, db_session, _usuario(db_session, refs))
    assert db_session.query(PedidoModel).filter_by(numero_mesa=3).count() == 0


def test_extra_invalido_no_crea_pedido(db_session, refs):
    det = _linea(db_session, refs.id_malteada, 1)
    data = PedidoLineaCreate(
        id_producto=refs.id_malteada,
        cantidad=1,
        precio_unitario=det.precio_unitario,
        extras=[
            ExtraLineaPedido(
                id_extra=99999, nombre="Fantasma", precio=5
            )
        ],
    )
    with pytest.raises(DatosInvalidosException):
        agregar_linea(4, data, refs.id_usuario, False, db_session, _usuario(db_session, refs))
    assert db_session.query(PedidoModel).filter_by(numero_mesa=4).count() == 0


def test_primer_producto_valido_atomico(db_session, refs):
    det = _linea(db_session, refs.id_malteada, 1)
    data = PedidoLineaCreate(
        id_producto=refs.id_malteada,
        cantidad=1,
        precio_unitario=det.precio_unitario,
        extras=[],
    )
    resp = agregar_linea(5, data, refs.id_usuario, False, db_session, _usuario(db_session, refs))
    assert resp["id_pedido"]
    assert resp["sin_pedido"] is False
    assert len(resp["lineas"]) == 1
    pedidos = db_session.query(PedidoModel).filter_by(numero_mesa=5, estado="ABIERTO").all()
    assert len(pedidos) == 1
    assert len(pedidos[0].detalles) == 1


def test_precio_invalido_rollback_sin_pedido_vacio(db_session, refs):
    data = PedidoLineaCreate(
        id_producto=refs.id_malteada,
        cantidad=1,
        precio_unitario=0.01,
        extras=[],
    )
    with pytest.raises(DatosInvalidosException):
        agregar_linea(6, data, refs.id_usuario, False, db_session, _usuario(db_session, refs))
    db_session.expire_all()
    assert db_session.query(PedidoModel).filter_by(numero_mesa=6).count() == 0


def test_pedido_existente_sigue_funcionando(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 8, refs.id_usuario)
    det = _linea(db_session, refs.id_cafe, 1)
    data = PedidoLineaCreate(
        id_producto=refs.id_cafe,
        cantidad=1,
        precio_unitario=det.precio_unitario,
        extras=[],
    )
    resp = agregar_linea(8, data, refs.id_usuario, False, db_session, _usuario(db_session, refs))
    assert resp["id_pedido"] == pedido.id_pedido
    assert len(resp["lineas"]) == 1


def test_pedido_vacio_contrato():
    vacio = pedido_vacio_mesa(7, 1, False)
    assert vacio["estado"] == "SIN_PEDIDO"
    assert vacio["sin_pedido"] is True
    assert vacio["id_pedido"] is None
