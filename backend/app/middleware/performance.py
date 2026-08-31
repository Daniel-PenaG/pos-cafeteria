"""Middleware de medición de rendimiento."""
from __future__ import annotations

import logging
import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utils.sql_counter import get_sql_count, reset_sql_count, sql_counting_enabled

logger = logging.getLogger("pos.performance")

PERF_LOG = os.getenv("PERF_LOG", "").lower() in ("1", "true", "yes")
PERF_LOG_DETAIL = os.getenv("PERF_LOG_DETAIL", "").lower() in ("1", "true", "yes")


class PerformanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        perf_active = PERF_LOG or sql_counting_enabled()
        if not perf_active:
            return await call_next(request)

        reset_sql_count()
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        sql_count = get_sql_count()

        response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
        if sql_count:
            response.headers["X-SQL-Query-Count"] = str(sql_count)

        if PERF_LOG:
            path = request.url.path
            logger.info(
                "perf request",
                extra={
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": elapsed_ms,
                    "sql_queries": sql_count,
                },
            )
            if PERF_LOG_DETAIL:
                logger.debug(
                    "perf detail method=%s path=%s status=%s duration_ms=%s sql=%s",
                    request.method,
                    path,
                    response.status_code,
                    elapsed_ms,
                    sql_count,
                )

        return response
