from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CierreCajaCreate(BaseModel):
    efectivo_contado: float = Field(..., ge=0)
    notas: Optional[str] = Field(None, max_length=500)
    fecha: Optional[date] = None


class CierreCajaOut(BaseModel):
    id_cierre: int
    fecha: date
    id_usuario: int
    num_ventas: int
    total_ventas: float
    total_efectivo: float
    total_tarjeta: float
    total_transferencia: float
    efectivo_contado: float
    diferencia: float
    notas: Optional[str] = None
    fecha_hora_registro: Optional[datetime] = None


class CierreCajaDetalle(CierreCajaOut):
    nombre_usuario: Optional[str] = None
    usuario_login: Optional[str] = None
    rol: Optional[str] = None


class ResumenCierreUsuario(BaseModel):
    fecha: date
    id_usuario: int
    nombre_usuario: str
    usuario_login: str
    num_ventas: int
    total_ventas: float
    total_efectivo: float
    total_tarjeta: float
    total_transferencia: float
    ya_cerrado: bool
    cierre: Optional[CierreCajaOut] = None
    ventas: List[dict] = []
