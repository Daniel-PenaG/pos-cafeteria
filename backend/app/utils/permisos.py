from fastapi import Depends, HTTPException, status

from app.models.models import UsuarioModel
from app.utils.acciones import tiene_accion
from app.utils.deps import get_current_user
from app.utils.modulos import modulos_efectivos


def require_module(*paths: str):
    """Exige al menos una de las rutas de módulo (normalizadas en constants/modulos)."""
    requeridas = tuple(paths)

    def checker(user: UsuarioModel = Depends(get_current_user)) -> UsuarioModel:
        efectivos = set(modulos_efectivos(user))
        if any(p in efectivos for p in requeridas):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para esta acción",
        )

    return checker


def require_accion(codigo: str):
    def checker(user: UsuarioModel = Depends(get_current_user)) -> UsuarioModel:
        if tiene_accion(user, codigo):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para esta acción",
        )

    return checker
