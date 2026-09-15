"""El token es la autoridad. id_usuario del cliente no atribuye operaciones."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.constants import auditoria as A
from app.models.models import UsuarioModel
from app.services.auditoria_service import registrar_auditoria


def id_usuario_autenticado(
    db: Session,
    current: UsuarioModel,
    id_cliente: int | None,
    contexto: str,
) -> int:
    """Usa siempre al usuario del token. Si el cliente envía otro id, se ignora y se audita.

    Decisión (compatibilidad APK/web): no responder 403 por discrepancia para no
    romper clientes que aún mandan id_usuario. CAJERO/COCINA no pueden operar
    en nombre de otro porque la atribución ignora ese campo.
    """
    if id_cliente is not None:
        try:
            enviado = int(id_cliente)
        except (TypeError, ValueError):
            enviado = None
        if enviado is not None and enviado != int(current.id_usuario):
            registrar_auditoria(
                db,
                usuario=current,
                accion=A.ID_USUARIO_DISCREPANCIA,
                entidad="usuario",
                entidad_id=current.id_usuario,
                detalles={"id_enviado": enviado, "contexto": contexto},
                origen=contexto,
            )
    return int(current.id_usuario)
