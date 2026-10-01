"""Fase 3B: canje de puntos y pago mixto. El backend recalcula equivalencia."""
from __future__ import annotations

import pytest

from app.exceptions import ConflictoOperacionException, DatosInvalidosException
from app.models.models import (
    ClienteModel,
    FidelidadConfigModel,
    FidelidadMovimientoModel,
    ProductoModel,
    UsuarioModel,
    VentaModel,
    VentaPagoModel,
)
from app.schemas.pedido import PedidoLineaCreate
from app.schemas.ventas import VentaCreate
from app.services.caja_service import _totales_sesion, abrir_caja, sesion_activa_usuario
from app.services.fidelidad_service import resolver_pago_puntos
from app.services.pedido_service import (
    agregar_linea_pedido,
    cobrar_pedido,
    obtener_pedido_abierto_mesa,
)
from app.services.venta_service import MESA_PARA_LLEVAR, registrar_venta
from app.utils.timezone_mx import today_mx
from tests.test_promociones_integracion import _linea


def _cliente(db, refs, saldo):
    cliente = db.get(ClienteModel, refs.id_cliente)
    cliente.puntos_saldo = saldo
    db.flush()
    return cliente


def _cobrar(db, refs, id_producto, cantidad, forma="EFECTIVO", puntos=0, con_cliente=True):
    det = _linea(db, id_producto, cantidad)
    return registrar_venta(
        db,
        VentaCreate(
            id_usuario=refs.id_usuario,
            numero_mesa=4,
            forma_pago=forma,
            id_cliente=refs.id_cliente if con_cliente else None,
            puntos_canje=puntos,
            detalles=[det],
        ),
    )


def _suma_componentes(db, id_venta) -> float:
    pagos = db.query(VentaPagoModel).filter(VentaPagoModel.id_venta == id_venta).all()
    total = 0.0
    for pago in pagos:
        if str(pago.metodo).upper() == "PUNTOS":
            total += float(pago.equivalencia_puntos or 0)
        else:
            total += float(pago.importe_monetario or 0)
    return round(total, 2)


def test_ticket_120_sin_puntos_genera_12(db_session, refs):
    _cliente(db_session, refs, 0)
    resp = _cobrar(db_session, refs, refs.id_refresco, 4)
    assert resp.total == 120
    assert resp.forma_pago == "EFECTIVO"
    assert resp.importe_monetario == 120
    assert resp.puntos_generados == 12
    assert resp.puntos_canje == 0
    movs = (
        db_session.query(FidelidadMovimientoModel)
        .filter(FidelidadMovimientoModel.id_venta == resp.id_venta)
        .all()
    )
    assert [m.tipo for m in movs] == ["ACUMULACION"]


def test_ticket_120_con_200_puntos_paga_100_y_genera_10(db_session, refs):
    _cliente(db_session, refs, 1000)
    resp = _cobrar(db_session, refs, refs.id_refresco, 4, puntos=200)
    assert resp.total == 120
    assert resp.forma_pago == "MIXTO"
    assert resp.puntos_canje == 200
    assert resp.equivalencia_puntos == 20
    assert resp.importe_monetario == 100
    assert resp.forma_pago_monetaria == "EFECTIVO"
    assert resp.puntos_generados == 10
    assert _suma_componentes(db_session, resp.id_venta) == 120
    cliente = db_session.get(ClienteModel, refs.id_cliente)
    assert int(cliente.puntos_saldo) == 1000 - 200 + 10
    tipos = [
        m.tipo
        for m in db_session.query(FidelidadMovimientoModel)
        .filter(FidelidadMovimientoModel.id_venta == resp.id_venta)
        .all()
    ]
    assert tipos == ["REDENCION", "ACUMULACION"]
    pagos = db_session.query(VentaPagoModel).filter_by(id_venta=resp.id_venta).all()
    assert len(pagos) == 2
    por_metodo = {p.metodo: p for p in pagos}
    assert float(por_metodo["PUNTOS"].importe_monetario) == 0
    assert por_metodo["PUNTOS"].cantidad_puntos == 200
    assert float(por_metodo["PUNTOS"].equivalencia_puntos) == 20
    assert por_metodo["EFECTIVO"].cantidad_puntos is None
    assert por_metodo["EFECTIVO"].equivalencia_puntos is None
    assert float(por_metodo["EFECTIVO"].importe_monetario) == 100
    assert por_metodo["PUNTOS"].operation_id.endswith(":PUNTOS")
    assert por_metodo["EFECTIVO"].operation_id.endswith(":MONETARIO")


