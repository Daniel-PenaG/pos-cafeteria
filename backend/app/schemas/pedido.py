import json
from pydantic import BaseModel, Field
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
    costo: Optional[float] = None
    id_insumo: Optional[int] = None
    cantidad_insumo: float = 1


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
    comentario: Optional[str] = None
    line_key: str
    fecha_envio_comanda: Optional[str] = None
    fecha_listo_comanda: Optional[str] = None
    segundos_preparacion: Optional[int] = None


class Pedido(BaseModel):
    id_pedido: int
    numero_mesa: int
    para_llevar: bool = False
    estado: str
    id_cliente: Optional[int] = None
    id_usuario: int
    id_venta: Optional[int] = None
    fecha_apertura: Optional[str] = None
    total: float
    lineas: List[DetallePedidoLinea] = []
    cliente_nombre: Optional[str] = None


class PedidoResumen(BaseModel):
    id_pedido: int
    numero_mesa: int
    para_llevar: bool = False
    total: float
    num_lineas: int
    pendientes_comanda: int
    fecha_apertura: Optional[str] = None
    segundos_activa: Optional[int] = None
    cliente_nombre: Optional[str] = None
    lineas: List[DetallePedidoLinea] = []


class PedidoLineaCreate(BaseModel):
    id_producto: int
    cantidad: float
    precio_unitario: float
    precio_original: Optional[float] = None
    id_promocion: Optional[int] = None
    extras: List[ExtraLineaPedido] = []
    enviar_comanda: bool = False
    comentario: Optional[str] = Field(None, max_length=300)


class PedidoLineaUpdate(BaseModel):
    cantidad: float


class PedidoClienteUpdate(BaseModel):
    id_cliente: Optional[int] = None


class PedidoCobrar(BaseModel):
    id_usuario: int
    forma_pago: str
    id_cliente: Optional[int] = None


class ComboPedidoCreate(BaseModel):
    id_promocion: int
    cantidad: float = Field(1, gt=0)
    enviar_comanda: bool = False


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
    comentario: Optional[str] = None
    fecha_envio_comanda: Optional[datetime] = None
    segundos_en_preparacion: Optional[int] = None


class ComandaMarcarListo(BaseModel):
    cantidad: float = 1
