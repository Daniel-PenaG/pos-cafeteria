"""Pruebas PostgreSQL de Tesorería.

Se omiten si POSTGRES_TEST_URL no está definido.
La base tiene que ser desechable y distinta de DATABASE_URL.
El DOWN solo corre dentro de estas pruebas, sobre esa base.
No imprime URLs ni credenciales.
"""
from __future__ import annotations

import os
import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import (
    CategoriaModel,
    CuentaTesoreriaModel,
    MovimientoTesoreriaModel,
    OperacionTesoreriaModel,
    ProductoModel,
    UsuarioModel,
    VentaModel,
)
from app.schemas.ventas import DetalleVentaItem, VentaCreate
from app.services.caja_service import abrir_caja, cerrar_caja
from app.services.migracion_tesoreria import (
    aplicar_down_tesoreria_desechable,
    aplicar_migracion_008_tesoreria,
    verificar_esquema_tesoreria,
)
from app.services.tesoreria_service import (
    activar,
    dinero,
    registrar_salida_origen,
    revertir,
    saldo_cuenta,
    traspasar,
)
from app.services.venta_service import registrar_venta
from app.utils.security import hash_password
from app.utils.timezone_mx import now_utc_naive
from tests.pg_test_guard import exigir_postgres_desechable

POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL no definido. No se ejecuta contra producción.",
)


def _tablas(conn) -> set[str]:
    return {
        fila[0]
        for fila in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    }


def _columnas(conn, tabla: str) -> set[str]:
    return {
        fila[0]
        for fila in conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :tabla"
            ),
            {"tabla": tabla},
        )
    }


def _reset(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))


def _pre_008(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "DROP TABLE IF EXISTS conciliaciones_tesoreria, movimientos_tesoreria, "
                "activacion_tesoreria, operaciones_tesoreria, cuentas_tesoreria CASCADE"
            )
        )
        for tabla, columna in (
            ("gastos", "estado_pago"),
            ("gastos", "clasificacion"),
            ("gastos", "id_cuenta_tesoreria"),
            ("compras", "estado_pago"),
            ("compras", "id_cuenta_tesoreria"),
        ):
            if tabla in _tablas(conn) and columna in _columnas(conn, tabla):
                conn.execute(text(f"ALTER TABLE {tabla} DROP COLUMN {columna}"))


@pytest.fixture(scope="module")
def pg_engine():
    exigir_postgres_desechable(POSTGRES_TEST_URL)
    engine = create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _timeouts(dbapi_conn, _connection_record):
        with dbapi_conn.cursor() as cur:
            cur.execute("SET lock_timeout TO '8s'")
            cur.execute("SET deadlock_timeout TO '200ms'")
        dbapi_conn.commit()

    _reset(engine)
    Base.metadata.create_all(engine)
    _pre_008(engine)
    aplicar_migracion_008_tesoreria(engine)
    aplicar_migracion_008_tesoreria(engine)
    verificar_esquema_tesoreria(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def sesiones(pg_engine):
    factory = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    with pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM arqueo_denominaciones"))
        conn.execute(text("DELETE FROM movimientos_caja"))
        conn.execute(text("DELETE FROM venta_pagos"))
        conn.execute(text("DELETE FROM detalle_venta"))
        conn.execute(text("UPDATE ventas SET id_sesion_caja = NULL"))
        conn.execute(text("DELETE FROM ventas"))
        conn.execute(text("DELETE FROM cierres_caja"))
        conn.execute(text("DELETE FROM sesiones_caja"))
        conn.execute(
            text(
                "TRUNCATE conciliaciones_tesoreria, movimientos_tesoreria, "
                "activacion_tesoreria, operaciones_tesoreria RESTART IDENTITY CASCADE"
            )
        )
    db = factory()
    admin = db.query(UsuarioModel).filter_by(usuario_login="admin_pg_tes").first()
    if not admin:
        admin = UsuarioModel(
            nombre="Admin demo",
            usuario_login="admin_pg_tes",
            hash_password=hash_password("test1234"),
            rol="ADMIN",
            activo=True,
        )
        db.add(admin)
        db.flush()
    if not db.query(ProductoModel).filter_by(nombre="Café demo pg").first():
        cat = CategoriaModel(nombre="Bebidas demo pg")
        db.add(cat)
        db.flush()
        db.add(ProductoModel(nombre="Café demo pg", id_categoria=cat.id_categoria, precio_venta=42, activo=True))
    db.commit()
    admin_id = admin.id_usuario
    cafe_id = db.query(ProductoModel).filter_by(nombre="Café demo pg").one().id_producto
    db.close()

    def abrir():
        return factory()

    return abrir, admin_id, cafe_id


def _admin(db, admin_id):
    return db.query(UsuarioModel).filter_by(id_usuario=admin_id).one()


def _activar(db, admin_id, cafeteria=500, casa=200, banco=300, operation_id="activacion-pg"):
    return activar(
        db,
        _admin(db, admin_id),
        fecha_corte=now_utc_naive() - timedelta(minutes=1),
        efectivo_cafeteria=dinero(cafeteria),
        efectivo_casa=dinero(casa),
        saldo_banco=dinero(banco),
        observacion="Corte sintético",
        operation_id=operation_id,
    )


def _saldos(db) -> dict[str, Decimal]:
    return {cuenta.codigo: saldo_cuenta(db, cuenta.id_cuenta) for cuenta in db.query(CuentaTesoreriaModel)}


def _hilos(trabajos: list) -> None:
    barrera = threading.Barrier(len(trabajos))

    def correr(fn):
        barrera.wait(timeout=15)
        fn()

    hilos = [threading.Thread(target=correr, args=(fn,)) for fn in trabajos]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=25)
        assert not hilo.is_alive(), "un hilo no terminó; posible deadlock"


