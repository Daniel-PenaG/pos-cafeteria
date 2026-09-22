from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.constants.caja import TERMINALES_CAJA
from app.database import get_db
from app.models.models import UsuarioModel
from app.schemas.caja import CajaAbrir, CajaAnular, CajaCerrar, CajaMovimientoCreate
from app.services.caja_service import (
    anular_cierre,
    abrir_caja,
    cerrar_caja,
    iniciar_arqueo,
    listar_sesiones,
    registrar_movimiento,
    revisar_cierre,
    sesion_a_dict,
    sesion_activa_usuario,
)
from app.exceptions import RecursoNoEncontradoException
from app.utils.deps import get_current_user
from app.utils.permisos import require_module
from app.constants.roles import ADMIN, normalizar_rol
from app.exceptions import DatosInvalidosException

router = APIRouter(prefix="/caja", tags=["Caja"])


@router.get("/terminales", dependencies=[Depends(require_module("/cierre-caja"))])
def terminales():
    return [{"codigo": t} for t in TERMINALES_CAJA]


@router.get("/sesion", dependencies=[Depends(require_module("/cierre-caja"))])
def mi_sesion(
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    from app.services.caja_service import caja_requerida_para_cobrar

    requerida = caja_requerida_para_cobrar()
    sesion = sesion_activa_usuario(db, current.id_usuario)
    if not sesion:
        return {"sesion": None, "caja_requerida": requerida}
    ciego = sesion.estado == "EN_ARQUEO"
    data = sesion_a_dict(db, sesion, ciego=ciego)
    data["caja_requerida"] = requerida
    return {"sesion": data}


@router.post("/abrir", dependencies=[Depends(require_module("/cierre-caja"))])
def abrir(
    data: CajaAbrir,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    return abrir_caja(
        db,
        current,
        fondo_inicial=data.fondo_inicial,
        terminal=data.terminal,
        observacion=data.observacion,
        operation_id=data.operation_id,
    )


@router.post("/movimientos", dependencies=[Depends(require_module("/cierre-caja"))])
def movimiento(
    data: CajaMovimientoCreate,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    return registrar_movimiento(
        db,
        current,
        tipo=data.tipo,
        importe=data.importe,
        motivo=data.motivo,
        metodo=data.metodo,
        referencia=data.referencia,
        id_gasto=data.id_gasto,
        operation_id=data.operation_id,
    )


@router.post("/arqueo", dependencies=[Depends(require_module("/cierre-caja"))])
def arqueo(
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    return iniciar_arqueo(db, current)


@router.post("/cerrar", dependencies=[Depends(require_module("/cierre-caja"))])
def cerrar(
    data: CajaCerrar,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    return cerrar_caja(
        db,
        current,
        denominaciones=[d.model_dump() for d in data.denominaciones],
        declarado_efectivo=data.declarado_efectivo,
        declarado_transferencia=data.declarado_transferencia,
        declarado_tarjeta=data.declarado_tarjeta,
        captura_directa=data.captura_directa,
        ref_terminal=data.ref_terminal,
        lote_terminal=data.lote_terminal,
        ref_transferencia=data.ref_transferencia,
        observacion=data.observacion,
        forzar=data.forzar,
        operation_id=data.operation_id,
    )


@router.get("/sesiones", dependencies=[Depends(require_module("/cierres-dia"))])
def sesiones(
    estado: Optional[str] = None,
    id_usuario: Optional[int] = None,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    if normalizar_rol(current.rol) != ADMIN:
        raise DatosInvalidosException("Solo administración puede listar todas las sesiones")
    return listar_sesiones(db, estado=estado, id_usuario=id_usuario)


@router.get("/sesiones/{id_sesion}", dependencies=[Depends(require_module("/cierre-caja", "/cierres-dia"))])
def detalle_sesion(
    id_sesion: int,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    from app.models.models import SesionCajaModel

    sesion = db.get(SesionCajaModel, id_sesion)
    if not sesion:
        raise RecursoNoEncontradoException("Sesión no encontrada")
    if normalizar_rol(current.rol) != ADMIN and int(sesion.id_usuario) != int(current.id_usuario):
        raise DatosInvalidosException("No puedes ver la caja de otro usuario")
    return sesion_a_dict(db, sesion)


@router.post("/sesiones/{id_sesion}/revisar", dependencies=[Depends(require_module("/cierres-dia"))])
def revisar(
    id_sesion: int,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    return revisar_cierre(db, current, id_sesion)


@router.post("/sesiones/{id_sesion}/anular", dependencies=[Depends(require_module("/cierres-dia"))])
def anular(
    id_sesion: int,
    data: CajaAnular,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    return anular_cierre(db, current, id_sesion, data.motivo)
