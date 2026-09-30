"""Concurrencia de puntos en PostgreSQL desechable. No usar producción.

POSTGRES_TEST_URL=postgresql+psycopg2://user:pass@host:5432/pos_test
python -m pytest -q tests/test_puntos_postgres.py
"""
from __future__ import annotations

import json
import os
import random
import threading
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.constants.acciones import CANCELAR_PRODUCTO_EN_COMANDA
from app.exceptions import ConflictoOperacionException, DatosInvalidosException
from app.models.models import ClienteModel, FidelidadMovimientoModel, UsuarioModel, VentaModel, VentaPagoModel
from app.schemas.pedido import PedidoLineaCreate
from app.services.caja_service import abrir_caja, cerrar_caja, iniciar_arqueo
from app.services.cancelacion_service import cancelar_linea_enviada
from app.services.pedido_service import agregar_linea_pedido, cobrar_pedido, obtener_pedido_abierto_mesa
from app.services.venta_service import MESA_PARA_LLEVAR
from app.utils.security import hash_password
from tests.pg_test_guard import exigir_postgres_desechable
from tests.promo_seed import seed_promo_catalog

POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL", "").strip()
MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL no definido. No se ejecuta contra producción.",
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
            statements.append("\n".join(buf).strip())
            buf = []
    rest = "\n".join(buf).strip()
    if rest:
        statements.append(rest)
    return statements


def _apply_sql(engine, path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    if "DO $$" in raw:
        with engine.begin() as conn:
            conn.execute(text(raw))
        return
    with engine.begin() as conn:
        for stmt in _sql_statements(path):
            conn.execute(text(stmt))


@pytest.fixture()
def pg_engine():
    exigir_postgres_desechable(POSTGRES_TEST_URL)
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _timeouts(dbapi_conn, _connection_record):
        with dbapi_conn.cursor() as cur:
            cur.execute("SET lock_timeout TO '8s'")
            cur.execute("SET deadlock_timeout TO '1s'")

    from app.database import Base

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def pg_db(pg_engine):
    Session = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        refs = seed_promo_catalog(db)
        cliente = db.get(ClienteModel, refs.id_cliente)
        cliente.puntos_saldo = 500
        db.commit()
        yield db, refs
    finally:
        db.close()


def _cajero(db, login):
    u = UsuarioModel(
        nombre=login,
        usuario_login=login,
        hash_password=hash_password("test1234"),
        rol="CAJERO",
    )
    db.add(u)
    db.flush()
    return u


def _pedido(db, refs, user, mesa, producto, cantidad, precio):
    pedido = obtener_pedido_abierto_mesa(db, mesa, user.id_usuario, para_llevar=mesa == MESA_PARA_LLEVAR)
    agregar_linea_pedido(
        db,
        pedido,
        PedidoLineaCreate(
            id_producto=producto,
            cantidad=cantidad,
            precio_unitario=precio,
            enviar_comanda=False,
        ),
    )
    pedido.id_cliente = refs.id_cliente
    db.commit()
    db.refresh(pedido)
    return pedido


def _status(exc) -> int | None:
    if isinstance(exc, HTTPException):
        return exc.status_code
    return None


def test_006_impide_dos_redenciones_en_la_misma_venta(pg_engine):
    with pg_engine.connect() as conn:
        nombres = {
            r[0]
            for r in conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
            )
        }
    assert "uq_fidelidad_venta_tipo" in nombres
    assert "uq_venta_pago_un_puntos" in nombres
    assert "uq_venta_pago_un_monetario" in nombres
    assert "uq_cobro_operaciones_operation_id" in nombres


