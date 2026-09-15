from typing import List, Optional

from app.exceptions import DatosInvalidosException
from app.models.models import UsuarioModel
from app.utils.acciones import acciones_efectivas, serializar_acciones
from app.utils.modulos import (
    modulos_efectivos,
    modulos_personalizados,
    serializar_modulos,
)

MODULOS_VACIOS_DETALLE = (
    "No se permiten módulos vacíos; usa null para los defaults del rol"
)


def usuario_a_out(usuario: UsuarioModel) -> dict:
    return {
        "id_usuario": usuario.id_usuario,
        "nombre": usuario.nombre,
        "usuario_login": usuario.usuario_login,
        "rol": usuario.rol,
        "activo": bool(getattr(usuario, "activo", True)),
        "modulos": modulos_personalizados(usuario),
        "modulos_efectivos": modulos_efectivos(usuario),
        "permisos_acciones": acciones_efectivas(usuario),
    }


def aplicar_modulos(usuario: UsuarioModel, modulos: Optional[List[str]]) -> None:
    if modulos is None:
        usuario.modulos_json = None
        return
    if len(modulos) == 0:
        raise DatosInvalidosException(MODULOS_VACIOS_DETALLE)
    serializado = serializar_modulos(modulos)
    if serializado == "[]":
        raise DatosInvalidosException(MODULOS_VACIOS_DETALLE)
    usuario.modulos_json = serializado


def aplicar_acciones(usuario: UsuarioModel, acciones: Optional[List[str]]) -> None:
    if acciones is None:
        return
    usuario.permisos_acciones_json = serializar_acciones(acciones)
