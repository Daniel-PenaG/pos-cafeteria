from pydantic import BaseModel, Field, validator
from typing import List, Optional
from decimal import Decimal


class RecetaInsumoBase(BaseModel):
    id_insumo: int
    cantidad: float = Field(..., gt=0, description="Cantidad debe ser mayor a 0")


class RecetaInsumoDetalle(BaseModel):
    id_insumo: int
    nombre_insumo: str
    cantidad: float
    costo_unitario: float
    subtotal: float

    class Config:
        from_attributes = True


class RecetaCreate(BaseModel):
    id_producto: int
    nombre: str
    descripcion: Optional[str] = None
    activo: bool = True
    insumos: List[RecetaInsumoBase] = Field(..., min_items=1, description="Debe tener al menos un insumo")

    @validator("nombre")
    def nombre_no_vacio(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("El nombre no puede estar vacío")
        return v


class RecetaUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    activo: Optional[bool] = None
    insumos: Optional[List[RecetaInsumoBase]] = None


class RecetaResponse(BaseModel):
    id_receta: int
    id_producto: int
    nombre: str
    descripcion: Optional[str]
    activo: bool
    costo_total: float
    insumos: List[RecetaInsumoDetalle]
    precio_venta_producto: float

    class Config:
        from_attributes = True
