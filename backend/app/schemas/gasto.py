from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class GastoCreate(BaseModel):
    descripcion: str = Field(..., min_length=1, max_length=300)
    monto: float = Field(..., gt=0)
    estado_pago: str = "PAGADO"
    clasificacion: str = "GASTO_OPERATIVO"
    codigo_cuenta: Optional[str] = None
    operation_id: Optional[str] = Field(None, max_length=80)


class GastoUpdate(BaseModel):
    descripcion: Optional[str] = Field(None, min_length=1, max_length=300)
    monto: Optional[float] = Field(None, gt=0)


class GastoPagar(BaseModel):
    codigo_cuenta: str = Field(..., min_length=1, max_length=40)
    operation_id: Optional[str] = Field(None, max_length=80)


class GastoResponse(BaseModel):
    id_gasto: int
    descripcion: str
    monto: float
    fecha_hora: datetime
    id_usuario: int
    usuario_nombre: Optional[str] = None

    class Config:
        from_attributes = True
