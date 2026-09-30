"""Migración 006 en el arranque. Idempotente. No imprime la URL ni credenciales."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

MIGRATION_FILE = (
    Path(__file__).resolve().parents[2] / "migrations" / "006_puntos_pagos_mixtos.up.sql"
)

INDICES_006 = (
    "uq_venta_pago_un_puntos",
    "uq_venta_pago_un_monetario",
    "ix_fidelidad_movimientos_id_cliente",
    "ix_fidelidad_movimientos_id_venta",
    "uq_fidelidad_venta_tipo",
    "uq_cobro_operaciones_operation_id",
)

COLUMNAS_COBRO = (
    "operation_id",
    "payload_hash",
    "id_pedido",
    "id_venta",
    "id_usuario",
    "saldo_anterior",
    "saldo_final",
    "fecha",
)

CONSULTA_DUPLICADOS = """
SELECT id_venta, tipo, COUNT(*) AS n
FROM fidelidad_movimientos
WHERE id_venta IS NOT NULL
  AND tipo IN ('REDENCION', 'ACUMULACION')
GROUP BY id_venta, tipo
HAVING COUNT(*) > 1
"""


def _engine(bind: Engine | None) -> Engine:
    if bind is not None:
        return bind
    from app.database import engine

    return engine


CONSULTA_PAGOS_PUNTOS = """
SELECT id_venta, COUNT(*) AS n
FROM venta_pagos
WHERE metodo = 'PUNTOS'
GROUP BY id_venta
HAVING COUNT(*) > 1
"""

CONSULTA_PAGOS_MONETARIOS = """
SELECT id_venta, COUNT(*) AS n
FROM venta_pagos
WHERE metodo <> 'PUNTOS'
GROUP BY id_venta
HAVING COUNT(*) > 1
"""


def duplicados_fidelidad(bind: Engine) -> list[tuple]:
    insp = inspect(bind)
    if "fidelidad_movimientos" not in set(insp.get_table_names()):
        return []
    with bind.connect() as conn:
        return list(conn.execute(text(CONSULTA_DUPLICADOS)).fetchall())


def _ids_conflicto(filas: list) -> list[int]:
    return sorted({int(r[0]) for r in filas})


def _mensaje_duplicados(filas: list) -> str:
    ids = sorted({int(r[0]) for r in filas})
    muestra = ", ".join(str(i) for i in ids[:30])
    extra = "" if len(ids) <= 30 else f" y {len(ids) - 30} más"
    return (
        f"Migración 006 detenida: {len(filas)} conflicto(s) de fidelidad "
        f"en {len(ids)} venta(s): {muestra}{extra}. "
        "No se borró ni se consolidó ningún movimiento. "
        "Revisa los duplicados con la consulta de diagnóstico y vuelve a iniciar. "
        "No se muestran credenciales ni la URL de la base."
    )


def _statements(sql: str) -> list[str]:
    chunks = [sql]
    if "DO $$" in sql:
        before, rest = sql.split("DO $$", 1)
        body, after = rest.split("END $$;", 1)
        chunks = [before, "DO $$" + body + "END $$;", after]
    statements = []
    for chunk in chunks:
        if chunk.strip().startswith("DO $$"):
            statements.append(chunk.strip())
            continue
        buf = []
        for line in chunk.splitlines():
            if line.strip().startswith("--"):
                continue
            buf.append(line)
            if line.strip().endswith(";"):
                statements.append("\n".join(buf).strip())
                buf = []
        tail = "\n".join(buf).strip()
        if tail:
            statements.append(tail)
    return [s for s in statements if s]


def _aplicar_sqlite(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS cobro_operaciones (
                id_operacion INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id VARCHAR(64) NOT NULL,
                payload_hash VARCHAR(64) NOT NULL,
                id_pedido INTEGER REFERENCES pedidos(id_pedido),
                id_venta INTEGER REFERENCES ventas(id_venta),
                id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
                saldo_anterior INTEGER,
                saldo_final INTEGER,
                fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    for sql in (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_cobro_operaciones_operation_id ON cobro_operaciones (operation_id)",
        "CREATE INDEX IF NOT EXISTS ix_fidelidad_movimientos_id_cliente ON fidelidad_movimientos (id_cliente)",
        "CREATE INDEX IF NOT EXISTS ix_fidelidad_movimientos_id_venta ON fidelidad_movimientos (id_venta)",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_fidelidad_venta_tipo
           ON fidelidad_movimientos (id_venta, tipo)
           WHERE id_venta IS NOT NULL AND tipo IN ('REDENCION', 'ACUMULACION')""",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_venta_pago_un_puntos
           ON venta_pagos (id_venta) WHERE metodo = 'PUNTOS'""",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_venta_pago_un_monetario
           ON venta_pagos (id_venta) WHERE metodo <> 'PUNTOS'""",
    ):
        conn.execute(text(sql))


