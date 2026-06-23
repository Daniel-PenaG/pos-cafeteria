from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from datetime import datetime


TIPOS_PROMO = {"PORCENTAJE", "PRECIO_FIJO", "DOS_X_UNO"}


class PromocionBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    tipo: str
    valor: float = Field(..., gt=0)
    activa: bool = True
    aplica_toda_tienda: bool = False
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    hora_inicio: Optional[str] = None
    hora_fin: Optional[str] = None
    dias_semana: Optional[str] = None
    margen_minimo: Optional[float] = Field(None, ge=0, le=100)
    ids_productos: List[int] = Field(default_factory=list)
    ids_categorias: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_tipo(self):
        t = (self.tipo or "").strip().upper()
        if t not in TIPOS_PROMO:
            raise ValueError(f"Tipo debe ser: {', '.join(sorted(TIPOS_PROMO))}")
        self.tipo = t
        if self.tipo == "PORCENTAJE" and self.valor > 100:
            raise ValueError("El porcentaje no puede ser mayor a 100")
        if not self.aplica_toda_tienda and not self.ids_productos and not self.ids_categorias:
            raise ValueError("Indica productos, categorías o marca 'toda la tienda'")
        return self


class PromocionCreate(PromocionBase):
    pass


class PromocionUpdate(PromocionBase):
    pass


class Promocion(PromocionBase):
    id_promocion: int

    class Config:
        from_attributes = True


class PromocionCalculada(BaseModel):
    id_promocion: Optional[int] = None
    nombre_promocion: Optional[str] = None
    tipo: Optional[str] = None
    precio_base: float
    precio_base_promo: float
    precio_extras: float
    precio_unitario: float
    precio_original_unitario: float
    descuento_unitario: float
    costo_unitario: float
    margen_porcentaje: Optional[float] = None
    margen_ok: bool = True
    mensaje: Optional[str] = None


class PromocionCalcularRequest(BaseModel):
    id_producto: int
    id_promocion: Optional[int] = None
    cantidad: float = Field(1, gt=0)
    precio_extras: float = Field(0, ge=0)


class PromocionResumen(BaseModel):
    total_ventas_con_promo: int
    total_descuento: float
    promociones_usadas: List[dict]