def test_ticket_50_solo_puntos_genera_0(db_session, refs):
    _cliente(db_session, refs, 500)
    resp = _cobrar(db_session, refs, refs.id_cafe, 1, puntos=500)
    assert resp.total == 50
    assert resp.forma_pago == "PUNTOS"
    assert resp.importe_monetario == 0
    assert resp.forma_pago_monetaria is None
    assert resp.puntos_generados == 0
    assert _suma_componentes(db_session, resp.id_venta) == 50
    pagos = db_session.query(VentaPagoModel).filter_by(id_venta=resp.id_venta).all()
    assert len(pagos) == 1
    assert pagos[0].metodo == "PUNTOS"
    assert float(pagos[0].importe_monetario) == 0
    cliente = db_session.get(ClienteModel, refs.id_cliente)
    assert int(cliente.puntos_saldo) == 0


def test_puntos_mas_transferencia_no_suma_efectivo(db_session, refs):
    user = db_session.get(UsuarioModel, refs.id_usuario)
    abrir_caja(db_session, user, fondo_inicial=100, terminal="CAJA-1", observacion="apertura")
    _cliente(db_session, refs, 1000)
    sesion = sesion_activa_usuario(db_session, user.id_usuario)
    antes = _totales_sesion(db_session, sesion)
    resp = _cobrar(db_session, refs, refs.id_refresco, 4, forma="TRANSFERENCIA", puntos=200)
    sesion = sesion_activa_usuario(db_session, user.id_usuario)
    tot = _totales_sesion(db_session, sesion)
    assert resp.forma_pago == "MIXTO"
    assert tot["ventas_efectivo"] == antes["ventas_efectivo"]
    assert tot["ventas_transferencia"] == round(antes["ventas_transferencia"] + 100, 2)
    assert tot["ventas_tarjeta"] == antes["ventas_tarjeta"]
    assert tot["num_ventas"] == antes["num_ventas"] + 1
    from app.routers.reportes import cuentas_por_cajero

    reporte = cuentas_por_cajero(today_mx(), db_session)
    cajero = reporte["por_cajero"][0]
    assert cajero["total"] == 120
    assert cajero["total_transferencia"] == 100
    assert cajero["total_efectivo"] == 0
    assert cajero["total_tarjeta"] == 0


def test_venta_solo_puntos_no_aumenta_ingreso_monetario(db_session, refs):
    user = db_session.get(UsuarioModel, refs.id_usuario)
    abrir_caja(db_session, user, fondo_inicial=80, terminal="CAJA-1", observacion="apertura")
    _cliente(db_session, refs, 500)
    sesion = sesion_activa_usuario(db_session, user.id_usuario)
    antes = _totales_sesion(db_session, sesion)
    resp = _cobrar(db_session, refs, refs.id_cafe, 1, puntos=500)
    sesion = sesion_activa_usuario(db_session, user.id_usuario)
    tot = _totales_sesion(db_session, sesion)
    assert resp.forma_pago == "PUNTOS"
    assert tot["num_ventas"] == antes["num_ventas"] + 1
    assert tot["ventas_total"] == round(antes["ventas_total"] + 50, 2)
    assert tot["ventas_efectivo"] == antes["ventas_efectivo"]
    assert tot["ingreso_monetario"] == antes["ingreso_monetario"]
    assert tot["efectivo_esperado"] == antes["efectivo_esperado"]


def test_minimo_acumular_usa_importe_monetario(db_session, refs):
    config = db_session.query(FidelidadConfigModel).first()
    config.minimo_compra_acumular = 50
    db_session.flush()
    _cliente(db_session, refs, 1000)
    resp = _cobrar(db_session, refs, refs.id_refresco, 4, puntos=800)
    assert resp.importe_monetario == 40
    assert resp.puntos_generados == 0


