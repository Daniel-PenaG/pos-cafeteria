"""Tesorería sobre SQLite aislado. No toca producción."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import (
    CategoriaModel,
    MovimientoTesoreriaModel,
    OperacionTesoreriaModel,
    ProductoModel,
    UsuarioModel,
    VentaModel,
    VentaPagoModel,
)
from app.services.migracion_tesoreria import (
    aplicar_down_tesoreria_desechable,
    aplicar_migracion_008_tesoreria,
    verificar_esquema_tesoreria,
)
from app.services.tesoreria_service import (
    activar,
    conciliar,
    dinero,
    registrar_venta_tesoreria,
    revertir,
    revisar_conciliacion,
    saldo_cuenta,
    traspasar,
)
from app.utils.security import hash_password
from app.utils.timezone_mx import now_utc_naive


def _engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture()
def db():
    engine = _engine()
    Base.metadata.create_all(bind=engine)
    aplicar_migracion_008_tesoreria(engine)
    verificar_esquema_tesoreria(engine)
    Session = sessionmaker(bind=engine)
    ses = Session()
    admin = UsuarioModel(
        nombre="Admin demo",
        usuario_login="admin_tes",
        hash_password=hash_password("test1234"),
        rol="ADMIN",
        activo=True,
    )
    cajero = UsuarioModel(
        nombre="Cajero demo",
        usuario_login="cajero_tes",
        hash_password=hash_password("test1234"),
        rol="CAJERO",
        activo=True,
    )
    cocina = UsuarioModel(
        nombre="Cocina demo",
        usuario_login="cocina_tes",
        hash_password=hash_password("test1234"),
        rol="COCINA",
        activo=True,
    )
    ses.add_all([admin, cajero, cocina])
    cat = CategoriaModel(nombre="Bebidas demo")
    ses.add(cat)
    ses.flush()
    cafe = ProductoModel(nombre="Café demo", id_categoria=cat.id_categoria, precio_venta=42, activo=True)
    ses.add(cafe)
    ses.commit()
    ses._engine = engine
    ses._cafe = cafe.id_producto
    try:
        yield ses
    finally:
        ses.close()
        engine.dispose()


def _admin(db):
    return db.query(UsuarioModel).filter_by(usuario_login="admin_tes").one()


def _activar(db, **montos):
    admin = _admin(db)
    corte = now_utc_naive() - timedelta(minutes=1)
    return activar(
        db,
        admin,
        fecha_corte=corte,
        efectivo_cafeteria=dinero(montos.get("cafeteria", 100)),
        efectivo_casa=dinero(montos.get("casa", 50)),
        saldo_banco=dinero(montos.get("banco", 200)),
        observacion="Corte sintético",
        operation_id=montos.get("operation_id", "activacion-demo-001"),
    )


def _vender(db, metodo, importe, total=None, cuando=None):
    admin = _admin(db)
    venta = VentaModel(
        fecha_hora=cuando or now_utc_naive(),
        id_usuario=admin.id_usuario,
        numero_mesa=1,
        total=total if total is not None else importe,
        forma_pago=metodo,
        puntos_generados=0,
    )
    db.add(venta)
    db.flush()
    if metodo != "PUNTOS":
        db.add(
            VentaPagoModel(
                id_venta=venta.id_venta,
                metodo=metodo,
                importe_monetario=importe,
                fecha_hora=venta.fecha_hora,
                id_usuario=admin.id_usuario,
                operation_id=f"pago-{venta.id_venta}-{metodo}",
            )
        )
    else:
        db.add(
            VentaPagoModel(
                id_venta=venta.id_venta,
                metodo="PUNTOS",
                importe_monetario=0,
                cantidad_puntos=int(importe),
                equivalencia_puntos=importe,
                fecha_hora=venta.fecha_hora,
                id_usuario=admin.id_usuario,
                operation_id=f"pago-{venta.id_venta}-puntos",
            )
        )
    db.flush()
    registrar_venta_tesoreria(db, venta, admin.id_usuario)
    return venta


def test_inicia_desactivada_y_venta_previa_no_mueve(db):
    assert db.query(OperacionTesoreriaModel).count() == 0
    antes = now_utc_naive() - timedelta(days=2)
    _vender(db, "EFECTIVO", 42, cuando=antes)
    assert db.query(MovimientoTesoreriaModel).count() == 0


def test_activacion_crea_saldos_y_no_se_repite(db):
    _activar(db)
    db.commit()
    tipos = [op.tipo for op in db.query(OperacionTesoreriaModel).all()]
    assert tipos.count("SALDO_INICIAL") == 3
    with pytest.raises(Exception):
        _activar(db, operation_id="activacion-demo-002")


def test_activacion_misma_clave_no_duplica(db):
    admin = _admin(db)
    corte = now_utc_naive()
    kwargs = dict(
        fecha_corte=corte,
        efectivo_cafeteria=dinero(100),
        efectivo_casa=dinero(50),
        saldo_banco=dinero(200),
        observacion="Corte sintético",
        operation_id="activacion-demo-001",
    )
    activar(db, admin, **kwargs)
    activar(db, admin, **kwargs)
    assert db.query(OperacionTesoreriaModel).filter_by(tipo="SALDO_INICIAL").count() == 3


def test_efectivo_transferencia_terminal_y_puntos(db):
    _activar(db, cafeteria=0, casa=0, banco=0)
    _vender(db, "EFECTIVO", 42)
    _vender(db, "TRANSFERENCIA", 42)
    _vender(db, "TARJETA", 80)
    _vender(db, "PUNTOS", 42, total=42)
    from app.services.tesoreria_service import cuenta_por_codigo

    cafe = saldo_cuenta(db, cuenta_por_codigo(db, "EFECTIVO_CAFETERIA").id_cuenta)
    banco = saldo_cuenta(db, cuenta_por_codigo(db, "BANCO").id_cuenta)
    assert cafe == dinero(42)
    assert banco == dinero(122)
    assert db.query(OperacionTesoreriaModel).filter_by(tipo="VENTA").count() == 3


def test_mixto_solo_remanente(db):
    _activar(db, cafeteria=0, casa=0, banco=0)
    admin = _admin(db)
    venta = VentaModel(
        fecha_hora=now_utc_naive(),
        id_usuario=admin.id_usuario,
        numero_mesa=1,
        total=42,
        forma_pago="MIXTO",
        puntos_generados=0,
    )
    db.add(venta)
    db.flush()
    db.add(
        VentaPagoModel(
            id_venta=venta.id_venta,
            metodo="PUNTOS",
            importe_monetario=0,
            cantidad_puntos=100,
            equivalencia_puntos=10,
            fecha_hora=venta.fecha_hora,
            id_usuario=admin.id_usuario,
            operation_id=f"pago-{venta.id_venta}-pts",
        )
    )
    db.add(
        VentaPagoModel(
            id_venta=venta.id_venta,
            metodo="EFECTIVO",
            importe_monetario=32,
            fecha_hora=venta.fecha_hora,
            id_usuario=admin.id_usuario,
            operation_id=f"pago-{venta.id_venta}-ef",
        )
    )
    db.flush()
    registrar_venta_tesoreria(db, venta, admin.id_usuario)
    from app.services.tesoreria_service import cuenta_por_codigo

    assert saldo_cuenta(db, cuenta_por_codigo(db, "EFECTIVO_CAFETERIA").id_cuenta) == dinero(32)


def test_replay_y_huella_distinta(db):
    _activar(db, cafeteria=100, casa=80, banco=0)
    admin = _admin(db)
    op = traspasar(
        db, admin,
        codigo_origen="EFECTIVO_CASA",
        codigo_destino="BANCO",
        importe=dinero(20),
        concepto="Depósito",
        observacion=None,
        operation_id="traspaso-001",
    )
    otra = traspasar(
        db, admin,
        codigo_origen="EFECTIVO_CASA",
        codigo_destino="BANCO",
        importe=dinero(20),
        concepto="Depósito",
        observacion=None,
        operation_id="traspaso-001",
    )
    assert op.id_operacion == otra.id_operacion
    with pytest.raises(Exception):
        traspasar(
            db, admin,
            codigo_origen="EFECTIVO_CASA",
            codigo_destino="BANCO",
            importe=dinero(10),
            concepto="Otro",
            observacion=None,
            operation_id="traspaso-001",
        )


def test_traspaso_rechaza_misma_cuenta_y_saldo_insuficiente(db):
    _activar(db, cafeteria=10, casa=5, banco=0)
    admin = _admin(db)
    with pytest.raises(Exception):
        traspasar(
            db, admin,
            codigo_origen="EFECTIVO_CASA",
            codigo_destino="EFECTIVO_CASA",
            importe=dinero(1),
            concepto="Mal",
            observacion=None,
            operation_id="traspaso-mal",
        )
    with pytest.raises(Exception):
        traspasar(
            db, admin,
            codigo_origen="EFECTIVO_CASA",
            codigo_destino="BANCO",
            importe=dinero(50),
            concepto="De más",
            observacion=None,
            operation_id="traspaso-mas",
        )
    from app.services.tesoreria_service import cuenta_por_codigo

    assert saldo_cuenta(db, cuenta_por_codigo(db, "EFECTIVO_CASA").id_cuenta) == dinero(5)


def test_cierre_no_suma_venta_y_gasto_caja_una_vez(db):
    from app.models.models import MovimientoCajaModel, SesionCajaModel
    from app.services.caja_service import registrar_movimiento

    _activar(db, cafeteria=100, casa=0, banco=0)
    _vender(db, "EFECTIVO", 42)
    from app.services.tesoreria_service import cuenta_por_codigo

    antes = saldo_cuenta(db, cuenta_por_codigo(db, "EFECTIVO_CAFETERIA").id_cuenta)
    assert antes == dinero(142)
    cajero = db.query(UsuarioModel).filter_by(usuario_login="cajero_tes").one()
    sesion = SesionCajaModel(
        id_usuario=cajero.id_usuario,
        terminal="CAJA-1",
        estado="ABIERTA",
        fondo_inicial=0,
        fecha_apertura=now_utc_naive(),
        operation_id="sesion-demo",
    )
    db.add(sesion)
    db.commit()
    registrar_movimiento(
        db,
        cajero,
        tipo="GASTO_CAJA",
        importe=10,
        motivo="Hielo demo",
        operation_id="gasto-caja-1",
    )
    registrar_movimiento(
        db,
        cajero,
        tipo="GASTO_CAJA",
        importe=10,
        motivo="Hielo demo",
        operation_id="gasto-caja-1",
    )
    despues = saldo_cuenta(db, cuenta_por_codigo(db, "EFECTIVO_CAFETERIA").id_cuenta)
    assert despues == dinero(132)
    assert db.query(MovimientoCajaModel).count() >= 1


def test_reverso_no_borra_original_ni_se_repite(db):
    _activar(db, cafeteria=0, casa=40, banco=0)
    admin = _admin(db)
    op = traspasar(
        db, admin,
        codigo_origen="EFECTIVO_CASA",
        codigo_destino="EFECTIVO_CAFETERIA",
        importe=dinero(15),
        concepto="Llevar cambio",
        observacion=None,
        operation_id="traspaso-rev",
    )
    rev = revertir(db, admin, op.id_operacion, motivo="Error de captura", operation_id="reversa-1")
    db.refresh(op)
    assert op.estado == "REVERTIDA"
    assert rev.tipo == "REVERSA"
    assert db.query(OperacionTesoreriaModel).filter_by(id_operacion=op.id_operacion).count() == 1
    with pytest.raises(Exception):
        revertir(db, admin, op.id_operacion, motivo="Otra vez", operation_id="reversa-2")


def test_conciliacion_no_ajusta_hasta_revision(db):
    _activar(db, cafeteria=100, casa=0, banco=0)
    admin = _admin(db)
    fila = conciliar(db, admin, codigo_cuenta="EFECTIVO_CAFETERIA", saldo_fisico=dinero(90), observacion="Faltan 10")
    assert fila.diferencia == dinero(-10)
    from app.services.tesoreria_service import cuenta_por_codigo

    assert saldo_cuenta(db, cuenta_por_codigo(db, "EFECTIVO_CAFETERIA").id_cuenta) == dinero(100)
    revisar_conciliacion(db, admin, fila.id_conciliacion, generar_ajuste=True, operation_id="ajuste-conc-1")
    assert saldo_cuenta(db, cuenta_por_codigo(db, "EFECTIVO_CAFETERIA").id_cuenta) == dinero(90)


def test_cocina_no_entra_y_cajero_no_ajusta(db):
    engine = db._engine
    Session = sessionmaker(bind=engine)

    def override():
        ses = Session()
        try:
            yield ses
        finally:
            ses.close()

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            cocina = client.post("/auth/login", json={"usuario_login": "cocina_tes", "password": "test1234"})
            token = cocina.json()["access_token"]
            res = client.get("/tesoreria/estado", headers={"Authorization": f"Bearer {token}"})
            assert res.status_code == 403
            cajero = client.post("/auth/login", json={"usuario_login": "cajero_tes", "password": "test1234"})
            token_c = cajero.json()["access_token"]
            ajuste = client.post(
                "/tesoreria/ajustes",
                headers={"Authorization": f"Bearer {token_c}"},
                json={
                    "codigo_cuenta": "EFECTIVO_CAFETERIA",
                    "importe": 1,
                    "concepto": "No",
                    "observacion": "No",
                    "operation_id": "ajuste-cajero",
                    "tipo": "AJUSTE_FALTANTE",
                },
            )
            assert ajuste.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_migracion_dos_veces_y_down_desechable(db):
    engine = db._engine
    aplicar_migracion_008_tesoreria(engine)
    verificar_esquema_tesoreria(engine)
    aplicar_down_tesoreria_desechable(engine)
    with pytest.raises(RuntimeError):
        verificar_esquema_tesoreria(engine)
    aplicar_migracion_008_tesoreria(engine)
    verificar_esquema_tesoreria(engine)


def test_retiro_no_cuenta_como_gasto_operativo(db):
    _activar(db, cafeteria=80, casa=0, banco=0)
    from app.services.tesoreria_service import TIPO_RETIRO, movimiento_simple, resumen

    admin = _admin(db)
    movimiento_simple(
        db, admin,
        codigo_cuenta="EFECTIVO_CAFETERIA",
        importe=dinero(30),
        direccion="SALIDA",
        tipo=TIPO_RETIRO,
        concepto="Retiro personal",
        observacion="Demo",
        operation_id="retiro-1",
    )
    data = resumen(db)
    assert Decimal(data["gastos_operativos"]) == dinero(0)
    assert Decimal(data["retiros_propietario"]) == dinero(30)
    assert Decimal(data["ingresos"]) == dinero(0)


def test_gasto_pendiente_no_mueve_y_el_pago_sale_una_vez(db):
    from app.models.models import CuentaTesoreriaModel
    from app.routers.gastos import pagar_gasto, registrar_gasto
    from app.schemas.gasto import GastoCreate, GastoPagar
    from app.services.tesoreria_service import TIPO_COMISION, movimiento_simple

    _activar(db, cafeteria=100, casa=0, banco=80)
    admin = _admin(db)
    registrar_gasto(
        GastoCreate(descripcion="Azúcar pendiente", monto=15, estado_pago="PENDIENTE"),
        db,
        admin,
    )
    cafe = db.query(CuentaTesoreriaModel).filter_by(codigo="EFECTIVO_CAFETERIA").one()
    assert saldo_cuenta(db, cafe.id_cuenta) == dinero(100)
    pagado = registrar_gasto(
        GastoCreate(
            descripcion="Leche",
            monto=20,
            estado_pago="PAGADO",
            codigo_cuenta="EFECTIVO_CAFETERIA",
            operation_id="gasto-leche",
        ),
        db,
        admin,
    )
    assert saldo_cuenta(db, cafe.id_cuenta) == dinero(80)
    from app.models.models import GastoModel

    pendiente = db.query(GastoModel).filter_by(descripcion="Azúcar pendiente").one()
    pagar_gasto(pendiente.id_gasto, GastoPagar(codigo_cuenta="EFECTIVO_CAFETERIA", operation_id="pagar-azucar"), db, admin)
    assert saldo_cuenta(db, cafe.id_cuenta) == dinero(65)
    with pytest.raises(Exception):
        pagar_gasto(pendiente.id_gasto, GastoPagar(codigo_cuenta="EFECTIVO_CASA", operation_id="pagar-azucar-2"), db, admin)
    banco = db.query(CuentaTesoreriaModel).filter_by(codigo="BANCO").one()
    movimiento_simple(
        db,
        admin,
        codigo_cuenta="BANCO",
        importe=dinero(5),
        direccion="SALIDA",
        tipo=TIPO_COMISION,
        concepto="Comisión terminal",
        observacion="Demo",
        operation_id="comision-1",
    )
    assert saldo_cuenta(db, banco.id_cuenta) == dinero(75)
    assert pagado.descripcion == "Leche"


def test_fondo_existente_no_crea_ingreso(db):
    from app.services.caja_service import abrir_caja

    _activar(db, cafeteria=100, casa=40, banco=0)
    admin = _admin(db)
    antes = db.query(OperacionTesoreriaModel).count()
    abierta = abrir_caja(db, admin, fondo_inicial=100, terminal="CAJA-1", operation_id="abre-1", origen_fondo="EXISTENTE")
    assert "advertencia_tesoreria" not in abierta
    assert db.query(OperacionTesoreriaModel).count() == antes
    abrir_caja(db, _cajero(db), fondo_inicial=10, terminal="CAJA-2", operation_id="abre-2", origen_fondo="CASA")
    casa = db.query(MovimientoTesoreriaModel).count()
    assert casa > 0
    traspasos = db.query(OperacionTesoreriaModel).filter_by(tipo="TRASPASO").count()
    assert traspasos == 1


def _cajero(db):
    return db.query(UsuarioModel).filter_by(usuario_login="cajero_tes").one()


def test_fallo_de_tesoreria_revierte_la_venta(db, monkeypatch):
    _activar(db)
    db.commit()
    admin = _admin(db)

    def boom(*_a, **_k):
        raise RuntimeError("fallo tesoreria")

    monkeypatch.setattr("app.services.tesoreria_service.registrar_venta_tesoreria", boom)
    from app.schemas.ventas import DetalleVentaItem, VentaCreate
    from app.services.venta_service import registrar_venta

    data = VentaCreate(
        id_usuario=admin.id_usuario,
        numero_mesa=1,
        forma_pago="EFECTIVO",
        operation_id="venta-falla-tesoreria",
        detalles=[DetalleVentaItem(id_producto=db._cafe, cantidad=1, precio_unitario=42, sin_promocion=True)],
    )
    with pytest.raises(RuntimeError):
        registrar_venta(db, data)
    assert db.query(VentaModel).count() == 0
    assert db.query(VentaPagoModel).count() == 0
    assert db.query(OperacionTesoreriaModel).filter_by(tipo="VENTA").count() == 0