def _trabajo(abrir, fn, salida: dict):
    def correr():
        db = abrir()
        try:
            fn(db)
            db.commit()
            salida["estado"] = "ok"
        except Exception as exc:
            db.rollback()
            salida["estado"] = type(exc).__name__
            salida["detalle"] = str(exc)
        finally:
            db.close()

    return correr


def test_la_guarda_rechaza_la_misma_base_que_database_url():
    exigir_postgres_desechable(POSTGRES_TEST_URL)


def test_008_sobre_pre_008_es_idempotente_y_conserva_el_esquema_previo(pg_engine):
    with pg_engine.connect() as conn:
        tablas = _tablas(conn)
        assert "ventas" in tablas
        assert "venta_pagos" in tablas
        assert "sesiones_caja" in tablas
        assert "detalle_pedido" in tablas
        detalle = _columnas(conn, "detalle_pedido")
        assert "sin_promocion" in detalle
        assert "subtotal" in detalle
        activaciones = conn.execute(text("SELECT COUNT(*) FROM activacion_tesoreria")).scalar()
        cuentas = {
            fila[0]
            for fila in conn.execute(text("SELECT codigo FROM cuentas_tesoreria"))
        }
    assert int(activaciones or 0) == 0
    assert cuentas == {"EFECTIVO_CAFETERIA", "EFECTIVO_CASA", "BANCO"}

    try:
        with pg_engine.begin() as conn:
            conn.execute(text("ALTER TABLE cuentas_tesoreria DROP COLUMN codigo"))
        with pytest.raises(RuntimeError, match="incompleto"):
            verificar_esquema_tesoreria(pg_engine)
    finally:
        with pg_engine.begin() as conn:
            conn.execute(
                text(
                    "DROP TABLE IF EXISTS conciliaciones_tesoreria, movimientos_tesoreria, "
                    "activacion_tesoreria, operaciones_tesoreria, cuentas_tesoreria CASCADE"
                )
            )
        aplicar_migracion_008_tesoreria(pg_engine)
        verificar_esquema_tesoreria(pg_engine)
    with pg_engine.connect() as conn:
        assert "ventas" in _tablas(conn)
        assert "sin_promocion" in _columnas(conn, "detalle_pedido")


def test_activacion_concurrente_deja_una_sola(sesiones):
    abrir, admin_id, _cafe = sesiones
    salidas = [{}, {}]

    def intento(db, clave):
        _activar(db, admin_id, operation_id=clave)

    _hilos([
        _trabajo(abrir, lambda db: intento(db, "act-a"), salidas[0]),
        _trabajo(abrir, lambda db: intento(db, "act-b"), salidas[1]),
    ])
    assert sorted(item["estado"] for item in salidas) == ["ConflictoOperacionException", "ok"]
    db = abrir()
    try:
        assert db.query(OperacionTesoreriaModel).filter_by(tipo="SALDO_INICIAL").count() == 3
        assert db.execute(text("SELECT COUNT(*) FROM activacion_tesoreria")).scalar() == 1
    finally:
        db.close()


def test_dos_traspasos_no_dejan_saldo_negativo(sesiones):
    abrir, admin_id, _cafe = sesiones
    db = abrir()
    _activar(db, admin_id, cafeteria=100, casa=0, banco=0)
    db.commit()
    db.close()
    salidas = [{}, {}]

    def mover(db, clave):
        traspasar(
            db,
            _admin(db, admin_id),
            codigo_origen="EFECTIVO_CAFETERIA",
            codigo_destino="EFECTIVO_CASA",
            importe=dinero(80),
            concepto="Traspaso",
            observacion="Demo",
            operation_id=clave,
        )

    _hilos([
        _trabajo(abrir, lambda db: mover(db, "tr-a"), salidas[0]),
        _trabajo(abrir, lambda db: mover(db, "tr-b"), salidas[1]),
    ])
    assert sorted(item["estado"] for item in salidas) == ["DatosInvalidosException", "ok"]
    db = abrir()
    try:
        saldos = _saldos(db)
        assert saldos["EFECTIVO_CAFETERIA"] == dinero(20)
        assert saldos["EFECTIVO_CASA"] == dinero(80)
        assert min(saldos.values()) >= 0
    finally:
        db.close()