@pytest.mark.parametrize(
    "saldo,puntos,cantidad,mensaje",
    [
        (1000, 40, 4, "mínimo"),
        (1000, 49, 4, "mínimo"),
        (1000, 55, 4, "múltiplos"),
        (100, 200, 4, "saldo"),
        (2000, 600, 1, "exceder"),
    ],
)
def test_canje_rechazado(db_session, refs, saldo, puntos, cantidad, mensaje):
    _cliente(db_session, refs, saldo)
    producto = refs.id_refresco if cantidad == 4 else refs.id_cafe
    with pytest.raises(DatosInvalidosException) as exc:
        _cobrar(db_session, refs, producto, cantidad, puntos=puntos)
    assert mensaje in str(exc.value.detail).lower()


def test_canje_sin_cliente_rechazado(db_session, refs):
    with pytest.raises(DatosInvalidosException) as exc:
        _cobrar(db_session, refs, refs.id_cafe, 1, puntos=50, con_cliente=False)
    assert "cliente" in str(exc.value.detail).lower()


def test_ticket_menor_a_cinco_no_canjea():
    class _Cfg:
        pesos_por_punto = 10
        minimo_compra_acumular = 0
        activo = True
        puntos_saldo = 500

    with pytest.raises(DatosInvalidosException) as exc:
        resolver_pago_puntos(
            cliente=_Cfg(),
            puntos_solicitados=50,
            total=4.5,
            forma_monetaria="EFECTIVO",
            config=_Cfg(),
        )
    assert "menor" in str(exc.value.detail).lower()


def _pedido(db, refs, mesa, para_llevar, id_producto, cantidad, precio):
    pedido = obtener_pedido_abierto_mesa(db, mesa, refs.id_usuario, para_llevar=para_llevar)
    agregar_linea_pedido(
        db,
        pedido,
        PedidoLineaCreate(
            id_producto=id_producto,
            cantidad=cantidad,
            precio_unitario=precio,
            enviar_comanda=False,
        ),
    )
    pedido.id_cliente = refs.id_cliente
    db.commit()
    db.refresh(pedido)
    return pedido


def test_saldo_300_canje_200_genera_10_queda_110(db_session, refs):
    _cliente(db_session, refs, 300)
    resp = _cobrar(db_session, refs, refs.id_refresco, 4, puntos=200)
    assert resp.saldo_anterior == 300
    assert resp.puntos_canje == 200
    assert resp.puntos_generados == 10
    assert resp.saldo_final == 110
    movs = (
        db_session.query(FidelidadMovimientoModel)
        .filter_by(id_venta=resp.id_venta)
        .order_by(FidelidadMovimientoModel.id_movimiento)
        .all()
    )
    assert [m.tipo for m in movs] == ["REDENCION", "ACUMULACION"]
    assert movs[0].saldo_despues == 100
    assert movs[1].saldo_despues == 110


def test_remanente_de_un_centavo(db_session, refs):
    producto = db_session.get(ProductoModel, refs.id_cafe)
    producto.precio_venta = 50.01
    db_session.flush()
    _cliente(db_session, refs, 500)
    resp = _cobrar(db_session, refs, refs.id_cafe, 1, puntos=500)
    assert resp.total == 50.01
    assert resp.equivalencia_puntos == 50
    assert resp.importe_monetario == 0.01
    assert resp.forma_pago == "MIXTO"


def test_sesenta_puntos_valen_seis(db_session, refs):
    _cliente(db_session, refs, 60)
    resp = _cobrar(db_session, refs, refs.id_cafe, 1, puntos=60)
    assert resp.equivalencia_puntos == 6
    assert resp.importe_monetario == 44


def test_mismo_operation_id_no_duplica_venta_ni_redencion(db_session, refs):
    _cliente(db_session, refs, 300)
    pedido = _pedido(db_session, refs, 4, False, refs.id_refresco, 4, 30)
    primero = cobrar_pedido(
        db_session, pedido, refs.id_usuario, "EFECTIVO", puntos_canje=200, operation_id="cobro-estable-1"
    )
    segundo = cobrar_pedido(
        db_session, pedido, refs.id_usuario, "EFECTIVO", puntos_canje=200, operation_id="cobro-estable-1"
    )
    assert primero.id_venta == segundo.id_venta
    assert segundo.saldo_anterior == 300
    assert segundo.saldo_final == 110
    assert db_session.query(VentaModel).filter_by(id_cliente=refs.id_cliente).count() == 1
    assert (
        db_session.query(FidelidadMovimientoModel)
        .filter_by(id_venta=primero.id_venta, tipo="REDENCION")
        .count()
        == 1
    )
    claves = {
        p.operation_id
        for p in db_session.query(VentaPagoModel).filter_by(id_venta=primero.id_venta)
    }
    assert claves == {"cobro-estable-1:PUNTOS", "cobro-estable-1:MONETARIO"}


