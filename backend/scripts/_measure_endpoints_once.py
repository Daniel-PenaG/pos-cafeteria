"""Medición única de endpoints (invocado por benchmark_before_after)."""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ["LOCAL_SEED_CATALOG"] = "false"

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

_query_count = 0


@event.listens_for(Engine, "before_cursor_execute")
def _count_sql(conn, cursor, statement, parameters, context, executemany):
    global _query_count
    _query_count += 1


def _reset_sql():
    global _query_count
    _query_count = 0


def _seed(db):
    try:
        from tests.seed_perf import seed_perf_db

        seed_perf_db(db, num_ventas=120)
        return
    except ImportError:
        pass

    from datetime import timedelta
    from app.models.models import (
        UsuarioModel,
        CategoriaModel,
        ProductoModel,
        InsumoModel,
        RecetaModel,
        RecetaInsumoModel,
        VentaModel,
        DetalleVentaModel,
        PromocionModel,
    )
    from app.constants.roles import ADMIN
    from app.utils.security import hash_password
    from app.utils.timezone_mx import now_utc_naive

    admin = UsuarioModel(
        nombre="Admin Test",
        usuario_login="admintest",
        hash_password=hash_password("test1234"),
        rol=ADMIN,
    )
    db.add(admin)
    db.flush()
    cat = CategoriaModel(nombre="Bebidas")
    db.add(cat)
    db.flush()
    insumo_a = InsumoModel(nombre="Leche", unidad="ml", stock_actual=5000, stock_minimo=500, costo_unitario=0.02)
    insumo_b = InsumoModel(nombre="Cafe", unidad="g", stock_actual=3000, stock_minimo=300, costo_unitario=0.05)
    db.add_all([insumo_a, insumo_b])
    db.flush()
    prod_a = ProductoModel(nombre="Latte", id_categoria=cat.id_categoria, precio_venta=48, activo=True)
    prod_b = ProductoModel(nombre="Americano", id_categoria=cat.id_categoria, precio_venta=35, activo=True)
    db.add_all([prod_a, prod_b])
    db.flush()
    rec_a = RecetaModel(id_producto=prod_a.id_producto, nombre="Latte", activo=True, costo_total=12)
    rec_b = RecetaModel(id_producto=prod_b.id_producto, nombre="Americano", activo=True, costo_total=8)
    db.add_all([rec_a, rec_b])
    db.flush()
    db.add_all(
        [
            RecetaInsumoModel(id_receta=rec_a.id_receta, id_insumo=insumo_a.id_insumo, cantidad=200),
            RecetaInsumoModel(id_receta=rec_a.id_receta, id_insumo=insumo_b.id_insumo, cantidad=18),
            RecetaInsumoModel(id_receta=rec_b.id_receta, id_insumo=insumo_b.id_insumo, cantidad=15),
            RecetaInsumoModel(id_receta=rec_b.id_receta, id_insumo=insumo_a.id_insumo, cantidad=50),
        ]
    )
    promo = PromocionModel(
        nombre="2x1 test", tipo="DESCUENTO_FIJO", valor=5, activa=True, aplica_toda_tienda=True
    )
    db.add(promo)
    db.flush()
    base = now_utc_naive() - timedelta(days=45)
    for i in range(120):
        fh = base + timedelta(hours=i * 2, minutes=i % 60)
        venta = VentaModel(
            id_usuario=admin.id_usuario,
            total=83,
            forma_pago="EFECTIVO",
            fecha_hora=fh,
            numero_mesa=(i % 5) + 1,
        )
        db.add(venta)
        db.flush()
        db.add(
            DetalleVentaModel(
                id_venta=venta.id_venta,
                id_producto=prod_a.id_producto,
                cantidad=1,
                precio_unitario=48,
                subtotal=48,
            )
        )


def _setup():
    from app.database import Base, get_db
    from app.main import app as api

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    _seed(db)
    db.commit()
    db.close()

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    api.dependency_overrides[get_db] = override
    return api, Session


def _login(client: TestClient) -> dict:
    res = client.post("/auth/login", json={"usuario_login": "admintest", "password": "test1234"})
    res.raise_for_status()
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _bench(client, path, headers, runs=5):
    sql_counts, times = [], []
    for _ in range(runs):
        _reset_sql()
        t0 = time.perf_counter()
        res = client.get(path, headers=headers)
        res.raise_for_status()
        elapsed = (time.perf_counter() - t0) * 1000
        sql_counts.append(_query_count)
        times.append(float(res.headers.get("X-Process-Time-Ms", elapsed)))
    return statistics.mean(sql_counts), statistics.mean(times)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run")
    args = parser.parse_args()
    _ = args

    os.environ["PERF_LOG"] = "1"
    os.environ["PERF_LOG_SQL"] = "1"

    from app.utils.timezone_mx import today_mx

    api, _Session = _setup()
    hoy = today_mx()
    inicio = hoy.replace(day=1)
    paths = [
        f"/reportes/ventas-mes?anio={hoy.year}&mes={hoy.month}",
        f"/reportes/ventas-rango?fecha_inicio={inicio}&fecha_fin={hoy}",
        "/reportes/resumen-dashboard",
        f"/reportes/consumo-insumos?fecha={hoy}",
        f"/reportes/productos-ranking?periodo=mes&anio={hoy.year}&mes={hoy.month}",
        "/pedidos/activos",
        "/catalogo/productos",
        "/catalogo/insumos",
    ]

    with TestClient(api) as client:
        headers = _login(client)
        for path in paths:
            sql_avg, ms_avg = _bench(client, path, headers)
            print(f"ROW|{path}|{sql_avg:.1f}|{ms_avg:.2f}")
    api.dependency_overrides.clear()
    return 0


if __name__ == "__main__":
    sys.exit(main())
