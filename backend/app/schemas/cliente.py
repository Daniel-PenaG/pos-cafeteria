from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class FidelidadConfig(BaseModel):
    pesos_por_punto: float = Field(10, gt=0, description="Pesos MXN por 1 punto ganado")
    minimo_compra_acumular: float = Field(0, ge=0)
    fecha_actualizacion: Optional[datetime] = None

    class Config:
        from_attributes = True


class FidelidadConfigUpdate(BaseModel):
    pesos_por_punto: float = Field(..., gt=0)
    minimo_compra_acumular: float = Field(..., ge=0)


class ClienteBase(BaseModel):
    nombre: str
    telefono: str


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    telefono: Optional[str] = None
    activo: Optional[bool] = None


class Cliente(ClienteBase):
    id_cliente: int
    codigo_fidelidad: str
    puntos_saldo: int
    activo: bool
    fecha_alta: datetime

    class Config:
        from_attributes = True


class FidelidadMovimiento(BaseModel):
    id_movimiento: int
    tipo: str
    puntos: int
    saldo_despues: int
    id_venta: Optional[int] = None
    notas: Optional[str] = None
    fecha_hora: datetime

    class Config:
        from_attributes = True


class ClienteDetalle(Cliente):
    movimientos: List[FidelidadMovimiento] = []


class AjustePuntosRequest(BaseModel):
    puntos: int = Field(..., description="Positivo suma, negativo resta")
    notas: str = Field(..., min_length=1, max_length=300)
    id_usuario: int


class PuntosPreview(BaseModel):
    total_compra: float
    puntos_a_ganar: int
    pesos_por_punto: float
    minimo_compra_acumular: float


class ClienteBusqueda(BaseModel):
    resultados: List[Cliente]
