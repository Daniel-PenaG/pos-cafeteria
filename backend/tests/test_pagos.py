"""Pruebas de formas de pago, cierre y desglose."""
from __future__ import annotations

import pytest

from app.exceptions import DatosInvalidosException
from app.models.models import VentaModel
from app.schemas.ventas import DetalleVentaItem, VentaCreate
from app.services.cierre_service import resumen_ventas_usuario
from app.services.pago_reporte_service import desglose_pagos_periodo
from app.services.venta_service import registrar_venta
from app.utils.forma_pago import etiqueta_forma_pago, normalizar_forma_pago
from app.utils.timezone_mx import today_mx
from tests.promo_seed import promo_vigente_siempre


def _linea_simple(db, refs, id_producto, cantidad=1):
    from tests.test_promociones_integracion import _linea

    return _linea(db, id_producto, cantidad)


def _venta(db, refs, forma_pago="EFECTIVO", **kwargs):
    det = _linea_simple(db, refs, refs.id_malteada, 1)
    data = VentaCreate(
        id_usuario=refs.id_usuario,
        numero_mesa=kwargs.get("numero_mesa", 5),
        forma_pago=forma_pago,
        para_llevar=kwargs.get("para_llevar", False),
        detalles=[det],
    )
    return registrar_venta(db, data)


def test_venta_efectivo(db_session, refs):
    resp = _venta(db_session, refs, "EFECTIVO")
    assert resp.forma_pago == "EFECTIVO"


def test_venta_transferencia(db_session, refs):
    resp = _venta(db_session, refs, "TRANSFERENCIA")
    assert resp.forma_pago == "TRANSFERENCIA"


def test_venta_terminal_tarjeta_interna(db_session, refs):
    resp = _venta(db_session, refs, "TARJETA")
    assert resp.forma_pago == "TARJETA"
    assert etiqueta_forma_pago("TARJETA") == "Terminal"


def test_forma_pago_invalida_rechazada(db_session, refs):
    with pytest.raises(DatosInvalidosException):
        _venta(db_session, refs, "BITCOIN")


def test_etiqueta_tarjeta_historica_es_terminal():
    assert etiqueta_forma_pago("TARJETA") == "Terminal"


def test_cierre_totales_por_metodo(db_session, refs):
    _venta(db_session, refs, "EFECTIVO")
    _venta(db_session, refs, "TRANSFERENCIA")
    _venta(db_session, refs, "TARJETA")
    res = resumen_ventas_usuario(db_session, refs.id_usuario, today_mx())
    assert res["num_efectivo"] >= 1
    assert res["num_transferencia"] >= 1
    assert res["num_tarjeta"] >= 1
    suma = res["total_efectivo"] + res["total_transferencia"] + res["total_tarjeta"]
    assert abs(suma - res["total_ventas"]) < 0.02


def test_total_general_igual_suma_metodos(db_session, refs):
    for fp in ("EFECTIVO", "TRANSFERENCIA", "TARJETA"):
        _venta(db_session, refs, fp)
    hoy = today_mx()
    desglose = desglose_pagos_periodo(db_session, hoy, hoy)
    metodos = desglose["por_metodo"]
    suma = sum(metodos[k]["importe"] for k in metodos)
    assert abs(suma - desglose["total_general"]) < 0.02


def test_efectivo_esperado_excluye_otros_metodos(db_session, refs):
    _venta(db_session, refs, "TRANSFERENCIA")
    _venta(db_session, refs, "TARJETA")
    res = resumen_ventas_usuario(db_session, refs.id_usuario, today_mx())
    assert res["total_efectivo"] == 0.0 or res["num_efectivo"] == 0


def test_normalizar_forma_pago():
    assert normalizar_forma_pago(" efectivo ") == "EFECTIVO"


def test_desglose_por_cajero_metodos(db_session, refs):
    """Totales por método de un cajero coinciden con sus ventas."""
    from app.utils.forma_pago import agregar_por_forma_pago

    for fp in ("EFECTIVO", "TRANSFERENCIA", "TARJETA", "EFECTIVO"):
        _venta(db_session, refs, fp)
    ventas = (
        db_session.query(VentaModel)
        .filter(VentaModel.id_usuario == refs.id_usuario)
        .all()
    )
    agg = agregar_por_forma_pago(ventas)
    assert agg["num_efectivo"] == 2
    assert agg["num_transferencia"] == 1
    assert agg["num_tarjeta"] == 1
    suma = agg["total_efectivo"] + agg["total_transferencia"] + agg["total_tarjeta"]
    assert abs(suma - agg["total_general"]) < 0.02


def test_desglose_reportes_respeta_fecha(db_session, refs):
    hoy = today_mx()
    _venta(db_session, refs, "EFECTIVO")
    desglose_hoy = desglose_pagos_periodo(db_session, hoy, hoy)
    assert desglose_hoy["num_ventas"] >= 1
    from datetime import timedelta

    ayer = hoy - timedelta(days=1)
    desglose_ayer = desglose_pagos_periodo(db_session, ayer, ayer)
    assert desglose_ayer["num_ventas"] == 0
    assert desglose_ayer["total_general"] == 0.0
