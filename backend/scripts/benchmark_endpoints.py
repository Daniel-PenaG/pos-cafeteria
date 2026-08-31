"""Benchmark de endpoints con conteo SQL (dev/test)."""
from __future__ import annotations

import os
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_pos_perf.db")
os.environ.setdefault("PERF_LOG", "1")
os.environ.setdefault("PERF_LOG_SQL", "1")

import app.utils.sql_counter  # noqa: F401 — registra listener
from app.main import app as api  # noqa: E402
from app.utils.sql_counter import reset_sql_count, get_sql_count  # noqa: E402
from app.utils.timezone_mx import today_mx  # noqa: E402


def _login(client: TestClient) -> dict:
    credenciales = [
        {"usuario_login": "admintest", "password": "test1234"},
        {"usuario_login": os.getenv("LOCAL_ADMIN_LOGIN", "admin"), "password": os.getenv("LOCAL_ADMIN_PASSWORD", "admin123")},
    ]
    for body in credenciales:
        res = client.post("/auth/login", json=body)
        if res.status_code == 200:
            token = res.json()["access_token"]
            return {"Authorization": f"Bearer {token}"}
    raise RuntimeError("Login falló — ejecuta pytest o configura LOCAL_ADMIN_*")


def _bench(client, path, headers, runs=5):
    times = []
    sql_counts = []
    for _ in range(runs):
        reset_sql_count()
        res = client.get(path, headers=headers)
        res.raise_for_status()
        times.append(float(res.headers.get("X-Process-Time-Ms", 0)))
        sql_counts.append(get_sql_count())
    return {
        "endpoint": path,
        "sql_avg": round(statistics.mean(sql_counts), 1),
        "time_avg_ms": round(statistics.mean(times), 2),
    }


def main():
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
        rows = [_bench(client, p, headers) for p in paths]

    print(f"{'Endpoint':<70} {'SQL avg':>8} {'ms avg':>10}")
    print("-" * 90)
    for r in rows:
        print(f"{r['endpoint']:<70} {r['sql_avg']:>8} {r['time_avg_ms']:>10}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
