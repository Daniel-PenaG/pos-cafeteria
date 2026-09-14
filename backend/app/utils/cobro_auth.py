from fastapi import HTTPException, status

from app.constants.acciones import (
    COBRAR_DESDE_COMANDERA,
    ORIGEN_COMANDERA,
    ORIGEN_VENTAS,
    ORIGENES_COBRO,
)
from app.models.models import UsuarioModel
from app.utils.acciones import tiene_accion
from app.utils.modulos import modulos_efectivos


def normalizar_origen_cobro(origen: str | None) -> str:
    valor = (origen or ORIGEN_VENTAS).strip().upper()
    if valor not in ORIGENES_COBRO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Origen de cobro inválido",
        )
    return valor


def autorizar_cobro(usuario: UsuarioModel, origen: str | None) -> str:
    """Cobro desde Ventas requiere módulo de ventas. Desde Comandera, la acción."""
    origen_n = normalizar_origen_cobro(origen)
    mods = set(modulos_efectivos(usuario))
    if origen_n == ORIGEN_COMANDERA:
        if not tiene_accion(usuario, COBRAR_DESDE_COMANDERA):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta acción",
            )
        if "/comandera" not in mods:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta acción",
            )
        return origen_n
    if not mods.intersection({"/ventas", "/mesas-activas", "/ventas-para-llevar"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para esta acción",
        )
    return origen_n
