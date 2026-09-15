"""Concurrencia PostgreSQL: cancelar vs marcar listo vs cobro.

    set POSTGRES_TEST_URL=postgresql+psycopg2://user:pass@host:5432/pos_test
    python -m pytest -q tests/test_cancelacion_postgres.py

Si POSTGRES_TEST_URL no está definido, las pruebas se omiten.
NUNCA ejecutar contra producción.
"""
from __future__ import annotations

import json
import os
import random
import threading
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.constants.acciones import CANCELAR_PRODUCTO_EN_COMANDA
from app.models.models import (
    DetallePedidoModel,
    PedidoCancelacionModel,
    PedidoModel,
    ProductoModel,
    UsuarioModel,
    VentaModel,
)
from app.services.cancelacion_service import (
    cancelar_linea_enviada,
    marcar_linea_comanda_listo,
)
from app.services.pedido_service import (
    agregar_linea_pedido_con_respuesta,
    cobrar_pedido,
    obtener_pedido_abierto_mesa,
)
from tests.promo_seed import PromoSeed, seed_promo_catalog
from tests.test_estabilidad_idempotencia import _data

POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL", "").strip()
MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason=(
        "POSTGRES_TEST_URL no definido. "
        "Pendiente ejecutar estas pruebas contra PostgreSQL de prueba, no producción."
    ),
)


def _sql_statements(path: Path) -> list[str]:
    statements = []
    buf = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
    rest = "\n".join(buf).strip()
    if rest:
        statements.append(rest)
    return statements


def _apply_sql(engine, path: Path) -> None:
    with engine.begin() as conn:
        for stmt in _sql_statements(path):
            conn.execute(text(stmt))


def _grant_cancel(db, id_usuario: int) -> None:
    user = db.get(UsuarioModel, id_usuario)
    user.permisos_acciones_json = json.dumps([CANCELAR_PRODUCTO_EN_COMANDA])


def _load_refs(db) -> PromoSeed:
    refs = PromoSeed()
    user = db.query(UsuarioModel).filter_by(usuario_login="cajero_test").first()
    cafe = db.query(ProductoModel).filter_by(nombre="Cafe").first()
    malteada = db.query(ProductoModel).filter_by(nombre="Malteada").first()
    if not user or not cafe:
        raise RuntimeError("Catálogo de prueba PostgreSQL incompleto")
    refs.id_usuario = user.id_usuario
    refs.id_cafe = cafe.id_producto
    refs.id_malteada = malteada.id_producto if malteada else cafe.id_producto
    _grant_cancel(db, user.id_usuario)
    return refs


def _status(exc) -> int | None:
    if isinstance(exc, HTTPException):
        return exc.status_code
    return None


def _is_deadlock(exc) -> bool:
    return "deadlock" in str(exc).lower()


def _mesa() -> int:
    return random.randint(10000, 19999)


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _timeouts(dbapi_conn, _connection_record):
        with dbapi_conn.cursor() as cur:
            cur.execute("SET lock_timeout TO '8s'")
            cur.execute("SET deadlock_timeout TO '1s'")

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
    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        refs = seed_promo_catalog(db)
        _grant_cancel(db, refs.id_usuario)
        db.commit()
    except IntegrityError:
        db.rollback()
        refs = _load_refs(db)
        db.commit()
    db.close()
    return refs, Session


def _linea_en_comanda(Session, refs, mesa: int, cantidad: float = 2, para_llevar: bool = False):
    db = Session()
    try:
        pedido = obtener_pedido_abierto_mesa(
            db, mesa, refs.id_usuario, para_llevar=para_llevar
        )
        _, detalle = agregar_linea_pedido_con_respuesta(
            db,
            pedido,
            _data(db, refs.id_cafe, cantidad=cantidad, enviar_comanda=True),
        )
        return pedido.id_pedido, detalle.id_detalle_pedido
    finally:
        db.close()


def _invariantes(detalle: DetallePedidoModel) -> None:
    cant = float(detalle.cantidad or 0)
    lista = float(detalle.cantidad_lista or 0)
    cancelada = float(getattr(detalle, "cantidad_cancelada", 0) or 0)
    assert cant >= 0
    assert lista >= 0
    assert cancelada >= 0
    assert lista <= cant + 0.001
    if getattr(detalle, "estado_linea", "ACTIVA") == "CANCELADA":
        assert cant == 0


