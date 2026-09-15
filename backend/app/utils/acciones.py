import json
from typing import List

from app.constants.acciones import ALL_ACCIONES, ROLE_DEFAULT_ACCIONES
from app.constants.roles import ADMIN, normalizar_rol
from app.models.models import UsuarioModel


def acciones_efectivas(usuario: UsuarioModel) -> List[str]:
    rol = normalizar_rol(usuario.rol)
    if rol == ADMIN:
        return list(ALL_ACCIONES)

    raw = getattr(usuario, "permisos_acciones_json", None)
    if raw is not None and str(raw).strip() != "":
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [p for p in data if p in ALL_ACCIONES]
        except (json.JSONDecodeError, TypeError):
            pass
    return list(ROLE_DEFAULT_ACCIONES.get(rol, []))


def serializar_acciones(acciones: List[str] | None) -> str | None:
    if acciones is None:
        return None
    valid = [p for p in acciones if p in ALL_ACCIONES]
    return json.dumps(valid)


def tiene_accion(usuario: UsuarioModel, codigo: str) -> bool:
    return codigo in acciones_efectivas(usuario)
