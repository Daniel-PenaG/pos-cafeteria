"""Fase 3A: apertura, movimientos, arqueo y conciliación de caja."""
from __future__ import annotations

import json

import pytest

from app.constants.acciones import (
    ABRIR_CAJA,
    CERRAR_CAJA,
    FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS,
    REGISTRAR_MOVIMIENTO_CAJA,
)
from app.constants.caja import (
    ESTADO_ABIERTA,
    ESTADO_CERRADA_CONCILIADA,
    ESTADO_CERRADA_CON_DIFERENCIA,
    ESTADO_EN_ARQUEO,
    ESTADO_REVISADA,
    MSG_CAJA_CERRADA,
    MSG_CAJA_CERRANDO,
    MSG_DOBLE_APERTURA,
    MSG_NO_REVISAR_PROPIO,
    MSG_OBS_DIFERENCIA,
    MSG_PAYLOAD,
    MSG_PEDIDOS_ABIERTOS,
    MSG_SIN_CAJA,
)
from app.exceptions import (
    AccesoNegadoException,
    ConflictoOperacionException,
    DatosInvalidosException,
)
from app.models.models import PedidoModel, UsuarioModel, VentaModel, VentaPagoModel
from app.schemas.ventas import DetalleVentaItem, VentaCreate
from app.services.caja_service import (
    _totales_sesion,
    anular_cierre,
    abrir_caja,
    caja_requerida_para_cobrar,
    cerrar_caja,
    iniciar_arqueo,
    registrar_movimiento,
    revisar_cierre,
    sesion_activa_usuario,
)
from app.services.pedido_service import obtener_pedido_abierto_mesa
from app.services.venta_service import registrar_venta
from app.utils.security import hash_password
from app.utils.timezone_mx import today_mx
from tests.test_promociones_integracion import _linea


def _user(db, refs) -> UsuarioModel:
    return db.get(UsuarioModel, refs.id_usuario)


def _admin(db, login="admin_caja_test") -> UsuarioModel:
    existente = db.query(UsuarioModel).filter_by(usuario_login=login).first()
    if existente:
        return existente
    u = UsuarioModel(
        nombre="Admin Caja",
        usuario_login=login,
        hash_password=hash_password("test1234"),
        rol="ADMIN",
    )
    db.add(u)
    db.flush()
    return u


def _abrir(db, user, fondo=100, terminal="CAJA-1", oid=None):
    return abrir_caja(
        db,
        user,
        fondo_inicial=fondo,
        terminal=terminal,
        observacion="apertura test",
        operation_id=oid,
    )


def _venta(db, refs, forma="EFECTIVO"):
    det = _linea(db, refs.id_cafe, 1)
    return registrar_venta(
        db,
        VentaCreate(
            id_usuario=refs.id_usuario,
            numero_mesa=7,
            forma_pago=forma,
            detalles=[det],
        ),
    )


def _cerrar_ok(db, user, efectivo=100, trans=0, tarjeta=0, obs=None, oid=None, forzar=False):
    return cerrar_caja(
        db,
        user,
        denominaciones=[],
        declarado_efectivo=efectivo,
        declarado_transferencia=trans,
        declarado_tarjeta=tarjeta,
        captura_directa=True,
        observacion=obs,
        forzar=forzar,
        operation_id=oid,
    )


def test_abrir_caja_y_fondo_inicial(db_session, refs):
    user = _user(db_session, refs)
    data = _abrir(db_session, user, fondo=150)
    assert data["estado"] == ESTADO_ABIERTA
    assert data["fondo_inicial"] == 150
    assert data["efectivo_esperado"] == 150
    assert any(m["tipo"] == "FONDO_INICIAL" for m in data["movimientos"])


def test_impedir_doble_apertura(db_session, refs):
    user = _user(db_session, refs)
    _abrir(db_session, user)
    with pytest.raises(ConflictoOperacionException) as exc:
        _abrir(db_session, user, terminal="CAJA-2")
    assert MSG_DOBLE_APERTURA in str(exc.value.detail)


