"""Migración 007. Idempotente. No imprime la URL ni credenciales."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

UP_007 = (
    Path(__file__).resolve().parents[2] / "migrations" / "007_promocion_modo_subtotal.up.sql"
)


def aplicar_migracion_007_promo_modo(bind: Engine) -> None:
    """Agrega sin_promocion y subtotal. No toca filas que ya tienen subtotal."""
    insp = inspect(bind)
    if "detalle_pedido" not in set(insp.get_table_names()):
        return
    dialect = bind.dialect.name
    cols = {c["name"] for c in insp.get_columns("detalle_pedido")}
    sentencias: list[str] = []
    if "sin_promocion" not in cols:
        if dialect == "postgresql":
            sentencias.append(
                "ALTER TABLE detalle_pedido ADD COLUMN IF NOT EXISTS sin_promocion BOOLEAN"
            )
        else:
            sentencias.append("ALTER TABLE detalle_pedido ADD COLUMN sin_promocion BOOLEAN")
    if "subtotal" not in cols:
        if dialect == "postgresql":
            sentencias.append(
                "ALTER TABLE detalle_pedido ADD COLUMN IF NOT EXISTS subtotal NUMERIC(10, 2)"
            )
        else:
            sentencias.append("ALTER TABLE detalle_pedido ADD COLUMN subtotal NUMERIC(10, 2)")
    sentencias.append(
        "UPDATE detalle_pedido SET subtotal = ROUND(cantidad * precio_unitario, 2) "
        "WHERE subtotal IS NULL"
    )
    try:
        with bind.begin() as conn:
            for sql in sentencias:
                conn.execute(text(sql))
    except Exception as exc:
        mensaje = str(exc).lower()
        if dialect == "sqlite" and "duplicate column" in mensaje:
            return
        logging.error(
            "Migración 007 de modo de promoción falló (%s). No se muestran credenciales.",
            type(exc).__name__,
        )
        raise RuntimeError(
            "Esquema de promociones incompleto (migración 007). "
            "Aplica 007_promocion_modo_subtotal.up.sql y vuelve a arrancar."
        ) from None


def verificar_esquema_promo_modo(bind: Engine) -> None:
    """Detiene el arranque si 007 quedó a medias. No imprime la URL."""
    insp = inspect(bind)
    if "detalle_pedido" not in set(insp.get_table_names()):
        return
    cols = {c["name"]: c for c in insp.get_columns("detalle_pedido")}
    faltantes: list[str] = []
    if "sin_promocion" not in cols:
        faltantes.append("detalle_pedido.sin_promocion")
    elif bind.dialect.name == "postgresql":
        tipo = str(cols["sin_promocion"]["type"]).lower()
        if "bool" not in tipo:
            faltantes.append("detalle_pedido.sin_promocion BOOLEAN")
    if "subtotal" not in cols:
        faltantes.append("detalle_pedido.subtotal")
    elif bind.dialect.name == "postgresql":
        tipo = str(cols["subtotal"]["type"]).lower()
        if "numeric" not in tipo and "decimal" not in tipo:
            faltantes.append("detalle_pedido.subtotal NUMERIC(10,2)")
    if faltantes:
        logging.error(
            "Esquema 007 incompleto: %s. No se muestran credenciales.",
            ", ".join(faltantes),
        )
        raise RuntimeError(
            "El esquema de promociones está incompleto. No se inicia el backend. Falta: "
            + ", ".join(faltantes)
            + ". No se muestran credenciales ni la URL de la base."
        )
