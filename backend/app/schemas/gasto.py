from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class GastoCreate(BaseModel):
    descripcion: str = Field(..., min_length=1, max_length=300)
    monto: float = Field(..., gt=0)


class GastoUpdate(BaseModel):
    descripcion: Optional[str] = Field(None, min_length=1, max_length=300)
    monto: Optional[float] = Field(None, gt=0)


class GastoResponse(BaseModel):
    id_gasto: int
    descripcion: str
    monto: float
    fecha_hora: datetime
    id_usuario: int
    usuario_nombre: Optional[str] = None

    class Config:
        from_attributes = True