def test_misma_operation_id_concurrente_no_duplica(sesiones):
    abrir, admin_id, _cafe = sesiones
    db = abrir()
    _activar(db, admin_id, cafeteria=100, casa=0, banco=0, operation_id="act-replay")
    db.commit()
    db.close()
    salidas = [{}, {}]

    def mover(db):
        traspasar(
            db,
            _admin(db, admin_id),
            codigo_origen="EFECTIVO_CAFETERIA",
            codigo_destino="BANCO",
            importe=dinero(30),
            concepto="Depósito",
            observacion="Demo",
            operation_id="deposito-unico",
        )

    _hilos([
        _trabajo(abrir, mover, salidas[0]),
        _trabajo(abrir, mover, salidas[1]),
    ])
    assert [item["estado"] for item in salidas] == ["ok", "ok"]
    db = abrir()
    try:
        assert db.query(OperacionTesoreriaModel).filter_by(operation_id="deposito-unico").count() == 1
        assert _saldos(db)["EFECTIVO_CAFETERIA"] == dinero(70)
        huerfanos = db.execute(
            text(
                "SELECT COUNT(*) FROM movimientos_tesoreria m "
                "LEFT JOIN operaciones_tesoreria o ON o.id_operacion = m.id_operacion "
                "WHERE o.id_operacion IS NULL"
            )
        ).scalar()
        assert int(huerfanos or 0) == 0
    finally:
        db.close()


def test_traspaso_contra_gasto_no_deja_saldo_negativo(sesiones):
    abrir, admin_id, _cafe = sesiones
    db = abrir()
    _activar(db, admin_id, cafeteria=50, casa=0, banco=0, operation_id="act-gasto")
    db.commit()
    db.close()
    salidas = [{}, {}]

    def mover(db):
        traspasar(
            db,
            _admin(db, admin_id),
            codigo_origen="EFECTIVO_CAFETERIA",
            codigo_destino="EFECTIVO_CASA",
            importe=dinero(40),
            concepto="A casa",
            observacion=None,
            operation_id="tr-vs-gasto",
        )

    def gastar(db):
        registrar_salida_origen(
            db,
            usuario=_admin(db, admin_id),
            codigo_cuenta="EFECTIVO_CAFETERIA",
            importe=dinero(40),
            tipo="GASTO_OPERATIVO",
            concepto="Insumo",
            operation_id="gasto-vs-tr",
            origen_tipo="GASTO",
            origen_id=9001,
        )

    _hilos([
        _trabajo(abrir, mover, salidas[0]),
        _trabajo(abrir, gastar, salidas[1]),
    ])
    assert sorted(item["estado"] for item in salidas) == ["DatosInvalidosException", "ok"]
    db = abrir()
    try:
        assert _saldos(db)["EFECTIVO_CAFETERIA"] == dinero(10)
        assert min(_saldos(db).values()) >= 0
    finally:
        db.close()


def test_cobro_contra_traspaso_y_cierre_no_duplica(sesiones):
    abrir, admin_id, cafe_id = sesiones
    db = abrir()
    admin = _admin(db, admin_id)
    _activar(db, admin_id, cafeteria=100, casa=0, banco=0, operation_id="act-cobro")
    abrir_caja(db, admin, fondo_inicial=100, terminal="CAJA-1", operation_id="caja-pg", origen_fondo="EXISTENTE")
    db.commit()
    db.close()
    salidas = [{}, {}]

    def cobrar(db):
        registrar_venta(
            db,
            VentaCreate(
                id_usuario=admin_id,
                numero_mesa=1,
                forma_pago="EFECTIVO",
                operation_id="venta-pg-1",
                detalles=[
                    DetalleVentaItem(
                        id_producto=cafe_id,
                        cantidad=1,
                        precio_unitario=42,
                        sin_promocion=True,
                    )
                ],
            ),
        )

    def mover(db):
        traspasar(
            db,
            _admin(db, admin_id),
            codigo_origen="EFECTIVO_CAFETERIA",
            codigo_destino="EFECTIVO_CASA",
            importe=dinero(40),
            concepto="Retiro a casa",
            observacion=None,
            operation_id="tr-vs-cobro",
        )

    _hilos([
        _trabajo(abrir, cobrar, salidas[0]),
        _trabajo(abrir, mover, salidas[1]),
    ])
    assert all(item["estado"] == "ok" for item in salidas)
    db = abrir()
    try:
        assert db.query(OperacionTesoreriaModel).filter_by(tipo="VENTA").count() == 1
        assert db.query(VentaModel).count() == 1
        admin = _admin(db, admin_id)
        antes = db.query(OperacionTesoreriaModel).count()
        cerrar_caja(
            db,
            admin,
            denominaciones=None,
            declarado_efectivo=142,
            declarado_transferencia=0,
            declarado_tarjeta=0,
            captura_directa=True,
            observacion="Cierre sintético",
            operation_id="cierre-pg",
        )
        assert db.query(OperacionTesoreriaModel).count() == antes
        assert db.query(OperacionTesoreriaModel).filter_by(tipo="VENTA").count() == 1
        assert min(_saldos(db).values()) >= 0
        huerfanos = db.query(MovimientoTesoreriaModel).filter(
            ~MovimientoTesoreriaModel.id_operacion.in_(db.query(OperacionTesoreriaModel.id_operacion))
        ).count()
        assert huerfanos == 0
    finally:
        db.close()