def test_mismo_operation_id_con_otros_puntos_es_409(db_session, refs):
    _cliente(db_session, refs, 300)
    pedido = _pedido(db_session, refs, 6, False, refs.id_cafe, 1, 50)
    cobrar_pedido(
        db_session, pedido, refs.id_usuario, "EFECTIVO", puntos_canje=0, operation_id="cobro-conflicto"
    )
    with pytest.raises(ConflictoOperacionException):
        cobrar_pedido(
            db_session,
            pedido,
            refs.id_usuario,
            "TARJETA",
            puntos_canje=100,
            operation_id="cobro-conflicto",
        )
    assert db_session.query(VentaModel).count() == 1


def test_dos_cobros_intencionales_usan_claves_distintas(db_session, refs):
    _cliente(db_session, refs, 0)
    mesa = _pedido(db_session, refs, 8, False, refs.id_cafe, 1, 50)
    a = cobrar_pedido(db_session, mesa, refs.id_usuario, "EFECTIVO", operation_id="cobro-a")
    llevar = _pedido(db_session, refs, MESA_PARA_LLEVAR, True, refs.id_cafe, 1, 50)
    b = cobrar_pedido(db_session, llevar, refs.id_usuario, "EFECTIVO", operation_id="cobro-b")
    assert a.id_venta != b.id_venta


def test_mesa_para_llevar_y_comandera_acumulan_si_hay_cliente(db_session, refs):
    _cliente(db_session, refs, 0)
    casos = [
        (3, False, None),
        (MESA_PARA_LLEVAR, True, None),
        (9, False, "COMANDERA"),
    ]
    saldo = 0
    for mesa, llevar, origen in casos:
        pedido = _pedido(db_session, refs, mesa, llevar, refs.id_cafe, 1, 50)
        resp = cobrar_pedido(
            db_session,
            pedido,
            refs.id_usuario,
            "EFECTIVO",
            origen_cobro=origen,
            operation_id=f"flujo-{mesa}-{llevar}",
        )
        assert resp.puntos_generados == 5
        saldo += 5
        assert resp.saldo_final == saldo


def test_saldo_insuficiente_desde_el_inicio_es_422(db_session, refs):
    from app.exceptions import SaldoPuntosCambioException

    _cliente(db_session, refs, 40)
    with pytest.raises(DatosInvalidosException) as exc:
        _cobrar(db_session, refs, refs.id_cafe, 1, puntos=50)
    assert not isinstance(exc.value, SaldoPuntosCambioException)
    assert exc.value.status_code == 422


def test_pedido_con_cliente_acumula_aunque_el_cuerpo_no_lo_repita(db_session, refs):
    _cliente(db_session, refs, 0)
    pedido = _pedido(db_session, refs, 11, False, refs.id_cafe, 1, 50)
    resp = cobrar_pedido(
        db_session,
        pedido,
        refs.id_usuario,
        "EFECTIVO",
        operation_id="conserva-cliente",
        id_cliente=None,
        desasociar_cliente=False,
    )
    assert resp.id_cliente == refs.id_cliente
    assert resp.puntos_generados == 5


def test_lectura_de_pedido_incluye_saldo_para_precargar(db_session, refs):
    from app.services.pedido_service import pedido_respuesta_lectura

    _cliente(db_session, refs, 300)
    pedido = _pedido(db_session, refs, 3, False, refs.id_cafe, 1, 50)
    data = pedido_respuesta_lectura(db_session, pedido)
    assert data["id_cliente"] == refs.id_cliente
    assert data["cliente_puntos_saldo"] == 300
    assert data["cliente_activo"] is True
    assert data["cliente_nombre"]


def test_quitar_cliente_cobra_sin_puntos_y_no_toca_saldo(db_session, refs):
    cliente = _cliente(db_session, refs, 80)
    casos = (
        (12, False, None, "quita-mesa"),
        (MESA_PARA_LLEVAR, True, None, "quita-llevar"),
        (13, False, "COMANDERA", "quita-comandera"),
    )
    for mesa, llevar, origen, oid in casos:
        pedido = _pedido(db_session, refs, mesa, llevar, refs.id_cafe, 1, 50)
        resp = cobrar_pedido(
            db_session,
            pedido,
            refs.id_usuario,
            "EFECTIVO",
            origen_cobro=origen,
            operation_id=oid,
            desasociar_cliente=True,
        )
        assert resp.id_cliente is None
        assert resp.puntos_generados == 0
    db_session.refresh(cliente)
    assert int(cliente.puntos_saldo) == 80


