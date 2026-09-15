from fastapi import HTTPException, status

from app.constants.acciones import (
    COBRAR_DESDE_COMANDERA,
    ORIGEN_COMANDERA,
    ORIGEN_VENTAS,
    ORIGENES_COBRO,
)
from app.models.models import UsuarioModel
from app.utils.acciones import tiene_accion
from app.utils.permisos import exigir_modulo, exigir_modulo_pedido


def normalizar_origen_cobro(origen: str | None) -> str:
    valor = (origen or ORIGEN_VENTAS).strip().upper()
    if valor not in ORIGENES_COBRO:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Origen de cobro inválido",
        )
    return valor


def autorizar_cobro(
    usuario: UsuarioModel,
    origen: str | None,
    para_llevar: bool = False,
) -> str:
    """Solo para POST /pedidos/{id}/cobrar. POST /ventas/ no llama esta función."""
    origen_n = normalizar_origen_cobro(origen)
    if origen_n == ORIGEN_COMANDERA:
        if not tiene_accion(usuario, COBRAR_DESDE_COMANDERA):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta acción",
            )
        exigir_modulo(usuario, "/comandera")
        return origen_n
    exigir_modulo_pedido(usuario, para_llevar)
    return origen_n