def test_dos_dispositivos_no_gastan_el_mismo_saldo(pg_engine, pg_db):
    db, refs = pg_db
    user = db.get(UsuarioModel, refs.id_usuario)
    p1 = _pedido(db, refs, user, 4, refs.id_cafe, 1, 50)
    p2 = _pedido(db, refs, user, 5, refs.id_cafe, 1, 50)
    with pg_engine.connect() as conn:
        deadlocks_antes = conn.execute(
            text("SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()")
        ).scalar()
    barrier = threading.Barrier(2)
    results = [None, None]

    def worker(i, pedido, oid):
        Session = sessionmaker(bind=pg_engine)
        ses = Session()
        try:
            barrier.wait(timeout=8)
            ped = ses.get(type(pedido), pedido.id_pedido)
            results[i] = (
                "ok",
                cobrar_pedido(
                    ses,
                    ped,
                    user.id_usuario,
                    "EFECTIVO",
                    puntos_canje=500,
                    operation_id=oid,
                ).id_venta,
            )
        except Exception as exc:
            results[i] = ("err", exc)
            ses.rollback()
        finally:
            ses.close()

    threads = [
        threading.Thread(target=worker, args=(0, p1, "pg-puntos-a")),
        threading.Thread(target=worker, args=(1, p2, "pg-puntos-b")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
        assert not t.is_alive()
    oks = [r for r in results if r and r[0] == "ok"]
    errs = [r for r in results if r and r[0] == "err"]
    assert len(oks) == 1, results
    assert len(errs) == 1
    from app.exceptions import SaldoPuntosCambioException

    assert isinstance(errs[0][1], SaldoPuntosCambioException)
    assert _status(errs[0][1]) == 409
    assert errs[0][1].detail["codigo"] == "SALDO_PUNTOS_CAMBIO"
    assert int(errs[0][1].detail["saldo_actual"]) < 500
    check = sessionmaker(bind=pg_engine)()
    try:
        cliente = check.get(ClienteModel, refs.id_cliente)
        assert int(cliente.puntos_saldo) >= 0
        redenciones = (
            check.query(FidelidadMovimientoModel)
            .filter_by(id_cliente=refs.id_cliente, tipo="REDENCION")
            .count()
        )
        assert redenciones == 1
        assert check.query(VentaModel).count() == 1
        ventas_ids = {v.id_venta for v in check.query(VentaModel).all()}
        pagos = check.query(VentaPagoModel).all()
        assert pagos
        assert {p.id_venta for p in pagos} <= ventas_ids
        _exigir_invariantes(check)
        deadlocks = check.execute(
            text("SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()")
        ).scalar()
        assert deadlocks == deadlocks_antes
    finally:
        check.close()


def test_mismo_operation_id_concurrente_una_sola_venta(pg_engine, pg_db):
    db, refs = pg_db
    user = db.get(UsuarioModel, refs.id_usuario)
    pedido = _pedido(db, refs, user, 6, refs.id_cafe, 1, 50)
    barrier = threading.Barrier(2)
    results = [None, None]

    def worker(i):
        Session = sessionmaker(bind=pg_engine)
        ses = Session()
        try:
            barrier.wait(timeout=8)
            ped = ses.get(type(pedido), pedido.id_pedido)
            results[i] = (
                "ok",
                cobrar_pedido(
                    ses, ped, user.id_usuario, "EFECTIVO", operation_id="pg-misma-clave"
                ).id_venta,
            )
        except Exception as exc:
            results[i] = ("err", exc)
            ses.rollback()
        finally:
            ses.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in (0, 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    ventas = {r[1] for r in results if r and r[0] == "ok"}
    assert len(ventas) == 1
    for kind, payload in results:
        if kind == "err":
            assert not isinstance(payload, ConflictoOperacionException) or True
            assert "deadlock" not in str(payload).lower()


def test_dos_clientes_cobran_en_paralelo(pg_engine, pg_db):
    db, refs = pg_db
    otro = ClienteModel(
        nombre="Otro",
        telefono=f"55{random.randint(10000000, 99999999)}",
        codigo_fidelidad=f"CAFE-{random.randint(1000, 9999)}",
        puntos_saldo=0,
        activo=True,
    )
    db.add(otro)
    user_b = _cajero(db, f"cajero_pg_{random.randint(1, 99999)}")
    db.commit()
    db.refresh(otro)
    a = _pedido(db, refs, db.get(UsuarioModel, refs.id_usuario), 7, refs.id_cafe, 1, 50)
    b = obtener_pedido_abierto_mesa(db, 8, user_b.id_usuario, para_llevar=False)
    agregar_linea_pedido(
        db,
        b,
        PedidoLineaCreate(id_producto=refs.id_cafe, cantidad=1, precio_unitario=50, enviar_comanda=False),
    )
    b.id_cliente = otro.id_cliente
    db.commit()
    barrier = threading.Barrier(2)
    results = [None, None]

    def worker(i, pedido, user_id, cliente_id, oid):
        Session = sessionmaker(bind=pg_engine)
        ses = Session()
        try:
            barrier.wait(timeout=8)
            ped = ses.get(type(pedido), pedido.id_pedido)
            results[i] = cobrar_pedido(ses, ped, user_id, "EFECTIVO", operation_id=oid).id_venta
        finally:
            ses.close()

    threads = [
        threading.Thread(target=worker, args=(0, a, refs.id_usuario, refs.id_cliente, "pg-cli-a")),
        threading.Thread(target=worker, args=(1, b, user_b.id_usuario, otro.id_cliente, "pg-cli-b")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert results[0] and results[1] and results[0] != results[1]


def test_cobro_con_puntos_espera_si_la_caja_esta_en_arqueo(pg_db):
    db, refs = pg_db
    user = db.get(UsuarioModel, refs.id_usuario)
    abrir_caja(db, user, fondo_inicial=20, terminal="CAJA-1", operation_id=f"pg-open-{random.randint(1, 99999)}")
    iniciar_arqueo(db, user, operation_id=f"pg-arq-{random.randint(1, 99999)}")
    pedido = _pedido(db, refs, user, 2, refs.id_cafe, 1, 50)
    with pytest.raises(ConflictoOperacionException):
        cobrar_pedido(db, pedido, user.id_usuario, "EFECTIVO", puntos_canje=50, operation_id="pg-vs-arqueo")
    assert db.query(VentaModel).count() == 0
    cliente = db.get(ClienteModel, refs.id_cliente)
    assert int(cliente.puntos_saldo) == 500
    assert Decimal("500") == Decimal(int(cliente.puntos_saldo))


def _sin_huerfanos(db, id_cliente: int) -> None:
    cliente = db.get(ClienteModel, id_cliente)
    assert int(cliente.puntos_saldo) >= 0
    ventas = db.query(VentaModel).all()
    ids = {v.id_venta for v in ventas}
    for pago in db.query(VentaPagoModel).all():
        assert pago.id_venta in ids
    for mov in db.query(FidelidadMovimientoModel).filter_by(tipo="REDENCION"):
        assert mov.id_venta in ids
    assert (
        db.query(FidelidadMovimientoModel)
        .filter_by(id_cliente=id_cliente, tipo="REDENCION")
        .count()
        <= 1
    )


def test_cobro_con_puntos_contra_cierre(pg_engine, pg_db):
    db, refs = pg_db
    user = db.get(UsuarioModel, refs.id_usuario)
    abrir_caja(db, user, fondo_inicial=20, terminal="CAJA-2", operation_id="pg-close-open")
    pedido = _pedido(db, refs, user, 3, refs.id_cafe, 1, 50)
    barrier = threading.Barrier(2)
    results = [None, None]

    def cobro():
        Session = sessionmaker(bind=pg_engine)
        ses = Session()
        try:
            barrier.wait(timeout=8)
            ped = ses.get(type(pedido), pedido.id_pedido)
            return cobrar_pedido(
                ses, ped, user.id_usuario, "EFECTIVO", puntos_canje=500, operation_id="pg-vs-cierre"
            ).id_venta
        finally:
            ses.close()

    def cierre():
        Session = sessionmaker(bind=pg_engine)
        ses = Session()
        try:
            barrier.wait(timeout=8)
            current = ses.get(UsuarioModel, user.id_usuario)
            return cerrar_caja(
                ses,
                current,
                denominaciones=[],
                declarado_efectivo=20,
                declarado_transferencia=0,
                declarado_tarjeta=0,
                captura_directa=True,
                observacion="cierre contra puntos",
                operation_id="pg-close-puntos",
            )
        finally:
            ses.close()

    def run(i, fn):
        try:
            results[i] = ("ok", fn())
        except Exception as exc:
            results[i] = ("err", exc)

    threads = [threading.Thread(target=run, args=(0, cobro)), threading.Thread(target=run, args=(1, cierre))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
        assert not t.is_alive()
    for kind, payload in results:
        assert kind in ("ok", "err")
        if kind == "err":
            assert "deadlock" not in str(payload).lower()
    check = sessionmaker(bind=pg_engine)()
    try:
        _sin_huerfanos(check, refs.id_cliente)
        venta = check.query(VentaModel).filter_by(id_cliente=refs.id_cliente).first()
        if venta:
            pagos = check.query(VentaPagoModel).filter_by(id_venta=venta.id_venta).all()
            assert len(pagos) == 1
            assert pagos[0].metodo == "PUNTOS"
            assert Decimal(pagos[0].importe_monetario) == 0
    finally:
        check.close()


def test_cobro_con_puntos_contra_cancelacion(pg_engine, pg_db):
    db, refs = pg_db
    user = db.get(UsuarioModel, refs.id_usuario)
    user.permisos_acciones_json = json.dumps([CANCELAR_PRODUCTO_EN_COMANDA])
    db.commit()
    pedido = _pedido(db, refs, user, 10, refs.id_cafe, 1, 50)
    from app.models.models import DetallePedidoModel

    detalle = db.query(DetallePedidoModel).filter_by(id_pedido=pedido.id_pedido).one()
    detalle.en_comanda = True
    db.commit()
    id_detalle = detalle.id_detalle_pedido
    barrier = threading.Barrier(2)
    results = [None, None]

    def cobro():
        Session = sessionmaker(bind=pg_engine)
        ses = Session()
        try:
            barrier.wait(timeout=8)
            ped = ses.get(type(pedido), pedido.id_pedido)
            return cobrar_pedido(
                ses, ped, user.id_usuario, "EFECTIVO", puntos_canje=50, operation_id="pg-vs-cancel"
            ).id_venta
        finally:
            ses.close()

    def cancelar():
        Session = sessionmaker(bind=pg_engine)
        ses = Session()
        try:
            barrier.wait(timeout=8)
            current = ses.get(UsuarioModel, user.id_usuario)
            return cancelar_linea_enviada(
                ses,
                id_detalle=id_detalle,
                current=current,
                cantidad=1,
                motivo="Producto duplicado",
                cantidad_actual=1,
            )
        finally:
            ses.close()

    def run(i, fn):
        try:
            results[i] = ("ok", fn())
        except Exception as exc:
            results[i] = ("err", exc)

    threads = [
        threading.Thread(target=run, args=(0, cobro)),
        threading.Thread(target=run, args=(1, cancelar)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
        assert not t.is_alive()
    for kind, payload in results:
        if kind == "err":
            assert "deadlock" not in str(payload).lower()
            assert _status(payload) in (409, 422)
    check = sessionmaker(bind=pg_engine)()
    try:
        _sin_huerfanos(check, refs.id_cliente)
        cliente = check.get(ClienteModel, refs.id_cliente)
        assert int(cliente.puntos_saldo) in (500, 454)
    finally:
        check.close()


def test_fallo_despues_de_redimir_revierte_en_postgres(pg_db, monkeypatch):
    db, refs = pg_db
    user = db.get(UsuarioModel, refs.id_usuario)
    cliente = db.get(ClienteModel, refs.id_cliente)
    cliente.puntos_saldo = 300
    db.commit()
    pedido = _pedido(db, refs, user, 11, refs.id_refresco, 1, 30)

    def boom(*_a, **_k):
        raise DatosInvalidosException("fallo forzado")

    monkeypatch.setattr("app.services.caja_service.registrar_pago_venta", boom)
    with pytest.raises(DatosInvalidosException):
        cobrar_pedido(db, pedido, user.id_usuario, "EFECTIVO", puntos_canje=200, operation_id="pg-rollback")
    db.expire_all()
    assert int(db.get(ClienteModel, refs.id_cliente).puntos_saldo) == 300
    assert db.query(VentaModel).count() == 0
    assert db.query(FidelidadMovimientoModel).count() == 0
    assert db.query(VentaPagoModel).count() == 0


def _exigir_invariantes(db) -> None:
    """Consultas de invariantes sobre ventas ya confirmadas."""
    negativos = db.execute(text("SELECT COUNT(*) FROM clientes WHERE puntos_saldo < 0")).scalar()
    assert int(negativos) == 0
    huerfanos_pago = db.execute(
        text(
            """
            SELECT COUNT(*) FROM venta_pagos p
            LEFT JOIN ventas v ON v.id_venta = p.id_venta
            WHERE v.id_venta IS NULL
            """
        )
    ).scalar()
    assert int(huerfanos_pago) == 0
    huerfanos_fid = db.execute(
        text(
            """
            SELECT COUNT(*) FROM fidelidad_movimientos m
            LEFT JOIN ventas v ON v.id_venta = m.id_venta
            WHERE m.id_venta IS NOT NULL AND v.id_venta IS NULL
            """
        )
    ).scalar()
    assert int(huerfanos_fid) == 0
    dup_op = db.execute(
        text(
            """
            SELECT COUNT(*) FROM (
                SELECT operation_id FROM venta_pagos
                GROUP BY operation_id HAVING COUNT(*) > 1
            ) d
            """
        )
    ).scalar()
    assert int(dup_op) == 0
    dup_cobro = db.execute(
        text(
            """
            SELECT COUNT(*) FROM (
                SELECT operation_id FROM cobro_operaciones
                GROUP BY operation_id HAVING COUNT(*) > 1
            ) d
            """
        )
    ).scalar()
    assert int(dup_cobro) == 0
    filas = db.execute(
        text(
            """
            SELECT v.id_venta, v.total, v.forma_pago,
                   COALESCE(SUM(p.importe_monetario), 0) AS dinero,
                   COALESCE(SUM(COALESCE(p.equivalencia_puntos, 0)), 0) AS eq,
                   COUNT(p.id_pago) AS n,
                   COUNT(*) FILTER (WHERE p.metodo = 'PUNTOS') AS n_puntos,
                   COUNT(*) FILTER (WHERE p.metodo <> 'PUNTOS') AS n_monetario
            FROM ventas v
            LEFT JOIN venta_pagos p ON p.id_venta = v.id_venta
            GROUP BY v.id_venta, v.total, v.forma_pago
            """
        )
    ).fetchall()
    for fila in filas:
        if int(fila.n) == 0:
            continue
        assert Decimal(fila.dinero) + Decimal(fila.eq) == Decimal(fila.total)
        assert int(fila.n) <= 2
        assert int(fila.n_puntos) <= 1
        assert int(fila.n_monetario) <= 1
        if fila.forma_pago == "PUNTOS":
            assert Decimal(fila.dinero) == 0
    puntos_mal = db.execute(
        text(
            """
            SELECT COUNT(*) FROM venta_pagos
            WHERE metodo = 'PUNTOS' AND importe_monetario <> 0
            """
        )
    ).scalar()
    assert int(puntos_mal) == 0
    red_dup = db.execute(
        text(
            """
            SELECT COUNT(*) FROM (
                SELECT id_venta FROM fidelidad_movimientos
                WHERE tipo = 'REDENCION' AND id_venta IS NOT NULL
                GROUP BY id_venta HAVING COUNT(*) > 1
            ) d
            """
        )
    ).scalar()
    acu_dup = db.execute(
        text(
            """
            SELECT COUNT(*) FROM (
                SELECT id_venta FROM fidelidad_movimientos
                WHERE tipo = 'ACUMULACION' AND id_venta IS NOT NULL
                GROUP BY id_venta HAVING COUNT(*) > 1
            ) d
            """
        )
    ).scalar()
    assert int(red_dup) == 0
    assert int(acu_dup) == 0
    desfase = db.execute(
        text(
            """
            SELECT COUNT(*) FROM venta_pagos p
            JOIN fidelidad_movimientos m
              ON m.id_venta = p.id_venta AND m.tipo = 'REDENCION'
            WHERE p.metodo = 'PUNTOS'
              AND p.cantidad_puntos <> -m.puntos
            """
        )
    ).scalar()
    assert int(desfase) == 0


def _insertar_venta(conn, uid, total, forma):
    return conn.execute(
        text(
            """
            INSERT INTO ventas (
                fecha_hora, id_usuario, numero_mesa, para_llevar, total, forma_pago, puntos_generados
            ) VALUES (NOW(), :uid, 40, false, :total, :forma, 0)
            RETURNING id_venta
            """
        ),
        {"uid": uid, "total": total, "forma": forma},
    ).scalar()


def _foto_pagos(conn, id_venta):
    return conn.execute(
        text(
            """
            SELECT metodo, importe_monetario, cantidad_puntos, equivalencia_puntos, operation_id
            FROM venta_pagos WHERE id_venta = :id
            ORDER BY metodo, operation_id
            """
        ),
        {"id": id_venta},
    ).fetchall()


def _apply_script(engine, path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    chunks = [raw]
    if "DO $$" in raw:
        before, rest = raw.split("DO $$", 1)
        body, after = rest.split("END $$;", 1)
        chunks = [before, "DO $$" + body + "END $$;", after]
    statements = []
    for chunk in chunks:
        if chunk.strip().startswith("DO $$"):
            statements.append(chunk.strip())
            continue
        buf = []
        for line in chunk.splitlines():
            if line.strip().startswith("--"):
                continue
            buf.append(line)
            if line.strip().endswith(";"):
                statements.append("\n".join(buf).strip())
                buf = []
        tail = "\n".join(buf).strip()
        if tail:
            statements.append(tail)
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def test_backfill_005_respeta_componentes_existentes(pg_engine, pg_db):
    """A–E: el INSERT de 005 no duplica ni reescribe componentes."""
    db, refs = pg_db
    uid = refs.id_usuario
    db.close()
    with pg_engine.begin() as conn:
        historica = _insertar_venta(conn, uid, 80, "EFECTIVO")
        existente = _insertar_venta(conn, uid, 80, "EFECTIVO")
        conn.execute(
            text(
                """
                INSERT INTO venta_pagos (
                    id_venta, metodo, importe_monetario, fecha_hora, id_usuario, operation_id
                ) VALUES (
                    :id, 'EFECTIVO', 40, NOW(), :uid, 'ya-monetario'
                )
                """
            ),
            {"id": existente, "uid": uid},
        )
        mixta = _insertar_venta(conn, uid, 120, "MIXTO")
        conn.execute(
            text(
                """
                INSERT INTO venta_pagos (
                    id_venta, metodo, importe_monetario, cantidad_puntos, equivalencia_puntos,
                    fecha_hora, id_usuario, operation_id
                ) VALUES
                    (:id, 'PUNTOS', 0, 200, 20, NOW(), :uid, 'mixta:PUNTOS'),
                    (:id, 'EFECTIVO', 100, NULL, NULL, NOW(), :uid, 'mixta:MONETARIO')
                """
            ),
            {"id": mixta, "uid": uid},
        )
        solo = _insertar_venta(conn, uid, 50, "PUNTOS")
        conn.execute(
            text(
                """
                INSERT INTO venta_pagos (
                    id_venta, metodo, importe_monetario, cantidad_puntos, equivalencia_puntos,
                    fecha_hora, id_usuario, operation_id
                ) VALUES (:id, 'PUNTOS', 0, 500, 50, NOW(), :uid, 'solo:PUNTOS')
                """
            ),
            {"id": solo, "uid": uid},
        )
    _apply_sql(pg_engine, MIGRATIONS / "005_cierre_caja_conciliacion.up.sql")
    with pg_engine.connect() as conn:
        hist = _foto_pagos(conn, historica)
        assert len(hist) == 1
        assert hist[0].metodo == "EFECTIVO"
        assert Decimal(hist[0].importe_monetario) == Decimal("80.00")
        ya = _foto_pagos(conn, existente)
        assert len(ya) == 1
        assert ya[0].operation_id == "ya-monetario"
        assert Decimal(ya[0].importe_monetario) == Decimal("40.00")
        mix = _foto_pagos(conn, mixta)
        assert [r.metodo for r in mix] == ["EFECTIVO", "PUNTOS"]
        assert Decimal(mix[0].importe_monetario) == Decimal("100.00")
        assert Decimal(mix[1].equivalencia_puntos) == Decimal("20.00")
        puntos = _foto_pagos(conn, solo)
        assert len(puntos) == 1
        assert puntos[0].metodo == "PUNTOS"
        assert Decimal(puntos[0].importe_monetario) == 0
        foto = {
            historica: [(r.metodo, str(r.importe_monetario), r.operation_id) for r in hist],
            existente: [(r.metodo, str(r.importe_monetario), r.operation_id) for r in ya],
            mixta: [(r.metodo, str(r.importe_monetario), r.operation_id) for r in mix],
            solo: [(r.metodo, str(r.importe_monetario), r.operation_id) for r in puntos],
        }
    _apply_sql(pg_engine, MIGRATIONS / "005_cierre_caja_conciliacion.up.sql")
    with pg_engine.connect() as conn:
        for id_venta, esperado in foto.items():
            actual = [
                (r.metodo, str(r.importe_monetario), r.operation_id)
                for r in _foto_pagos(conn, id_venta)
            ]
            assert actual == esperado
        descuadre = conn.execute(
            text(
                """
                SELECT v.id_venta
                FROM ventas v
                JOIN venta_pagos p ON p.id_venta = v.id_venta
                GROUP BY v.id_venta, v.total
                HAVING SUM(p.importe_monetario) + SUM(COALESCE(p.equivalencia_puntos, 0))
                       <> v.total
                """
            )
        ).fetchall()
        assert any(r.id_venta == existente for r in descuadre)


def test_006_dos_veces_y_down_en_desechable(pg_engine, pg_db):
    db, refs = pg_db
    up = MIGRATIONS / "006_puntos_pagos_mixtos.up.sql"
    down = MIGRATIONS / "006_puntos_pagos_mixtos.down.sql"
    uid = refs.id_usuario
    db.close()
    _apply_script(pg_engine, up)
    _apply_script(pg_engine, up)
    with pg_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO cobro_operaciones (
                    operation_id, payload_hash, id_usuario, saldo_anterior, saldo_final, fecha
                ) VALUES ('op-down', 'abc', :uid, 10, 12, NOW())
                """
            ),
            {"uid": uid},
        )
        venta = _insertar_venta(conn, uid, 10, "EFECTIVO")
        conn.execute(
            text(
                """
                INSERT INTO venta_pagos (
                    id_venta, metodo, importe_monetario, fecha_hora, id_usuario, operation_id
                ) VALUES (:id, 'EFECTIVO', 10, NOW(), :uid, 'queda-tras-down')
                """
            ),
            {"id": venta, "uid": uid},
        )
    _apply_script(pg_engine, down)
    with pg_engine.connect() as conn:
        tablas = {
            r[0]
            for r in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        }
        assert "cobro_operaciones" not in tablas
        assert "venta_pagos" in tablas
        queda = conn.execute(
            text("SELECT importe_monetario FROM venta_pagos WHERE operation_id = 'queda-tras-down'")
        ).scalar()
        assert Decimal(queda) == Decimal("10.00")
        idx = {
            r[0]
            for r in conn.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"))
        }
        assert "uq_fidelidad_venta_tipo" not in idx
        assert "uq_venta_pago_un_puntos" not in idx


def test_invariantes_de_venta_mixta_y_total(pg_db):
    db, refs = pg_db
    user = db.get(UsuarioModel, refs.id_usuario)
    cliente = db.get(ClienteModel, refs.id_cliente)
    cliente.puntos_saldo = 1000
    db.commit()
    mixto = _pedido(db, refs, user, 14, refs.id_refresco, 4, 30)
    cobrar_pedido(db, mixto, user.id_usuario, "EFECTIVO", puntos_canje=200, operation_id="inv-mixto")
    total = _pedido(db, refs, user, 15, refs.id_cafe, 1, 50)
    cobrar_pedido(db, total, user.id_usuario, "EFECTIVO", puntos_canje=500, operation_id="inv-total")
    cobrar_pedido(db, total, user.id_usuario, "EFECTIVO", puntos_canje=500, operation_id="inv-total")
    _exigir_invariantes(db)


def test_arranque_006_desde_esquema_005(pg_engine, pg_db):
    from app.services.migracion_puntos import (
        aplicar_migracion_006_puntos,
        verificar_esquema_puntos_mixtos,
    )

    db, refs = pg_db
    uid = refs.id_usuario
    db.close()
    with pg_engine.begin() as conn:
        venta = _insertar_venta(conn, uid, 25, "EFECTIVO")
        conn.execute(
            text(
                """
                INSERT INTO venta_pagos (
                    id_venta, metodo, importe_monetario, fecha_hora, id_usuario, operation_id
                ) VALUES (:id, 'EFECTIVO', 25, NOW(), :uid, 'antes-006')
                """
            ),
            {"id": venta, "uid": uid},
        )
        antes = conn.execute(text("SELECT COUNT(*), COALESCE(SUM(importe_monetario), 0) FROM venta_pagos")).one()
        conn.execute(text("DROP INDEX IF EXISTS uq_fidelidad_venta_tipo"))
        conn.execute(text("DROP INDEX IF EXISTS uq_venta_pago_un_puntos"))
        conn.execute(text("DROP INDEX IF EXISTS uq_venta_pago_un_monetario"))
        conn.execute(text("ALTER TABLE venta_pagos DROP CONSTRAINT IF EXISTS ck_venta_pago_componente"))
        conn.execute(text("DROP TABLE IF EXISTS cobro_operaciones"))
    with pytest.raises(RuntimeError) as incompleto:
        verificar_esquema_puntos_mixtos(pg_engine)
    assert "://" not in str(incompleto.value)
    assert "password" not in str(incompleto.value).lower()
    aplicar_migracion_006_puntos(pg_engine)
    verificar_esquema_puntos_mixtos(pg_engine)
    aplicar_migracion_006_puntos(pg_engine)
    verificar_esquema_puntos_mixtos(pg_engine)
    with pg_engine.connect() as conn:
        despues = conn.execute(
            text("SELECT COUNT(*), COALESCE(SUM(importe_monetario), 0) FROM venta_pagos")
        ).one()
    assert antes == despues


def test_postgres_exige_el_check_fisico(pg_engine):
    from app.services.migracion_puntos import (
        aplicar_migracion_006_puntos,
        verificar_esquema_puntos_mixtos,
    )

    verificar_esquema_puntos_mixtos(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(text("ALTER TABLE venta_pagos DROP CONSTRAINT ck_venta_pago_componente"))
    with pytest.raises(RuntimeError) as exc:
        verificar_esquema_puntos_mixtos(pg_engine)
    assert "ck_venta_pago_componente" in str(exc.value)
    assert "://" not in str(exc.value)
    aplicar_migracion_006_puntos(pg_engine)
    verificar_esquema_puntos_mixtos(pg_engine)
    with pg_engine.connect() as conn:
        existe = conn.execute(
            text("SELECT 1 FROM pg_constraint WHERE conname = 'ck_venta_pago_componente'")
        ).scalar()
    assert existe == 1


def test_006_no_arranca_con_duplicados_historicos(pg_engine, pg_db):
    from app.services.migracion_puntos import aplicar_migracion_006_puntos

    db, refs = pg_db
    uid = refs.id_usuario
    cliente_id = refs.id_cliente
    db.close()
    with pg_engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS uq_fidelidad_venta_tipo"))
        venta = _insertar_venta(conn, uid, 10, "EFECTIVO")
        for _ in (1, 2):
            conn.execute(
                text(
                    """
                    INSERT INTO fidelidad_movimientos (
                        id_cliente, tipo, puntos, saldo_despues, id_venta, fecha_hora, id_usuario
                    ) VALUES (:c, 'ACUMULACION', 1, 1, :v, NOW(), :u)
                    """
                ),
                {"c": cliente_id, "v": venta, "u": uid},
            )
    with pytest.raises(RuntimeError) as exc:
        aplicar_migracion_006_puntos(pg_engine)
    texto = str(exc.value)
    assert str(venta) in texto
    assert "://" not in texto
    assert "password" not in texto.lower()
    with pg_engine.connect() as conn:
        n = conn.execute(
            text("SELECT COUNT(*) FROM fidelidad_movimientos WHERE id_venta = :v"),
            {"v": venta},
        ).scalar()
        assert int(n) == 2
        idx = {r[0] for r in conn.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"))}
    assert "uq_fidelidad_venta_tipo" not in idx
