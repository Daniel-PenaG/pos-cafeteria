from pydantic import BaseModel
from typing import List
from datetime import datetime


class DetalleCompraItem(BaseModel):
    id_insumo: int
    cantidad: float
    costo_unitario: float


class CompraCreate(BaseModel):
    proveedor: str
    detalles: List[DetalleCompraItem]


class CompraResponse(BaseModel):
    id_compra: int
    fecha_hora: datetime
    proveedor: str
    total: float

    class Config:
        from_attributes = True
