from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional

from app.database import get_db
from app.models.models import UsuarioModel
from app.schemas.cierre import CierreCajaCreate, ResumenCierreUsuario
from app.services.cierre_service import (
    resumen_ventas_usuario,
    registrar_cierre,
    listar_cierres_dia,
)
from app.utils.deps import get_current_user, require_admin, require_pos
from app.constants.roles import ADMIN, normalizar_rol
from app.exceptions import DatosInvalidosException

router = APIRouter(prefix="/cierres", tags=["Cierre de caja"])


@router.get("/resumen", response_model=ResumenCierreUsuario, dependencies=[Depends(require_pos)])
def obtener_resumen_cierre(
    fecha: Optional[date] = None,
    id_usuario: Optional[int] = None,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    es_admin = normalizar_rol(current.rol) == ADMIN
    uid = id_usuario if es_admin and id_usuario else current.id_usuario
    if not es_admin and id_usuario and id_usuario != current.id_usuario:
        raise DatosInvalidosException("No puedes ver el cierre de otro usuario")
    try:
        return resumen_ventas_usuario(db, uid, fecha)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo cargar el resumen de cierre: {exc}",
        ) from exc


@router.post("/", dependencies=[Depends(require_pos)])
def crear_cierre(
    data: CierreCajaCreate,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    return registrar_cierre(
        db,
        current.id_usuario,
        data.efectivo_contado,
        data.notas,
        data.fecha,
    )


@router.get("/", dependencies=[Depends(require_admin)])
def listar_cierres(
    fecha: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return listar_cierres_dia(db, fecha)
