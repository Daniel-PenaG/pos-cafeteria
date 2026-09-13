"""Medición de endpoints de pedido: tiempo, SQL y cabeceras PERF_LOG."""
from __future__ import annotations

from app.schemas.pedido import PedidoLineaCreate
from app.services.pedido_service import (
    agregar_combo_pedido,
    agregar_linea_pedido_con_respuesta,
    buscar_pedido_abierto_mesa,
    listar_pedidos_activos_resumen,
    obtener_pedido_abierto_mesa,
    pedido_respuesta_lectura,
)
from app.services.producto_contexto_service import obtener_contexto_producto
from app.utils.sql_counter import get_sql_count, reset_sql_count
from tests.promo_seed import crear_promo, promo_vigente_siempre
from tests.test_promociones_integracion import _extra_linea, _linea


def _medir(fn):
    reset_sql_count()
    result = fn()
    return result, get_sql_count()


def test_medir_operaciones_pedido(db_session, refs):
    ctx, q_ctx = _medir(lambda: obtener_contexto_producto(db_session, refs.id_malteada))
    assert ctx["producto"]["id_producto"] == refs.id_malteada
    assert q_ctx > 0

    det = _linea(db_session, refs.id_cafe, 1)
    data = PedidoLineaCreate(
        id_producto=refs.id_cafe,
        cantidad=1,
        precio_unitario=det.precio_unitario,
        extras=[],
    )
    resp, q_simple = _medir(
        lambda: agregar_linea_pedido_con_respuesta(
            db_session,
            obtener_pedido_abierto_mesa(db_session, 2, refs.id_usuario),
            data,
        )[0]
    )
    assert resp["id_pedido"]
    assert q_simple > 0

    extra = _extra_linea(db_session, refs)
    det_e = _linea(db_session, refs.id_malteada, 1, extras=[extra])
    data_e = PedidoLineaCreate(
        id_producto=refs.id_malteada,
        cantidad=1,
        precio_unitario=det_e.precio_unitario,
        extras=[extra.model_dump() if hasattr(extra, "model_dump") else extra],
    )
    pedido = buscar_pedido_abierto_mesa(db_session, 2)
    _, q_extra = _medir(
        lambda: agregar_linea_pedido_con_respuesta(db_session, pedido, data_e)[0]
    )
    assert q_extra > 0

    promo = crear_promo(
        db_session,
        nombre="Combo perf",
        tipo="COMBO",
        valor=80,
        productos_combo=[refs.id_combo_a, refs.id_combo_b],
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = buscar_pedido_abierto_mesa(db_session, 2)
    _, q_combo = _medir(lambda: agregar_combo_pedido(db_session, pedido, promo.id_promocion, 1))
    assert q_combo > 0

    pedido = buscar_pedido_abierto_mesa(db_session, 2)
    _, q_get = _medir(lambda: pedido_respuesta_lectura(db_session, pedido))
    _, q_activos = _medir(lambda: listar_pedidos_activos_resumen(db_session))
    assert q_get > 0
    assert q_activos > 0

    print(
        "PERF_ESTABILIDAD "
        f"contexto_sql={q_ctx} simple_sql={q_simple} extras_sql={q_extra} "
        f"combo_sql={q_combo} get_pedido_sql={q_get} activos_sql={q_activos}"
    )


def test_headers_perf_contexto(client, auth_headers):
    res = client.get("/ventas/productos/1/contexto", headers=auth_headers)
    assert res.status_code == 200
    assert "X-Process-Time-Ms" in res.headers
    assert "X-SQL-Query-Count" in res.headers


def test_medir_http_pedido(client, auth_headers):
    """Registra tiempo y SQL de los endpoints pedidos (seed_perf)."""
    uid = 1
    ctx = client.get("/ventas/productos/1/contexto", headers=auth_headers)
    assert ctx.status_code == 200
    precio = ctx.json()["calculo_inicial"]["precio_unitario"]

    def _row(res, label):
        print(
            f"HTTP_PERF {label} status={res.status_code} "
            f"ms={res.headers.get('X-Process-Time-Ms')} "
            f"sql={res.headers.get('X-SQL-Query-Count')}"
        )
        return res

    _row(ctx, "GET contexto")
    vacio = _row(
        client.get(f"/pedidos/mesa/2?id_usuario={uid}", headers=auth_headers),
        "GET mesa vacía",
    )
    assert vacio.status_code == 200
    assert vacio.json().get("sin_pedido") is True or vacio.json().get("id_pedido") in (None, 0)

    add = _row(
        client.post(
            f"/pedidos/mesa/2/lineas?id_usuario={uid}",
            headers=auth_headers,
            json={
                "id_producto": 1,
                "cantidad": 1,
                "precio_unitario": precio,
                "extras": [],
                "operation_id": "11111111-1111-4111-8111-111111111111",
            },
        ),
        "POST linea simple",
    )
    assert add.status_code == 200
    id_detalle = add.json()["lineas"][0]["id_detalle_pedido"]

    _row(
        client.post(
            f"/pedidos/mesa/2/lineas?id_usuario={uid}",
            headers=auth_headers,
            json={
                "id_producto": 1,
                "cantidad": 1,
                "precio_unitario": precio,
                "extras": [],
                "operation_id": "11111111-1111-4111-8111-111111111111",
            },
        ),
        "POST linea retry misma clave",
    )
    _row(
        client.patch(
            f"/pedidos/lineas/{id_detalle}",
            headers=auth_headers,
            json={"cantidad": 2},
        ),
        "PATCH cantidad",
    )
    _row(client.get(f"/pedidos/mesa/2?id_usuario={uid}", headers=auth_headers), "GET pedido")
    _row(client.get("/pedidos/activos", headers=auth_headers), "GET activos")
    _row(client.delete(f"/pedidos/lineas/{id_detalle}", headers=auth_headers), "DELETE detalle")
