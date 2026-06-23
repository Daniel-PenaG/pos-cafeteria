import json
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


def _segundos_transcurridos(inicio: datetime | None) -> int | None:
    if not inicio:
        return None
    return max(0, int((datetime.now() - inicio).total_seconds()))


class ExtraLineaPedido(BaseModel):
    id_extra: int
    nombre: str
    precio: float


class DetallePedidoLinea(BaseModel):
    id_detalle_pedido: int
    id_producto: int
    nombre_producto: str
    cantidad: float
    cantidad_lista: float
    cantidad_pendiente: float
    precio_unitario: float
    precio_original: Optional[float] = None
    descuento_unitario: Optional[float] = None
    id_promocion: Optional[int] = None
    nombre_promocion: Optional[str] = None
    extras: List[ExtraLineaPedido] = []
    en_comanda: bool
    line_key: str


class Pedido(BaseModel):
    id_pedido: int
    numero_mesa: int
    estado: str
    id_cliente: Optional[int] = None
    id_usuario: int
    id_venta: Optional[int] = None
    fecha_apertura: datetime
    total: float
    lineas: List[DetallePedidoLinea] = []
    cliente_nombre: Optional[str] = None


class PedidoResumen(BaseModel):
    id_pedido: int
    numero_mesa: int
    total: float
    num_lineas: int
    pendientes_comanda: int


class PedidoLineaCreate(BaseModel):
    id_producto: int
    cantidad: float
    precio_unitario: float
    precio_original: Optional[float] = None
    id_promocion: Optional[int] = None
    extras: List[ExtraLineaPedido] = []
    enviar_comanda: bool = True


class PedidoLineaUpdate(BaseModel):
    cantidad: float


class PedidoClienteUpdate(BaseModel):
    id_cliente: Optional[int] = None


class PedidoCobrar(BaseModel):
    id_usuario: int
    forma_pago: str
    id_cliente: Optional[int] = None


class ComandaLinea(BaseModel):
    id_detalle_pedido: int
    id_pedido: int
    numero_mesa: int
    nombre_producto: str
    cantidad: float
    cantidad_lista: float
    cantidad_pendiente: float
    extras: List[ExtraLineaPedido] = []
    nombre_promocion: Optional[str] = None
    fecha_envio_comanda: Optional[datetime] = None
    segundos_en_preparacion: Optional[int] = None


class ComandaMarcarListo(BaseModel):
    cantidad: float = 1
