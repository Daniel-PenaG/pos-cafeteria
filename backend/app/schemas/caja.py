from typing import List, Optional

from pydantic import BaseModel, Field


class CajaAbrir(BaseModel):
    fondo_inicial: float = Field(..., ge=0)
    terminal: str = Field(..., min_length=2, max_length=40)
    observacion: Optional[str] = Field(None, max_length=500)
    operation_id: Optional[str] = Field(None, max_length=64)


class CajaMovimientoCreate(BaseModel):
    tipo: str
    importe: float = Field(..., gt=0)
    motivo: str = Field(..., min_length=1, max_length=200)
    metodo: str = "EFECTIVO"
    referencia: Optional[str] = Field(None, max_length=80)
    id_gasto: Optional[int] = None
    operation_id: Optional[str] = Field(None, max_length=64)


class DenominacionIn(BaseModel):
    codigo: str
    cantidad: int = Field(..., ge=0)


class CajaCerrar(BaseModel):
    denominaciones: List[DenominacionIn] = []
    declarado_efectivo: Optional[float] = Field(None, ge=0)
    declarado_transferencia: float = Field(..., ge=0)
    declarado_tarjeta: float = Field(..., ge=0)
    captura_directa: bool = False
    ref_terminal: Optional[str] = Field(None, max_length=80)
    lote_terminal: Optional[str] = Field(None, max_length=80)
    ref_transferencia: Optional[str] = Field(None, max_length=80)
    observacion: Optional[str] = Field(None, max_length=500)
    forzar: bool = False
    operation_id: Optional[str] = Field(None, max_length=64)


class CajaAnular(BaseModel):
    motivo: str = Field(..., min_length=1, max_length=500)
