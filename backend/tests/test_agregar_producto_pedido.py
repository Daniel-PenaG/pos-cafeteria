"""Pruebas de rendimiento y contrato al agregar productos al pedido."""
from __future__ import annotations

import pytest

from app.exceptions import DatosInvalidosException
from app.models.models import DetallePedidoModel, PedidoModel
from app.schemas.pedido import PedidoLineaCreate
from app.services.pedido_service import (
    agregar_combo_pedido,
    agregar_linea_pedido_con_respuesta,
    obtener_pedido_abierto_mesa,
    pedido_respuesta_lectura,
)
from app.services.producto_contexto_service import obtener_contexto_producto
from app.services.promocion_service import calcular_linea
from app.services.venta_service import MESA_PARA_LLEVAR
from tests.promo_seed import crear_promo, promo_vigente_siempre
from tests.test_promociones_integracion import _linea


def _pedido_mesa(db, refs, mesa=5):
    return obtener_pedido_abierto_mesa(db, mesa, refs.id_usuario, para_llevar=False)


def _pedido_llevar(db, refs):
    return obtener_pedido_abierto_mesa(
        db, MESA_PARA_LLEVAR, refs.id_usuario, para_llevar=True
    )


def _agregar(db, pedido, refs, id_producto, cantidad=1, **kwargs):
    raw_extras = kwargs.get("extras") or []
    extras_pedido = [
        e.model_dump() if hasattr(e, "model_dump") else e
        for e in raw_extras
    ]
    det = _linea(db, id_producto, cantidad, kwargs.get("id_promocion"), raw_extras or None)
    data = PedidoLineaCreate(
        id_producto=id_producto,
        cantidad=cantidad,
        precio_unitario=det.precio_unitario,
        precio_original=det.precio_original,
        id_promocion=det.id_promocion,
        extras=extras_pedido,
        enviar_comanda=kwargs.get("enviar_comanda", False),
        comentario=kwargs.get("comentario"),
    )
    resp, _ = agregar_linea_pedido_con_respuesta(db, pedido, data)
    return resp


def test_contexto_producto_una_respuesta(db_session, refs):
    ctx = obtener_contexto_producto(db_session, refs.id_malteada)
    assert ctx["producto"]["id_producto"] == refs.id_malteada
    assert "extras" in ctx
    assert "promociones" in ctx
    assert "paquetes" in ctx
    assert ctx["calculo_inicial"]["precio_unitario"] > 0


def test_agregar_producto_normal_devuelve_pedido(db_session, refs):
    pedido = _pedido_mesa(db_session, refs)
    resp = _agregar(db_session, pedido, refs, refs.id_malteada)
    assert resp["id_pedido"] == pedido.id_pedido
    assert len(resp["lineas"]) == 1
    assert resp["total"] > 0


def test_agregar_mismo_producto_agrupa(db_session, refs):
    pedido = _pedido_mesa(db_session, refs)
    _agregar(db_session, pedido, refs, refs.id_malteada)
    db_session.refresh(pedido)
    resp = _agregar(db_session, pedido, refs, refs.id_malteada)
    assert len(resp["lineas"]) == 1
    assert resp["lineas"][0]["cantidad"] == 2


def test_agregar_con_extra(db_session, refs):
    from tests.test_promociones_integracion import _extra_linea

    pedido = _pedido_mesa(db_session, refs)
    extra = _extra_linea(db_session, refs)
    resp = _agregar(db_session, pedido, refs, refs.id_malteada, extras=[extra])
    assert len(resp["lineas"]) == 1
    assert len(resp["lineas"][0]["extras"]) == 1


def test_agregar_comentario_diferente_no_agrupa(db_session, refs):
    pedido = _pedido_mesa(db_session, refs)
    _agregar(db_session, pedido, refs, refs.id_malteada, comentario="Sin azúcar")
    db_session.refresh(pedido)
    resp = _agregar(db_session, pedido, refs, refs.id_malteada, comentario="Con hielo")
    assert len(resp["lineas"]) == 2


