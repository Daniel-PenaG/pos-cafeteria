from pydantic import BaseModel, Field
from typing import List, Optional


class MesasConfigResponse(BaseModel):
    mesas: List[int]


class MesaAgregarRequest(BaseModel):
    numero: Optional[int] = Field(
        None,
        ge=1,
        le=98,
        description="Número de mesa; si se omite, se asigna el siguiente disponible",
    )