def _run_parallel(workers):
    n = len(workers)
    barrier = threading.Barrier(n)
    results = [None] * n

    def wrap(i, fn):
        try:
            barrier.wait(timeout=8)
            results[i] = ("ok", fn())
        except Exception as exc:
            results[i] = ("err", exc)

    threads = [threading.Thread(target=wrap, args=(i, fn)) for i, fn in enumerate(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
        assert not t.is_alive(), "hilo no terminó (posible bloqueo)"
    for kind, payload in results:
        if kind == "err" and _is_deadlock(payload):
            pytest.fail(f"deadlock: {payload}")
        if kind == "err" and _status(payload) == 500:
            pytest.fail(f"error 500: {payload}")
        if kind == "err" and _status(payload) is None:
            pytest.fail(f"error inesperado: {type(payload).__name__}: {payload}")
    return results


def _permite_abierto(pedido: PedidoModel) -> bool:
    return pedido is not None and pedido.estado == "ABIERTO"


def test_migracion_004_se_puede_aplicar_dos_veces(pg_engine, pg_refs):
    _apply_sql(pg_engine, MIGRATIONS / "002_pedido_operaciones.up.sql")
    _apply_sql(pg_engine, MIGRATIONS / "003_usuarios_permisos_auditoria.up.sql")
    _apply_sql(pg_engine, MIGRATIONS / "004_cancelacion_lineas.up.sql")
    _apply_sql(pg_engine, MIGRATIONS / "004_cancelacion_lineas.up.sql")
    with pg_engine.connect() as conn:
        det_cols = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'detalle_pedido'"
                )
            )
        }
        assert "estado_linea" in det_cols
        assert "cantidad_cancelada" in det_cols
        tables = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
            )
        }
        assert "pedido_cancelaciones" in tables
        can_cols = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'pedido_cancelaciones'"
                )
            )
        }
        for col in (
            "id_cancelacion",
            "id_pedido",
            "id_detalle_pedido",
            "cantidad",
            "cantidad_anterior",
            "cantidad_nueva",
            "motivo",
            "estado_anterior",
            "estado_nuevo",
            "aviso",
            "aviso_texto",
            "id_usuario",
            "fecha_hora",
            "vista_comandera",
        ):
            assert col in can_cols, col
        idxs = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = 'public' AND tablename = 'pedido_cancelaciones'"
                )
            )
        }
        assert "idx_cancelaciones_pedido" in idxs
        assert "idx_cancelaciones_detalle" in idxs
        assert "idx_cancelaciones_vista" in idxs

    refs, Session = pg_refs
    pedido_id, id_detalle = _linea_en_comanda(Session, refs, _mesa(), cantidad=2)
    db = Session()
    try:
        current = db.get(UsuarioModel, refs.id_usuario)
        cancelar_linea_enviada(
            db,
            id_detalle=id_detalle,
            current=current,
            cantidad=1,
            motivo="Producto duplicado",
            cantidad_actual=2,
        )
        avisos = (
            db.query(PedidoCancelacionModel)
            .filter_by(id_detalle_pedido=id_detalle)
            .all()
        )
        assert len(avisos) == 1
        det = db.get(DetallePedidoModel, id_detalle)
        _invariantes(det)
        pedido = db.get(PedidoModel, pedido_id)
        assert pedido is not None
    finally:
        db.close()


def test_cancelacion_total_y_marcar_listo_simultaneos(pg_refs):
    refs, Session = pg_refs
    pedido_id, id_detalle = _linea_en_comanda(Session, refs, _mesa(), cantidad=2)

    def cancelar():
        db = Session()
        try:
            current = db.get(UsuarioModel, refs.id_usuario)
            return cancelar_linea_enviada(
                db,
                id_detalle=id_detalle,
                current=current,
                cantidad=2,
                motivo="Producto no disponible",
                cantidad_actual=2,
            )
        finally:
            db.close()

    def listo():
        db = Session()
        try:
            return marcar_linea_comanda_listo(
                db,
                id_detalle=id_detalle,
                cantidad=1,
                cantidad_actual=2,
                cantidad_lista_actual=0,
                pedido_permite_listo=_permite_abierto,
            )
        finally:
            db.close()

    results = _run_parallel([cancelar, listo])
    oks = [r for r in results if r[0] == "ok"]
    errs = [r for r in results if r[0] == "err"]
    assert oks, results
    for _, exc in errs:
        assert _status(exc) in (409, 422)

    db = Session()
    try:
        det = db.get(DetallePedidoModel, id_detalle)
        _invariantes(det)
        if det.estado_linea == "CANCELADA":
            listo_despues = None
            try:
                listo_despues = marcar_linea_comanda_listo(
                    db,
                    id_detalle=id_detalle,
                    cantidad=1,
                    pedido_permite_listo=_permite_abierto,
                )
            except HTTPException as exc:
                assert exc.status_code in (409, 422)
            assert listo_despues is None
        avisos = (
            db.query(PedidoCancelacionModel)
            .filter_by(id_detalle_pedido=id_detalle)
            .count()
        )
        assert avisos <= 1
        assert db.get(PedidoModel, pedido_id) is not None
    finally:
        db.close()


