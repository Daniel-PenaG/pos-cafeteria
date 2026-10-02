"""Migración 007 en SQLite y, si hay URL, en PostgreSQL desechable."""
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app.services.migracion_promo_modo import (
    aplicar_migracion_007_promo_modo,
    verificar_esquema_promo_modo,
)

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL", "").strip()


def test_007_sqlite_conserva_datos_y_es_idempotente():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE detalle_pedido (
                id_detalle_pedido INTEGER PRIMARY KEY,
                cantidad NUMERIC(10, 2) NOT NULL,
                precio_unitario NUMERIC(10, 2) NOT NULL,
                nombre_producto VARCHAR(50) NOT NULL
            )
            """
        ))
        conn.execute(text(
            "INSERT INTO detalle_pedido (cantidad, precio_unitario, nombre_producto) "
            "VALUES (3, 37.33, 'Cafe')"
        ))
    aplicar_migracion_007_promo_modo(engine)
    aplicar_migracion_007_promo_modo(engine)
    with engine.connect() as conn:
        fila = conn.execute(text(
            "SELECT cantidad, subtotal, sin_promocion, nombre_producto FROM detalle_pedido"
        )).one()
    assert fila.nombre_producto == "Cafe"
    assert Decimal(str(fila.cantidad)) == Decimal("3")
    assert Decimal(str(fila.subtotal)) == Decimal("111.99")
    assert fila.sin_promocion is None
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE detalle_pedido SET subtotal = 112 WHERE nombre_producto = 'Cafe'"
        ))
        conn.execute(text(
            "INSERT INTO detalle_pedido (cantidad, precio_unitario, nombre_producto) "
            "VALUES (1, 10, 'Extra')"
        ))
    aplicar_migracion_007_promo_modo(engine)
    with engine.connect() as conn:
        filas = {
            row.nombre_producto: row
            for row in conn.execute(text(
                "SELECT nombre_producto, subtotal, sin_promocion FROM detalle_pedido"
            ))
        }
    assert Decimal(str(filas["Cafe"].subtotal)) == Decimal("112.00")
    assert Decimal(str(filas["Extra"].subtotal)) == Decimal("10.00")
    assert filas["Cafe"].sin_promocion is None


def test_verificacion_detiene_esquema_parcial():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE detalle_pedido (id_detalle_pedido INTEGER PRIMARY KEY, sin_promocion BOOLEAN)"
        ))
    with pytest.raises(RuntimeError, match="incompleto") as exc:
        verificar_esquema_promo_modo(engine)
    assert "://" not in str(exc.value)


def test_arranque_aplica_007_despues_de_006():
    import inspect as pyinspect

    from app.database import aplicar_migraciones_sqlite

    src = pyinspect.getsource(aplicar_migraciones_sqlite)
    assert src.index("aplicar_migracion_006_puntos") < src.index("verificar_esquema_puntos_mixtos")
    assert src.index("verificar_esquema_puntos_mixtos") < src.index("aplicar_migracion_007_promo_modo")
    assert src.index("aplicar_migracion_007_promo_modo") < src.index("verificar_esquema_promo_modo")
    down = (MIGRATIONS / "007_promocion_modo_subtotal.down.sql").read_text(encoding="utf-8")
    assert "No ejecutar en producción" in down
    assert "Pérdida irreversible" in down


def _sql_statements(path: Path) -> list[str]:
    statements = []
    buf = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buf).strip())
            buf = []
    rest = "\n".join(buf).strip()
    if rest:
        statements.append(rest)
    return statements


def _apply_sql(engine, path: Path) -> None:
    with engine.begin() as conn:
        for stmt in _sql_statements(path):
            conn.execute(text(stmt))


MARCADORES_002_006 = (
    "uq_pedidos_abierto_mesa",
    "uq_pedido_operaciones_operation_id",
    "ck_venta_pago_componente",
    "uq_cobro_operaciones_operation_id",
    "uq_sesion_caja_operation_id",
)


def _nombres_pg(engine, sql: str) -> set[str]:
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(text(sql))}


@pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL no definido. No se ejecuta contra producción.",
)
def test_007_postgres_historia_flujo_nuevo_y_down():
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.models.models import ProductoModel
    from app.schemas.pedido import PedidoLineaCreate
    from app.services.pedido_service import agregar_linea_pedido, obtener_pedido_abierto_mesa
    from app.services.promocion_ticket_service import recalcular_lineas_ticket
    from tests.pg_test_guard import exigir_postgres_desechable
    from tests.promo_seed import crear_promo, promo_vigente_siempre, seed_promo_catalog

    exigir_postgres_desechable(POSTGRES_TEST_URL)
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    indices = _nombres_pg(engine, "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
    constraints = _nombres_pg(
        engine,
        "SELECT conname FROM pg_constraint WHERE connamespace = 'public'::regnamespace",
    )
    presentes = indices | constraints
    for nombre in MARCADORES_002_006:
        assert nombre in presentes

    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        refs = seed_promo_catalog(db)
        cafe = db.get(ProductoModel, refs.id_cafe)
        cafe.precio_venta = Decimal("42")
        db.commit()
        pedido = obtener_pedido_abierto_mesa(db, 80, refs.id_usuario)
        db.commit()
        id_pedido = pedido.id_pedido
        id_producto = refs.id_cafe
        id_usuario = refs.id_usuario
    finally:
        db.close()

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE detalle_pedido DROP COLUMN IF EXISTS subtotal"))
        conn.execute(text("ALTER TABLE detalle_pedido DROP COLUMN IF EXISTS sin_promocion"))
        conn.execute(
            text(
                """
                INSERT INTO detalle_pedido (
                    id_pedido, id_producto, nombre_producto, cantidad, cantidad_lista,
                    precio_unitario, line_key, estado_linea, cantidad_cancelada, en_comanda
                ) VALUES (
                    :id_pedido, :id_producto, 'Cafe historico', 3, 0,
                    37.33, 'legacy-hist', 'ACTIVA', 0, false
                )
                """
            ),
            {"id_pedido": id_pedido, "id_producto": id_producto},
        )

    aplicar_migracion_007_promo_modo(engine)
    aplicar_migracion_007_promo_modo(engine)
    verificar_esquema_promo_modo(engine)
    with engine.connect() as conn:
        tipos = {
            row.column_name: row
            for row in conn.execute(text(
                """
                SELECT column_name, data_type, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'detalle_pedido'
                  AND column_name IN ('sin_promocion', 'subtotal')
                """
            ))
        }
        fila = conn.execute(text(
            """
            SELECT id_detalle_pedido, id_pedido, id_producto, cantidad, precio_unitario,
                   nombre_producto, subtotal, sin_promocion
            FROM detalle_pedido
            WHERE line_key = 'legacy-hist'
            """
        )).one()
    assert tipos["sin_promocion"].data_type == "boolean"
    assert tipos["subtotal"].data_type == "numeric"
    assert int(tipos["subtotal"].numeric_precision) == 10
    assert int(tipos["subtotal"].numeric_scale) == 2
    assert fila.id_pedido == id_pedido
    assert fila.id_producto == id_producto
    assert Decimal(str(fila.cantidad)) == Decimal("3")
    assert Decimal(str(fila.precio_unitario)) == Decimal("37.33")
    assert fila.nombre_producto == "Cafe historico"
    assert Decimal(str(fila.subtotal)) == Decimal("111.99")
    assert fila.sin_promocion is None
    despues = _nombres_pg(engine, "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
    despues_c = _nombres_pg(
        engine,
        "SELECT conname FROM pg_constraint WHERE connamespace = 'public'::regnamespace",
    )
    assert indices <= despues
    assert constraints <= despues_c

    db = Session()
    try:
        promo = crear_promo(
            db,
            nombre="2 x 70",
            tipo="CANTIDAD_PRECIO",
            valor=Decimal("70"),
            cantidad_requerida=2,
            id_producto=id_producto,
            **promo_vigente_siempre(),
        )
        db.commit()
        recalc = recalcular_lineas_ticket(
            db,
            [{
                "id_producto": id_producto,
                "cantidad": 3,
                "precio_extras": 0,
                "extras": [],
                "id_promocion": promo.id_promocion,
                "sin_promocion": False,
                "forzar_promo_linea": True,
            }],
        )
        linea = recalc["lineas"][0]
        pedido_nuevo = obtener_pedido_abierto_mesa(db, 81, id_usuario)
        agregar_linea_pedido(
            db,
            pedido_nuevo,
            PedidoLineaCreate(
                id_producto=id_producto,
                cantidad=3,
                precio_unitario=linea["precio_unitario"],
                id_promocion=promo.id_promocion,
                sin_promocion=False,
                extras=[],
            ),
        )
        db.commit()
    finally:
        db.close()

    aplicar_migracion_007_promo_modo(engine)
    with engine.connect() as conn:
        historico = conn.execute(text(
            "SELECT subtotal, sin_promocion FROM detalle_pedido WHERE line_key = 'legacy-hist'"
        )).one()
        nuevo = conn.execute(text(
            """
            SELECT subtotal FROM detalle_pedido
            WHERE id_pedido <> :id_pedido AND cantidad = 3
            """
        ), {"id_pedido": id_pedido}).one()
    assert Decimal(str(historico.subtotal)) == Decimal("111.99")
    assert historico.sin_promocion is None
    assert Decimal(str(nuevo.subtotal)) == Decimal("112.00")

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE detalle_pedido DROP COLUMN subtotal"))
    with pytest.raises(RuntimeError, match="incompleto") as exc:
        verificar_esquema_promo_modo(engine)
    assert "://" not in str(exc.value)

    _apply_sql(engine, MIGRATIONS / "007_promocion_modo_subtotal.down.sql")
    cols = {c["name"] for c in inspect(engine).get_columns("detalle_pedido")}
    assert "subtotal" not in cols
    assert "sin_promocion" not in cols
    with engine.connect() as conn:
        fila = conn.execute(text(
            "SELECT id_pedido, id_producto, cantidad, precio_unitario, nombre_producto "
            "FROM detalle_pedido WHERE line_key = 'legacy-hist'"
        )).one()
        tablas = {row[0] for row in conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ))}
    assert fila.nombre_producto == "Cafe historico"
    assert Decimal(str(fila.cantidad)) == Decimal("3")
    assert Decimal(str(fila.precio_unitario)) == Decimal("37.33")
    assert fila.id_pedido == id_pedido
    for tabla in ("pedidos", "venta_pagos", "pedido_cancelaciones", "cobro_operaciones", "sesiones_caja", "pedido_operaciones"):
        assert tabla in tablas
    assert "uq_pedidos_abierto_mesa" in _nombres_pg(
        engine, "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
    )
    Base.metadata.drop_all(engine)
    engine.dispose()
