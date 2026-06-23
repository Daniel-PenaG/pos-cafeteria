import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.schemas.ventas import VentaCreate, VentaResponse, ExtraVenta
from app.services.extras_venta_service import extras_para_producto, extras_para_categoria
from app.services.venta_service import registrar_venta
from app.exceptions import DatosInvalidosException

router = APIRouter(prefix="/ventas", tags=["Ventas"])


@router.get("/extras", response_model=List[ExtraVenta])
def listar_extras_venta(
    id_producto: Optional[int] = None,
    id_categoria: Optional[int] = None,
    db: Session = Depends(get_db),
):
    if id_producto:
        return extras_para_producto(db, id_producto)
    if id_categoria:
        return extras_para_categoria(db, id_categoria)
    raise DatosInvalidosException("Indica id_producto o id_categoria")


@router.post("/", response_model=VentaResponse)
def registrar_venta_endpoint(data: VentaCreate, db: Session = Depends(get_db)):
    return registrar_venta(db, data)
