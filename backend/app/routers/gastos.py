from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models.models import GastoModel, UsuarioModel
from app.schemas.gasto import GastoCreate, GastoUpdate, GastoResponse
from app.utils.deps import get_current_user, require_admin
from app.utils.timezone_mx import today_mx, bounds_utc_naive_for_mx_date, now_utc_naive

router = APIRouter(
    prefix="/gastos",
    tags=["Gastos"],
    dependencies=[Depends(require_admin)],
)


def _gasto_a_response(gasto: GastoModel, usuario: Optional[UsuarioModel] = None) -> GastoResponse:
    return GastoResponse(
        id_gasto=gasto.id_gasto,
        descripcion=gasto.descripcion,
        monto=float(gasto.monto),
        fecha_hora=gasto.fecha_hora,
        id_usuario=gasto.id_usuario,
        usuario_nombre=usuario.nombre if usuario else None,
    )


@router.get("/", response_model=List[GastoResponse])
def listar_gastos(
    fecha: Optional[date] = Query(None, description="YYYY-MM-DD; default hoy"),
    db: Session = Depends(get_db),
):
    dia = fecha or today_mx()
    inicio, fin = bounds_utc_naive_for_mx_date(dia)
    rows = (
        db.query(GastoModel, UsuarioModel)
        .join(UsuarioModel, UsuarioModel.id_usuario == GastoModel.id_usuario)
        .filter(GastoModel.fecha_hora >= inicio, GastoModel.fecha_hora <= fin)
        .order_by(GastoModel.fecha_hora.desc())
        .all()
    )
    return [_gasto_a_response(g, u) for g, u in rows]


@router.post("/", response_model=GastoResponse, status_code=201)
def registrar_gasto(
    data: GastoCreate,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    descripcion = data.descripcion.strip()
    if not descripcion:
        raise HTTPException(status_code=400, detail="La descripción es obligatoria")

    gasto = GastoModel(
        descripcion=descripcion,
        monto=data.monto,
        fecha_hora=now_utc_naive(),
        id_usuario=current.id_usuario,
    )
    db.add(gasto)
    db.commit()
    db.refresh(gasto)
    return _gasto_a_response(gasto, current)


@router.put("/{id_gasto}", response_model=GastoResponse)
def actualizar_gasto(
    id_gasto: int,
    data: GastoUpdate,
    db: Session = Depends(get_db),
):
    gasto = db.query(GastoModel).filter(GastoModel.id_gasto == id_gasto).first()
    if not gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")

    if data.descripcion is not None:
        desc = data.descripcion.strip()
        if not desc:
            raise HTTPException(status_code=400, detail="La descripción es obligatoria")
        gasto.descripcion = desc
    if data.monto is not None:
        gasto.monto = data.monto

    db.commit()
    db.refresh(gasto)
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id_usuario == gasto.id_usuario).first()
    return _gasto_a_response(gasto, usuario)


@router.delete("/{id_gasto}")
def eliminar_gasto(id_gasto: int, db: Session = Depends(get_db)):
    gasto = db.query(GastoModel).filter(GastoModel.id_gasto == id_gasto).first()
    if not gasto:
        raise HTTPException(status_code=404, detail="Gasto no encontrado")
    db.delete(gasto)
    db.commit()
    return {"message": "Gasto eliminado"}
