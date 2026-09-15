"""Cancelación de líneas, duplicados e idempotencia (Waffle / producto simple)."""
from __future__ import annotations

import json
import threading
import uuid

from sqlalchemy.orm import sessionmaker

from app.constants.acciones import CANCELAR_PRODUCTO_EN_COMANDA
from app.constants.cancelacion import MSG_COBRADO, MSG_ENVIADA, MSG_SIN_PERMISO, MSG_STALE
from app.models.models import (
    DetallePedidoModel,
    UsuarioModel,
)
from app.services.cancelacion_service import cancelar_linea_enviada
from app.services.pedido_service import (
    agregar_linea_pedido_con_respuesta,
    obtener_pedido_abierto_mesa,
)
from tests.promo_seed import seed_promo_catalog
from tests.test_estabilidad_idempotencia import _data, _sqlite_file_engine
from tests.test_seguridad_fase2a import (
    _agregar_linea,
    _crear_usuario,
    _headers,
    _login,
    _precio_producto,
)


MESA_DUP = 11
MESA_TWO = 12
MESA_DEL = 13
MESA_PATCH = 14
MESA_SEND = 15
MESA_ONE = 16
MESA_ALL = 17
MESA_LL = 99
MESA_PERM = 18
MESA_MOD = 19
MESA_CAJERO_OK = 20
MESA_STALE = 21
MESA_COBRO = 22
MESA_JWT = 23
MESA_ROLL = 24


def _ensure_mesa(client, headers, numero):
    res = client.post("/pedidos/mesas", headers=headers, json={"numero": numero})
    if res.status_code not in (200, 422):
        raise AssertionError(res.text)


def _linea_id(body):
    activas = [l for l in body["lineas"] if l.get("estado_linea") != "CANCELADA" and l["cantidad"] > 0]
    return activas[0]["id_detalle_pedido"]


def test_misma_clave_una_unidad(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_DUP)
    key = str(uuid.uuid4())
    r1 = client.post(
        f"/pedidos/mesa/{MESA_DUP}/lineas",
        headers=auth_headers,
        json={
            "id_producto": 1,
            "cantidad": 1,
            "precio_unitario": precio,
            "extras": [],
            "operation_id": key,
        },
    )
    r2 = client.post(
        f"/pedidos/mesa/{MESA_DUP}/lineas",
        headers=auth_headers,
        json={
            "id_producto": 1,
            "cantidad": 1,
            "precio_unitario": precio,
            "extras": [],
            "operation_id": key,
        },
    )
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    lineas = [l for l in r2.json()["lineas"] if l["cantidad"] > 0]
    assert len(lineas) == 1
    assert lineas[0]["cantidad"] == 1