def test_cobro_sin_id_cliente_no_acumula_aunque_el_pedido_lo_tuviera(db_session, refs):
    _cliente(db_session, refs, 0)
    pedido = _pedido(db_session, refs, 11, False, refs.id_cafe, 1, 50)
    pedido.id_cliente = None
    db_session.commit()
    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO", operation_id="sin-cliente")
    assert resp.id_cliente is None
    assert resp.puntos_generados == 0
    assert (
        db_session.query(FidelidadMovimientoModel).filter_by(id_venta=resp.id_venta).count() == 0
    )


def test_cliente_inactivo_no_acumula_ni_canjea(db_session, refs):
    cliente = _cliente(db_session, refs, 500)
    cliente.activo = False
    db_session.commit()
    with pytest.raises(Exception):
        _cobrar(db_session, refs, refs.id_cafe, 1, puntos=50)
    db_session.refresh(cliente)
    assert int(cliente.puntos_saldo) == 500


def test_fallo_despues_de_redimir_revierte_todo(db_session, refs, monkeypatch):
    _cliente(db_session, refs, 300)
    db_session.commit()

    def boom(*_a, **_k):
        raise DatosInvalidosException("fallo forzado")

    monkeypatch.setattr("app.services.caja_service.registrar_pago_venta", boom)
    with pytest.raises(DatosInvalidosException):
        _cobrar(db_session, refs, refs.id_refresco, 4, puntos=200)
    cliente = db_session.get(ClienteModel, refs.id_cliente)
    assert int(cliente.puntos_saldo) == 300
    assert db_session.query(VentaModel).filter_by(id_cliente=refs.id_cliente).count() == 0
    assert db_session.query(FidelidadMovimientoModel).filter_by(id_cliente=refs.id_cliente).count() == 0


def test_id_usuario_del_body_no_atribuye_puntos(client, auth_headers):
    cliente = client.post(
        "/clientes/",
        headers=auth_headers,
        json={"nombre": "Ana Puntos", "telefono": "5511112233"},
    )
    assert cliente.status_code == 200, cliente.text
    id_cliente = cliente.json()["id_cliente"]
    ajuste = client.post(
        f"/clientes/{id_cliente}/ajustar-puntos",
        headers=auth_headers,
        json={"puntos": 300, "notas": "saldo de prueba"},
    )
    assert ajuste.status_code == 200, ajuste.text
    ctx = client.get("/ventas/productos/1/contexto", headers=auth_headers)
    precio = ctx.json()["calculo_inicial"]["precio_unitario"]
    add = client.post(
        "/pedidos/mesa/99/lineas?para_llevar=true",
        headers=auth_headers,
        json={"id_producto": 1, "cantidad": 1, "precio_unitario": precio, "extras": []},
    )
    assert add.status_code == 200, add.text
    me = client.get("/auth/me", headers=auth_headers).json()
    cobro = client.post(
        f"/pedidos/{add.json()['id_pedido']}/cobrar",
        headers=auth_headers,
        json={
            "id_usuario": 99999,
            "forma_pago": "EFECTIVO",
            "id_cliente": id_cliente,
            "puntos_canje": 0,
            "origen": "VENTAS",
            "operation_id": "api-puntos-owner",
        },
    )
    assert cobro.status_code == 200, cobro.text
    body = cobro.json()
    assert body["id_usuario"] == me["id_usuario"]
    assert body["id_usuario"] != 99999
    assert body["puntos_generados"] > 0
    assert body["saldo_final"] == body["saldo_anterior"] + body["puntos_generados"]


