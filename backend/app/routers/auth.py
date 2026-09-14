from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.constants import auditoria as A
from app.constants.roles import ROLES_VALIDOS, normalizar_rol
from app.database import get_db
from app.models.models import UsuarioModel
from app.schemas.auth import UserCreate, UserLogin
from app.services.auditoria_service import registrar_auditoria
from app.services.login_lock_service import (
    LOGIN_FAIL_DETAIL,
    LOGIN_LOCKED_DETAIL,
    bloqueo_activo,
    registrar_exito,
    registrar_fallo,
)
from app.utils.acciones import acciones_efectivas
from app.utils.deps import get_current_user, require_admin
from app.utils.modulos import modulos_efectivos
from app.utils.password_policy import validar_password_nueva
from app.utils.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Autenticacion"])


def _meta(request: Request | None) -> dict:
    if request is None:
        return {"ip": None, "user_agent": None}
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


def _user_payload(user: UsuarioModel) -> dict:
    rol = normalizar_rol(user.rol)
    return {
        "id_usuario": user.id_usuario,
        "nombre": user.nombre,
        "usuario_login": user.usuario_login,
        "rol": rol,
        "activo": bool(getattr(user, "activo", True)),
        "modulos": modulos_efectivos(user),
        "permisos_acciones": acciones_efectivas(user),
    }


@router.get("/me")
def get_me(current: UsuarioModel = Depends(get_current_user)):
    return _user_payload(current)


@router.post("/register")
def register_user(
    user: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(require_admin),
):
    existing_user = db.query(UsuarioModel).filter(UsuarioModel.usuario_login == user.usuario_login).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="El usuario ya existe")

    if normalizar_rol(user.rol) not in ROLES_VALIDOS:
        raise HTTPException(status_code=400, detail="Rol no válido")

    try:
        password = validar_password_nueva(user.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_user = UsuarioModel(
        nombre=user.nombre,
        usuario_login=user.usuario_login,
        hash_password=hash_password(password),
        rol=normalizar_rol(user.rol),
        activo=True,
    )
    db.add(new_user)
    registrar_auditoria(
        db,
        usuario=current,
        accion=A.USUARIO_CREADO,
        entidad="usuario",
        detalles={"usuario_login": user.usuario_login, "rol": new_user.rol},
        origen="auth.register",
        **_meta(request),
    )
    db.commit()
    db.refresh(new_user)
    return {"message": "Usuario registrado correctamente"}


@router.post("/login")
def login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    meta = _meta(request)
    login_name = (user.usuario_login or "").strip()
    try:
        if bloqueo_activo(db, login_name, meta["ip"]):
            registrar_auditoria(
                db,
                accion=A.LOGIN_BLOQUEADO,
                usuario_login_intentado=login_name,
                origen="auth.login",
                **meta,
            )
            db.commit()
            raise HTTPException(status_code=400, detail=LOGIN_LOCKED_DETAIL)

        db_user = db.query(UsuarioModel).filter(UsuarioModel.usuario_login == user.usuario_login).first()
        if not db_user or not verify_password(user.password, db_user.hash_password):
            bloqueado = registrar_fallo(db, login_name, meta["ip"])
            registrar_auditoria(
                db,
                accion=A.LOGIN_FALLIDO,
                usuario_login_intentado=login_name,
                origen="auth.login",
                detalles={"bloqueado": bloqueado},
                **meta,
            )
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=LOGIN_LOCKED_DETAIL if bloqueado else LOGIN_FAIL_DETAIL,
            )

        if getattr(db_user, "activo", True) is False:
            registrar_auditoria(
                db,
                accion=A.LOGIN_FALLIDO,
                usuario_login_intentado=login_name,
                origen="auth.login",
                detalles={"motivo": "inactivo"},
                **meta,
            )
            db.commit()
            raise HTTPException(status_code=400, detail=LOGIN_FAIL_DETAIL)

        registrar_exito(db, login_name, meta["ip"])
        token = create_access_token({"sub": db_user.usuario_login})
        rol = normalizar_rol(db_user.rol)
        if rol != db_user.rol:
            db_user.rol = rol
        registrar_auditoria(
            db,
            usuario=db_user,
            accion=A.LOGIN_OK,
            entidad="usuario",
            entidad_id=db_user.id_usuario,
            origen="auth.login",
            **meta,
        )
        db.commit()
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": _user_payload(db_user),
        }
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="No se pudo iniciar sesión")
