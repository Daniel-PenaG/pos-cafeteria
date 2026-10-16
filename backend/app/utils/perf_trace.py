"""Trazas internas de fases (solo con PERF_LOG_DETAIL). No registra datos sensibles."""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager

logger = logging.getLogger("pos.performance")

_ENABLED = os.getenv("PERF_LOG_DETAIL", "").lower() in ("1", "true", "yes")


@contextmanager
def perf_phase(operacion: str, fase: str):
    from app.utils.sql_signature_profiler import profiling_enabled, set_sql_phase, clear_sql_phase

    if profiling_enabled():
        set_sql_phase(operacion, fase)
    if not _ENABLED and not profiling_enabled():
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = round((time.perf_counter() - t0) * 1000, 2)
        if _ENABLED:
            logger.info(
                "perf phase",
                extra={"operacion": operacion, "fase": fase, "duration_ms": ms},
            )
        if profiling_enabled():
            clear_sql_phase()
