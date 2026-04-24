from pydantic import BaseModel

class RecetaBase(BaseModel):
    id_producto: int
    id_insumo: int
    cantidad_por_producto: float

class RecetaCreate(RecetaBase):
    pass

class Receta(RecetaBase):
    id_receta: int

    class Config:
        from_attributes = True
