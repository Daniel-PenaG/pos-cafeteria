import json
from typing import List

from app.constants.modulos import ALL_MODULE_PATHS, ROLE_DEFAULT_MODULES
from app.constants.roles import ADMIN, normalizar_rol
from app.models.models import UsuarioModel


def modulos_efectivos(usuario: UsuarioModel) -> List[str]:
    rol = normalizar_rol(usuario.rol)
    if rol == ADMIN:
        return list(ALL_MODULE_PATHS)

    if usuario.modulos_json:
        try:
            data = json.loads(usuario.modulos_json)
            if isinstance(data, list) and data:
                valid = [p for p in data if p in ALL_MODULE_PATHS]
                if valid:
                    return valid
        except (json.JSONDecodeError, TypeError):
            pass

    return list(ROLE_DEFAULT_MODULES.get(rol, []))


def serializar_modulos(modulos: List[str] | None) -> str | None:
    if not modulos:
        return None
    valid = [p for p in modulos if p in ALL_MODULE_PATHS]
    return json.dumps(valid) if valid else None
