from pydantic import BaseModel
from typing import List

class DetalleVentaBase(BaseModel):
    id_producto: int
    cantidad: float

class VentaCreate(BaseModel):
    id_usuario: int
    forma_pago: str
    detalles: List[DetalleVentaBase]

class VentaResponse(BaseModel):
    id_venta: int
    total: float

    class Config:
        orm_mode = True
