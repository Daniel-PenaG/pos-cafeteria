from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Usuario
from app.schemas.auth import UserCreate, UserLogin, Token
from app.utils.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Autenticacion"])

# Registro de usuarios
@router.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # Verifica si el usuario ya existe
    existing_user = db.query(Usuario).filter(Usuario.usuario_login == user.usuario_login).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    
    hashed = hash_password(user.password)

    new_user = Usuario(
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
@router.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(Usuario).filter(Usuario.usuario_login == user.usuario_login).first()

    if not db_user:
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrecto")

    if not verify_password(user.password, db_user.hash_password):
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrecto")
    
    token = create_access_token({"sub": db_user.usuario_login})
    return {"access_token": token, "token_type": "bearer"}