def aplicar_migracion_006_puntos(bind: Engine | None = None) -> None:
    """Aplica 006. Si hay redenciones o acumulaciones duplicadas, no toca datos y aborta."""
    engine = _engine(bind)
    insp = inspect(engine)
    tablas = set(insp.get_table_names())
    if "ventas" not in tablas or "venta_pagos" not in tablas:
        return
    try:
        with engine.begin() as conn:
            if "fidelidad_movimientos" in tablas:
                filas = list(conn.execute(text(CONSULTA_DUPLICADOS)).fetchall())
                if filas:
                    raise RuntimeError(_mensaje_duplicados(filas))
            if "venta_pagos" in tablas:
                puntos = list(conn.execute(text(CONSULTA_PAGOS_PUNTOS)).fetchall())
                monetarios = list(conn.execute(text(CONSULTA_PAGOS_MONETARIOS)).fetchall())
                if puntos or monetarios:
                    ids = _ids_conflicto(puntos + monetarios)
                    muestra = ", ".join(str(i) for i in ids[:30])
                    raise RuntimeError(
                        f"Migración 006 detenida: hay ventas con más de un componente "
                        f"del mismo tipo ({len(ids)} venta(s): {muestra}). "
                        "No se borró ningún pago. Revisa venta_pagos antes de publicar. "
                        "No se muestran credenciales ni la URL de la base."
                    )
            if engine.dialect.name == "postgresql":
                sql = MIGRATION_FILE.read_text(encoding="utf-8")
                for stmt in _statements(sql):
                    conn.execute(text(stmt))
            else:
                _aplicar_sqlite(conn)
    except RuntimeError:
        raise
    except Exception as exc:
        logger.error(
            "Migración 006 de puntos falló (%s). No se muestran credenciales.",
            type(exc).__name__,
        )
        raise RuntimeError(
            "Esquema de puntos incompleto (migración 006). "
            "No se inicia el backend. Revisa los duplicados de fidelidad o aplica "
            "006_puntos_pagos_mixtos.up.sql y vuelve a arrancar. "
            "No se muestran credenciales ni la URL de la base."
        ) from None


def verificar_esquema_puntos_mixtos(bind: Engine | None = None) -> None:
    """No arranca si falta la protección de 006. No depende de create_all."""
    engine = _engine(bind)
    insp = inspect(engine)
    tablas = set(insp.get_table_names())
    if "ventas" not in tablas:
        return
    faltantes: list[str] = []
    if "venta_pagos" not in tablas:
        faltantes.append("tabla venta_pagos")
    else:
        cols = {c["name"]: c for c in insp.get_columns("venta_pagos")}
        if "operation_id" not in cols:
            faltantes.append("venta_pagos.operation_id")
        elif engine.dialect.name == "postgresql":
            with engine.connect() as conn:
                largo = conn.execute(
                    text(
                        """
                        SELECT character_maximum_length
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'venta_pagos'
                          AND column_name = 'operation_id'
                        """
                    )
                ).scalar()
            if largo is not None and int(largo) < 80:
                faltantes.append("venta_pagos.operation_id VARCHAR(80)")
        if not _tiene_check(engine, insp):
            faltantes.append("CHECK ck_venta_pago_componente")
    if "cobro_operaciones" not in tablas:
        faltantes.append("tabla cobro_operaciones")
    else:
        cols_op = {c["name"] for c in insp.get_columns("cobro_operaciones")}
        for col in COLUMNAS_COBRO:
            if col not in cols_op:
                faltantes.append(f"cobro_operaciones.{col}")
    presentes = _indices(engine)
    for nombre in INDICES_006:
        if nombre not in presentes:
            faltantes.append(f"índice {nombre}")
    if faltantes:
        logger.error(
            "Esquema 006 incompleto: %s. No se muestran credenciales.",
            ", ".join(faltantes),
        )
        raise RuntimeError(
            "El esquema de puntos y pagos mixtos está incompleto. "
            "No se inicia el backend. Falta: "
            + ", ".join(faltantes)
            + ". No se muestran credenciales ni la URL de la base."
        )


def _indices(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        if engine.dialect.name == "postgresql":
            rows = conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
            ).fetchall()
            return {r[0] for r in rows}
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'index'")
        ).fetchall()
        return {r[0] for r in rows}


def _tiene_check(engine: Engine, insp) -> bool:
    if "venta_pagos" not in set(insp.get_table_names()):
        return False
    with engine.connect() as conn:
        if engine.dialect.name == "postgresql":
            encontrado = conn.execute(
                text(
                    """
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'ck_venta_pago_componente'
                    """
                )
            ).scalar()
            return bool(encontrado)
        sql = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'venta_pagos'")
        ).scalar()
    return bool(sql and "ck_venta_pago_componente" in sql)
