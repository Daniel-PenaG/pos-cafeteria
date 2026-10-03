from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ActivarTesoreria(BaseModel):
    fecha_corte: datetime
    efectivo_cafeteria: float = Field(..., ge=0)
    efectivo_casa: float = Field(..., ge=0)
    saldo_banco: float = Field(..., ge=0)
    observacion: str = Field(..., min_length=1, max_length=500)
    confirmar: bool = False
    operation_id: str = Field(..., min_length=8, max_length=80)


class TraspasoIn(BaseModel):
    codigo_origen: str
    codigo_destino: str
    importe: float = Field(..., gt=0)
    concepto: str = Field(..., min_length=1, max_length=200)
    observacion: Optional[str] = Field(None, max_length=500)
    operation_id: str = Field(..., min_length=8, max_length=80)
    fecha_operacion: Optional[datetime] = None


class MovimientoCuentaIn(BaseModel):
    codigo_cuenta: str
    importe: float = Field(..., gt=0)
    concepto: str = Field(..., min_length=1, max_length=200)
    observacion: Optional[str] = Field(None, max_length=500)
    operation_id: str = Field(..., min_length=8, max_length=80)
    fecha_operacion: Optional[datetime] = None


class AjusteIn(MovimientoCuentaIn):
    tipo: str


class ReversaIn(BaseModel):
    motivo: str = Field(..., min_length=1, max_length=500)
    operation_id: str = Field(..., min_length=8, max_length=80)


class ConciliacionIn(BaseModel):
    codigo_cuenta: str
    saldo_fisico: float = Field(..., ge=0)
    observacion: Optional[str] = Field(None, max_length=500)


class RevisionConciliacionIn(BaseModel):
    generar_ajuste: bool = False
    operation_id: Optional[str] = Field(None, max_length=80)
