"""Pruebas comandera y pedidos para llevar."""
from __future__ import annotations

import pytest

from app.exceptions import DatosInvalidosException
from app.models.models import DetallePedidoModel, PedidoModel
from app.schemas.pedido import PedidoLineaCreate
from app.services.pedido_service import (
    agregar_linea_pedido,
    cobrar_pedido,
    confirmar_comanda_pedido,
    obtener_pedido_abierto_mesa,
)
from app.services.venta_service import MESA_PARA_LLEVAR
from tests.promo_seed import promo_vigente_siempre


def _pedido_para_llevar(db, refs):
    pedido = obtener_pedido_abierto_mesa(
        db, MESA_PARA_LLEVAR, refs.id_usuario, para_llevar=True
    )
    agregar_linea_pedido(
        db,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_malteada,
            cantidad=1,
            precio_unitario=65,
            enviar_comanda=False,
        ),
    )
    db.commit()
    db.refresh(pedido)
    return pedido


def test_confirmar_pedido_para_llevar(db_session, refs):
    pedido = _pedido_para_llevar(db_session, refs)
    n = confirmar_comanda_pedido(db_session, pedido)
    assert n == 1
    linea = db_session.query(DetallePedidoModel).filter_by(id_pedido=pedido.id_pedido).first()
    assert linea.en_comanda is True
    assert linea.fecha_envio_comanda is not None
    assert pedido.para_llevar is True


def test_para_llevar_en_comandera_schema(db_session, refs):
    from app.routers.comandera import listar_pendientes

    pedido = _pedido_para_llevar(db_session, refs)
    confirmar_comanda_pedido(db_session, pedido)
    pendientes = listar_pendientes(db_session)
    assert any(p["para_llevar"] and p["id_pedido"] == pedido.id_pedido for p in pendientes)


def test_dos_pedidos_para_llevar_distintos(db_session, refs):
    p1 = _pedido_para_llevar(db_session, refs)
    confirmar_comanda_pedido(db_session, p1)
    cobrar_pedido(db_session, p1, refs.id_usuario, "EFECTIVO")
    db_session.refresh(p1)
    p2 = _pedido_para_llevar(db_session, refs)
    confirmar_comanda_pedido(db_session, p2)
    assert p1.id_pedido != p2.id_pedido


def test_no_duplica_lineas_ya_enviadas(db_session, refs):
    pedido = _pedido_para_llevar(db_session, refs)
    confirmar_comanda_pedido(db_session, pedido)
    with pytest.raises(DatosInvalidosException):
        confirmar_comanda_pedido(db_session, pedido)


def test_enviar_lineas_adicionales(db_session, refs):
    from app.models.models import ProductoModel
    from app.services.promocion_service import calcular_linea

    pedido = _pedido_para_llevar(db_session, refs)
    confirmar_comanda_pedido(db_session, pedido)
    producto = db_session.get(ProductoModel, refs.id_cafe)
    precio = calcular_linea(db_session, producto, 1, 0, None)["precio_unitario"]
    agregar_linea_pedido(
        db_session,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_cafe,
            cantidad=1,
            precio_unitario=precio,
            enviar_comanda=False,
        ),
    )
    db_session.commit()
    n = confirmar_comanda_pedido(db_session, pedido)
    assert n == 1
    lineas = db_session.query(DetallePedidoModel).filter_by(id_pedido=pedido.id_pedido).all()
    assert all(l.en_comanda for l in lineas)


def test_marcar_unidad_lista(db_session, refs):
    from app.routers.comandera import marcar_listo
    from app.schemas.pedido import ComandaMarcarListo

    pedido = _pedido_para_llevar(db_session, refs)
    confirmar_comanda_pedido(db_session, pedido)
    det = db_session.query(DetallePedidoModel).filter_by(id_pedido=pedido.id_pedido).first()
    res = marcar_listo(det.id_detalle_pedido, ComandaMarcarListo(cantidad=1), db_session)
    assert res["cantidad_lista"] == 1


def test_cobrar_para_llevar_tras_enviar(db_session, refs):
    pedido = _pedido_para_llevar(db_session, refs)
    confirmar_comanda_pedido(db_session, pedido)
    venta = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    assert venta.para_llevar is True
    db_session.refresh(pedido)
    assert pedido.estado == "COBRADO"


def test_mesa_normal_en_comandera(db_session, refs):
    from app.routers.comandera import listar_pendientes
    from app.services.pedido_service import agregar_linea_pedido, confirmar_comanda_pedido, obtener_pedido_abierto_mesa

    pedido = obtener_pedido_abierto_mesa(db_session, 4, refs.id_usuario, para_llevar=False)
    agregar_linea_pedido(
        db_session,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_malteada,
            cantidad=1,
            precio_unitario=65,
            enviar_comanda=False,
        ),
    )
    db_session.commit()
    confirmar_comanda_pedido(db_session, pedido)
    pendientes = listar_pendientes(db_session)
    match = [p for p in pendientes if p["id_pedido"] == pedido.id_pedido]
    assert len(match) == 1
    assert match[0]["para_llevar"] is False
    assert match[0]["numero_mesa"] == 4


def test_doble_cobro_para_llevar_rechazado(db_session, refs):
    pedido = _pedido_para_llevar(db_session, refs)
    confirmar_comanda_pedido(db_session, pedido)
    cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    db_session.refresh(pedido)
    with pytest.raises(DatosInvalidosException):
        cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
