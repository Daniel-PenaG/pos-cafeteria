"""Presupuesto SQL por operación (regresión; SQLite promo_seed)."""
from __future__ import annotations

import uuid

from app.schemas.pedido import PedidoLineaCreate
from app.services.pedido_service import (
    agregar_linea_pedido_con_respuesta,
    buscar_pedido_abierto_mesa,
    confirmar_comanda_pedido,
    obtener_pedido_abierto_mesa,
)
from app.services.producto_contexto_service import obtener_contexto_producto
from app.services.promocion_ticket_service import recalcular_lineas_ticket
from app.services.pedido_service import cobrar_pedido
from app.utils.sql_counter import get_sql_count, reset_sql_count
from tests.promo_seed import crear_promo, promo_vigente_siempre
from tests.test_promociones_integracion import _extra_linea, _linea


def _medir(fn):
    reset_sql_count()
    out = fn()
    return out, get_sql_count()


def test_presupuesto_contexto_producto(db_session, refs):
    _, sql = _medir(lambda: obtener_contexto_producto(db_session, refs.id_malteada))
    assert sql <= 12, f"contexto producto: {sql} consultas (presupuesto 12)"


def test_presupuesto_agregar_primera_linea(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 5, refs.id_usuario)
    det = _linea(db_session, refs.id_cafe, 1)
    data = PedidoLineaCreate(
        id_producto=refs.id_cafe,
        cantidad=1,
        precio_unitario=det.precio_unitario,
        extras=[],
    )
    _, sql = _medir(lambda: agregar_linea_pedido_con_respuesta(db_session, pedido, data)[0])
    assert sql <= 35, f"agregar 1ª línea: {sql} consultas (presupuesto 35)"


def test_presupuesto_agregar_decima_linea(db_session, refs):
    pedido = buscar_pedido_abierto_mesa(db_session, 6) or obtener_pedido_abierto_mesa(
        db_session, 6, refs.id_usuario
    )
    det = _linea(db_session, refs.id_cafe, 1)
    for _ in range(9):
        agregar_linea_pedido_con_respuesta(
            db_session,
            pedido,
            PedidoLineaCreate(
                id_producto=refs.id_cafe,
                cantidad=1,
                precio_unitario=det.precio_unitario,
                extras=[],
                operation_id=str(uuid.uuid4()),
            ),
        )
    reset_sql_count()
    _, sql = _medir(
        lambda: agregar_linea_pedido_con_respuesta(
            db_session,
            pedido,
            PedidoLineaCreate(
                id_producto=refs.id_cafe,
                cantidad=1,
                precio_unitario=det.precio_unitario,
                extras=[],
                operation_id=str(uuid.uuid4()),
            ),
        )[0]
    )
    assert sql <= 45, f"agregar 10ª línea: {sql} consultas (presupuesto 45)"


def test_presupuesto_confirmar_pedido(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 7, refs.id_usuario)
    det = _linea(db_session, refs.id_cafe, 1)
    agregar_linea_pedido_con_respuesta(
        db_session,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_cafe,
            cantidad=1,
            precio_unitario=det.precio_unitario,
            extras=[],
        ),
    )
    _, sql = _medir(lambda: confirmar_comanda_pedido(db_session, pedido))
    assert sql <= 25, f"confirmar: {sql} consultas (presupuesto 25)"


def test_presupuesto_recalc_10_lineas_promo_extras(db_session, refs):
    crear_promo(
        db_session,
        nombre="2x70",
        tipo="CANTIDAD_PRECIO",
        valor=70,
        id_producto=refs.id_cafe,
        cantidad_requerida=2,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    extra = _extra_linea(db_session, refs)
    lineas = []
    for _ in range(10):
        det = _linea(db_session, refs.id_malteada, 1, extras=[extra])
        lineas.append(
            {
                "id_producto": refs.id_malteada,
                "cantidad": 1,
                "precio_extras": float(extra.precio),
                "extras": [extra.model_dump()],
            }
        )
    lineas.append(
        {
            "id_producto": refs.id_cafe,
            "cantidad": 2,
            "precio_extras": 0,
            "extras": [],
        }
    )
    _, sql = _medir(lambda: recalcular_lineas_ticket(db_session, lineas))
    assert sql <= 18, f"recalc 10+ líneas promo/extras: {sql} consultas (presupuesto 18)"


def test_presupuesto_confirmar_10_lineas_http(client, auth_headers, refs):
    uid = refs.id_usuario
    mesa = 3
    client.get(f"/pedidos/mesa/{mesa}?id_usuario={uid}", headers=auth_headers)
    ctx = client.get(f"/ventas/productos/{refs.id_cafe}/contexto", headers=auth_headers)
    precio = ctx.json()["calculo_inicial"]["precio_unitario"]
    for _ in range(10):
        client.post(
            f"/pedidos/mesa/{mesa}/lineas?id_usuario={uid}",
            headers=auth_headers,
            json={
                "id_producto": refs.id_cafe,
                "cantidad": 1,
                "precio_unitario": precio,
                "extras": [],
                "operation_id": str(uuid.uuid4()),
            },
        ).raise_for_status()
    ped = client.get(f"/pedidos/mesa/{mesa}?id_usuario={uid}", headers=auth_headers).json()
    reset_sql_count()
    res = client.post(
        f"/pedidos/{ped['id_pedido']}/confirmar-comanda", headers=auth_headers
    )
    sql = get_sql_count()
    assert res.status_code == 200, res.text
    assert sql <= 80, f"confirmar 10 líneas HTTP: {sql} consultas (presupuesto 80)"


def test_presupuesto_cobrar_una_linea(db_session, refs):
    from app.services.pedido_service import agregar_linea_pedido

    pedido = obtener_pedido_abierto_mesa(db_session, 8, refs.id_usuario)
    det = _linea(db_session, refs.id_cafe, 1)
    agregar_linea_pedido(
        db_session,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_cafe,
            cantidad=1,
            precio_unitario=det.precio_unitario,
            extras=[],
        ),
    )
    confirmar_comanda_pedido(db_session, pedido)
    _, sql = _medir(
        lambda: cobrar_pedido(
            db_session, pedido, refs.id_usuario, "EFECTIVO", operation_id="presup-cobro-1"
        )
    )
    assert sql <= 85, f"cobrar 1 línea: {sql} consultas (presupuesto 85)"
