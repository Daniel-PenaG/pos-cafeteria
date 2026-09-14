from typing import List, Optional

from pydantic import BaseModel, Field


class UsuarioCreate(BaseModel):
    nombre: str
    usuario_login: str
    password: str
    rol: str
    modulos: Optional[List[str]] = None
    permisos_acciones: Optional[List[str]] = None
    activo: bool = True


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    modulos: Optional[List[str]] = None
    permisos_acciones: Optional[List[str]] = None
    activo: Optional[bool] = None


class UsuarioOut(BaseModel):
    id_usuario: int
    nombre: str
    usuario_login: str
    rol: str
    activo: bool = True
    modulos: Optional[List[str]] = None
    modulos_efectivos: Optional[List[str]] = None
    permisos_acciones: Optional[List[str]] = None

    class Config:
        from_attributes = True
