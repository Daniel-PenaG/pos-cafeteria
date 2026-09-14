import json
from typing import List

from app.constants.modulos import ALL_MODULE_PATHS, ROLE_DEFAULT_MODULES
from app.constants.roles import ADMIN, normalizar_rol
from app.models.models import UsuarioModel


def modulos_personalizados(usuario: UsuarioModel) -> List[str] | None:
    """Lista guardada o None si no hay personalización (usar defaults).

    null / ausente → None (defaults del rol).
    [] → lista vacía (sin módulos).
    """
    raw = usuario.modulos_json
    if raw is None or str(raw).strip() == "":
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [p for p in data if p in ALL_MODULE_PATHS]
    except (json.JSONDecodeError, TypeError):
        return None
    return None


def modulos_efectivos(usuario: UsuarioModel) -> List[str]:
    rol = normalizar_rol(usuario.rol)
    if rol == ADMIN:
        return list(ALL_MODULE_PATHS)

    personalizados = modulos_personalizados(usuario)
    if personalizados is not None:
        return personalizados

    return list(ROLE_DEFAULT_MODULES.get(rol, []))


def serializar_modulos(modulos: List[str] | None) -> str | None:
    if modulos is None:
        return None
    valid = [p for p in modulos if p in ALL_MODULE_PATHS]
    return json.dumps(valid)
