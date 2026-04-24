from pydantic import BaseModel
from typing import Optional

#Categgoria

class Categoriabase(BaseModel):
    nombre: str

class CategoriaCreate(Categoriabase):
    pass

class Categoria(Categoriabase):
    id_categoria: int

    class Config:
        orm_mode = True

#Productos

class ProductoBase(BaseModel):
    nombre: str
    id_categoria: int
    precio_venta: float
    activo: Optional[bool] = True

class ProductoCreate(ProductoBase):
    pass

class Producto(ProductoBase):
    id_producto:int

    class Config:
        orm_mode = True

#Onsumo
class InsumoBase(BaseModel):
    nombre: str
    unidad: str
    stock_actual: float
    stock_minimo: float
    costo_unitario: float

class InsumoCreate(InsumoBase):
    pass

class Insumo(InsumoBase):
    id_insumo: int

    class Config:
        orm_mode = True