def test_reintento_misma_clave_abre_una_vez(db_session, refs):
    user = _user(db_session, refs)
    a = _abrir(db_session, user, fondo=80, oid="open-same-1")
    b = _abrir(db_session, user, fondo=80, oid="open-same-1")
    assert a["id_sesion_caja"] == b["id_sesion_caja"]


def test_misma_clave_payload_diferente_409(db_session, refs):
    user = _user(db_session, refs)
    _abrir(db_session, user, fondo=80, oid="open-diff-1")
    with pytest.raises(ConflictoOperacionException) as exc:
        _abrir(db_session, user, fondo=90, oid="open-diff-1")
    assert MSG_PAYLOAD in str(exc.value.detail)


def test_venta_vinculada_a_sesion(db_session, refs):
    user = _user(db_session, refs)
    sesion = _abrir(db_session, user)
    resp = _venta(db_session, refs, "EFECTIVO")
    venta = db_session.get(VentaModel, resp.id_venta)
    assert venta.id_sesion_caja == sesion["id_sesion_caja"]
    pago = (
        db_session.query(VentaPagoModel)
        .filter(VentaPagoModel.id_venta == venta.id_venta)
        .first()
    )
    assert pago is not None
    assert float(pago.importe_monetario) == float(venta.total)


def test_cobro_sin_caja_segun_flag(db_session, refs, monkeypatch):
    monkeypatch.setenv("CAJA_REQUERIDA_PARA_COBRAR", "0")
    resp = _venta(db_session, refs, "EFECTIVO")
    venta = db_session.get(VentaModel, resp.id_venta)
    assert venta.id_sesion_caja is None

    monkeypatch.setenv("CAJA_REQUERIDA_PARA_COBRAR", "1")
    assert caja_requerida_para_cobrar() is True
    with pytest.raises(DatosInvalidosException) as exc:
        _venta(db_session, refs, "EFECTIVO")
    assert MSG_SIN_CAJA in str(exc.value.detail)


def test_entrada_retiro_gasto_y_esperado(db_session, refs):
    user = _user(db_session, refs)
    _abrir(db_session, user, fondo=200)
    _venta(db_session, refs, "EFECTIVO")  # +50
    registrar_movimiento(db_session, user, tipo="ENTRADA", importe=20, motivo="cambio")
    registrar_movimiento(db_session, user, tipo="RETIRO", importe=30, motivo="retiro")
    registrar_movimiento(db_session, user, tipo="GASTO_CAJA", importe=10, motivo="azucar")
    sesion = sesion_activa_usuario(db_session, user.id_usuario)
    tot = _totales_sesion(db_session, sesion)
    assert tot["efectivo_esperado"] == 230.0
    assert tot["entradas"] == 20
    assert tot["retiros"] == 30
    assert tot["gastos_caja"] == 10


def test_arqueo_ciego_no_expone_esperados(db_session, refs):
    user = _user(db_session, refs)
    _abrir(db_session, user, fondo=80)
    _venta(db_session, refs, "EFECTIVO")
    data = iniciar_arqueo(db_session, user)
    assert data["ciego"] is True
    assert "efectivo_esperado" not in data
    assert "esperado_efectivo" not in data
    assert "ventas_efectivo" not in data
    assert "ventas_total" not in data
    assert "ingreso_monetario" not in data


def test_arqueo_denominaciones_y_conciliado(db_session, refs):
    user = _user(db_session, refs)
    _abrir(db_session, user, fondo=100)
    iniciar_arqueo(db_session, user)
    data = cerrar_caja(
        db_session,
        user,
        denominaciones=[{"codigo": "B100", "cantidad": 1}],
        declarado_efectivo=None,
        declarado_transferencia=0,
        declarado_tarjeta=0,
        captura_directa=False,
    )
    assert data["estado"] == ESTADO_CERRADA_CONCILIADA
    assert data["declarado_efectivo"] == 100
    assert data["diferencia_efectivo"] == 0


