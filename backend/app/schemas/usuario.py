from typing import Optional

from pydantic import BaseModel, Field


class UsuarioCreate(BaseModel):
    nombre: str
    usuario_login: str
    password: str
    rol: str


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None


class UsuarioOut(BaseModel):
    id_usuario: int
    nombre: str
    usuario_login: str
    rol: str

    class Config:
        from_attributes = True
