from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.constants.roles import ROLES_VALIDOS, normalizar_rol
from app.database import get_db
from app.models.models import UsuarioModel
from app.schemas.auth import UserCreate, UserLogin, Token
from app.utils.deps import get_current_user, require_admin
from app.utils.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Autenticacion"])


@router.get("/me")
def get_me(current: UsuarioModel = Depends(get_current_user)):
    return {
        "id_usuario": current.id_usuario,
        "nombre": current.nombre,
        "usuario_login": current.usuario_login,
        "rol": normalizar_rol(current.rol),
    }


# Registro de usuarios (solo administrador)
@router.post("/register")
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    _: UsuarioModel = Depends(require_admin),
):
    # Verifica si el usuario ya existe
    existing_user = db.query(UsuarioModel).filter(UsuarioModel.usuario_login == user.usuario_login).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="El usuario ya existe")

    if normalizar_rol(user.rol) not in ROLES_VALIDOS:
        raise HTTPException(status_code=400, detail="Rol no válido")

    hashed = hash_password(user.password)

    new_user = UsuarioModel(
        nombre=user.nombre,
        usuario_login=user.usuario_login,
        hash_password=hashed,
        rol=user.rol
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "Usuario registrado correctamente"}

# Login
@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    try:
        db_user = db.query(UsuarioModel).filter(UsuarioModel.usuario_login == user.usuario_login).first()

        if not db_user:
            raise HTTPException(status_code=400, detail="Usuario o contraseña incorrecto")

        if not verify_password(user.password, db_user.hash_password):
            raise HTTPException(status_code=400, detail="Usuario o contraseña incorrecto")
        
        token = create_access_token({"sub": db_user.usuario_login})

        rol = normalizar_rol(db_user.rol)
        if rol != db_user.rol:
            db_user.rol = rol
            db.commit()

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id_usuario": db_user.id_usuario,
                "nombre": db_user.nombre,
                "usuario_login": db_user.usuario_login,
                "rol": rol,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en login: {str(e)}")
