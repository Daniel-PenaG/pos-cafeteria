"""Una promoción N×precio no bloquea la venta de unidades sueltas."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.exceptions import DatosInvalidosException
from app.models.models import ClienteModel, ProductoModel, VentaModel
from app.schemas.pedido import PedidoLineaCreate
from app.schemas.ventas import DetalleVentaItem, VentaCreate
from app.services.pedido_service import (
    agregar_combo_pedido,
    agregar_linea_pedido,
    cobrar_pedido,
    obtener_pedido_abierto_mesa,
    recalcular_promociones_pedido,
)
from app.services.promocion_service import calcular_linea
from app.services.promocion_ticket_service import recalcular_lineas_ticket
from app.services.venta_service import MESA_PARA_LLEVAR, registrar_venta
from tests.promo_seed import crear_promo, promo_vigente_siempre


def _cafe(db, refs, precio=42):
    producto = db.get(ProductoModel, refs.id_cafe)
    producto.precio_venta = precio
    db.commit()
    return producto


def _promo_2x70(db, refs, **extra):
    datos = dict(
        nombre="2 cafés",
        tipo="CANTIDAD_PRECIO",
        valor=70,
        cantidad_requerida=2,
        id_producto=refs.id_cafe,
    )
    datos.update(promo_vigente_siempre())
    datos.update(extra)
    promo = crear_promo(db, **datos)
    db.commit()
    return promo


def _vender(db, refs, cantidad, id_promocion=None, **kwargs):
    entrada = {
        "id_producto": refs.id_cafe,
        "cantidad": cantidad,
        "precio_extras": 0,
        "extras": [],
        "id_promocion": id_promocion,
        "sin_promocion": kwargs.pop("sin_promocion", False),
    }
    recalc = recalcular_lineas_ticket(db, [entrada])
    linea = recalc["lineas"][0]
    det = DetalleVentaItem(
        id_producto=refs.id_cafe,
        cantidad=cantidad,
        precio_unitario=linea["precio_unitario"],
        precio_original=linea.get("precio_original"),
        id_promocion=linea.get("id_promocion"),
        sin_promocion=kwargs.pop("sin_promocion", False),
    )
    data = VentaCreate(
        id_usuario=refs.id_usuario,
        numero_mesa=kwargs.pop("numero_mesa", 5),
        forma_pago=kwargs.pop("forma_pago", "EFECTIVO"),
        id_cliente=kwargs.pop("id_cliente", None),
        para_llevar=kwargs.pop("para_llevar", False),
        puntos_canje=kwargs.pop("puntos_canje", 0),
        operation_id=kwargs.pop("operation_id", None),
        detalles=[det],
    )
    resp = registrar_venta(db, data)
    return resp, linea, recalc


def test_cantidad_1_precio_normal_y_venta_permitida(db_session, refs):
    _cafe(db_session, refs)
    promo = _promo_2x70(db_session, refs)
    producto = db_session.get(ProductoModel, refs.id_cafe)
    calc = calcular_linea(db_session, producto, 1, id_promocion=promo.id_promocion)
    assert calc["precio_unitario"] == 42
    assert calc["id_promocion"] is None
    resp, linea, _ = _vender(db_session, refs, 1, promo.id_promocion)
    assert resp.total == 42
    assert linea["id_promocion"] is None


def test_cantidad_2_una_promocion(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs)
    resp, linea, _ = _vender(db_session, refs, 2)
    assert resp.total == 70
    assert linea["aplicaciones"] == 1
    assert linea["unidades_normales"] == 0


def test_cantidad_3_promo_mas_normal(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs)
    resp, linea, _ = _vender(db_session, refs, 3)
    assert resp.total == 112
    assert linea["aplicaciones"] == 1
    assert linea["unidades_normales"] == 1


def test_cantidad_4_dos_promociones(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs)
    resp, linea, _ = _vender(db_session, refs, 4)
    assert resp.total == 140
    assert linea["aplicaciones"] == 2
    assert linea["unidades_normales"] == 0


def test_cantidad_5_dos_promos_mas_normal(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs)
    resp, linea, _ = _vender(db_session, refs, 5)
    assert resp.total == 182
    assert linea["aplicaciones"] == 2
    assert linea["unidades_normales"] == 1


def test_reducir_de_2_a_1_vuelve_a_precio_normal(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs)
    pedido = obtener_pedido_abierto_mesa(db_session, 4, refs.id_usuario)
    recalc = recalcular_lineas_ticket(
        db_session,
        [{"id_producto": refs.id_cafe, "cantidad": 2, "precio_extras": 0, "extras": []}],
    )
    linea = recalc["lineas"][0]
    agregar_linea_pedido(
        db_session,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_cafe,
            cantidad=2,
            precio_unitario=linea["precio_unitario"],
            id_promocion=linea.get("id_promocion"),
            extras=[],
        ),
    )
    db_session.refresh(pedido)
    detalle = pedido.detalles[0]
    detalle.cantidad = 1
    recalcular_promociones_pedido(db_session, pedido)
    db_session.refresh(detalle)
    assert float(detalle.subtotal) == 42
    assert float(detalle.precio_unitario) == 42
    assert detalle.sin_promocion is False
    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    assert resp.total == 42


def test_combo_incompleto_cobra_el_resto_a_precio_normal(db_session, refs):
    _cafe(db_session, refs)
    promo = crear_promo(
        db_session,
        nombre="Café y refresco",
        tipo="COMBO",
        valor=50,
        productos_combo=[refs.id_cafe, refs.id_refresco],
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = obtener_pedido_abierto_mesa(db_session, 6, refs.id_usuario)
    agregar_combo_pedido(db_session, pedido, promo.id_promocion, 1)
    db_session.refresh(pedido)
    sobra = next(d for d in pedido.detalles if d.id_producto == refs.id_refresco)
    db_session.delete(sobra)
    db_session.flush()
    recalcular_promociones_pedido(db_session, pedido)
    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    assert resp.total == 42


def test_promocion_vencida_precio_normal(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(
        db_session,
        refs,
        fecha_inicio=datetime(2020, 1, 1),
        fecha_fin=datetime(2020, 1, 2),
    )
    resp, linea, _ = _vender(db_session, refs, 2)
    assert resp.total == 84
    assert linea["id_promocion"] is None


def test_promocion_fuera_de_horario_precio_normal(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs, hora_inicio="08:00", hora_fin="09:00")
    tarde = datetime(2026, 6, 15, 20, 0, 0)
    recalc = recalcular_lineas_ticket(
        db_session,
        [{"id_producto": refs.id_cafe, "cantidad": 2, "precio_extras": 0, "extras": []}],
        ahora=tarde,
    )
    assert recalc["total"] == 84
    assert recalc["lineas"][0]["id_promocion"] is None


def test_promocion_inactiva_precio_normal(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs, activa=False)
    resp, linea, _ = _vender(db_session, refs, 2)
    assert resp.total == 84
    assert linea["id_promocion"] is None


def test_para_llevar_mismo_calculo(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs)
    resp, _, _ = _vender(
        db_session, refs, 3, numero_mesa=MESA_PARA_LLEVAR, para_llevar=True
    )
    assert resp.total == 112
    assert resp.para_llevar is True


def test_mesa_mismo_calculo(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs)
    pedido = obtener_pedido_abierto_mesa(db_session, 8, refs.id_usuario)
    recalc = recalcular_lineas_ticket(
        db_session,
        [{"id_producto": refs.id_cafe, "cantidad": 3, "precio_extras": 0, "extras": []}],
    )
    linea = recalc["lineas"][0]
    agregar_linea_pedido(
        db_session,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_cafe,
            cantidad=3,
            precio_unitario=linea["precio_unitario"],
            id_promocion=linea.get("id_promocion"),
            extras=[],
        ),
    )
    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    assert resp.total == 112
    assert resp.numero_mesa == 8


def test_comandera_mismo_calculo(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs)
    pedido = obtener_pedido_abierto_mesa(db_session, 9, refs.id_usuario)
    recalc = recalcular_lineas_ticket(
        db_session,
        [{"id_producto": refs.id_cafe, "cantidad": 5, "precio_extras": 0, "extras": []}],
    )
    linea = recalc["lineas"][0]
    agregar_linea_pedido(
        db_session,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_cafe,
            cantidad=5,
            precio_unitario=linea["precio_unitario"],
            id_promocion=linea.get("id_promocion"),
            extras=[],
        ),
    )
    resp = cobrar_pedido(
        db_session, pedido, refs.id_usuario, "TARJETA", origen_cobro="COMANDERA"
    )
    assert resp.total == 182


def test_pago_con_puntos_usa_el_total_recalculado(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs)
    cliente = db_session.get(ClienteModel, refs.id_cliente)
    cliente.puntos_saldo = 80
    db_session.commit()
    resp, _, _ = _vender(db_session, refs, 1, id_cliente=refs.id_cliente, puntos_canje=50)
    assert resp.total == 42
    assert resp.puntos_canje == 50
    assert resp.equivalencia_puntos == 5
    assert resp.importe_monetario == 37
    assert resp.puntos_generados == 3


def test_doble_toque_no_duplica_la_venta(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs)
    pedido = obtener_pedido_abierto_mesa(db_session, 11, refs.id_usuario)
    recalc = recalcular_lineas_ticket(
        db_session,
        [{"id_producto": refs.id_cafe, "cantidad": 1, "precio_extras": 0, "extras": []}],
    )
    linea = recalc["lineas"][0]
    agregar_linea_pedido(
        db_session,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_cafe,
            cantidad=1,
            precio_unitario=linea["precio_unitario"],
            extras=[],
        ),
    )
    primero = cobrar_pedido(
        db_session, pedido, refs.id_usuario, "EFECTIVO", operation_id="promo-1-cafe"
    )
    segundo = cobrar_pedido(
        db_session, pedido, refs.id_usuario, "EFECTIVO", operation_id="promo-1-cafe"
    )
    assert primero.id_venta == segundo.id_venta
    assert db_session.query(VentaModel).count() == 1


def test_precio_alterado_se_rechaza(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs)
    det = DetalleVentaItem(
        id_producto=refs.id_cafe,
        cantidad=1,
        precio_unitario=1,
        extras=[],
    )
    with pytest.raises(DatosInvalidosException):
        registrar_venta(
            db_session,
            VentaCreate(
                id_usuario=refs.id_usuario,
                numero_mesa=5,
                forma_pago="EFECTIVO",
                detalles=[det],
            ),
        )


def test_dos_promociones_no_duplican_descuento(db_session, refs):
    _cafe(db_session, refs)
    _promo_2x70(db_session, refs, nombre="2 x 70")
    crear_promo(
        db_session,
        nombre="2 x 60",
        tipo="CANTIDAD_PRECIO",
        valor=60,
        cantidad_requerida=2,
        id_producto=refs.id_cafe,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    resp, linea, recalc = _vender(db_session, refs, 2)
    assert resp.total == 60
    assert len(recalc["resumen_promociones"]) == 1
    assert linea["id_promocion"] is not None


def test_margen_insuficiente_cobra_precio_normal(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="2 malteadas imposibles",
        tipo="CANTIDAD_PRECIO",
        valor=10,
        cantidad_requerida=2,
        id_producto=refs.id_malteada,
        margen_minimo=80,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    recalc = recalcular_lineas_ticket(
        db_session,
        [{"id_producto": refs.id_malteada, "cantidad": 2, "precio_extras": 0, "extras": []}],
    )
    assert recalc["total"] == 130
    assert recalc["lineas"][0]["id_promocion"] is None
    producto = db_session.get(ProductoModel, refs.id_malteada)
    calc = calcular_linea(db_session, producto, 2, id_promocion=promo.id_promocion)
    assert calc["margen_ok"] is True
    assert calc["id_promocion"] is None
    assert calc["total_linea"] == 130
