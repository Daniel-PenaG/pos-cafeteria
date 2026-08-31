"""Configuración de horario de operación (defaults compatibles con comportamiento previo)."""
from __future__ import annotations

import os


def hora_operacion_inicio() -> int:
    return int(os.getenv("HORA_OPERACION_INICIO", "9"))


def hora_operacion_fin() -> int:
    return int(os.getenv("HORA_OPERACION_FIN", "21"))
