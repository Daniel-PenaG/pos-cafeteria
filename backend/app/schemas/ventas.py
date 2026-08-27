from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ExtraVentaLinea(BaseModel):
    id_extra: int
    nombre: str
    precio: float
    id_insumo: Optional[int] = None
    cantidad_insumo: float = 1


class ExtraVenta(BaseModel):
    id_extra: int
    nombre: str
    precio: float
    costo: float = 0
    tipo: str
    activo: bool
    id_insumo: Optional[int] = None
    cantidad_insumo: float = 1
    unidad: Optional[str] = None

    class Config:
        from_attributes = True


class DetalleVentaItem(BaseModel):
    id_producto: int
    cantidad: float
    precio_unitario: float
    extras: List[ExtraVentaLinea] = []
    id_promocion: Optional[int] = None
    precio_original: Optional[float] = None


class VentaCreate(BaseModel):
    id_usuario: int
    numero_mesa: int
    forma_pago: str
    id_cliente: Optional[int] = None
    para_llevar: bool = False
    detalles: List[DetalleVentaItem]


class VentaResponse(BaseModel):
    id_venta: int
    fecha_hora: datetime
    id_usuario: int
    numero_mesa: int
    total: float
    forma_pago: str
    id_cliente: Optional[int] = None
    puntos_generados: int = 0
    cliente_nombre: Optional[str] = None
    cliente_puntos_saldo: Optional[int] = None
    para_llevar: bool = False
    advertencias_stock: List[str] = []

    class Config:
        from_attributes = True
