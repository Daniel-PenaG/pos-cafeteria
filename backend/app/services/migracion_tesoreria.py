"""Migración 008. Idempotente. No imprime la URL ni credenciales.

Se aplica al arrancar, después de verificar 007. Tesorería queda desactivada.
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.utils.timezone_mx import now_utc_naive

UP_008 = Path(__file__).resolve().parents[2] / "migrations" / "008_tesoreria_saldos.up.sql"
DOWN_008 = Path(__file__).resolve().parents[2] / "migrations" / "008_tesoreria_saldos.down.sql"

CUENTAS = (
    ("EFECTIVO_CAFETERIA", "Efectivo en cafetería", "EFECTIVO"),
    ("EFECTIVO_CASA", "Efectivo del negocio en casa", "EFECTIVO"),
    ("BANCO", "Cuenta bancaria", "BANCO"),
)

TABLAS = (
    "cuentas_tesoreria",
    "operaciones_tesoreria",
    "movimientos_tesoreria",
    "activacion_tesoreria",
    "conciliaciones_tesoreria",
)


def _ejecutar(conn, sql: str) -> None:
    conn.execute(text(sql))


def aplicar_migracion_008_tesoreria(bind: Engine) -> None:
    """Crea el libro de Tesorería y las tres cuentas. No activa ni reconstruye ventas."""
    dialect = bind.dialect.name
    insp = inspect(bind)
    tablas = set(insp.get_table_names())
    try:
        with bind.begin() as conn:
            if dialect == "postgresql" and "usuarios" in tablas:
                _ejecutar(
                    conn,
                    "ALTER TABLE usuarios ALTER COLUMN permisos_acciones_json TYPE VARCHAR(2000)",
                )
            if "cuentas_tesoreria" not in tablas:
                if dialect == "postgresql":
                    _ejecutar(
                        conn,
                        """
                        CREATE TABLE cuentas_tesoreria (
                            id_cuenta SERIAL PRIMARY KEY,
                            codigo VARCHAR(40) NOT NULL UNIQUE,
                            nombre VARCHAR(120) NOT NULL,
                            tipo VARCHAR(20) NOT NULL,
                            moneda VARCHAR(3) NOT NULL DEFAULT 'MXN',
                            activa BOOLEAN NOT NULL DEFAULT TRUE,
                            es_sistema BOOLEAN NOT NULL DEFAULT FALSE,
                            fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """,
                    )
                else:
                    _ejecutar(
                        conn,
                        """
                        CREATE TABLE cuentas_tesoreria (
                            id_cuenta INTEGER PRIMARY KEY,
                            codigo VARCHAR(40) NOT NULL UNIQUE,
                            nombre VARCHAR(120) NOT NULL,
                            tipo VARCHAR(20) NOT NULL,
                            moneda VARCHAR(3) NOT NULL DEFAULT 'MXN',
                            activa BOOLEAN NOT NULL DEFAULT 1,
                            es_sistema BOOLEAN NOT NULL DEFAULT 0,
                            fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """,
                    )
            if "operaciones_tesoreria" not in tablas:
                pk = "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY"
                boolish = "BOOLEAN" if dialect == "postgresql" else "BOOLEAN"
                _ejecutar(
                    conn,
                    f"""
                    CREATE TABLE operaciones_tesoreria (
                        id_operacion {pk},
                        operation_id VARCHAR(80) NOT NULL UNIQUE,
                        payload_hash VARCHAR(64) NOT NULL,
                        tipo VARCHAR(40) NOT NULL,
                        estado VARCHAR(20) NOT NULL DEFAULT 'CONFIRMADA',
                        fecha_operacion TIMESTAMP NOT NULL,
                        id_usuario INTEGER NOT NULL,
                        origen_tipo VARCHAR(40),
                        origen_id INTEGER,
                        referencia VARCHAR(80),
                        concepto VARCHAR(200) NOT NULL,
                        observacion VARCHAR(500),
                        id_operacion_revertida INTEGER,
                        fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """,
                )
                _ = boolish
            if "movimientos_tesoreria" not in tablas:
                pk = "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY"
                _ejecutar(
                    conn,
                    f"""
                    CREATE TABLE movimientos_tesoreria (
                        id_movimiento {pk},
                        id_operacion INTEGER NOT NULL,
                        id_cuenta INTEGER NOT NULL,
                        direccion VARCHAR(10) NOT NULL,
                        importe NUMERIC(12, 2) NOT NULL,
                        fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """,
                )
            if "activacion_tesoreria" not in tablas:
                pk = "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY"
                _ejecutar(
                    conn,
                    f"""
                    CREATE TABLE activacion_tesoreria (
                        id_activacion {pk},
                        fecha_corte TIMESTAMP NOT NULL,
                        id_usuario INTEGER NOT NULL,
                        fecha_confirmacion TIMESTAMP NOT NULL,
                        estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVA',
                        efectivo_cafeteria NUMERIC(12, 2) NOT NULL,
                        efectivo_casa NUMERIC(12, 2) NOT NULL,
                        saldo_banco NUMERIC(12, 2) NOT NULL,
                        observacion VARCHAR(500),
                        unica INTEGER NOT NULL DEFAULT 1 UNIQUE
                    )
                    """,
                )
            if "conciliaciones_tesoreria" not in tablas:
                pk = "SERIAL PRIMARY KEY" if dialect == "postgresql" else "INTEGER PRIMARY KEY"
                _ejecutar(
                    conn,
                    f"""
                    CREATE TABLE conciliaciones_tesoreria (
                        id_conciliacion {pk},
                        id_cuenta INTEGER NOT NULL,
                        saldo_sistema NUMERIC(12, 2) NOT NULL,
                        saldo_fisico NUMERIC(12, 2) NOT NULL,
                        diferencia NUMERIC(12, 2) NOT NULL,
                        observacion VARCHAR(500),
                        estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
                        id_usuario INTEGER NOT NULL,
                        id_usuario_revision INTEGER,
                        fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        fecha_revision TIMESTAMP,
                        id_operacion_ajuste INTEGER
                    )
                    """,
                )
            _ejecutar(
                conn,
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_tesoreria_origen_confirmada
                ON operaciones_tesoreria (origen_tipo, origen_id)
                WHERE origen_tipo IS NOT NULL
                  AND origen_id IS NOT NULL
                  AND tipo <> 'REVERSA'
                  AND estado = 'CONFIRMADA'
                """,
            )
            _agregar_columna(conn, dialect, "gastos", "estado_pago", "VARCHAR(20) NOT NULL DEFAULT 'PAGADO'")
            _agregar_columna(conn, dialect, "gastos", "clasificacion", "VARCHAR(40) NOT NULL DEFAULT 'GASTO_OPERATIVO'")
            _agregar_columna(conn, dialect, "gastos", "id_cuenta_tesoreria", "INTEGER")
            _agregar_columna(conn, dialect, "compras", "estado_pago", "VARCHAR(20) NOT NULL DEFAULT 'PAGADO'")
            _agregar_columna(conn, dialect, "compras", "id_cuenta_tesoreria", "INTEGER")
            ahora = now_utc_naive().isoformat(sep=" ")
            for codigo, nombre, tipo in CUENTAS:
                _ejecutar(
                    conn,
                    f"""
                    INSERT INTO cuentas_tesoreria (codigo, nombre, tipo, moneda, activa, es_sistema, fecha_creacion)
                    SELECT '{codigo}', '{nombre}', '{tipo}', 'MXN', {1 if dialect != 'postgresql' else 'TRUE'},
                           {1 if dialect != 'postgresql' else 'TRUE'}, '{ahora}'
                    WHERE NOT EXISTS (SELECT 1 FROM cuentas_tesoreria WHERE codigo = '{codigo}')
                    """,
                )
    except Exception as exc:
        logging.error(
            "Migración 008 de tesorería falló (%s). No se muestran credenciales.",
            type(exc).__name__,
        )
        raise RuntimeError(
            "Esquema de tesorería incompleto (migración 008). "
            "No se inicia el backend. No se muestran credenciales ni la URL de la base."
        ) from None


def _agregar_columna(conn, dialect: str, tabla: str, columna: str, definicion: str) -> None:
    if dialect == "postgresql":
        _ejecutar(conn, f"ALTER TABLE {tabla} ADD COLUMN IF NOT EXISTS {columna} {definicion}")
        return
    insp = inspect(conn)
    nombres = {c["name"] for c in insp.get_columns(tabla)} if tabla in set(insp.get_table_names()) else set()
    if columna not in nombres and tabla in set(insp.get_table_names()):
        _ejecutar(conn, f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")


def verificar_esquema_tesoreria(bind: Engine) -> None:
    """Detiene el arranque si 008 quedó a medias. No imprime la URL."""
    insp = inspect(bind)
    if hasattr(insp, "clear_cache"):
        insp.clear_cache()
    tablas = set(insp.get_table_names())
    faltantes: list[str] = []
    for tabla in TABLAS:
        if tabla not in tablas:
            faltantes.append(tabla)
    if "cuentas_tesoreria" in tablas:
        cols = {c["name"] for c in insp.get_columns("cuentas_tesoreria")}
        for requerida in ("codigo", "tipo", "moneda", "es_sistema"):
            if requerida not in cols:
                faltantes.append(f"cuentas_tesoreria.{requerida}")
        codigos = set()
        if "codigo" in cols:
            try:
                with bind.connect() as conn:
                    filas = conn.execute(text("SELECT codigo FROM cuentas_tesoreria")).fetchall()
                    codigos = {fila[0] for fila in filas}
            except Exception:
                faltantes.append("cuentas_tesoreria.codigo")
        for codigo, _nombre, _tipo in CUENTAS:
            if codigo not in codigos:
                faltantes.append(f"cuenta {codigo}")
    if "movimientos_tesoreria" in tablas:
        cols = {c["name"] for c in insp.get_columns("movimientos_tesoreria")}
        for requerida in ("direccion", "importe", "id_cuenta", "id_operacion"):
            if requerida not in cols:
                faltantes.append(f"movimientos_tesoreria.{requerida}")
    if "activacion_tesoreria" in tablas:
        with bind.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM activacion_tesoreria")).scalar()
        if int(n or 0) > 1:
            faltantes.append("activacion_tesoreria duplicada")
    if faltantes:
        logging.error(
            "Esquema 008 incompleto: %s. No se muestran credenciales.",
            ", ".join(faltantes),
        )
        raise RuntimeError(
            "El esquema de tesorería está incompleto. No se inicia el backend. Falta: "
            + ", ".join(faltantes)
            + ". No se muestran credenciales ni la URL de la base."
        )


def aplicar_down_tesoreria_desechable(bind: Engine) -> None:
    """Borra el historial de Tesorería. El caller debe garantizar que la base es desechable."""
    with bind.begin() as conn:
        for tabla in (
            "conciliaciones_tesoreria",
            "movimientos_tesoreria",
            "activacion_tesoreria",
            "operaciones_tesoreria",
            "cuentas_tesoreria",
        ):
            conn.execute(text(f"DROP TABLE IF EXISTS {tabla}"))
