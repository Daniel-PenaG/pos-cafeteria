import json
from typing import List, Optional

from app.models.models import UsuarioModel
from app.utils.modulos import modulos_efectivos, serializar_modulos


def usuario_a_out(usuario: UsuarioModel) -> dict:
    modulos_custom = None
    if usuario.modulos_json:
        try:
            modulos_custom = json.loads(usuario.modulos_json)
        except (json.JSONDecodeError, TypeError):
            modulos_custom = None

    return {
        "id_usuario": usuario.id_usuario,
        "nombre": usuario.nombre,
        "usuario_login": usuario.usuario_login,
        "rol": usuario.rol,
        "modulos": modulos_custom,
        "modulos_efectivos": modulos_efectivos(usuario),
    }


def aplicar_modulos(usuario: UsuarioModel, modulos: Optional[List[str]]) -> None:
    if modulos is None:
        return
    if len(modulos) == 0:
        usuario.modulos_json = None
        return
    usuario.modulos_json = serializar_modulos(modulos)
