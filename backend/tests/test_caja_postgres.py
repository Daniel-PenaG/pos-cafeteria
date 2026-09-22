"""Concurrencia PostgreSQL: sesiones de caja (migración 005).

    set POSTGRES_TEST_URL=postgresql+psycopg2://user:pass@host:5432/pos_test
    python -m pytest -q tests/test_caja_postgres.py

Si POSTGRES_TEST_URL no está definido, las pruebas se omiten.
NUNCA ejecutar contra producción.
"""
from __future__ import annotations

import os
import random
import threading
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.constants.caja import ESTADOS_ACTIVOS
from app.models.models import SesionCajaModel, UsuarioModel, VentaModel
from app.schemas.ventas import DetalleVentaItem, VentaCreate
from app.services.caja_service import abrir_caja, cerrar_caja, registrar_movimiento
from app.services.venta_service import registrar_venta
from app.utils.security import hash_password
from tests.pg_test_guard import exigir_postgres_desechable
from tests.promo_seed import PromoSeed, seed_promo_catalog

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


def _tablas(conn) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
    }


def _columnas(conn, tabla: str) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t"
            ),
            {"t": tabla},
        )
    }


def _indices(conn, tabla: str) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = :t"
            ),
            {"t": tabla},
        )
    }


def _aplicar_005(engine) -> None:
    _apply_sql(engine, MIGRATIONS / "005_cierre_caja_conciliacion.up.sql")


