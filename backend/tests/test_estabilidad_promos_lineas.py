"""Promociones con líneas repetidas y comentarios distintos."""
from __future__ import annotations

from app.services.pedido_service import (
    _lineas_desde_pedido,
    agregar_linea_pedido_con_respuesta,
    obtener_pedido_abierto_mesa,
    recalcular_promociones_pedido,
)
from app.services.promocion_ticket_service import recalcular_lineas_ticket
from app.schemas.pedido import PedidoLineaCreate
from tests.promo_seed import crear_promo, promo_vigente_siempre
from tests.test_promociones_integracion import _linea


def _agregar(db, pedido, id_producto, comentario=None):
    det = _linea(db, id_producto, 1)
    data = PedidoLineaCreate(
        id_producto=id_producto,
        cantidad=1,
        precio_unitario=det.precio_unitario,
        extras=[],
        comentario=comentario,
    )
    resp, _ = agregar_linea_pedido_con_respuesta(db, pedido, data)
    return resp


def test_dos_iguales_comentarios_distintos_no_mezclan(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 5, refs.id_usuario)
    _agregar(db_session, pedido, refs.id_malteada, "Sin azúcar")
    db_session.refresh(pedido)
    resp = _agregar(db_session, pedido, refs.id_malteada, "Con hielo")
    assert len(resp["lineas"]) == 2
    comentarios = {l["comentario"] for l in resp["lineas"]}
    assert comentarios == {"Sin azúcar", "Con hielo"}


def test_comentario_vacio_y_lleno_lineas_independientes(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 6, refs.id_usuario)
    _agregar(db_session, pedido, refs.id_malteada, None)
    db_session.refresh(pedido)
    resp = _agregar(db_session, pedido, refs.id_malteada, "Extra caliente")
    assert len(resp["lineas"]) == 2
    vacia = next(l for l in resp["lineas"] if not l["comentario"])
    con_nota = next(l for l in resp["lineas"] if l["comentario"] == "Extra caliente")
    assert vacia["id_detalle_pedido"] != con_nota["id_detalle_pedido"]


def test_promo_ticket_asigna_descuento_a_detalle_correcto(db_session, refs):
    crear_promo(
        db_session,
        nombre="2 malteadas 90",
        tipo="CANTIDAD_PRECIO",
        valor=90,
        cantidad_requerida=2,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = obtener_pedido_abierto_mesa(db_session, 7, refs.id_usuario)
    _agregar(db_session, pedido, refs.id_malteada, "A")
    db_session.refresh(pedido)
    resp = _agregar(db_session, pedido, refs.id_malteada, "B")
    assert abs(resp["total"] - 90) < 0.05
    por_comentario = {l["comentario"]: l for l in resp["lineas"]}
    assert "A" in por_comentario and "B" in por_comentario
    assert por_comentario["A"]["id_detalle_pedido"] != por_comentario["B"]["id_detalle_pedido"]


def test_promo_general_ticket(db_session, refs):
    from app.models.models import ProductoModel

    crear_promo(
        db_session,
        nombre="Ticket $5",
        tipo="DESCUENTO_FIJO",
        valor=5,
        cantidad_requerida=1,
        aplica_toda_tienda=True,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = obtener_pedido_abierto_mesa(db_session, 8, refs.id_usuario)
    cafe = db_session.get(ProductoModel, refs.id_cafe)
    data = PedidoLineaCreate(
        id_producto=refs.id_cafe,
        cantidad=1,
        precio_unitario=float(cafe.precio_venta),
        extras=[],
        comentario="Nota 1",
    )
    resp, _ = agregar_linea_pedido_con_respuesta(db_session, pedido, data)
    assert resp["total"] > 0
    assert resp["lineas"][0]["comentario"] == "Nota 1"


def test_recalcular_varias_veces_estable(db_session, refs):
    crear_promo(
        db_session,
        nombre="2x90 estable",
        tipo="CANTIDAD_PRECIO",
        valor=90,
        cantidad_requerida=2,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = obtener_pedido_abierto_mesa(db_session, 4, refs.id_usuario)
    _agregar(db_session, pedido, refs.id_malteada, "Uno")
    db_session.refresh(pedido)
    _agregar(db_session, pedido, refs.id_malteada, "Dos")
    db_session.refresh(pedido)
    r1 = recalcular_promociones_pedido(db_session, pedido)
    db_session.refresh(pedido)
    r2 = recalcular_promociones_pedido(db_session, pedido)
    assert r1["total"] == r2["total"]
    assert r1["descuento_promociones"] == r2["descuento_promociones"]
    lineas = _lineas_desde_pedido(db_session, pedido)
    t1 = recalcular_lineas_ticket(db_session, lineas)
    t2 = recalcular_lineas_ticket(db_session, lineas)
    assert t1["lineas"][0]["precio_unitario"] == t2["lineas"][0]["precio_unitario"]
    assert t1["lineas"][1]["precio_unitario"] == t2["lineas"][1]["precio_unitario"]
    comentarios = [d.comentario for d in pedido.detalles]
    assert comentarios.count("Uno") == 1
    assert comentarios.count("Dos") == 1


def test_index_ambiguo_no_asocia_primera_linea():
    """Dos dicts iguales no deben resolverse con list.index()."""
    trabajo = [
        {"id_producto": 1, "cantidad": 1, "precio_extras": 0},
        {"id_producto": 1, "cantidad": 1, "precio_extras": 0},
    ]
    indices = [i for i, _ in enumerate(trabajo)]
    assert indices == [0, 1]
    assert trabajo.index(trabajo[1]) == 0
