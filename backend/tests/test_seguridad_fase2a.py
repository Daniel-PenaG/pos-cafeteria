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


def _token_modulos(client, auth_headers, login, modulos, rol="CAJERO", **extra):
    _crear_usuario(client, auth_headers, login, rol=rol, modulos=modulos, **extra)
    token = _login(client, login).json()["access_token"]
    return _headers(token)


def _precio_producto(client, auth_headers, id_producto=1):
    ctx = client.get(f"/ventas/productos/{id_producto}/contexto", headers=auth_headers)
    assert ctx.status_code == 200, ctx.text
    return ctx.json()["calculo_inicial"]["precio_unitario"]


def _agregar_linea(client, headers, mesa, precio, para_llevar=False):
    qs = "?para_llevar=true" if para_llevar else ""
    return client.post(
        f"/pedidos/mesa/{mesa}/lineas{qs}",
        headers=headers,
        json={"id_producto": 1, "cantidad": 1, "precio_unitario": precio, "extras": []},
    )


def test_solo_mesas_activas_no_modifica_ni_cobra(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    add = _agregar_linea(client, auth_headers, 7, precio)
    assert add.status_code == 200, add.text
    pedido = add.json()
    linea_id = pedido["lineas"][0]["id_detalle_pedido"]
    tok = _token_modulos(client, auth_headers, "solo_mesas", ["/mesas-activas"])

    assert client.get("/pedidos/activos", headers=tok).status_code == 200
    assert client.get("/pedidos/mesa/7", headers=tok).status_code == 403
    assert _agregar_linea(client, tok, 7, precio).status_code == 403
    assert client.patch(
        f"/pedidos/lineas/{linea_id}",
        headers=tok,
        json={"cantidad": 2},
    ).status_code == 403
    assert client.delete(f"/pedidos/lineas/{linea_id}", headers=tok).status_code == 403
    assert client.put(
        f"/pedidos/{pedido['id_pedido']}/cliente",
        headers=tok,
        json={"id_cliente": None},
    ).status_code == 403
    assert client.post(
        f"/pedidos/{pedido['id_pedido']}/confirmar-comanda",
        headers=tok,
    ).status_code == 403
    assert client.post(
        f"/pedidos/{pedido['id_pedido']}/cobrar",
        headers=tok,
        json={"forma_pago": "EFECTIVO", "origen": "VENTAS"},
    ).status_code == 403
    venta = client.post(
        "/ventas/",
        headers=tok,
        json={
            "id_usuario": 1,
            "numero_mesa": 2,
            "forma_pago": "EFECTIVO",
            "para_llevar": False,
            "detalles": [
                {"id_producto": 1, "cantidad": 1, "precio_unitario": precio, "extras": []}
            ],
        },
    )
    assert venta.status_code == 403


def test_ventas_y_para_llevar_separados(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    add_mesa = _agregar_linea(client, auth_headers, 8, precio)
    add_ll = _agregar_linea(client, auth_headers, 99, precio, para_llevar=True)
    assert add_mesa.status_code == 200, add_mesa.text
    assert add_ll.status_code == 200, add_ll.text
    linea_mesa = add_mesa.json()["lineas"][0]["id_detalle_pedido"]
    linea_ll = add_ll.json()["lineas"][0]["id_detalle_pedido"]

    tok_ll = _token_modulos(client, auth_headers, "solo_para_llevar", ["/ventas-para-llevar"])
    tok_v = _token_modulos(client, auth_headers, "solo_ventas", ["/ventas"])

    assert _agregar_linea(client, tok_ll, 8, precio).status_code == 403
    assert client.get("/pedidos/mesa/8", headers=tok_ll).status_code == 403
    assert client.patch(
        f"/pedidos/lineas/{linea_mesa}",
        headers=tok_ll,
        json={"cantidad": 2},
    ).status_code == 403
    assert _agregar_linea(client, tok_ll, 99, precio, para_llevar=True).status_code == 200

    assert _agregar_linea(client, tok_v, 99, precio, para_llevar=True).status_code == 403
    assert client.get("/pedidos/mesa/99?para_llevar=true", headers=tok_v).status_code == 403
    assert client.patch(
        f"/pedidos/lineas/{linea_ll}",
        headers=tok_v,
        json={"cantidad": 2},
    ).status_code == 403
    assert client.delete(f"/pedidos/lineas/{linea_ll}", headers=tok_v).status_code == 403
    assert client.post(
        f"/pedidos/{add_ll.json()['id_pedido']}/cobrar",
        headers=tok_v,
        json={"forma_pago": "EFECTIVO", "origen": "VENTAS"},
    ).status_code == 403
    assert _agregar_linea(client, tok_v, 8, precio).status_code == 200


def test_ventas_no_ve_insumos_ni_costos(client, auth_headers):
    tok = _token_modulos(client, auth_headers, "ventas_sin_costos", ["/ventas"])
    assert client.get("/catalogo/insumos", headers=tok).status_code == 403
    assert client.get("/extras-venta/insumos-importables", headers=tok).status_code == 403
    assert client.get("/extras-venta/", headers=tok).status_code == 403
    extras = client.get("/ventas/extras?id_producto=1", headers=tok)
    assert extras.status_code == 200, extras.text
    assert all(float(e.get("costo") or 0) == 0 for e in extras.json())


def test_cuentas_cajero_no_ve_dashboard(client, auth_headers):
    tok = _token_modulos(client, auth_headers, "solo_cuentas", ["/cuentas-cajero"])
    assert client.get("/reportes/resumen-dashboard", headers=tok).status_code == 403


def test_cocina_cobro_exige_modulo_y_accion(client, auth_headers):
    precio = _precio_producto(client, auth_headers)
    add = _agregar_linea(client, auth_headers, 9, precio)
    assert add.status_code == 200, add.text
    pedido_id = add.json()["id_pedido"]

    tok_sin_mod = _token_modulos(
        client,
        auth_headers,
        "cocina_sin_cmd_mod",
        ["/ventas"],
        rol="COCINA",
        permisos_acciones=[COBRAR_DESDE_COMANDERA],
    )
    assert client.post(
        f"/pedidos/{pedido_id}/cobrar",
        headers=tok_sin_mod,
        json={"forma_pago": "EFECTIVO", "origen": "COMANDERA"},
    ).status_code == 403

    tok_sin_acc = _token_modulos(
        client,
        auth_headers,
        "cocina_sin_acc",
        ["/comandera"],
        rol="COCINA",
    )
    assert client.post(
        f"/pedidos/{pedido_id}/cobrar",
        headers=tok_sin_acc,
        json={"forma_pago": "EFECTIVO", "origen": "COMANDERA"},
    ).status_code == 403

    tok_ok = _token_modulos(
        client,
        auth_headers,
        "cocina_ambos",
        ["/comandera"],
        rol="COCINA",
        permisos_acciones=[COBRAR_DESDE_COMANDERA],
    )
    cobro = client.post(
        f"/pedidos/{pedido_id}/cobrar",
        headers=tok_ok,
        json={"forma_pago": "EFECTIVO", "origen": "COMANDERA"},
    )
    assert cobro.status_code == 200, cobro.text


def test_modulos_vacios_y_null(client, auth_headers, db_session):
    vacio = client.post(
        "/usuarios/",
        headers=auth_headers,
        json={
            "nombre": "vacio",
            "usuario_login": "mod_vacio",
            "password": "clave1234",
            "rol": "CAJERO",
            "modulos": [],
        },
    )
    assert vacio.status_code == 422

    creado = _crear_usuario(client, auth_headers, "mod_null")
    assert creado["modulos"] is None
    assert "/ventas" in creado["modulos_efectivos"]

    user = (
        db_session.query(UsuarioModel)
        .filter(UsuarioModel.usuario_login == "mod_null")
        .first()
    )
    user.modulos_json = "[]"
    db_session.commit()
    tok = _login(client, "mod_null").json()["access_token"]
    me = client.get("/auth/me", headers=_headers(tok))
    assert me.status_code == 200
    assert me.json()["modulos"] == []
    assert client.get("/pedidos/activos", headers=_headers(tok)).status_code == 403

    reset = client.put(
        f"/usuarios/{creado['id_usuario']}",
        headers=auth_headers,
        json={"modulos": None},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["modulos"] is None
    assert "/ventas" in reset.json()["modulos_efectivos"]
