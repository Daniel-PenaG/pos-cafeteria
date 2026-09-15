from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AuditoriaModel
from app.utils.deps import require_admin
from app.utils.permisos import require_module
from app.utils.timezone_mx import bounds_utc_naive_for_mx_date

router = APIRouter(
    prefix="/auditoria",
    tags=["Auditoría"],
    dependencies=[Depends(require_admin), Depends(require_module("/auditoria", "/usuarios"))],
)


@router.get("/")
def listar_auditoria(
    db: Session = Depends(get_db),
    fecha: Optional[date] = None,
    id_usuario: Optional[int] = None,
    accion: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    q = db.query(AuditoriaModel)
    if fecha:
        inicio, fin = bounds_utc_naive_for_mx_date(fecha)
        q = q.filter(AuditoriaModel.fecha_hora >= inicio, AuditoriaModel.fecha_hora <= fin)
    if id_usuario:
        q = q.filter(AuditoriaModel.id_usuario == id_usuario)
    if accion:
        q = q.filter(AuditoriaModel.accion == accion.strip().upper())
    total = q.count()
    filas = (
        q.order_by(AuditoriaModel.fecha_hora.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id_auditoria": f.id_auditoria,
                "id_usuario": f.id_usuario,
                "usuario_login_intentado": f.usuario_login_intentado,
                "accion": f.accion,
                "entidad": f.entidad,
                "entidad_id": f.entidad_id,
                "detalles_json": f.detalles_json,
                "origen": f.origen,
                "fecha_hora": f.fecha_hora,
                "ip": f.ip,
            }
            for f in filas
        ],
    }
