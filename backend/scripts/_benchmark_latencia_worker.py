"""Worker JSON de benchmark (invocado por benchmark_latencia_operativa).

Solo mide el endpoint bajo prueba: setup (prep) fuera de SQL y cronómetro.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("PERF_LOG", "1")
os.environ.setdefault("PERF_LOG_SQL", "1")

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


def _percentile(vals, p):
    s = sorted(vals)
    if not s:
        return 0.0
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def _stats(ms_list, sql_list, bytes_list, samples: int) -> dict:
    return {
        "samples": samples,
        "p50_ms": round(_percentile(ms_list, 50), 2),
        "p95_ms": round(_percentile(ms_list, 95), 2),
        "max_ms": round(max(ms_list), 2),
        "sql_p50": round(_percentile(sql_list, 50), 1),
        "sql_p95": round(_percentile(sql_list, 95), 1),
        "bytes_p50": int(_percentile(bytes_list, 50)),
    }


def _measure_call(fn, warmup, runs):
    for _ in range(warmup):
        fn()
    ms_list, sql_list, bytes_list = [], [], []
    for _ in range(runs):
        _reset_sql()
        t0 = time.perf_counter()
        res = fn()
        elapsed = (time.perf_counter() - t0) * 1000
        hdr_ms = float(res.headers.get("X-Process-Time-Ms", elapsed))
        ms_list.append(hdr_ms)
        sql_list.append(_query_count)
        body = res.content if hasattr(res, "content") else b""
        bytes_list.append(len(body))
    return _stats(ms_list, sql_list, bytes_list, runs)


def _measure_call_with_setup(setup_fn, action_fn, warmup, runs):
    for _ in range(warmup):
        ctx = setup_fn()
        action_fn(ctx)
    ms_list, sql_list, bytes_list = [], [], []
    for _ in range(runs):
        ctx = setup_fn()
        _reset_sql()
        t0 = time.perf_counter()
        res = action_fn(ctx)
        elapsed = (time.perf_counter() - t0) * 1000
        hdr_ms = float(res.headers.get("X-Process-Time-Ms", elapsed))
        ms_list.append(hdr_ms)
        sql_list.append(_query_count)
        body = res.content if hasattr(res, "content") else b""
        bytes_list.append(len(body))
    return _stats(ms_list, sql_list, bytes_list, runs)


def _setup():
    from app.database import Base, get_db
    from app.main import app as api

    url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    kw = {}
    if url.startswith("sqlite"):
        kw = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    engine = create_engine(url, **kw)
    if not url.startswith("sqlite:///:memory:"):
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        from tests.seed_perf import seed_perf_db

        seed_perf_db(db, num_ventas=120)
        db.commit()
    finally:
        db.close()

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    api.dependency_overrides[get_db] = override
    return api, Session


def _login(client):
    res = client.post("/auth/login", json={"usuario_login": "admintest", "password": "test1234"})
    res.raise_for_status()
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _precio_producto(client, headers, producto_id=1):
    ctx = client.get(f"/ventas/productos/{producto_id}/contexto", headers=headers)
    ctx.raise_for_status()
    return ctx.json()


def _prep_pedido(client, headers, uid, mesa, num_lineas, producto_id=1, extras=None):
    client.get(f"/pedidos/mesa/{mesa}?id_usuario={uid}", headers=headers)
    ctx_json = _precio_producto(client, headers, producto_id)
    precio = ctx_json["calculo_inicial"]["precio_unitario"]
    extras = extras if extras is not None else []
    if extras:
        precio = float(precio) + sum(float(x.get("precio") or 0) for x in extras)
    for _ in range(num_lineas):
        client.post(
            f"/pedidos/mesa/{mesa}/lineas?id_usuario={uid}",
            headers=headers,
            json={
                "id_producto": producto_id,
                "cantidad": 1,
                "precio_unitario": precio,
                "extras": extras,
                "operation_id": str(uuid.uuid4()),
            },
        ).raise_for_status()
    ped = client.get(f"/pedidos/mesa/{mesa}?id_usuario={uid}", headers=headers).json()
    return ped


def _extra_payload_desde_contexto(ctx_json):
    extras = ctx_json.get("extras") or []
    if not extras:
        return []
    e = extras[0]
    return [
        {
            "id_extra": e["id_extra"],
            "nombre": e.get("nombre") or "Extra",
            "precio": float(e.get("precio") or 0),
            "costo": float(e.get("costo") or 0) if e.get("costo") is not None else None,
            "id_insumo": e.get("id_insumo"),
            "cantidad_insumo": float(e.get("cantidad_insumo") or e.get("cantidad") or 1),
        }
    ]


def _mesa_rotativa(counter_attr):
    n = getattr(counter_attr, "n", 0)
    counter_attr.n = n + 1
    return (n % 5) + 1


def _want_scenario(sid: str) -> bool:
    only = (os.getenv("BENCHMARK_ONLY") or "").strip()
    if not only:
        return True
    allowed = {x.strip() for x in only.split(",") if x.strip()}
    return sid in allowed


def main():
    warmup = int(os.getenv("WARMUP", "3"))
    runs = int(os.getenv("RUNS", "10"))
    api, _ = _setup()
    scenarios = {}
    with TestClient(api) as client:
        headers = _login(client)
        uid = 1

        if _want_scenario("contexto_producto"):
            scenarios["contexto_producto"] = _measure_call(
            lambda: client.get("/ventas/productos/1/contexto", headers=headers),
            warmup,
            runs,
            )

        def _prep_primera_linea():
            m = _mesa_rotativa(_prep_primera_linea)
            client.get(f"/pedidos/mesa/{m}?id_usuario={uid}", headers=headers)
            ctx_json = _precio_producto(client, headers, 1)
            return {
                "mesa": m,
                "precio": ctx_json["calculo_inicial"]["precio_unitario"],
            }

        def _post_primera_linea(ctx):
            return client.post(
                f"/pedidos/mesa/{ctx['mesa']}/lineas?id_usuario={uid}",
                headers=headers,
                json={
                    "id_producto": 1,
                    "cantidad": 1,
                    "precio_unitario": ctx["precio"],
                    "extras": [],
                    "operation_id": str(uuid.uuid4()),
                },
            )

        if _want_scenario("agregar_primera_linea"):
            _prep_primera_linea.n = 0
            scenarios["agregar_primera_linea"] = _measure_call_with_setup(
                _prep_primera_linea, _post_primera_linea, warmup, runs
            )

        def _prep_decima_linea():
            m = _mesa_rotativa(_prep_decima_linea)
            _prep_pedido(client, headers, uid, m, 9)
            ctx_json = _precio_producto(client, headers, 1)
            return {
                "mesa": m,
                "precio": ctx_json["calculo_inicial"]["precio_unitario"],
            }

        def _post_decima_linea(ctx):
            return client.post(
                f"/pedidos/mesa/{ctx['mesa']}/lineas?id_usuario={uid}",
                headers=headers,
                json={
                    "id_producto": 1,
                    "cantidad": 1,
                    "precio_unitario": ctx["precio"],
                    "extras": [],
                    "operation_id": str(uuid.uuid4()),
                },
            )

        if _want_scenario("agregar_decima_linea"):
            _prep_decima_linea.n = 0
            scenarios["agregar_decima_linea"] = _measure_call_with_setup(
                _prep_decima_linea, _post_decima_linea, warmup, runs
            )

        def _prep_confirm_10():
            m = _mesa_rotativa(_prep_confirm_10)
            return _prep_pedido(client, headers, uid, m, 10)

        def _post_confirmar(ped):
            return client.post(
                f"/pedidos/{ped['id_pedido']}/confirmar-comanda", headers=headers
            )

        if _want_scenario("confirmar_10_lineas"):
            _prep_confirm_10.n = 0
            scenarios["confirmar_10_lineas"] = _measure_call_with_setup(
                _prep_confirm_10, _post_confirmar, warmup, runs
            )

        def _prep_marcar_listo():
            m = _mesa_rotativa(_prep_marcar_listo)
            ped = _prep_pedido(client, headers, uid, m, 1)
            client.post(
                f"/pedidos/{ped['id_pedido']}/confirmar-comanda", headers=headers
            ).raise_for_status()
            pend = client.get("/comandera/pendientes", headers=headers).json()
            row = next(
                (x for x in pend if x["id_pedido"] == ped["id_pedido"]),
                pend[0] if pend else None,
            )
            if not row:
                raise RuntimeError("sin línea comandera")
            return row

        def _post_marcar_listo(row):
            ca = row.get("cantidad_actual") or row.get("cantidad")
            cl = row.get("cantidad_lista_actual") or row.get("cantidad_lista") or 0
            return client.post(
                f"/comandera/lineas/{row['id_detalle_pedido']}/listo",
                headers=headers,
                json={"cantidad": 1, "cantidad_actual": ca, "cantidad_lista_actual": cl},
            )

        if _want_scenario("marcar_listo"):
            _prep_marcar_listo.n = 0
            scenarios["marcar_listo"] = _measure_call_with_setup(
                _prep_marcar_listo, _post_marcar_listo, warmup, runs
            )

        ses = client.get("/caja/sesion-actual", headers=headers)
        if not (ses.status_code == 200 and ses.json().get("abierta")):
            client.post(
                "/caja/apertura",
                headers=headers,
                json={"efectivo_inicial": 500, "operation_id": str(uuid.uuid4())},
            )

        def _prep_cobrar_linea():
            m = _mesa_rotativa(_prep_cobrar_linea)
            ped = _prep_pedido(client, headers, uid, m, 1)
            client.post(
                f"/pedidos/{ped['id_pedido']}/confirmar-comanda", headers=headers
            ).raise_for_status()
            return ped

        def _post_cobrar(ped):
            return client.post(
                f"/pedidos/{ped['id_pedido']}/cobrar",
                headers=headers,
                json={"forma_pago": "EFECTIVO", "operation_id": str(uuid.uuid4())},
            )

        if _want_scenario("cobrar_1_linea"):
            _prep_cobrar_linea.n = 0
            scenarios["cobrar_1_linea"] = _measure_call_with_setup(
                _prep_cobrar_linea, _post_cobrar, warmup, runs
            )

        def _prep_cobrar_10():
            m = _mesa_rotativa(_prep_cobrar_10)
            ctx_json = _precio_producto(client, headers, 1)
            extras = _extra_payload_desde_contexto(ctx_json)
            ped = _prep_pedido(client, headers, uid, m, 10, producto_id=1, extras=extras)
            client.post(
                f"/pedidos/{ped['id_pedido']}/confirmar-comanda", headers=headers
            ).raise_for_status()
            return ped

        if _want_scenario("cobrar_10_lineas_receta_extras_promo"):
            _prep_cobrar_10.n = 0
            scenarios["cobrar_10_lineas_receta_extras_promo"] = _measure_call_with_setup(
                _prep_cobrar_10, _post_cobrar, warmup, runs
            )

    api.dependency_overrides.clear()
    out = {
        "commit": os.getenv("PERF_GIT_COMMIT", ""),
        "warmup": warmup,
        "samples_per_scenario": runs,
        "setup_outside_sql_and_timer": True,
        "scenarios": scenarios,
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
