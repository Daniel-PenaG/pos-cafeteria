"""Caché de usuario en request.state: una petición, un lookup."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.constants.roles import ADMIN, CAJERO, normalizar_rol
from app.models.models import UsuarioModel
from app.utils.deps import get_current_user
from app.utils.security import create_access_token


def _request() -> Request:
    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    return Request(scope)


def test_usuario_cacheado_solo_dentro_del_mismo_request(db_session):
    user = db_session.query(UsuarioModel).filter(UsuarioModel.usuario_login == "admintest").first()
    assert user is not None
    token = create_access_token({"sub": user.usuario_login})
    req = _request()
    u1 = get_current_user(req, token=token, db=db_session)
    u2 = get_current_user(req, token=token, db=db_session)
    assert u1.id_usuario == u2.id_usuario
    assert getattr(req.state, "_auth_user", None) is u1


def test_cada_request_http_tiene_estado_aislado(db_session):
    user = db_session.query(UsuarioModel).filter(UsuarioModel.usuario_login == "admintest").first()
    token = create_access_token({"sub": user.usuario_login})
    req_a = _request()
    req_b = _request()
    get_current_user(req_a, token=token, db=db_session)
    get_current_user(req_b, token=token, db=db_session)
    assert req_a is not req_b
    assert hasattr(req_a.state, "_auth_user")
    assert hasattr(req_b.state, "_auth_user")


def test_token_distinto_no_reutiliza_cache_entre_requests(db_session):
    admin = db_session.query(UsuarioModel).filter(UsuarioModel.usuario_login == "admintest").first()
    otro = UsuarioModel(
        nombre="Otro",
        usuario_login="otrocache",
        hash_password=admin.hash_password,
        rol=CAJERO,
        activo=True,
    )
    db_session.add(otro)
    db_session.commit()
    t_admin = create_access_token({"sub": admin.usuario_login})
    t_otro = create_access_token({"sub": otro.usuario_login})
    req = _request()
    u_admin = get_current_user(req, token=t_admin, db=db_session)
    req2 = _request()
    u_otro = get_current_user(req2, token=t_otro, db=db_session)
    assert u_admin.usuario_login != u_otro.usuario_login


def test_usuario_inactivo_401(db_session):
    user = db_session.query(UsuarioModel).filter(UsuarioModel.usuario_login == "admintest").first()
    token = create_access_token({"sub": user.usuario_login})
    prev_activo = user.activo
    user.activo = False
    db_session.commit()
    try:
        req = _request()
        with pytest.raises(HTTPException) as exc:
            get_current_user(req, token=token, db=db_session)
        assert exc.value.status_code == 401
    finally:
        user.activo = prev_activo if prev_activo is not None else True
        db_session.commit()


def test_cambio_rol_visible_en_siguiente_request(db_session):
    user = db_session.query(UsuarioModel).filter(UsuarioModel.usuario_login == "admintest").first()
    token = create_access_token({"sub": user.usuario_login})
    rol_prev = user.rol
    user.rol = CAJERO
    db_session.commit()
    try:
        req1 = _request()
        u1 = get_current_user(req1, token=token, db=db_session)
        assert normalizar_rol(u1.rol) == CAJERO
        user.rol = ADMIN
        db_session.commit()
        db_session.expire_all()
        req2 = _request()
        u2 = get_current_user(req2, token=token, db=db_session)
        assert normalizar_rol(u2.rol) == ADMIN
    finally:
        user.rol = rol_prev
        db_session.commit()


def test_no_hay_cache_global_en_modulo():
    import app.utils.deps as deps

    assert not hasattr(deps, "_global_user_cache")
