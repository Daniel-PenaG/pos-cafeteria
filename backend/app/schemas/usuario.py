from typing import List, Optional

from pydantic import BaseModel, Field


class UsuarioCreate(BaseModel):
    nombre: str
    usuario_login: str
    password: str
    rol: str
    modulos: Optional[List[str]] = None


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    modulos: Optional[List[str]] = None


class UsuarioOut(BaseModel):
    id_usuario: int
    nombre: str
    usuario_login: str
    rol: str
    modulos: Optional[List[str]] = None

    class Config:
        from_attributes = True
