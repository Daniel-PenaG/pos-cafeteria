"""Fase 2A: identidad, módulos, cobro comandera, usuarios, login, auditoría."""
from __future__ import annotations

import json
from datetime import timedelta

from app.constants.acciones import COBRAR_DESDE_COMANDERA
from app.models.models import AuditoriaModel, LoginBloqueoModel, UsuarioModel
from app.utils.timezone_mx import now_utc_naive


def _login(client, usuario, password="clave1234"):
    res = client.post("/auth/login", json={"usuario_login": usuario, "password": password})
    return res


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _crear_usuario(client, auth_headers, login, rol="CAJERO", **extra):
    payload = {
        "nombre": login,
        "usuario_login": login,
        "password": "clave1234",
        "rol": rol,
        **extra,
    }
    res = client.post("/usuarios/", json=payload, headers=auth_headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_me_incluye_modulos_acciones_activo(client, auth_headers):
    res = client.get("/auth/me", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["activo"] is True
    assert "/ventas" in body["modulos"]
    assert COBRAR_DESDE_COMANDERA in body["permisos_acciones"]
    assert "hash_password" not in body


def test_id_usuario_manipulado_no_cambia_duenio(client, auth_headers):
    otro = _crear_usuario(client, auth_headers, "cajero_otro")
    ctx = client.get("/ventas/productos/1/contexto", headers=auth_headers)
    precio = ctx.json()["calculo_inicial"]["precio_unitario"]
    add = client.post(
        f"/pedidos/mesa/3/lineas?id_usuario={otro['id_usuario']}",
        headers=auth_headers,
        json={"id_producto": 1, "cantidad": 1, "precio_unitario": precio, "extras": []},
    )
    assert add.status_code == 200
    me = client.get("/auth/me", headers=auth_headers).json()
    assert add.json()["id_usuario"] == me["id_usuario"]
    assert add.json()["id_usuario"] != otro["id_usuario"]


def test_cobro_asociado_al_autenticado(client, auth_headers):
    ctx = client.get("/ventas/productos/1/contexto", headers=auth_headers)
    precio = ctx.json()["calculo_inicial"]["precio_unitario"]
    add = client.post(
        "/pedidos/mesa/4/lineas",
        headers=auth_headers,
        json={"id_producto": 1, "cantidad": 1, "precio_unitario": precio, "extras": []},
    )
    pedido_id = add.json()["id_pedido"]
    me = client.get("/auth/me", headers=auth_headers).json()
    cobro = client.post(
        f"/pedidos/{pedido_id}/cobrar",
        headers=auth_headers,
        json={"id_usuario": 99999, "forma_pago": "EFECTIVO", "origen": "VENTAS"},
    )
    assert cobro.status_code == 200, cobro.text
    assert cobro.json()["id_usuario"] == me["id_usuario"]


def test_modulo_retirado_403(client, auth_headers):
    _crear_usuario(client, auth_headers, "cajero_sin_cmd", modulos=["/ventas", "/dashboard"])
    token = _login(client, "cajero_sin_cmd").json()["access_token"]
    res = client.get("/comandera/pendientes", headers=_headers(token))
    assert res.status_code == 403


def test_modulo_permitido_y_defaults_rol(client, auth_headers):
    _crear_usuario(client, auth_headers, "cajero_ok")
    token = _login(client, "cajero_ok").json()["access_token"]
    res = client.get("/comandera/pendientes", headers=_headers(token))
    assert res.status_code == 200
    cocina = _crear_usuario(client, auth_headers, "cocina_ok", rol="COCINA")
    assert "/comandera" in cocina["modulos_efectivos"]
    tok_c = _login(client, "cocina_ok").json()["access_token"]
    assert client.get("/comandera/pendientes", headers=_headers(tok_c)).status_code == 200
    assert client.get("/pedidos/activos", headers=_headers(tok_c)).status_code == 403


def test_admin_mantiene_acceso(client, auth_headers):
    assert client.get("/usuarios/", headers=auth_headers).status_code == 200
    assert client.get("/auditoria/", headers=auth_headers).status_code == 200


def test_cocina_sin_permiso_cobro_403(client, auth_headers):
    _crear_usuario(client, auth_headers, "cocina_nocobro", rol="COCINA")
    token = _login(client, "cocina_nocobro").json()["access_token"]
    res = client.post(
        "/pedidos/1/cobrar",
        headers=_headers(token),
        json={"forma_pago": "EFECTIVO", "origen": "COMANDERA"},
    )
    assert res.status_code == 403


def test_cocina_con_permiso_puede_iniciar_cobro(client, auth_headers):
    u = _crear_usuario(
        client,
        auth_headers,
        "cocina_cobro",
        rol="COCINA",
        permisos_acciones=[COBRAR_DESDE_COMANDERA],
    )
    ctx = client.get("/ventas/productos/1/contexto", headers=auth_headers)
    precio = ctx.json()["calculo_inicial"]["precio_unitario"]
    add = client.post(
        "/pedidos/mesa/5/lineas",
        headers=auth_headers,
        json={"id_producto": 1, "cantidad": 1, "precio_unitario": precio, "extras": []},
    )
    pedido_id = add.json()["id_pedido"]
    token = _login(client, "cocina_cobro").json()["access_token"]
    cobro = client.post(
        f"/pedidos/{pedido_id}/cobrar",
        headers=_headers(token),
        json={"forma_pago": "EFECTIVO", "origen": "COMANDERA"},
    )
    assert cobro.status_code == 200, cobro.text
    assert cobro.json()["id_usuario"] == u["id_usuario"]


def test_retirar_permiso_vale_en_siguiente_peticion(client, auth_headers):
    u = _crear_usuario(
        client,
        auth_headers,
        "cocina_quita",
        rol="COCINA",
        permisos_acciones=[COBRAR_DESDE_COMANDERA],
    )
    token = _login(client, "cocina_quita").json()["access_token"]
    client.put(
        f"/usuarios/{u['id_usuario']}",
        headers=auth_headers,
        json={"permisos_acciones": []},
    )
    res = client.post(
        "/pedidos/1/cobrar",
        headers=_headers(token),
        json={"forma_pago": "EFECTIVO", "origen": "COMANDERA"},
    )
    assert res.status_code == 403


def test_usuario_inactivo_no_login_ni_sesion(client, auth_headers):
    u = _crear_usuario(client, auth_headers, "inactivo_tmp")
    token = _login(client, "inactivo_tmp").json()["access_token"]
    assert client.get("/auth/me", headers=_headers(token)).status_code == 200
    client.put(f"/usuarios/{u['id_usuario']}", headers=auth_headers, json={"activo": False})
    assert client.get("/auth/me", headers=_headers(token)).status_code == 401
    fail = _login(client, "inactivo_tmp")
    assert fail.status_code == 400
    assert "incorrecto" in fail.json()["detail"].lower() or "intentos" in fail.json()["detail"].lower()


def test_admin_no_se_desactiva_ni_ultimo(client, auth_headers, db_session):
    me = client.get("/auth/me", headers=auth_headers).json()
    res = client.put(f"/usuarios/{me['id_usuario']}", headers=auth_headers, json={"activo": False})
    assert res.status_code == 400
    activos = db_session.query(UsuarioModel).filter_by(rol="ADMIN", activo=True).count()
    assert activos >= 1


def test_password_corta_rechazada(client, auth_headers):
    res = client.post(
        "/usuarios/",
        headers=auth_headers,
        json={
            "nombre": "x",
            "usuario_login": "corto",
            "password": "123",
            "rol": "CAJERO",
        },
    )
    assert res.status_code == 400
    assert "8" in res.json()["detail"]


def test_login_fallido_generico_y_limite(client):
    r1 = _login(client, "noexiste", "mala")
    assert r1.status_code == 400
    assert r1.json()["detail"] == "Usuario o contraseña incorrecto"
    last = None
    for _ in range(5):
        last = _login(client, "locktarget", "wrongpass")
    assert last.status_code == 400
    assert "minutos" in last.json()["detail"].lower() or "intentos" in last.json()["detail"].lower()


def test_bloqueo_expira_y_exito_resetea(client, auth_headers, db_session):
    _crear_usuario(client, auth_headers, "lockexpira")
    fila = (
        db_session.query(LoginBloqueoModel)
        .filter(LoginBloqueoModel.usuario_login == "lockexpira")
        .first()
    )
    if not fila:
        fila = LoginBloqueoModel(usuario_login="lockexpira", ip="testclient", intentos=5)
        db_session.add(fila)
    fila.intentos = 5
    fila.bloqueado_hasta = now_utc_naive() - timedelta(minutes=1)
    db_session.commit()
    ok = _login(client, "lockexpira", "clave1234")
    assert ok.status_code == 200, ok.text


def test_auditoria_no_guarda_password(client, auth_headers, db_session):
    _login(client, "admintest", "test1234")
    _login(client, "admintest", "bad")
    filas = db_session.query(AuditoriaModel).all()
    blob = " ".join((f.detalles_json or "") + (f.usuario_login_intentado or "") for f in filas)
    assert "test1234" not in blob
    assert "password" not in blob.lower() or "hash" not in blob.lower()


def test_auditoria_cobro_y_solo_admin(client, auth_headers):
    ctx = client.get("/ventas/productos/1/contexto", headers=auth_headers)
    precio = ctx.json()["calculo_inicial"]["precio_unitario"]
    add = client.post(
        "/pedidos/mesa/6/lineas",
        headers=auth_headers,
        json={"id_producto": 1, "cantidad": 1, "precio_unitario": precio, "extras": []},
    )
    cobro = client.post(
        f"/pedidos/{add.json()['id_pedido']}/cobrar",
        headers=auth_headers,
        json={"forma_pago": "EFECTIVO", "origen": "VENTAS"},
    )
    assert cobro.status_code == 200
    aud = client.get("/auditoria/?accion=COBRO", headers=auth_headers)
    assert aud.status_code == 200
    items = aud.json()["items"]
    assert any(i["accion"] == "COBRO" and i["origen"] == "VENTAS" for i in items)
    _crear_usuario(client, auth_headers, "cajero_aud")
    tok = _login(client, "cajero_aud").json()["access_token"]
    assert client.get("/auditoria/", headers=_headers(tok)).status_code == 403


def test_ajuste_puntos_registrado(client, auth_headers):
    cli = client.post(
        "/clientes/",
        headers=auth_headers,
        json={"nombre": "Ana", "telefono": "5511112222"},
    )
    assert cli.status_code in (200, 201)
    cid = cli.json()["id_cliente"]
    adj = client.post(
        f"/clientes/{cid}/ajustar-puntos",
        headers=auth_headers,
        json={"puntos": 3, "notas": "ajuste prueba", "id_usuario": 1},
    )
    assert adj.status_code == 200, adj.text
    aud = client.get("/auditoria/?accion=PUNTOS_AJUSTE", headers=auth_headers)
    assert any(i["accion"] == "PUNTOS_AJUSTE" for i in aud.json()["items"])
