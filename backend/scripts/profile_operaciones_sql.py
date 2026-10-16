"""Perfil top-20 firmas SQL por operación (PERF_LOG_SQL_SIGNATURE=1)."""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("PERF_LOG_SQL_SIGNATURE", "1")
os.environ.setdefault("PERF_LOG_SQL", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("LOCAL_SEED_CATALOG", "false")
os.environ.setdefault("LOCAL_SEED_QUIET", "1")
for _k in ("CAPTURE_PASSWORD", "CAPTURE_LOGIN", "E2E_CAPTURE_PASSWORD", "E2E_CAPTURE_LOGIN"):
    os.environ.pop(_k, None)

import app.utils.sql_counter  # noqa: F401
from app.utils.perf_trace import perf_phase
from app.utils.sql_signature_profiler import clear_sql_phase, reset_profile, top_signatures, total_stats


def _setup():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.database import Base, get_db
    from app.main import app as api
    from fastapi.testclient import TestClient

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    from tests.seed_perf import seed_perf_db

    seed_perf_db(db, num_ventas=80)
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


def _run(label: str, fn):
    reset_profile()
    clear_sql_phase()
    with perf_phase(label, "total"):
        fn()
    return {"operacion": label, "stats": total_stats(), "top20": top_signatures(20)}


def main() -> int:
    api, Session = _setup()
    from fastapi.testclient import TestClient

    out = {}
    with TestClient(api) as client:
        login = client.post("/auth/login", json={"usuario_login": "admintest", "password": "test1234"})
        login.raise_for_status()
        h = {"Authorization": f"Bearer {login.json()['access_token']}"}
        uid = 1

        def ctx():
            client.get("/ventas/productos/1/contexto", headers=h).raise_for_status()

        out["contexto_producto"] = _run("contexto_producto", ctx)

        def linea1():
            client.post(
                f"/pedidos/mesa/2/lineas?id_usuario={uid}",
                headers=h,
                json={
                    "id_producto": 1,
                    "cantidad": 1,
                    "precio_unitario": client.get("/ventas/productos/1/contexto", headers=h).json()[
                        "calculo_inicial"
                    ]["precio_unitario"],
                    "extras": [],
                    "operation_id": str(uuid.uuid4()),
                },
            ).raise_for_status()

        out["agregar_linea_1"] = _run("agregar_linea_1", linea1)

        for i in range(9):
            linea1()
        out["agregar_linea_10"] = _run("agregar_linea_10", linea1)

        ped = client.get(f"/pedidos/mesa/2?id_usuario={uid}", headers=h).json()

        def confirmar():
            client.post(f"/pedidos/{ped['id_pedido']}/confirmar-comanda", headers=h).raise_for_status()

        out["confirmar_pedido"] = _run("confirmar_pedido", confirmar)

        mesa10 = 4
        client.get(f"/pedidos/mesa/{mesa10}?id_usuario={uid}", headers=h)
        precio10 = client.get("/ventas/productos/1/contexto", headers=h).json()["calculo_inicial"][
            "precio_unitario"
        ]
        for _ in range(10):
            client.post(
                f"/pedidos/mesa/{mesa10}/lineas?id_usuario={uid}",
                headers=h,
                json={
                    "id_producto": 1,
                    "cantidad": 1,
                    "precio_unitario": precio10,
                    "extras": [],
                    "operation_id": str(uuid.uuid4()),
                },
            ).raise_for_status()
        ped10 = client.get(f"/pedidos/mesa/{mesa10}?id_usuario={uid}", headers=h).json()

        def confirmar_10():
            client.post(
                f"/pedidos/{ped10['id_pedido']}/confirmar-comanda", headers=h
            ).raise_for_status()

        out["confirmar_10_lineas"] = _run("confirmar_10_lineas", confirmar_10)

        pend = client.get("/comandera/pendientes", headers=h).json()
        row = pend[0]

        def listo():
            client.post(
                f"/comandera/lineas/{row['id_detalle_pedido']}/listo",
                headers=h,
                json={
                    "cantidad": 1,
                    "cantidad_actual": row.get("cantidad") or row.get("cantidad_actual"),
                    "cantidad_lista_actual": row.get("cantidad_lista") or row.get("cantidad_lista_actual") or 0,
                },
            ).raise_for_status()

        out["marcar_listo"] = _run("marcar_listo", listo)

        client.post(
            "/caja/apertura",
            headers=h,
            json={"efectivo_inicial": 500, "operation_id": str(uuid.uuid4())},
        )

        def cobrar1():
            m = 3
            p = client.get(f"/pedidos/mesa/{m}?id_usuario={uid}", headers=h).json()
            if not p.get("id_pedido"):
                precio = client.get("/ventas/productos/1/contexto", headers=h).json()["calculo_inicial"][
                    "precio_unitario"
                ]
                client.post(
                    f"/pedidos/mesa/{m}/lineas?id_usuario={uid}",
                    headers=h,
                    json={
                        "id_producto": 1,
                        "cantidad": 1,
                        "precio_unitario": precio,
                        "extras": [],
                        "operation_id": str(uuid.uuid4()),
                    },
                ).raise_for_status()
                p = client.get(f"/pedidos/mesa/{m}?id_usuario={uid}", headers=h).json()
            client.post(f"/pedidos/{p['id_pedido']}/confirmar-comanda", headers=h)
            client.post(
                f"/pedidos/{p['id_pedido']}/cobrar",
                headers=h,
                json={"forma_pago": "EFECTIVO", "operation_id": str(uuid.uuid4())},
            ).raise_for_status()

        out["cobrar_1_linea"] = _run("cobrar_1_linea", cobrar1)

    doc_path = ROOT.parent / "docs" / "sql_profile_operaciones.json"
    doc_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Perfil escrito en {doc_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
