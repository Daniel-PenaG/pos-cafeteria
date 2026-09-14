"""Auditoría acotada. Un fallo aquí no debe revertir la operación de negocio."""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.constants.auditoria import DETALLES_PROHIBIDOS
from app.models.models import AuditoriaModel, UsuarioModel
from app.utils.timezone_mx import now_utc_naive

logger = logging.getLogger(__name__)


def sanitizar_detalles(detalles: dict | None) -> dict:
    if not detalles:
        return {}
    limpio = {}
    for clave, valor in detalles.items():
        k = str(clave).lower()
        if k in DETALLES_PROHIBIDOS or any(p in k for p in DETALLES_PROHIBIDOS):
            continue
        if isinstance(valor, (str, int, float, bool)) or valor is None:
            limpio[clave] = valor
        elif isinstance(valor, (list, tuple)):
            limpio[clave] = [v for v in valor if isinstance(v, (str, int, float, bool))][:20]
        else:
            limpio[clave] = str(valor)[:120]
    return limpio


def registrar_auditoria(
    db: Session,
    *,
    accion: str,
    usuario: UsuarioModel | None = None,
    usuario_login_intentado: str | None = None,
    entidad: str | None = None,
    entidad_id: int | None = None,
    detalles: dict | None = None,
    origen: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    payload = sanitizar_detalles(detalles)
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))[:2000] if payload else None
    try:
        with db.begin_nested():
            db.add(
                AuditoriaModel(
                    id_usuario=usuario.id_usuario if usuario is not None else None,
                    usuario_login_intentado=(usuario_login_intentado or "")[:80] or None,
                    accion=accion,
                    entidad=entidad,
                    entidad_id=entidad_id,
                    detalles_json=raw,
                    origen=origen,
                    fecha_hora=now_utc_naive(),
                    ip=(ip or "")[:64] or None,
                    user_agent=(user_agent or "")[:300] or None,
                )
            )
            db.flush()
    except Exception as exc:
        logger.warning("Auditoría omitida (%s): %s", accion, exc)
