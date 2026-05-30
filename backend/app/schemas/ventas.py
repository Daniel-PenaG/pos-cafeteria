from pydantic import BaseModel
from typing import List
from datetime import datetime


class ExtraVentaLinea(BaseModel):
    id_extra: int
    nombre: str
    precio: float


class ExtraVenta(BaseModel):
    id_extra: int
    nombre: str
    precio: float
    tipo: str
    activo: bool

    class Config:
        from_attributes = True


class DetalleVentaItem(BaseModel):
    id_producto: int
    cantidad: float
    precio_unitario: float
    extras: List[ExtraVentaLinea] = []


class VentaCreate(BaseModel):
    id_usuario: int
    numero_mesa: int
    forma_pago: str
    detalles: List[DetalleVentaItem]


class VentaResponse(BaseModel):
    id_venta: int
    fecha_hora: datetime
    id_usuario: int
    numero_mesa: int
    total: float
    forma_pago: str

    class Config:
        from_attributes = True