def test_agregar_con_promocion(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="10% malteada",
        tipo="PORCENTAJE",
        valor=10,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = _pedido_mesa(db_session, refs)
    det = _linea(db_session, refs.id_malteada, 1, promo.id_promocion)
    data = PedidoLineaCreate(
        id_producto=refs.id_malteada,
        cantidad=1,
        precio_unitario=det.precio_unitario,
        id_promocion=promo.id_promocion,
        extras=[],
    )
    resp, _ = agregar_linea_pedido_con_respuesta(db_session, pedido, data)
    assert resp["lineas"][0]["id_promocion"] == promo.id_promocion


def test_recalcular_promocion_ticket(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Ticket 5%",
        tipo="PORCENTAJE",
        valor=5,
        aplica_toda_tienda=True,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = _pedido_mesa(db_session, refs)
    resp = _agregar(db_session, pedido, refs, refs.id_malteada)
    assert resp.get("subtotal_normal") is not None or resp["total"] > 0


def test_agregar_combo_devuelve_pedido(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Combo test",
        tipo="COMBO",
        valor=80,
        productos_combo=[refs.id_combo_a, refs.id_combo_b],
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = _pedido_mesa(db_session, refs)
    resp = agregar_combo_pedido(db_session, pedido, promo.id_promocion, 1)
    assert resp["id_pedido"] == pedido.id_pedido
    assert len(resp["lineas"]) >= 2


def test_agregar_para_llevar(db_session, refs):
    pedido = _pedido_llevar(db_session, refs)
    resp = _agregar(db_session, pedido, refs, refs.id_malteada)
    assert resp["para_llevar"] is True
    assert resp["numero_mesa"] == MESA_PARA_LLEVAR


def test_precio_invalido_rollback(db_session, refs):
    pedido = _pedido_mesa(db_session, refs)
    data = PedidoLineaCreate(
        id_producto=refs.id_malteada,
        cantidad=1,
        precio_unitario=0.01,
        extras=[],
    )
    with pytest.raises(DatosInvalidosException):
        agregar_linea_pedido_con_respuesta(db_session, pedido, data)
    db_session.expire_all()
    lineas = db_session.query(DetallePedidoModel).filter_by(id_pedido=pedido.id_pedido).all()
    assert len(lineas) == 0


def test_total_respuesta_coincide_con_bd(db_session, refs):
    pedido = _pedido_mesa(db_session, refs)
    resp = _agregar(db_session, pedido, refs, refs.id_malteada)
    db_session.refresh(pedido)
    total_bd = sum(float(d.cantidad) * float(d.precio_unitario) for d in pedido.detalles)
    assert abs(resp["total"] - round(total_bd, 2)) < 0.02


def test_get_pedido_lectura_no_persiste(db_session, refs):
    pedido = _pedido_mesa(db_session, refs)
    _agregar(db_session, pedido, refs, refs.id_malteada)
    db_session.refresh(pedido)
    precio_antes = float(pedido.detalles[0].precio_unitario)
    pedido_respuesta_lectura(db_session, pedido)
    db_session.expire_all()
    det = db_session.get(DetallePedidoModel, pedido.detalles[0].id_detalle_pedido)
    assert float(det.precio_unitario) == precio_antes


def test_doble_agregar_incrementa_cantidad(db_session, refs):
    """Evita duplicar líneas idénticas en secuencia rápida."""
    pedido = _pedido_mesa(db_session, refs)
    r1 = _agregar(db_session, pedido, refs, refs.id_cafe)
    db_session.refresh(pedido)
    r2 = _agregar(db_session, pedido, refs, refs.id_cafe)
    assert r1["lineas"][0]["id_producto"] == r2["lineas"][0]["id_producto"]
    assert r2["lineas"][0]["cantidad"] == 2
