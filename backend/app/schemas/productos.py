from pydantic import BaseModel
from typing import Optional

#Categgoria

class Categoriabase(BaseModel):
    nombre: str

class CategoriaCreate(Categoriabase):
    pass

class CategoriaUpdate(Categoriabase):
    pass

class Categoria(Categoriabase):
    id_categoria: int

    class Config:
        from_attributes = True

#Productos

class ProductoBase(BaseModel):
    nombre: str
    id_categoria: int
    precio_venta: float
    activo: Optional[bool] = True

class ProductoCreate(ProductoBase):
    pass

class ProductoUpdate(ProductoBase):
    pass

class Producto(ProductoBase):
    id_producto:int

    class Config:
        from_attributes = True

#Onsumo
class InsumoBase(BaseModel):
    nombre: str
    unidad: str
    stock_bodega: float = 0
    stock_cafeteria: float = 0
    stock_minimo: float = 0
    costo_unitario: Optional[float] = None

class InsumoCreate(InsumoBase):
    pass

class InsumoUpdate(InsumoBase):
    pass

class Insumo(InsumoBase):
    id_insumo: int
    stock_actual: float = 0

    class Config:
        from_attributes = True


class InsumoTraspaso(BaseModel):
    cantidad: float


class InsumoActualizado(Insumo):
    productos_precio_actualizados: int = 0