def test_reversa_concurrente_queda_en_una(sesiones):
    abrir, admin_id, _cafe = sesiones
    db = abrir()
    _activar(db, admin_id, cafeteria=80, casa=0, banco=0, operation_id="act-rev")
    op = traspasar(
        db,
        _admin(db, admin_id),
        codigo_origen="EFECTIVO_CAFETERIA",
        codigo_destino="EFECTIVO_CASA",
        importe=dinero(20),
        concepto="Para revertir",
        observacion=None,
        operation_id="tr-rev",
    )
    db.commit()
    id_op = op.id_operacion
    db.close()
    salidas = [{}, {}]

    def rev(db, clave):
        revertir(db, _admin(db, admin_id), id_op, motivo="Error de captura", operation_id=clave)

    _hilos([
        _trabajo(abrir, lambda db: rev(db, "rev-a"), salidas[0]),
        _trabajo(abrir, lambda db: rev(db, "rev-b"), salidas[1]),
    ])
    assert sorted(item["estado"] for item in salidas) == ["ConflictoOperacionException", "ok"]
    db = abrir()
    try:
        original = db.query(OperacionTesoreriaModel).filter_by(id_operacion=id_op).one()
        assert original.estado == "REVERTIDA"
        assert db.query(OperacionTesoreriaModel).filter_by(tipo="REVERSA").count() == 1
        assert _saldos(db)["EFECTIVO_CAFETERIA"] == dinero(80)
    finally:
        db.close()


def test_direcciones_opuestas_no_hacen_deadlock(sesiones):
    abrir, admin_id, _cafe = sesiones
    db = abrir()
    _activar(db, admin_id, cafeteria=200, casa=200, banco=0, operation_id="act-dead")
    db.commit()
    db.close()
    salidas = [{}, {}]

    def hacia_casa(db):
        traspasar(
            db,
            _admin(db, admin_id),
            codigo_origen="EFECTIVO_CAFETERIA",
            codigo_destino="EFECTIVO_CASA",
            importe=dinero(25),
            concepto="A casa",
            observacion=None,
            operation_id="dead-casa",
        )

    def hacia_cafe(db):
        traspasar(
            db,
            _admin(db, admin_id),
            codigo_origen="EFECTIVO_CASA",
            codigo_destino="EFECTIVO_CAFETERIA",
            importe=dinero(25),
            concepto="A cafetería",
            observacion=None,
            operation_id="dead-cafe",
        )

    _hilos([
        _trabajo(abrir, hacia_casa, salidas[0]),
        _trabajo(abrir, hacia_cafe, salidas[1]),
    ])
    assert [item["estado"] for item in salidas] == ["ok", "ok"]
    db = abrir()
    try:
        saldos = _saldos(db)
        assert saldos["EFECTIVO_CAFETERIA"] == dinero(200)
        assert saldos["EFECTIVO_CASA"] == dinero(200)
    finally:
        db.close()


def test_down_desechable_no_borra_ventas(pg_engine):
    exigir_postgres_desechable(POSTGRES_TEST_URL)
    aplicar_down_tesoreria_desechable(pg_engine)
    with pg_engine.connect() as conn:
        tablas = _tablas(conn)
        assert "cuentas_tesoreria" not in tablas
        assert "ventas" in tablas
        assert "venta_pagos" in tablas
        assert "sesiones_caja" in tablas
    with pytest.raises(RuntimeError):
        verificar_esquema_tesoreria(pg_engine)
    aplicar_migracion_008_tesoreria(pg_engine)
    verificar_esquema_tesoreria(pg_engine)