def _sqlite_pre006(pagos):
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE usuarios (
                    id_usuario INTEGER PRIMARY KEY,
                    nombre TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(text("INSERT INTO usuarios (id_usuario, nombre) VALUES (1, 'Cajero demo')"))
        conn.execute(
            text(
                """
                CREATE TABLE ventas (
                    id_venta INTEGER PRIMARY KEY,
                    fecha_hora TEXT NOT NULL,
                    id_usuario INTEGER NOT NULL,
                    numero_mesa INTEGER NOT NULL,
                    total NUMERIC NOT NULL,
                    forma_pago TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO ventas (id_venta, fecha_hora, id_usuario, numero_mesa, total, forma_pago)
                VALUES (1, '2026-01-01', 1, 1, 40, 'EFECTIVO')
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE venta_pagos (
                    id_pago INTEGER PRIMARY KEY,
                    id_venta INTEGER NOT NULL,
                    metodo TEXT NOT NULL,
                    importe_monetario NUMERIC NOT NULL,
                    cantidad_puntos INTEGER,
                    equivalencia_puntos NUMERIC,
                    fecha_hora TEXT NOT NULL,
                    id_usuario INTEGER NOT NULL,
                    operation_id TEXT NOT NULL
                )
                """
            )
        )
        for pago in pagos:
            conn.execute(
                text(
                    """
                    INSERT INTO venta_pagos (
                        id_venta, metodo, importe_monetario, fecha_hora, id_usuario, operation_id
                    ) VALUES (1, :metodo, :importe, '2026-01-01', 1, :oid)
                    """
                ),
                pago,
            )
        conn.execute(
            text(
                """
                CREATE TABLE fidelidad_movimientos (
                    id_movimiento INTEGER PRIMARY KEY,
                    id_cliente INTEGER NOT NULL,
                    tipo TEXT NOT NULL,
                    puntos INTEGER NOT NULL,
                    saldo_despues INTEGER NOT NULL,
                    id_venta INTEGER,
                    fecha_hora TEXT NOT NULL
                )
                """
            )
        )
    return engine


def test_sqlite_pre_006_valida_actualiza_y_arranca():
    from sqlalchemy import text

    from app.services.migracion_puntos import (
        aplicar_migracion_006_puntos,
        verificar_esquema_puntos_mixtos,
    )

    engine = _sqlite_pre006(
        [{"metodo": "EFECTIVO", "importe": 40, "oid": "hist-1"}]
    )
    aplicar_migracion_006_puntos(engine)
    verificar_esquema_puntos_mixtos(engine)
    aplicar_migracion_006_puntos(engine)
    verificar_esquema_puntos_mixtos(engine)
    with engine.connect() as conn:
        fila = conn.execute(
            text("SELECT metodo, importe_monetario, operation_id FROM venta_pagos")
        ).one()
        n = conn.execute(text("SELECT COUNT(*) FROM venta_pagos")).scalar()
        sql = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'venta_pagos'")
        ).scalar()
        idx = {
            r[0]
            for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'index'"))
        }
        tablas = {
            r[0]
            for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))
        }
    assert int(n) == 1
    assert fila[0] == "EFECTIVO"
    assert float(fila[1]) == 40
    assert fila[2] == "hist-1"
    assert "ck_venta_pago_componente" not in (sql or "")
    assert "uq_venta_pago_un_monetario" in idx
    assert "cobro_operaciones" in tablas


def test_sqlite_nueva_incluye_el_check_del_modelo():
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.services.migracion_puntos import (
        aplicar_migracion_006_puntos,
        verificar_esquema_puntos_mixtos,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        sql = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'venta_pagos'")
        ).scalar()
    assert "ck_venta_pago_componente" in sql
    aplicar_migracion_006_puntos(engine)
    verificar_esquema_puntos_mixtos(engine)


def test_sqlite_componentes_duplicados_detienen_sin_borrar():
    from sqlalchemy import text

    from app.services.migracion_puntos import aplicar_migracion_006_puntos

    engine = _sqlite_pre006(
        [
            {"metodo": "EFECTIVO", "importe": 20, "oid": "dup-a"},
            {"metodo": "TARJETA", "importe": 20, "oid": "dup-b"},
        ]
    )
    with pytest.raises(RuntimeError) as exc:
        aplicar_migracion_006_puntos(engine)
    texto = str(exc.value)
    assert "1" in texto
    assert "://" not in texto
    assert "password" not in texto.lower()
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM venta_pagos")).scalar()
        importes = [
            float(r[0])
            for r in conn.execute(text("SELECT importe_monetario FROM venta_pagos ORDER BY operation_id"))
        ]
        idx = {
            r[0]
            for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'index'"))
        }
    assert int(n) == 2
    assert importes == [20.0, 20.0]
    assert "uq_venta_pago_un_monetario" not in idx
