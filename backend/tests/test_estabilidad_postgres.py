"""Concurrencia real de PostgreSQL.

SQLite no reproduce bloqueos ni el índice único parcial como PostgreSQL.

Preparada para ejecutarse antes del despliegue:

    set POSTGRES_TEST_URL=postgresql+psycopg2://user:pass@host:5432/pos_test
    python -m pytest -q tests/test_estabilidad_postgres.py

Si POSTGRES_TEST_URL no está definido, las pruebas se omiten (no fallan).
NO se conecta a producción. NO se aplica en el merge de esta revisión.
"""
from __future__ import annotations

import os
import random
import threading
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models.models import DetallePedidoModel, PedidoModel, PedidoOperacionModel, ProductoModel, UsuarioModel
from app.schemas.pedido import PedidoLineaCreate
from app.services.pedido_service import (
    agregar_linea_pedido_con_respuesta,
    obtener_pedido_abierto_mesa,
)
from tests.pg_test_guard import exigir_postgres_desechable
from tests.promo_seed import seed_promo_catalog
from tests.test_promociones_integracion import _linea

POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason=(
        "POSTGRES_TEST_URL no definido. "
        "Pendiente ejecutar estas pruebas contra PostgreSQL antes del despliegue."
    ),
)


def _data(db, id_producto, operation_id):
    det = _linea(db, id_producto, 1, None, None)
    return PedidoLineaCreate(
        id_producto=id_producto,
        cantidad=1,
        precio_unitario=det.precio_unitario,
        precio_original=det.precio_original,
        id_promocion=det.id_promocion,
        extras=[],
        enviar_comanda=False,
        operation_id=operation_id,
    )


@pytest.fixture(scope="module")
def pg_engine():
    exigir_postgres_desechable(POSTGRES_TEST_URL)
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)
    from app.database import Base

    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_pedidos_abierto_mesa
                ON pedidos (numero_mesa, para_llevar)
                WHERE estado = 'ABIERTO'
                """
            )
        )
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def pg_refs(pg_engine):
    from tests.promo_seed import PromoSeed

    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        refs = seed_promo_catalog(db)
        db.commit()
    except IntegrityError:
        db.rollback()
        refs = PromoSeed()
        user = db.query(UsuarioModel).filter_by(usuario_login="cajero_test").first()
        malteada = db.query(ProductoModel).filter_by(nombre="Malteada").first()
        cafe = db.query(ProductoModel).filter_by(nombre="Cafe").first()
        if not user or not malteada:
            raise RuntimeError("Catálogo de prueba PostgreSQL incompleto")
        refs.id_usuario = user.id_usuario
        refs.id_malteada = malteada.id_producto
        refs.id_cafe = cafe.id_producto if cafe else malteada.id_producto
        db.commit()
    db.close()
    return refs, Session


def _mesa() -> int:
    return random.randint(20000, 29999)


def test_postgres_misma_clave_concurrente(pg_refs):
    refs, Session = pg_refs
    mesa = _mesa()
    setup = Session()
    pedido = obtener_pedido_abierto_mesa(setup, mesa, refs.id_usuario)
    setup.commit()
    pedido_id = pedido.id_pedido
    setup.close()

    key = str(uuid.uuid4())
    errores = []
    respuestas = []
    barrier = threading.Barrier(2)

    def worker():
        db = Session()
        try:
            barrier.wait(timeout=5)
            p = db.get(PedidoModel, pedido_id)
            resp, _ = agregar_linea_pedido_con_respuesta(
                db, p, _data(db, refs.id_malteada, key)
            )
            respuestas.append(resp)
        except Exception as exc:
            errores.append(exc)
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    verify = Session()
    lineas = verify.query(DetallePedidoModel).filter_by(id_pedido=pedido_id).all()
    ops = verify.query(PedidoOperacionModel).filter_by(operation_id=key).all()
    vacios = [
        p.id_pedido
        for p in verify.query(PedidoModel).filter_by(numero_mesa=mesa, estado="ABIERTO").all()
        if verify.query(DetallePedidoModel).filter_by(id_pedido=p.id_pedido).count() == 0
    ]
    verify.close()

    assert errores == [], errores
    assert len(respuestas) == 2
    assert {r["id_pedido"] for r in respuestas} == {pedido_id}
    assert len(lineas) == 1
    assert float(lineas[0].cantidad) == 1
    assert vacios == []
    assert len(ops) == 1


def test_postgres_dos_sesiones_primer_producto(pg_refs):
    refs, Session = pg_refs
    mesa = _mesa()
    errores = []
    respuestas = []
    barrier = threading.Barrier(2)

    def worker(id_producto, key):
        db = Session()
        try:
            barrier.wait(timeout=5)
            pedido = obtener_pedido_abierto_mesa(db, mesa, refs.id_usuario)
            resp, _ = agregar_linea_pedido_con_respuesta(
                db, pedido, _data(db, id_producto, key)
            )
            respuestas.append(resp)
        except Exception as exc:
            errores.append(exc)
        finally:
            db.close()

    t1 = threading.Thread(target=worker, args=(refs.id_cafe, str(uuid.uuid4())))
    t2 = threading.Thread(target=worker, args=(refs.id_malteada, str(uuid.uuid4())))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    verify = Session()
    abiertos = (
        verify.query(PedidoModel)
        .filter_by(numero_mesa=mesa, estado="ABIERTO", para_llevar=False)
        .all()
    )
    lineas = (
        verify.query(DetallePedidoModel).filter_by(id_pedido=abiertos[0].id_pedido).all()
        if abiertos
        else []
    )
    ops = (
        verify.query(PedidoOperacionModel)
        .filter_by(id_pedido=abiertos[0].id_pedido)
        .all()
        if abiertos
        else []
    )
    verify.close()

    assert errores == [], errores
    assert len(respuestas) == 2
    assert len(abiertos) == 1
    assert {r["id_pedido"] for r in respuestas} == {abiertos[0].id_pedido}
    assert len(lineas) == 2
    assert {d.id_producto for d in lineas} == {refs.id_cafe, refs.id_malteada}
    assert len(ops) == 2