def test_transferencia_terminal_y_diferencia(db_session, refs):
    user = _user(db_session, refs)
    _abrir(db_session, user, fondo=0)
    _venta(db_session, refs, "TRANSFERENCIA")
    _venta(db_session, refs, "TARJETA")
    with pytest.raises(DatosInvalidosException) as exc:
        _cerrar_ok(db_session, user, efectivo=0, trans=0, tarjeta=0)
    assert MSG_OBS_DIFERENCIA in str(exc.value.detail)
    data = _cerrar_ok(db_session, user, efectivo=0, trans=40, tarjeta=50, obs="faltante terminal")
    assert data["estado"] == ESTADO_CERRADA_CON_DIFERENCIA
    assert data["esperado_transferencia"] == 50
    assert data["esperado_tarjeta"] == 50
    assert data["diferencia_transferencia"] == -10
    assert data["diferencia_tarjeta"] == 0


def test_observacion_obligatoria_fuera_tolerancia(db_session, refs):
    user = _user(db_session, refs)
    _abrir(db_session, user, fondo=100)
    with pytest.raises(DatosInvalidosException):
        _cerrar_ok(db_session, user, efectivo=90)
    ok = _cerrar_ok(db_session, user, efectivo=90, obs="faltan 10")
    assert ok["estado"] == ESTADO_CERRADA_CON_DIFERENCIA


def test_pedidos_abiertos_bloquean_y_admin_fuerza(db_session, refs):
    user = _user(db_session, refs)
    user.permisos_acciones_json = json.dumps(
        [ABRIR_CAJA, REGISTRAR_MOVIMIENTO_CAJA, CERRAR_CAJA, FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS]
    )
    db_session.commit()
    _abrir(db_session, user, fondo=50)
    obtener_pedido_abierto_mesa(db_session, 11, user.id_usuario)
    with pytest.raises(DatosInvalidosException) as exc:
        _cerrar_ok(db_session, user, efectivo=50)
    assert MSG_PEDIDOS_ABIERTOS in str(exc.value.detail)
    data = _cerrar_ok(db_session, user, efectivo=50, obs="fuerzo por corte", forzar=True)
    assert data["forzado"] is True
    abiertos = db_session.query(PedidoModel).filter_by(id_usuario=user.id_usuario, estado="ABIERTO").all()
    assert len(abiertos) >= 1


def test_cajero_no_revisa_propio_cierre(db_session, refs):
    admin = _admin(db_session)
    _abrir(db_session, admin, fondo=20, terminal="BARRA")
    cerrado = _cerrar_ok(db_session, admin, efectivo=20)
    with pytest.raises(AccesoNegadoException) as exc:
        revisar_cierre(db_session, admin, cerrado["id_sesion_caja"])
    assert MSG_NO_REVISAR_PROPIO in str(exc.value.detail)
    admin2 = _admin(db_session, "admin_caja_2")
    rev = revisar_cierre(db_session, admin2, cerrado["id_sesion_caja"])
    assert rev["estado"] == ESTADO_REVISADA


def test_usuario_ajeno_no_modifica_caja(db_session, refs):
    user = _user(db_session, refs)
    otro = UsuarioModel(
        nombre="Otro",
        usuario_login="otro_caja",
        hash_password=hash_password("test1234"),
        rol="CAJERO",
    )
    db_session.add(otro)
    db_session.flush()
    _abrir(db_session, user, fondo=10)
    with pytest.raises(DatosInvalidosException):
        registrar_movimiento(db_session, otro, tipo="ENTRADA", importe=5, motivo="no")