def _dejar_esquema_pre_005(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS venta_pagos CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS arqueo_denominaciones CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS movimientos_caja CASCADE"))
        conn.execute(text("ALTER TABLE ventas DROP COLUMN IF EXISTS id_sesion_caja"))
        conn.execute(text("ALTER TABLE cierres_caja DROP COLUMN IF EXISTS id_sesion_caja"))
        conn.execute(text("DROP TABLE IF EXISTS sesiones_caja CASCADE"))
        conn.execute(text("ALTER TABLE configuracion DROP COLUMN IF EXISTS tolerancia_efectivo"))


def _assert_pre_005(engine) -> None:
    with engine.connect() as conn:
        tablas = _tablas(conn)
        assert "sesiones_caja" not in tablas
        assert "movimientos_caja" not in tablas
        assert "venta_pagos" not in tablas
        if "ventas" in tablas:
            assert "id_sesion_caja" not in _columnas(conn, "ventas")


def _assert_post_005(engine) -> None:
    with engine.connect() as conn:
        tablas = _tablas(conn)
        for t in ("sesiones_caja", "movimientos_caja", "arqueo_denominaciones", "venta_pagos"):
            assert t in tablas, t
        assert "id_sesion_caja" in _columnas(conn, "ventas")
        idxs = _indices(conn, "sesiones_caja")
        assert "uq_sesion_caja_operation_id" in idxs
        assert "uq_sesion_caja_usuario_activa" in idxs
        assert "uq_sesion_caja_terminal_activa" in idxs


def _status(exc) -> int | None:
    if isinstance(exc, HTTPException):
        return exc.status_code
    return None


def _is_deadlock(exc) -> bool:
    return "deadlock" in str(exc).lower()


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
        if kind == "err" and _status(payload) is None and not isinstance(payload, IntegrityError):
            orig = getattr(payload, "orig", None)
            if orig and "unique" in str(orig).lower():
                continue
            pytest.fail(f"error inesperado: {type(payload).__name__}: {payload}")
    return results


def _load_user(db) -> UsuarioModel:
    user = db.query(UsuarioModel).filter_by(usuario_login="cajero_test").first()
    if not user:
        raise RuntimeError("Catálogo de prueba PostgreSQL incompleto")
    return user


def _otro_cajero(db, login: str) -> UsuarioModel:
    u = db.query(UsuarioModel).filter_by(usuario_login=login).first()
    if u:
        return u
    u = UsuarioModel(
        nombre=login,
        usuario_login=login,
        hash_password=hash_password("test1234"),
        rol="CAJERO",
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture(scope="module")
def pg_engine():
    exigir_postgres_desechable(POSTGRES_TEST_URL)
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _timeouts(dbapi_conn, _connection_record):
        with dbapi_conn.cursor() as cur:
            cur.execute("SET lock_timeout TO '8s'")
            cur.execute("SET deadlock_timeout TO '1s'")

    from app.database import Base

    Base.metadata.create_all(engine)
    _aplicar_005(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def pg_refs(pg_engine):
    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        refs = seed_promo_catalog(db)
        db.commit()
    except IntegrityError:
        db.rollback()
        refs = PromoSeed()
        user = db.query(UsuarioModel).filter_by(usuario_login="cajero_test").first()
        refs.id_usuario = user.id_usuario
        db.commit()
    db.close()
    return refs, Session


def test_guarda_rechaza_misma_base_que_database_url():
    exigir_postgres_desechable(POSTGRES_TEST_URL)


def test_migracion_005_se_puede_aplicar_dos_veces(pg_engine):
    exigir_postgres_desechable(POSTGRES_TEST_URL)
    _dejar_esquema_pre_005(pg_engine)
    _assert_pre_005(pg_engine)
    _aplicar_005(pg_engine)
    _assert_post_005(pg_engine)
    _aplicar_005(pg_engine)
    _assert_post_005(pg_engine)


def _cerrar_si_abierta(db, user):
    from app.services.caja_service import sesion_activa_usuario

    activa = sesion_activa_usuario(db, user.id_usuario)
    if not activa:
        return
    cerrar_caja(
        db,
        user,
        denominaciones=[],
        declarado_efectivo=float(activa.fondo_inicial or 0),
        declarado_transferencia=0,
        declarado_tarjeta=0,
        captura_directa=True,
        observacion="cleanup test",
        operation_id=f"pg-cleanup-{random.randint(1, 9_999_999)}",
    )


def _cerrar_activas_terminal(db, terminal: str):
    activas = (
        db.query(SesionCajaModel)
        .filter(SesionCajaModel.terminal == terminal, SesionCajaModel.estado.in_(ESTADOS_ACTIVOS))
        .all()
    )
    for s in activas:
        user = db.get(UsuarioModel, s.id_usuario)
        if user:
            _cerrar_si_abierta(db, user)


def test_indices_unicos_apertura(pg_refs):
    refs, Session = pg_refs
    db = Session()
    try:
        user = _otro_cajero(db, "cajero_idx_pg")
        _cerrar_si_abierta(db, user)
        _cerrar_activas_terminal(db, "CAJA-1")
        abrir_caja(db, user, fondo_inicial=10, terminal="CAJA-1", operation_id=f"pg-open-{random.randint(1, 99999)}")
        with pytest.raises(HTTPException):
            abrir_caja(db, user, fondo_inicial=10, terminal="CAJA-2", operation_id=f"pg-open-b-{random.randint(1, 99999)}")
    finally:
        db.close()


def test_apertura_concurrente(pg_refs):
    refs, Session = pg_refs
    db = Session()
    try:
        user = _otro_cajero(db, "cajero_conc_pg")
        _cerrar_si_abierta(db, user)
        uid = user.id_usuario
        db.commit()
    finally:
        db.close()
    oid_a = f"pg-conc-a-{random.randint(1, 9_999_999)}"
    oid_b = f"pg-conc-b-{random.randint(1, 9_999_999)}"

    def worker(oid, terminal):
        db = Session()
        try:
            user = db.get(UsuarioModel, uid)
            return abrir_caja(db, user, fondo_inicial=15, terminal=terminal, operation_id=oid)
        finally:
            db.close()

    results = _run_parallel(
        [
            lambda: worker(oid_a, "CAJA-2"),
            lambda: worker(oid_b, "CAJA-3"),
        ]
    )
    oks = [r for r in results if r[0] == "ok"]
    errs = [r for r in results if r[0] == "err"]
    assert len(oks) == 1
    assert len(errs) == 1
    assert _status(errs[0][1]) == 409


def test_doble_cierre_concurrente(pg_refs):
    refs, Session = pg_refs
    db = Session()
    try:
        user = _otro_cajero(db, "cajero_cierre_pg")
        abrir_caja(db, user, fondo_inicial=20, terminal="BARRA", operation_id=f"pg-bar-{random.randint(1, 99999)}")
        uid = user.id_usuario
        db.commit()
    finally:
        db.close()

    def worker(oid):
        dbw = Session()
        try:
            current = dbw.get(UsuarioModel, uid)
            return cerrar_caja(
                dbw,
                current,
                denominaciones=[],
                declarado_efectivo=20,
                declarado_transferencia=0,
                declarado_tarjeta=0,
                captura_directa=True,
                operation_id=oid,
            )
        finally:
            dbw.close()

    results = _run_parallel(
        [
            lambda: worker("pg-close-same"),
            lambda: worker("pg-close-same"),
        ]
    )
    oks = [r for r in results if r[0] == "ok"]
    assert len(oks) >= 1
    ids = {r[1]["id_sesion_caja"] for r in oks}
    assert len(ids) == 1


def test_movimientos_concurrentes_e_idempotencia(pg_refs):
    refs, Session = pg_refs
    db = Session()
    try:
        user = _otro_cajero(db, "cajero_mov_pg")
        _cerrar_si_abierta(db, user)
        _cerrar_activas_terminal(db, "CAJA-1")
        abrir_caja(db, user, fondo_inicial=50, terminal="CAJA-1", operation_id=f"pg-mov-open-{random.randint(1, 99999)}")
        uid = user.id_usuario
        db.commit()
    except Exception:
        db.rollback()
        user = db.query(UsuarioModel).filter_by(usuario_login="cajero_mov_pg").first()
        uid = user.id_usuario
    finally:
        db.close()

    oid = f"pg-mov-idem-{random.randint(1, 9_999_999)}"

    def worker():
        dbw = Session()
        try:
            current = dbw.get(UsuarioModel, uid)
            return registrar_movimiento(
                dbw,
                current,
                tipo="ENTRADA",
                importe=5,
                motivo="entrada idem",
                operation_id=oid,
            )
        finally:
            dbw.close()

    results = _run_parallel([worker, worker])
    oks = [r for r in results if r[0] == "ok"]
    assert len(oks) >= 1
    ids = {r[1]["id_movimiento"] for r in oks}
    assert len(ids) == 1


def test_venta_contra_cierre(pg_refs):
    refs, Session = pg_refs
    from app.models.models import ProductoModel

    db = Session()
    try:
        user = _otro_cajero(db, "cajero_venta_cierre")
        _cerrar_si_abierta(db, user)
        _cerrar_activas_terminal(db, "CAJA-3")
        abrir_caja(
            db,
            user,
            fondo_inicial=30,
            terminal="CAJA-3",
            operation_id=f"pg-vc-open-{random.randint(1, 99999)}",
        )
        cafe = db.query(ProductoModel).filter_by(nombre="Cafe").first()
        uid = user.id_usuario
        pid = cafe.id_producto
        db.commit()
    finally:
        db.close()

    def cobro():
        dbw = Session()
        try:
            return registrar_venta(
                dbw,
                VentaCreate(
                    id_usuario=uid,
                    numero_mesa=14,
                    forma_pago="EFECTIVO",
                    detalles=[DetalleVentaItem(id_producto=pid, cantidad=1, precio_unitario=50)],
                ),
            )
        finally:
            dbw.close()

    def cierre():
        dbw = Session()
        try:
            current = dbw.get(UsuarioModel, uid)
            return cerrar_caja(
                dbw,
                current,
                denominaciones=[],
                declarado_efectivo=30,
                declarado_transferencia=0,
                declarado_tarjeta=0,
                captura_directa=True,
                observacion="cierre vs venta",
                operation_id=f"pg-vc-close-{random.randint(1, 99999)}",
            )
        finally:
            dbw.close()

    results = _run_parallel([cobro, cierre])
    oks = [r for r in results if r[0] == "ok"]
    assert len(oks) >= 1
    db = Session()
    try:
        ventas = db.query(VentaModel).filter(VentaModel.id_usuario == uid).all()
        for v in ventas:
            if v.id_sesion_caja:
                sesion = db.get(SesionCajaModel, v.id_sesion_caja)
                assert sesion is not None
    finally:
        db.close()
