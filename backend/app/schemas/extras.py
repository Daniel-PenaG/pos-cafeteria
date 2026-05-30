from pydantic import BaseModel, Field, model_validator
from typing import List, Optional


class ExtraVentaCatalogoBase(BaseModel):
    nombre: str
    cantidad: float = Field(1, gt=0)
    costo_unitario: float = Field(0, ge=0)
    usar_precio_manual: bool = False
    precio_personalizado: Optional[float] = Field(None, ge=0)
    tipo: str = "OTRO"
    activo: bool = True
    unidad: Optional[str] = None

    @model_validator(mode="after")
    def validar_precio_manual(self):
        if self.usar_precio_manual:
            if self.precio_personalizado is None or self.precio_personalizado < 0:
                raise ValueError("Indica un precio personalizado válido")
        return self


class ExtraVentaCatalogoCreate(ExtraVentaCatalogoBase):
    pass


class ExtraVentaCatalogoUpdate(ExtraVentaCatalogoBase):
    pass


class ExtraVentaCatalogo(ExtraVentaCatalogoBase):
    id_extra: int
    precio: float = Field(..., ge=0)
    id_insumo_origen: Optional[int] = None

    class Config:
        from_attributes = True


class ExtraVentaDesdeInsumo(BaseModel):
    cantidad: float = Field(1, gt=0)
    costo_unitario: Optional[float] = Field(None, ge=0)
    usar_precio_manual: bool = False
    precio_personalizado: Optional[float] = Field(None, ge=0)
    tipo: str = "OTRO"
    activo: bool = True

    @model_validator(mode="after")
    def validar_precio_manual(self):
        if self.usar_precio_manual and self.precio_personalizado is None:
            raise ValueError("Indica un precio personalizado")
        return self


class InsumoParaImportar(BaseModel):
    id_insumo: int
    nombre: str
    unidad: str
    costo_unitario: float


class CategoriaExtrasConfig(BaseModel):
    ids_extras: List[int] = Field(default_factory=list)


class CategoriaExtrasConfigResponse(BaseModel):
    id_categoria: int
    nombre_categoria: str
    ids_extras: List[int] = []
    extras: List[ExtraVentaCatalogo] = []