def test_doble_cierre_y_reintento(db_session, refs):
    user = _user(db_session, refs)
    _abrir(db_session, user, fondo=40)
    a = _cerrar_ok(db_session, user, efectivo=40, oid="close-1")
    b = _cerrar_ok(db_session, user, efectivo=40, oid="close-1")
    assert a["id_sesion_caja"] == b["id_sesion_caja"]
    with pytest.raises(ConflictoOperacionException) as exc:
        _cerrar_ok(db_session, user, efectivo=40, oid="close-2")
    assert MSG_CAJA_CERRADA in str(exc.value.detail)


def test_venta_mientras_arqueo(db_session, refs):
    user = _user(db_session, refs)
    _abrir(db_session, user, fondo=10)
    iniciar_arqueo(db_session, user)
    sesion = sesion_activa_usuario(db_session, user.id_usuario)
    assert sesion.estado == ESTADO_EN_ARQUEO
    with pytest.raises(ConflictoOperacionException) as exc:
        _venta(db_session, refs, "EFECTIVO")
    assert MSG_CAJA_CERRANDO in str(exc.value.detail)


def test_metodo_desconocido_no_incrementa_efectivo(db_session, refs):
    user = _user(db_session, refs)
    sesion = _abrir(db_session, user, fondo=0)
    hist = VentaModel(
        fecha_hora=__import__("datetime").datetime.utcnow(),
        id_usuario=user.id_usuario,
        numero_mesa=1,
        total=99,
        forma_pago="PUNTOS",
        id_sesion_caja=sesion["id_sesion_caja"],
    )
    db_session.add(hist)
    db_session.commit()
    locked = sesion_activa_usuario(db_session, user.id_usuario)
    tot = _totales_sesion(db_session, locked)
    assert tot["ventas_efectivo"] == 0
    assert tot["ventas_desconocido"] == 99
    assert tot["efectivo_esperado"] == 0


def test_ventas_historicas_sin_sesion(db_session, refs):
    resp = _venta(db_session, refs, "EFECTIVO")
    venta = db_session.get(VentaModel, resp.id_venta)
    assert venta.id_sesion_caja is None
    user = _user(db_session, refs)
    nueva = _abrir(db_session, user, fondo=5)
    db_session.refresh(venta)
    assert venta.id_sesion_caja is None
    assert nueva["num_ventas"] == 0


def test_impresion_no_esta_en_cierre(db_session, refs):
    """La impresión es post-cierre en frontend; el backend ya persistió."""
    user = _user(db_session, refs)
    _abrir(db_session, user, fondo=15)
    data = _cerrar_ok(db_session, user, efectivo=15)
    assert data["estado"] == ESTADO_CERRADA_CONCILIADA
    assert sesion_activa_usuario(db_session, user.id_usuario) is None


def test_zona_horaria_mexico_snapshot(db_session, refs):
    user = _user(db_session, refs)
    _abrir(db_session, user, fondo=12)
    data = _cerrar_ok(db_session, user, efectivo=12)
    from app.models.models import CierreCajaModel

    snap = (
        db_session.query(CierreCajaModel)
        .filter(CierreCajaModel.id_sesion_caja == data["id_sesion_caja"])
        .first()
    )
    assert snap is not None
    assert snap.fecha == today_mx()
    assert data["fecha_apertura"].endswith("Z") or "+" in data["fecha_apertura"] or "T" in data["fecha_apertura"]


def test_anular_con_motivo(db_session, refs):
    admin = _admin(db_session, "admin_anula")
    _abrir(db_session, admin, fondo=8, terminal="CAJA-3")
    cerrado = _cerrar_ok(db_session, admin, efectivo=8)
    anulado = anular_cierre(db_session, admin, cerrado["id_sesion_caja"], "corte mal capturado")
    assert anulado["estado"] == "ANULADA"
    assert anulado["motivo_anulacion"] == "corte mal capturado"


def test_movimiento_importe_negativo_rechazado(db_session, refs):
    user = _user(db_session, refs)
    _abrir(db_session, user, fondo=5)
    with pytest.raises(DatosInvalidosException):
        registrar_movimiento(db_session, user, tipo="ENTRADA", importe=-1, motivo="x")
