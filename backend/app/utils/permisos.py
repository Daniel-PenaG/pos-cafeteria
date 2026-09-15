from fastapi import Depends, HTTPException, status

from app.models.models import UsuarioModel
from app.utils.acciones import tiene_accion
from app.utils.deps import get_current_user
from app.utils.modulos import modulos_efectivos

FORBIDDEN_DETAIL = "No tienes permiso para esta acción"


def tiene_algun_modulo(user: UsuarioModel, *paths: str) -> bool:
    efectivos = set(modulos_efectivos(user))
    return any(p in efectivos for p in paths)


def exigir_modulo(user: UsuarioModel, *paths: str) -> None:
    if not tiene_algun_modulo(user, *paths):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=FORBIDDEN_DETAIL,
        )


def modulo_tipo_pedido(para_llevar: bool) -> str:
    return "/ventas-para-llevar" if para_llevar else "/ventas"


def exigir_modulo_pedido(user: UsuarioModel, para_llevar: bool) -> None:
    exigir_modulo(user, modulo_tipo_pedido(bool(para_llevar)))


def require_module(*paths: str):
    """Exige al menos una de las rutas de módulo (normalizadas en constants/modulos)."""
    requeridas = tuple(paths)

    def checker(user: UsuarioModel = Depends(get_current_user)) -> UsuarioModel:
        exigir_modulo(user, *requeridas)
        return user

    return checker


def require_accion(codigo: str):
    def checker(user: UsuarioModel = Depends(get_current_user)) -> UsuarioModel:
        if tiene_accion(user, codigo):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=FORBIDDEN_DETAIL,
        )

    return checker
