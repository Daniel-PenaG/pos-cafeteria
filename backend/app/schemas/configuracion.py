from pydantic import BaseModel, Field
from datetime import datetime


class ConfiguracionBase(BaseModel):
    margen_ganancia: float = Field(..., ge=0, le=100, description="Margen de ganancia en porcentaje")
    gastos_fijos: float = Field(..., ge=0, description="Gastos fijos mensuales")


class ConfiguracionCreate(ConfiguracionBase):
    pass


class ConfiguracionUpdate(ConfiguracionBase):
    pass


class Configuracion(ConfiguracionBase):
    id_configuracion: int
    fecha_actualizacion: datetime

    class Config:
        from_attributes = True


class ConfiguracionActualizada(Configuracion):
    productos_precio_actualizados: int = 0
