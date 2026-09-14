from pydantic import BaseModel, Field
from typing import List, Optional

from app.utils.timezone_mx import segundos_desde


def _segundos_transcurridos(inicio) -> int | None:
    """Segundos transcurridos en UTC. Nunca negativo."""
    return segundos_desde(inicio)


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
    id_pedido: Optional[int] = None
    numero_mesa: int
    para_llevar: bool = False
    estado: str
    id_cliente: Optional[int] = None
    id_usuario: Optional[int] = None
    id_venta: Optional[int] = None
    fecha_apertura: Optional[str] = None
    total: float
    lineas: List[DetallePedidoLinea] = []
    cliente_nombre: Optional[str] = None
    subtotal_normal: Optional[float] = None
    descuento_promociones: Optional[float] = None
    resumen_promociones: List[dict] = []
    sin_pedido: bool = False


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
    operation_id: Optional[str] = Field(None, max_length=64)


class PedidoLineaUpdate(BaseModel):
    cantidad: Optional[float] = None
    comentario: Optional[str] = Field(None, max_length=300)


class PedidoClienteUpdate(BaseModel):
    id_cliente: Optional[int] = None


class PedidoCobrar(BaseModel):
    id_usuario: Optional[int] = None
    forma_pago: str
    id_cliente: Optional[int] = None
    origen: Optional[str] = "VENTAS"


class ComboPedidoCreate(BaseModel):
    id_promocion: int
    cantidad: float = Field(1, gt=0)
    enviar_comanda: bool = False
    operation_id: Optional[str] = Field(None, max_length=64)


class ComandaLinea(BaseModel):
    id_detalle_pedido: int
    id_pedido: int
    numero_mesa: int
    para_llevar: bool = False
    nombre_producto: str
    cantidad: float
    cantidad_lista: float
    cantidad_pendiente: float
    extras: List[ExtraLineaPedido] = []
    nombre_promocion: Optional[str] = None
    comentario: Optional[str] = None
    fecha_envio_comanda: Optional[str] = None
    segundos_en_preparacion: Optional[int] = None


class ComandaMarcarListo(BaseModel):
    cantidad: float = 1
