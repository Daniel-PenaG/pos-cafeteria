from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.constants import auditoria as A
from app.constants.acciones import ACCIONES_CATALOGO, ROLE_DEFAULT_ACCIONES
from app.constants.modulos import MODULOS_CATALOGO, ROLE_DEFAULT_MODULES
from app.constants.roles import ADMIN, ROLES_LABELS, ROLES_VALIDOS, normalizar_rol
from app.database import get_db
from app.models.models import UsuarioModel
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.services.auditoria_service import registrar_auditoria
from app.utils.deps import get_current_user, require_admin
from app.utils.password_policy import validar_password_nueva
from app.utils.permisos import require_module
from app.utils.security import hash_password
from app.utils.usuario_helpers import aplicar_acciones, aplicar_modulos, usuario_a_out

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"],
    dependencies=[Depends(require_admin), Depends(require_module("/usuarios"))],
)


def _meta(request: Request) -> dict:
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


def _admins_activos(db: Session) -> int:
    return (
        db.query(UsuarioModel)
        .filter(UsuarioModel.rol == ADMIN, UsuarioModel.activo.is_(True))
        .count()
    )


@router.get("/perfiles")
def listar_perfiles():
    return [{"codigo": r, "nombre": ROLES_LABELS[r]} for r in ROLES_VALIDOS]


@router.get("/modulos-catalogo")
def catalogo_modulos():
    return {
        "modulos": MODULOS_CATALOGO,
        "defaults_por_rol": ROLE_DEFAULT_MODULES,
        "acciones": ACCIONES_CATALOGO,
        "acciones_defaults_por_rol": ROLE_DEFAULT_ACCIONES,
    }


@router.get("/")
def listar_usuarios(
    activos: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(UsuarioModel)
    if activos is True:
        q = q.filter(UsuarioModel.activo.is_(True))
    elif activos is False:
        q = q.filter(UsuarioModel.activo.is_(False))
    usuarios = q.order_by(UsuarioModel.nombre).all()
    return [usuario_a_out(u) for u in usuarios]


@router.post("/")
def crear_usuario(
    data: UsuarioCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    if data.rol not in ROLES_VALIDOS:
        raise HTTPException(status_code=400, detail="Rol no válido")

    existe = db.query(UsuarioModel).filter(UsuarioModel.usuario_login == data.usuario_login).first()
    if existe:
        raise HTTPException(status_code=400, detail="El usuario ya existe")

    try:
        password = validar_password_nueva(data.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    nuevo = UsuarioModel(
        nombre=data.nombre,
        usuario_login=data.usuario_login,
        hash_password=hash_password(password),
        rol=data.rol,
        activo=bool(data.activo),
    )
    aplicar_modulos(nuevo, data.modulos)
    aplicar_acciones(nuevo, data.permisos_acciones)
    db.add(nuevo)
    db.flush()
    registrar_auditoria(
        db,
        usuario=current,
        accion=A.USUARIO_CREADO,
        entidad="usuario",
        entidad_id=nuevo.id_usuario,
        detalles={"usuario_login": nuevo.usuario_login, "rol": nuevo.rol},
        origen="usuarios",
        **_meta(request),
    )
    db.commit()
    db.refresh(nuevo)
    return usuario_a_out(nuevo)


@router.put("/{id_usuario}")
def actualizar_usuario(
    id_usuario: int,
    data: UsuarioUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if data.rol is not None:
        if data.rol not in ROLES_VALIDOS:
            raise HTTPException(status_code=400, detail="Rol no válido")
        if usuario.id_usuario == current.id_usuario and data.rol != ADMIN:
            raise HTTPException(status_code=400, detail="No puedes quitarte el rol de administrador")
        usuario.rol = data.rol

    if data.nombre is not None:
        usuario.nombre = data.nombre

    if data.password:
        try:
            password = validar_password_nueva(data.password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        usuario.hash_password = hash_password(password)

    if data.modulos is not None:
        aplicar_modulos(usuario, data.modulos)

    if data.permisos_acciones is not None:
        aplicar_acciones(usuario, data.permisos_acciones)

    if data.activo is not None:
        if data.activo is False:
            if usuario.id_usuario == current.id_usuario:
                raise HTTPException(status_code=400, detail="No puedes desactivar tu propio usuario")
            if normalizar_rol(usuario.rol) == ADMIN and _admins_activos(db) <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="No se puede desactivar el último administrador activo",
                )
            usuario.activo = False
            accion = A.USUARIO_DESACTIVADO
        else:
            usuario.activo = True
            accion = A.USUARIO_ACTIVADO
        registrar_auditoria(
            db,
            usuario=current,
            accion=accion,
            entidad="usuario",
            entidad_id=usuario.id_usuario,
            origen="usuarios",
            **_meta(request),
        )
    else:
        registrar_auditoria(
            db,
            usuario=current,
            accion=A.USUARIO_EDITADO,
            entidad="usuario",
            entidad_id=usuario.id_usuario,
            detalles={"rol": usuario.rol},
            origen="usuarios",
            **_meta(request),
        )

    db.commit()
    db.refresh(usuario)
    return usuario_a_out(usuario)


@router.delete("/{id_usuario}")
def desactivar_usuario(
    id_usuario: int,
    request: Request,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    """No se elimina el historial: se desactiva."""
    if id_usuario == current.id_usuario:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propio usuario")

    usuario = db.query(UsuarioModel).filter(UsuarioModel.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if normalizar_rol(usuario.rol) == ADMIN and usuario.activo and _admins_activos(db) <= 1:
        raise HTTPException(
            status_code=400,
            detail="No se puede desactivar el último administrador activo",
        )
    usuario.activo = False
    registrar_auditoria(
        db,
        usuario=current,
        accion=A.USUARIO_DESACTIVADO,
        entidad="usuario",
        entidad_id=usuario.id_usuario,
        origen="usuarios",
        **_meta(request),
    )
    db.commit()
    return {"message": "Usuario desactivado", "activo": False}
