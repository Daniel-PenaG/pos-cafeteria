"""Contador de consultas SQL por petición (solo dev/test)."""
from __future__ import annotations

import os
from contextvars import ContextVar

from sqlalchemy import event
from sqlalchemy.engine import Engine

_query_count: ContextVar[int] = ContextVar("sql_query_count", default=0)
_counting_enabled: ContextVar[bool] = ContextVar("sql_counting_enabled", default=False)


def sql_counting_enabled() -> bool:
    return os.getenv("PERF_LOG_SQL", "").lower() in ("1", "true", "yes")


def reset_sql_count() -> None:
    _query_count.set(0)
    enabled = sql_counting_enabled()
    _counting_enabled.set(enabled)


def get_sql_count() -> int:
    if not (sql_counting_enabled() or _counting_enabled.get()):
        return 0
    return _query_count.get()


def _increment() -> None:
    if sql_counting_enabled() or _counting_enabled.get():
        _query_count.set(_query_count.get() + 1)


@event.listens_for(Engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    _increment()
