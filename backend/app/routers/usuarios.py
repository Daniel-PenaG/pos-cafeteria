from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.constants.roles import ROLES_LABELS, ROLES_VALIDOS
from app.database import get_db
from app.models.models import UsuarioModel
from app.schemas.usuario import UsuarioCreate, UsuarioOut, UsuarioUpdate
from app.utils.deps import get_current_user, require_admin
from app.utils.security import hash_password

router = APIRouter(prefix="/usuarios", tags=["Usuarios"], dependencies=[Depends(require_admin)])


@router.get("/perfiles")
def listar_perfiles():
    return [{"codigo": r, "nombre": ROLES_LABELS[r]} for r in ROLES_VALIDOS]


@router.get("/", response_model=list[UsuarioOut])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(UsuarioModel).order_by(UsuarioModel.nombre).all()


@router.post("/", response_model=UsuarioOut)
def crear_usuario(data: UsuarioCreate, db: Session = Depends(get_db)):
    if data.rol not in ROLES_VALIDOS:
        raise HTTPException(status_code=400, detail="Rol no válido")

    existe = db.query(UsuarioModel).filter(UsuarioModel.usuario_login == data.usuario_login).first()
    if existe:
        raise HTTPException(status_code=400, detail="El usuario ya existe")

    nuevo = UsuarioModel(
        nombre=data.nombre,
        usuario_login=data.usuario_login,
        hash_password=hash_password(data.password),
        rol=data.rol,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.put("/{id_usuario}", response_model=UsuarioOut)
def actualizar_usuario(
    id_usuario: int,
    data: UsuarioUpdate,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if data.rol is not None:
        if data.rol not in ROLES_VALIDOS:
            raise HTTPException(status_code=400, detail="Rol no válido")
        if usuario.id_usuario == current.id_usuario and data.rol != "ADMIN":
            raise HTTPException(status_code=400, detail="No puedes quitarte el rol de administrador")
        usuario.rol = data.rol

    if data.nombre is not None:
        usuario.nombre = data.nombre

    if data.password:
        usuario.hash_password = hash_password(data.password)

    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{id_usuario}")
def eliminar_usuario(
    id_usuario: int,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    if id_usuario == current.id_usuario:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propio usuario")

    usuario = db.query(UsuarioModel).filter(UsuarioModel.id_usuario == id_usuario).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    db.delete(usuario)
    db.commit()
    return {"message": "Usuario eliminado"}