def test_dos_agregados_intencionales_dos_unidades(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    mesa = MESA_TWO
    _ensure_mesa(client, auth_headers, mesa)
    r1 = client.post(
        f"/pedidos/mesa/{mesa}/lineas",
        headers=auth_headers,
        json={
            "id_producto": 1,
            "cantidad": 1,
            "precio_unitario": precio,
            "extras": [],
            "operation_id": str(uuid.uuid4()),
        },
    )
    r2 = client.post(
        f"/pedidos/mesa/{mesa}/lineas",
        headers=auth_headers,
        json={
            "id_producto": 1,
            "cantidad": 1,
            "precio_unitario": precio,
            "extras": [],
            "operation_id": str(uuid.uuid4()),
        },
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    lineas = [l for l in r2.json()["lineas"] if l["cantidad"] > 0]
    assert len(lineas) == 1
    assert lineas[0]["cantidad"] == 2


def test_eliminar_linea_no_enviada_con_operation_id(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_DEL)
    add = client.post(
        f"/pedidos/mesa/{MESA_DEL}/lineas",
        headers=auth_headers,
        json={
            "id_producto": 1,
            "cantidad": 1,
            "precio_unitario": precio,
            "extras": [],
            "operation_id": str(uuid.uuid4()),
        },
    )
    assert add.status_code == 200, add.text
    lid = _linea_id(add.json())
    deleted = client.delete(f"/pedidos/lineas/{lid}", headers=auth_headers)
    assert deleted.status_code == 200, deleted.text
    mesa = client.get(f"/pedidos/mesa/{MESA_DEL}", headers=auth_headers)
    assert mesa.status_code == 200
    activas = [l for l in mesa.json()["lineas"] if l["cantidad"] > 0]
    assert activas == []


def test_disminuir_cantidad_antes_de_comanda(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_PATCH)
    add = client.post(
        f"/pedidos/mesa/{MESA_PATCH}/lineas",
        headers=auth_headers,
        json={"id_producto": 1, "cantidad": 2, "precio_unitario": precio, "extras": []},
    )
    lid = _linea_id(add.json())
    patch = client.patch(
        f"/pedidos/lineas/{lid}",
        headers=auth_headers,
        json={"cantidad": 1, "cantidad_actual": 2},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["cantidad"] == 1


def test_linea_enviada_no_se_borra_silenciosamente(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_SEND)
    add = _agregar_linea(client, auth_headers, MESA_SEND, precio)
    pedido_id = add.json()["id_pedido"]
    lid = _linea_id(add.json())
    conf = client.post(f"/pedidos/{pedido_id}/confirmar-comanda", headers=auth_headers)
    assert conf.status_code == 200, conf.text
    deleted = client.delete(f"/pedidos/lineas/{lid}", headers=auth_headers)
    assert deleted.status_code == 422
    assert deleted.json()["detail"] == MSG_ENVIADA
    mesa = client.get(f"/pedidos/mesa/{MESA_SEND}", headers=auth_headers).json()
    assert any(l["id_detalle_pedido"] == lid and l["cantidad"] == 1 for l in mesa["lineas"])


def test_cancelar_una_de_dos_unidades_enviadas(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_ONE)
    add = client.post(
        f"/pedidos/mesa/{MESA_ONE}/lineas",
        headers=auth_headers,
        json={"id_producto": 1, "cantidad": 2, "precio_unitario": precio, "extras": []},
    )
    pedido_id = add.json()["id_pedido"]
    lid = _linea_id(add.json())
    client.post(f"/pedidos/{pedido_id}/confirmar-comanda", headers=auth_headers)
    res = client.post(
        f"/pedidos/lineas/{lid}/cancelar",
        headers=auth_headers,
        json={"cantidad": 1, "motivo": "Producto duplicado", "cantidad_actual": 2},
    )
    assert res.status_code == 200, res.text
    linea = next(l for l in res.json()["lineas"] if l["id_detalle_pedido"] == lid)
    assert linea["cantidad"] == 1
    assert linea["estado_linea"] == "ACTIVA"
    pend = client.get("/comandera/pendientes", headers=auth_headers).json()
    avisos = [x for x in pend if x.get("tipo") == "CANCELACION" and x["id_detalle_pedido"] == lid]
    assert avisos
    assert "CANTIDAD CAMBIÓ DE 2 A 1" in avisos[0]["aviso_texto"]


def test_cancelar_toda_la_linea_enviada_deja_historial(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_ALL)
    add = _agregar_linea(client, auth_headers, MESA_ALL, precio)
    pedido_id = add.json()["id_pedido"]
    lid = _linea_id(add.json())
    client.post(f"/pedidos/{pedido_id}/confirmar-comanda", headers=auth_headers)
    res = client.post(
        f"/pedidos/lineas/{lid}/cancelar",
        headers=auth_headers,
        json={"cantidad": 1, "motivo": "Error de captura", "cantidad_actual": 1},
    )
    assert res.status_code == 200, res.text
    linea = next(l for l in res.json()["lineas"] if l["id_detalle_pedido"] == lid)
    assert linea["cantidad"] == 0
    assert linea["estado_linea"] == "CANCELADA"
    pend = client.get("/comandera/pendientes", headers=auth_headers).json()
    avisos = [x for x in pend if x.get("id_cancelacion") and x["id_detalle_pedido"] == lid]
    assert avisos and avisos[0]["aviso_texto"] == "CANCELADO"
    visto = client.post(
        f"/comandera/cancelaciones/{avisos[0]['id_cancelacion']}/visto",
        headers=auth_headers,
    )
    assert visto.status_code == 200
    pend2 = client.get("/comandera/pendientes", headers=auth_headers).json()
    assert not any(x.get("id_cancelacion") == avisos[0]["id_cancelacion"] for x in pend2)


def test_para_llevar_conserva_etiqueta(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    add = client.post(
        "/pedidos/mesa/99/lineas?para_llevar=true",
        headers=auth_headers,
        json={
            "id_producto": 1,
            "cantidad": 1,
            "precio_unitario": precio,
            "extras": [],
            "comentario": "cancel-para-llevar",
        },
    )
    assert add.status_code == 200, add.text
    pedido_id = add.json()["id_pedido"]
    lid = next(
        l["id_detalle_pedido"]
        for l in add.json()["lineas"]
        if l.get("comentario") == "cancel-para-llevar"
    )
    client.post(f"/pedidos/{pedido_id}/confirmar-comanda", headers=auth_headers)
    client.post(
        f"/pedidos/lineas/{lid}/cancelar",
        headers=auth_headers,
        json={"cantidad": 1, "motivo": "Cambio solicitado por cliente", "cantidad_actual": 1},
    )
    pend = client.get("/comandera/pendientes", headers=auth_headers).json()
    avisos = [x for x in pend if x.get("tipo") == "CANCELACION" and x["id_detalle_pedido"] == lid]
    assert avisos
    assert avisos[0]["para_llevar"] is True


def test_sin_permiso_accion_403(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_PERM)
    add = _agregar_linea(client, auth_headers, MESA_PERM, precio)
    pedido_id = add.json()["id_pedido"]
    lid = _linea_id(add.json())
    client.post(f"/pedidos/{pedido_id}/confirmar-comanda", headers=auth_headers)
    _crear_usuario(client, auth_headers, "cajero_nocancel")
    tok = _headers(_login(client, "cajero_nocancel").json()["access_token"])
    res = client.post(
        f"/pedidos/lineas/{lid}/cancelar",
        headers=tok,
        json={"cantidad": 1, "motivo": "Producto duplicado", "cantidad_actual": 1},
    )
    assert res.status_code == 403
    assert res.json()["detail"] == MSG_SIN_PERMISO


def test_sin_modulo_ventas_403(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_MOD)
    add = _agregar_linea(client, auth_headers, MESA_MOD, precio)
    pedido_id = add.json()["id_pedido"]
    lid = _linea_id(add.json())
    client.post(f"/pedidos/{pedido_id}/confirmar-comanda", headers=auth_headers)
    _crear_usuario(
        client,
        auth_headers,
        "solo_cocina_cancel",
        rol="COCINA",
        permisos_acciones=[CANCELAR_PRODUCTO_EN_COMANDA],
    )
    tok = _headers(_login(client, "solo_cocina_cancel").json()["access_token"])
    res = client.post(
        f"/pedidos/lineas/{lid}/cancelar",
        headers=tok,
        json={"cantidad": 1, "motivo": "Producto duplicado", "cantidad_actual": 1},
    )
    assert res.status_code == 403


def test_cajero_con_accion_puede_cancelar(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_CAJERO_OK)
    add = _agregar_linea(client, auth_headers, MESA_CAJERO_OK, precio)
    pedido_id = add.json()["id_pedido"]
    lid = _linea_id(add.json())
    client.post(f"/pedidos/{pedido_id}/confirmar-comanda", headers=auth_headers)
    _crear_usuario(
        client,
        auth_headers,
        "cajero_sicancel",
        permisos_acciones=[CANCELAR_PRODUCTO_EN_COMANDA],
    )
    tok = _headers(_login(client, "cajero_sicancel").json()["access_token"])
    res = client.post(
        f"/pedidos/lineas/{lid}/cancelar",
        headers=tok,
        json={"cantidad": 1, "motivo": "Producto duplicado", "cantidad_actual": 1},
    )
    assert res.status_code == 200, res.text


def test_cantidad_stale_409(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_STALE)
    add = client.post(
        f"/pedidos/mesa/{MESA_STALE}/lineas",
        headers=auth_headers,
        json={"id_producto": 1, "cantidad": 2, "precio_unitario": precio, "extras": []},
    )
    pedido_id = add.json()["id_pedido"]
    lid = _linea_id(add.json())
    client.post(f"/pedidos/{pedido_id}/confirmar-comanda", headers=auth_headers)
    res = client.post(
        f"/pedidos/lineas/{lid}/cancelar",
        headers=auth_headers,
        json={"cantidad": 1, "motivo": "Producto duplicado", "cantidad_actual": 1},
    )
    assert res.status_code == 409
    assert res.json()["detail"] == MSG_STALE


def test_pedido_cobrado_no_se_modifica(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_COBRO)
    add = _agregar_linea(client, auth_headers, MESA_COBRO, precio)
    pedido_id = add.json()["id_pedido"]
    lid = _linea_id(add.json())
    cobro = client.post(
        f"/pedidos/{pedido_id}/cobrar",
        headers=auth_headers,
        json={"forma_pago": "EFECTIVO", "origen": "VENTAS"},
    )
    assert cobro.status_code == 200, cobro.text
    deleted = client.delete(f"/pedidos/lineas/{lid}", headers=auth_headers)
    assert deleted.status_code == 422
    assert deleted.json()["detail"] == MSG_COBRADO
    cancel = client.post(
        f"/pedidos/lineas/{lid}/cancelar",
        headers=auth_headers,
        json={"cantidad": 1, "motivo": "Producto duplicado", "cantidad_actual": 1},
    )
    assert cancel.status_code == 422
    assert cancel.json()["detail"] == MSG_COBRADO


def test_error_no_cambia_cantidad(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_ROLL)
    add = client.post(
        f"/pedidos/mesa/{MESA_ROLL}/lineas",
        headers=auth_headers,
        json={"id_producto": 1, "cantidad": 2, "precio_unitario": precio, "extras": []},
    )
    pedido_id = add.json()["id_pedido"]
    lid = _linea_id(add.json())
    client.post(f"/pedidos/{pedido_id}/confirmar-comanda", headers=auth_headers)
    bad = client.post(
        f"/pedidos/lineas/{lid}/cancelar",
        headers=auth_headers,
        json={"cantidad": 9, "motivo": "Producto duplicado", "cantidad_actual": 2},
    )
    assert bad.status_code == 422
    mesa = client.get(f"/pedidos/mesa/{MESA_ROLL}", headers=auth_headers).json()
    linea = next(l for l in mesa["lineas"] if l["id_detalle_pedido"] == lid)
    assert linea["cantidad"] == 2
    assert linea["estado_linea"] == "ACTIVA"


def test_usuario_atribuido_por_jwt(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    _ensure_mesa(client, auth_headers, MESA_JWT)
    add = _agregar_linea(client, auth_headers, MESA_JWT, precio)
    pedido_id = add.json()["id_pedido"]
    lid = _linea_id(add.json())
    client.post(f"/pedidos/{pedido_id}/confirmar-comanda", headers=auth_headers)
    me = client.get("/auth/me", headers=auth_headers).json()
    res = client.post(
        f"/pedidos/lineas/{lid}/cancelar",
        headers=auth_headers,
        json={"cantidad": 1, "motivo": "Producto no disponible", "cantidad_actual": 1},
    )
    assert res.status_code == 200
    aud = client.get("/auditoria/?accion=CANCELACION", headers=auth_headers)
    assert aud.status_code == 200
    items = aud.json()["items"]
    assert any(
        i["accion"] == "CANCELACION" and i["id_usuario"] == me["id_usuario"] for i in items
    )


def test_dos_sesiones_no_generan_cantidad_negativa(tmp_path):
    from app.database import Base

    engine = _sqlite_file_engine(tmp_path / "cancel_conc.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    setup = Session()
    refs2 = seed_promo_catalog(setup)
    user = setup.query(UsuarioModel).filter_by(id_usuario=refs2.id_usuario).first()
    user.permisos_acciones_json = json.dumps([CANCELAR_PRODUCTO_EN_COMANDA])
    setup.flush()
    pedido = obtener_pedido_abierto_mesa(setup, 8, refs2.id_usuario)
    _, detalle = agregar_linea_pedido_con_respuesta(
        setup,
        pedido,
        _data(setup, refs2.id_cafe, cantidad=2, enviar_comanda=True),
    )
    id_detalle = detalle.id_detalle_pedido
    id_usuario = refs2.id_usuario
    setup.close()

    barrier = threading.Barrier(2)
    resultados = []

    def worker():
        db = Session()
        try:
            barrier.wait(timeout=5)
            current = db.query(UsuarioModel).filter_by(id_usuario=id_usuario).first()
            out = cancelar_linea_enviada(
                db,
                id_detalle=id_detalle,
                current=current,
                cantidad=1,
                motivo="Producto duplicado",
                cantidad_actual=2,
            )
            resultados.append(("ok", out))
        except Exception as exc:
            resultados.append(("err", exc))
        finally:
            db.close()

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    verify = Session()
    det = verify.query(DetallePedidoModel).filter_by(id_detalle_pedido=id_detalle).first()
    assert det is not None
    assert float(det.cantidad) >= 0
    oks = [r for r in resultados if r[0] == "ok"]
    errs = [r for r in resultados if r[0] == "err"]
    assert len(oks) + len(errs) == 2, resultados
    assert len(oks) >= 1, resultados
    verify.close()
    engine.dispose()
