"""Límite de intentos de login persistido en BD (sin Redis)."""

from __future__ import annotations

import os
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.models import LoginBloqueoModel
from app.utils.timezone_mx import now_utc_naive

LOGIN_FAIL_DETAIL = "Usuario o contraseña incorrecto"
LOGIN_LOCKED_DETAIL = "Demasiados intentos. Intenta de nuevo en unos minutos."


def _max_attempts() -> int:
    try:
        return max(1, int(os.getenv("LOGIN_MAX_ATTEMPTS", "5")))
    except ValueError:
        return 5


def _lock_minutes() -> int:
    try:
        return max(1, int(os.getenv("LOGIN_LOCK_MINUTES", "5")))
    except ValueError:
        return 5


def _clave(usuario_login: str, ip: str | None) -> tuple[str, str]:
    return (usuario_login or "").strip().lower()[:80], (ip or "")[:64]


def _fila(db: Session, login: str, ip: str) -> LoginBloqueoModel | None:
    return (
        db.query(LoginBloqueoModel)
        .filter(LoginBloqueoModel.usuario_login == login, LoginBloqueoModel.ip == ip)
        .first()
    )


def bloqueo_activo(db: Session, usuario_login: str, ip: str | None) -> bool:
    login, ipn = _clave(usuario_login, ip)
    fila = _fila(db, login, ipn)
    if not fila or not fila.bloqueado_hasta:
        return False
    ahora = now_utc_naive()
    if fila.bloqueado_hasta > ahora:
        return True
    fila.bloqueado_hasta = None
    fila.intentos = 0
    db.flush()
    return False


def registrar_fallo(db: Session, usuario_login: str, ip: str | None) -> bool:
    """Incrementa fallos. True si acaba de quedar bloqueado."""
    login, ipn = _clave(usuario_login, ip)
    ahora = now_utc_naive()
    fila = _fila(db, login, ipn)
    if not fila:
        fila = LoginBloqueoModel(
            usuario_login=login,
            ip=ipn,
            intentos=0,
            actualizado=ahora,
        )
        db.add(fila)
    if fila.bloqueado_hasta and fila.bloqueado_hasta <= ahora:
        fila.bloqueado_hasta = None
        fila.intentos = 0
    fila.intentos = int(fila.intentos or 0) + 1
    fila.actualizado = ahora
    if fila.intentos >= _max_attempts():
        fila.bloqueado_hasta = ahora + timedelta(minutes=_lock_minutes())
        db.flush()
        return True
    db.flush()
    return False


def registrar_exito(db: Session, usuario_login: str, ip: str | None) -> None:
    login, ipn = _clave(usuario_login, ip)
    fila = _fila(db, login, ipn)
    if not fila:
        return
    fila.intentos = 0
    fila.bloqueado_hasta = None
    fila.actualizado = now_utc_naive()
    db.flush()
