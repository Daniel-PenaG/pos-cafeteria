"""Perfil SQL por firma normalizada y fase (PERF_LOG_SQL_SIGNATURE=1). Sin parámetros."""
from __future__ import annotations

import os
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine

_phase_operacion: ContextVar[str] = ContextVar("sql_prof_operacion", default="")
_phase_fase: ContextVar[str] = ContextVar("sql_prof_fase", default="")


def profiling_enabled() -> bool:
    return os.getenv("PERF_LOG_SQL_SIGNATURE", "").lower() in ("1", "true", "yes")


def set_sql_phase(operacion: str, fase: str) -> None:
    _phase_operacion.set(operacion or "")
    _phase_fase.set(fase or "")


def clear_sql_phase() -> None:
    _phase_operacion.set("")
    _phase_fase.set("")


@dataclass
class SqlSigRow:
    firma: str
    tabla: str
    count: int = 0
    ms_total: float = 0.0
    operacion: str = ""
    fase: str = ""

    def add(self, ms: float, operacion: str, fase: str) -> None:
        self.count += 1
        self.ms_total += ms
        if not self.operacion:
            self.operacion = operacion
        if not self.fase:
            self.fase = fase


_rows: ContextVar[dict[str, SqlSigRow]] = ContextVar("sql_prof_rows", default=None)


def reset_profile() -> None:
    _rows.set({})


def _normalize_sql(statement: str) -> tuple[str, str]:
    s = re.sub(r"\s+", " ", (statement or "").strip()).lower()
    s = re.sub(r"'(?:''|[^'])*'", "?", s)
    s = re.sub(r"\b\d+\.?\d*\b", "?", s)
    tabla = ""
    m = re.search(r"\bfrom\s+([\"`]?\w+[\"`]?)", s)
    if m:
        tabla = m.group(1).strip("\"`")
    else:
        m = re.search(r"\binto\s+([\"`]?\w+[\"`]?)", s)
        if m:
            tabla = m.group(1).strip("\"`")
        else:
            m = re.search(r"\bupdate\s+([\"`]?\w+[\"`]?)", s)
            if m:
                tabla = m.group(1).strip("\"`")
    firma = s[:240]
    return firma, tabla


def top_signatures(n: int = 20) -> list[dict]:
    rows = _rows.get() or {}
    ordered = sorted(rows.values(), key=lambda r: (-r.count, -r.ms_total))
    out = []
    for r in ordered[:n]:
        out.append(
            {
                "firma": r.firma,
                "tabla": r.tabla,
                "repeticiones": r.count,
                "ms_acumulado": round(r.ms_total, 3),
                "operacion": r.operacion,
                "fase": r.fase,
            }
        )
    return out


def total_stats() -> dict:
    rows = _rows.get() or {}
    total_q = sum(r.count for r in rows.values())
    total_ms = sum(r.ms_total for r in rows.values())
    return {"consultas": total_q, "ms_sql_acumulado": round(total_ms, 3)}


@event.listens_for(Engine, "before_cursor_execute")
def _prof_before(conn, cursor, statement, parameters, context, executemany):
    if not profiling_enabled():
        return
    conn.info["_prof_t0"] = time.perf_counter()


@event.listens_for(Engine, "after_cursor_execute")
def _prof_after(conn, cursor, statement, parameters, context, executemany):
    if not profiling_enabled():
        return
    t0 = conn.info.pop("_prof_t0", None)
    ms = (time.perf_counter() - t0) * 1000 if t0 else 0.0
    firma, tabla = _normalize_sql(statement)
    key = firma
    store = _rows.get()
    if store is None:
        store = {}
        _rows.set(store)
    row = store.get(key)
    op = _phase_operacion.get() or ""
    fase = _phase_fase.get() or ""
    if row is None:
        row = SqlSigRow(firma=firma, tabla=tabla, operacion=op, fase=fase)
        store[key] = row
    row.add(ms, op, fase)