def test_cancelacion_parcial_y_marcar_listo_simultaneos(pg_refs):
    refs, Session = pg_refs
    _, id_detalle = _linea_en_comanda(Session, refs, _mesa(), cantidad=2)

    def cancelar():
        db = Session()
        try:
            current = db.get(UsuarioModel, refs.id_usuario)
            return cancelar_linea_enviada(
                db,
                id_detalle=id_detalle,
                current=current,
                cantidad=1,
                motivo="Producto duplicado",
                cantidad_actual=2,
            )
        finally:
            db.close()

    def listo():
        db = Session()
        try:
            return marcar_linea_comanda_listo(
                db,
                id_detalle=id_detalle,
                cantidad=1,
                cantidad_actual=2,
                cantidad_lista_actual=0,
                pedido_permite_listo=_permite_abierto,
            )
        finally:
            db.close()

    results = _run_parallel([cancelar, listo])
    for kind, payload in results:
        if kind == "err":
            assert _status(payload) in (409, 422)
    db = Session()
    try:
        det = db.get(DetallePedidoModel, id_detalle)
        _invariantes(det)
        avisos = (
            db.query(PedidoCancelacionModel)
            .filter_by(id_detalle_pedido=id_detalle)
            .count()
        )
        assert avisos <= 1
    finally:
        db.close()


def test_dos_cancelaciones_misma_cantidad_actual(pg_refs):
    refs, Session = pg_refs
    _, id_detalle = _linea_en_comanda(Session, refs, _mesa(), cantidad=2)

    def cancelar():
        db = Session()
        try:
            current = db.get(UsuarioModel, refs.id_usuario)
            return cancelar_linea_enviada(
                db,
                id_detalle=id_detalle,
                current=current,
                cantidad=1,
                motivo="Producto duplicado",
                cantidad_actual=2,
            )
        finally:
            db.close()

    results = _run_parallel([cancelar, cancelar])
    oks = [r for r in results if r[0] == "ok"]
    errs = [r for r in results if r[0] == "err"]
    assert len(oks) == 1, results
    assert len(errs) == 1
    assert _status(errs[0][1]) in (409, 422)
    db = Session()
    try:
        det = db.get(DetallePedidoModel, id_detalle)
        _invariantes(det)
        assert float(det.cantidad) == 1
        avisos = (
            db.query(PedidoCancelacionModel)
            .filter_by(id_detalle_pedido=id_detalle)
            .count()
        )
        assert avisos == 1
    finally:
        db.close()


def test_dos_marcar_listo_simultaneos(pg_refs):
    refs, Session = pg_refs
    _, id_detalle = _linea_en_comanda(Session, refs, _mesa(), cantidad=2)

    def listo():
        db = Session()
        try:
            return marcar_linea_comanda_listo(
                db,
                id_detalle=id_detalle,
                cantidad=1,
                cantidad_actual=2,
                cantidad_lista_actual=0,
                pedido_permite_listo=_permite_abierto,
            )
        finally:
            db.close()

    results = _run_parallel([listo, listo])
    oks = [r for r in results if r[0] == "ok"]
    errs = [r for r in results if r[0] == "err"]
    assert len(oks) == 1, results
    assert len(errs) == 1
    assert _status(errs[0][1]) in (409, 422)
    db = Session()
    try:
        det = db.get(DetallePedidoModel, id_detalle)
        _invariantes(det)
        assert float(det.cantidad_lista) == 1
        assert det.estado_linea != "CANCELADA"
    finally:
        db.close()


def test_cobro_simultaneo_con_cancelacion(pg_refs):
    refs, Session = pg_refs
    pedido_id, id_detalle = _linea_en_comanda(Session, refs, _mesa(), cantidad=2)

    def cancelar():
        db = Session()
        try:
            current = db.get(UsuarioModel, refs.id_usuario)
            return cancelar_linea_enviada(
                db,
                id_detalle=id_detalle,
                current=current,
                cantidad=1,
                motivo="Producto duplicado",
                cantidad_actual=2,
            )
        finally:
            db.close()

    def cobro():
        db = Session()
        try:
            pedido = db.get(PedidoModel, pedido_id)
            return cobrar_pedido(
                db, pedido, refs.id_usuario, "EFECTIVO", origen_cobro="VENTAS"
            )
        finally:
            db.close()

    results = _run_parallel([cancelar, cobro])
    for kind, payload in results:
        if kind == "err":
            assert _status(payload) in (409, 422)
    db = Session()
    try:
        pedido = db.get(PedidoModel, pedido_id)
        det = db.get(DetallePedidoModel, id_detalle)
        _invariantes(det)
        avisos = (
            db.query(PedidoCancelacionModel)
            .filter_by(id_detalle_pedido=id_detalle)
            .count()
        )
        assert avisos <= 1
        if pedido.estado == "COBRADO":
            assert pedido.id_venta is not None
            venta = db.get(VentaModel, pedido.id_venta)
            assert venta is not None
            qty_venta = sum(float(d.cantidad) for d in venta.detalles)
            assert abs(qty_venta - float(det.cantidad)) < 0.02
        else:
            assert pedido.estado == "ABIERTO"
            assert float(det.cantidad) == 1
    finally:
        db.close()
