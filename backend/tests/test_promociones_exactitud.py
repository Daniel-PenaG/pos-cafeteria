"""Subtotal exacto, cancelación parcial y modo explícito de promoción."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.exceptions import RecalculoTotalException
from app.models.models import (
    ClienteModel,
    DetallePedidoModel,
    DetalleVentaModel,
    FidelidadMovimientoModel,
    MovimientoInventarioModel,
    PedidoCancelacionModel,
    PedidoModel,
    ProductoModel,
    UsuarioModel,
    VentaModel,
    VentaPagoModel,
)
from app.services.fidelidad_service import calcular_puntos_ganados, obtener_config
from app.schemas.pedido import PedidoLineaCreate
from app.services.cancelacion_service import cancelar_linea_enviada
from app.services.pedido_service import (
    _subtotal_guardado,
    agregar_combo_pedido,
    agregar_linea_pedido,
    cobrar_pedido,
    obtener_pedido_abierto_mesa,
    pedido_respuesta_lectura,
    recalcular_promociones_pedido,
)
from app.services.venta_service import MESA_PARA_LLEVAR
from app.services.promocion_service import dinero
from app.services.promocion_ticket_service import recalcular_lineas_ticket
from tests.promo_seed import crear_promo, promo_vigente_siempre

NORMAL = Decimal("42")


def _cafe(db, refs):
    producto = db.get(ProductoModel, refs.id_cafe)
    producto.precio_venta = NORMAL
    db.commit()
    return producto


def _promo(db, refs, *, nombre, requerida, precio):
    promo = crear_promo(
        db,
        nombre=nombre,
        tipo="CANTIDAD_PRECIO",
        valor=precio,
        cantidad_requerida=requerida,
        id_producto=refs.id_cafe,
        **promo_vigente_siempre(),
    )
    db.commit()
    return promo


def _esperado(cantidad: int, requerida: int, precio_paquete: Decimal) -> Decimal:
    apps = cantidad // requerida
    sobrantes = cantidad % requerida
    return dinero(precio_paquete * apps + NORMAL * sobrantes)


def _vender_pedido(db, refs, mesa, cantidad, promo_id=None, sin_promocion=False, para_llevar=False):
    pedido = obtener_pedido_abierto_mesa(db, mesa, refs.id_usuario, para_llevar=para_llevar)
    recalc = recalcular_lineas_ticket(
        db,
        [{
            "id_producto": refs.id_cafe,
            "cantidad": cantidad,
            "precio_extras": 0,
            "extras": [],
            "id_promocion": None if sin_promocion else promo_id,
            "sin_promocion": sin_promocion,
            "forzar_promo_linea": bool(promo_id) and not sin_promocion,
        }],
    )
    linea = recalc["lineas"][0]
    agregar_linea_pedido(
        db,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_cafe,
            cantidad=cantidad,
            precio_unitario=linea["precio_unitario"],
            id_promocion=None if sin_promocion else promo_id,
            sin_promocion=sin_promocion,
            extras=[],
        ),
    )
    db.refresh(pedido)
    return pedido, linea


def _assert_venta_exacta(db, resp, esperado: Decimal):
    assert dinero(resp.total) == esperado
    venta = db.get(VentaModel, resp.id_venta)
    assert dinero(venta.total) == esperado
    detalles = (
        db.query(DetalleVentaModel)
        .filter(DetalleVentaModel.id_venta == resp.id_venta)
        .all()
    )
    suma = sum((dinero(d.subtotal) for d in detalles), Decimal("0"))
    assert dinero(suma) == esperado
    for det in detalles:
        unit = dinero(det.precio_unitario)
        cant = Decimal(str(det.cantidad))
        sub = dinero(det.subtotal)
        if dinero(unit * cant) != sub:
            assert unit == dinero(det.precio_original)
            assert dinero(unit * cant) != sub
    pagos = (
        db.query(VentaPagoModel)
        .filter(VentaPagoModel.id_venta == resp.id_venta)
        .all()
    )
    equiv = dinero(getattr(resp, "equivalencia_puntos", 0) or 0)
    monetario = dinero(resp.importe_monetario)
    assert dinero(monetario + equiv) == esperado
    config = obtener_config(db)
    if resp.id_cliente:
        assert resp.puntos_generados == calcular_puntos_ganados(float(monetario), config)
    else:
        assert resp.puntos_generados == 0
    if pagos:
        caja = sum(
            (dinero(p.importe_monetario) for p in pagos if (p.metodo or "") != "PUNTOS"),
            Decimal("0"),
        )
        puntos_eq = sum(
            (dinero(p.equivalencia_puntos or 0) for p in pagos if (p.metodo or "") == "PUNTOS"),
            Decimal("0"),
        )
        assert dinero(caja) == monetario
        assert dinero(caja + puntos_eq) == esperado
    from app.routers.reportes import _productos_ranking

    _ranking, _cant, total_sub = _productos_ranking(db, VentaModel.id_venta == resp.id_venta)
    assert dinero(total_sub) == esperado


@pytest.mark.parametrize("cantidad", range(1, 8))
@pytest.mark.parametrize(
    ("requerida", "precio"),
    [
        (2, Decimal("70")),
        (3, Decimal("100")),
        (4, Decimal("99")),
    ],
)
def test_subtotal_exacto_en_cantidades(db_session, refs, cantidad, requerida, precio):
    _cafe(db_session, refs)
    promo = _promo(
        db_session,
        refs,
        nombre=f"{requerida} x {precio}",
        requerida=requerida,
        precio=precio,
    )
    esperado = _esperado(cantidad, requerida, precio)
    pedido, linea = _vender_pedido(
        db_session, refs, 20 + cantidad + requerida, cantidad, promo.id_promocion
    )
    assert dinero(linea["subtotal"]) == esperado
    partes = [dinero(p["importe"]) for p in linea["desglose"]]
    assert dinero(sum(partes, Decimal("0"))) == esperado
    detalle = next(d for d in pedido.detalles if float(d.cantidad) > 0)
    assert dinero(detalle.subtotal) == esperado
    suma_pedido = sum(
        (_subtotal_guardado(d) for d in pedido.detalles if float(d.cantidad or 0) > 0),
        Decimal("0"),
    )
    assert dinero(suma_pedido) == esperado
    vista = pedido_respuesta_lectura(db_session, pedido)
    assert dinero(vista["total"]) == esperado
    assert dinero(sum(dinero(ln["subtotal"]) for ln in vista["lineas"] if float(ln["cantidad"]) > 0)) == esperado
    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    _assert_venta_exacta(db_session, resp, esperado)


def test_tres_por_100_genera_puntos_sobre_el_total_exacto(db_session, refs):
    _cafe(db_session, refs)
    promo = _promo(db_session, refs, nombre="3 x 100", requerida=3, precio=Decimal("100"))
    cliente = db_session.get(ClienteModel, refs.id_cliente)
    cliente.puntos_saldo = 0
    db_session.commit()
    pedido, _ = _vender_pedido(db_session, refs, 31, 3, promo.id_promocion)
    pedido.id_cliente = cliente.id_cliente
    db_session.commit()
    resp = cobrar_pedido(
        db_session, pedido, refs.id_usuario, "EFECTIVO", id_cliente=cliente.id_cliente
    )
    _assert_venta_exacta(db_session, resp, Decimal("100"))
    assert resp.puntos_generados == 10


def test_reducir_3_a_2_y_3_a_1_recalcula(db_session, refs):
    _cafe(db_session, refs)
    promo = _promo(db_session, refs, nombre="2 x 70", requerida=2, precio=Decimal("70"))
    pedido, _ = _vender_pedido(db_session, refs, 32, 3, promo.id_promocion)
    detalle = pedido.detalles[0]
    assert dinero(detalle.subtotal) == Decimal("112")

    detalle.cantidad = 2
    recalcular_promociones_pedido(db_session, pedido)
    db_session.refresh(detalle)
    assert dinero(detalle.subtotal) == Decimal("70")

    detalle.cantidad = 1
    recalcular_promociones_pedido(db_session, pedido)
    db_session.refresh(detalle)
    assert dinero(detalle.subtotal) == Decimal("42")
    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    _assert_venta_exacta(db_session, resp, Decimal("42"))


def test_cancelar_parcial_en_comandera_recalcula(db_session, refs):
    _cafe(db_session, refs)
    promo = _promo(db_session, refs, nombre="2 x 70 c", requerida=2, precio=Decimal("70"))
    pedido, _ = _vender_pedido(db_session, refs, 33, 3, promo.id_promocion)
    detalle = pedido.detalles[0]
    detalle.en_comanda = True
    usuario = db_session.get(UsuarioModel, refs.id_usuario)
    usuario.rol = "ADMIN"
    db_session.commit()

    cancelar_linea_enviada(
        db_session,
        id_detalle=detalle.id_detalle_pedido,
        current=usuario,
        cantidad=1,
        motivo="Producto duplicado",
        cantidad_actual=3,
    )
    db_session.refresh(detalle)
    assert float(detalle.cantidad) == 2
    assert dinero(detalle.subtotal) == Decimal("70")
    assert db_session.query(PedidoCancelacionModel).count() == 1
    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    _assert_venta_exacta(db_session, resp, Decimal("70"))

    pedido2, _ = _vender_pedido(db_session, refs, 34, 3, promo.id_promocion)
    detalle2 = pedido2.detalles[0]
    detalle2.en_comanda = True
    db_session.commit()
    cancelar_linea_enviada(
        db_session,
        id_detalle=detalle2.id_detalle_pedido,
        current=usuario,
        cantidad=2,
        motivo="Producto duplicado",
        cantidad_actual=3,
    )
    db_session.refresh(detalle2)
    assert float(detalle2.cantidad) == 1
    assert dinero(detalle2.subtotal) == Decimal("42")
    resp2 = cobrar_pedido(db_session, pedido2, refs.id_usuario, "EFECTIVO")
    _assert_venta_exacta(db_session, resp2, Decimal("42"))


def test_precio_normal_explicito_sobrevive_la_recarga(db_session, refs):
    _cafe(db_session, refs)
    promo = _promo(db_session, refs, nombre="2 x 70 n", requerida=2, precio=Decimal("70"))
    pedido, linea = _vender_pedido(
        db_session, refs, 35, 2, promo.id_promocion, sin_promocion=True
    )
    assert dinero(linea["subtotal"]) == Decimal("84")
    detalle = pedido.detalles[0]
    assert detalle.sin_promocion is True
    assert detalle.id_promocion is None
    vista = pedido_respuesta_lectura(db_session, pedido)
    assert vista["lineas"][0]["modo_promocion"] == "PRECIO_NORMAL"
    assert dinero(vista["total"]) == Decimal("84")
    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    _assert_venta_exacta(db_session, resp, Decimal("84"))


def test_pedido_anterior_no_adopta_promocion_nueva(db_session, refs):
    _cafe(db_session, refs)
    pedido = obtener_pedido_abierto_mesa(db_session, 36, refs.id_usuario)
    db_session.add(
        DetallePedidoModel(
            id_pedido=pedido.id_pedido,
            id_producto=refs.id_cafe,
            nombre_producto="Cafe",
            cantidad=2,
            cantidad_lista=0,
            precio_unitario=NORMAL,
            subtotal=Decimal("84"),
            sin_promocion=None,
            id_promocion=None,
            line_key="legacy-cafe",
            en_comanda=False,
        )
    )
    db_session.commit()
    _promo(db_session, refs, nombre="2 x 70 nueva", requerida=2, precio=Decimal("70"))
    db_session.refresh(pedido)
    vista = pedido_respuesta_lectura(db_session, pedido)
    assert vista["lineas"][0]["modo_promocion"] == "LEGACY"
    assert dinero(vista["total"]) == Decimal("84")
    assert vista.get("aviso_recalculo") is None
    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    _assert_venta_exacta(db_session, resp, Decimal("84"))


def test_subtotal_guardado_no_reconstruye_con_el_unitario():
    linea = DetallePedidoModel(
        cantidad=3,
        precio_unitario=Decimal("37.33"),
        subtotal=Decimal("112.00"),
    )
    assert _subtotal_guardado(linea) == Decimal("112.00")


def _contar_efectos(db):
    return (
        db.query(VentaModel).count(),
        db.query(VentaPagoModel).count(),
        db.query(FidelidadMovimientoModel).count(),
        db.query(MovimientoInventarioModel).count(),
    )


def test_recalculo_409_conserva_el_pedido_hasta_confirmar(db_session, refs):
    _cafe(db_session, refs)
    promo = _promo(db_session, refs, nombre="2 x 70 vence", requerida=2, precio=Decimal("70"))
    pedido, _ = _vender_pedido(db_session, refs, 37, 2, promo.id_promocion)
    assert dinero(pedido.detalles[0].subtotal) == Decimal("70")
    promo.fecha_fin = datetime(2020, 1, 2)
    db_session.commit()
    db_session.refresh(pedido)
    vista = pedido_respuesta_lectura(db_session, pedido)
    assert dinero(vista["total"]) == Decimal("70")
    assert vista["aviso_recalculo"]
    assert dinero(vista["total_recalculado"]) == Decimal("84")
    antes = _contar_efectos(db_session)
    with pytest.raises(RecalculoTotalException) as exc:
        cobrar_pedido(
            db_session,
            pedido,
            refs.id_usuario,
            "EFECTIVO",
            operation_id="recalc-70",
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["codigo"] == "RECALCULO"
    assert _contar_efectos(db_session) == antes
    pedido = obtener_pedido_abierto_mesa(db_session, 37, refs.id_usuario)
    assert pedido.estado == "ABIERTO"
    assert dinero(pedido.detalles[0].subtotal) == Decimal("70")
    with pytest.raises(RecalculoTotalException) as otra:
        cobrar_pedido(
            db_session,
            pedido,
            refs.id_usuario,
            "EFECTIVO",
            operation_id="recalc-70",
        )
    assert otra.value.detail["codigo"] == "RECALCULO"
    assert _contar_efectos(db_session) == antes
    pedido = obtener_pedido_abierto_mesa(db_session, 37, refs.id_usuario)
    resp = cobrar_pedido(
        db_session,
        pedido,
        refs.id_usuario,
        "EFECTIVO",
        operation_id="recalc-70",
        confirmar_recalculo=True,
    )
    _assert_venta_exacta(db_session, resp, Decimal("84"))
    repetido = cobrar_pedido(
        db_session,
        pedido,
        refs.id_usuario,
        "EFECTIVO",
        operation_id="recalc-70",
        confirmar_recalculo=True,
    )
    assert repetido.id_venta == resp.id_venta
    assert db_session.query(VentaModel).count() == antes[0] + 1


def test_recalculo_api_usa_el_usuario_del_jwt(db_session, refs):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app
    from app.utils.identidad import id_usuario_autenticado

    _cafe(db_session, refs)
    promo = _promo(db_session, refs, nombre="2 x 70 jwt", requerida=2, precio=Decimal("70"))
    pedido, _ = _vender_pedido(db_session, refs, 39, 2, promo.id_promocion)
    promo.fecha_fin = datetime(2020, 1, 2)
    current = db_session.get(UsuarioModel, refs.id_usuario)
    assert id_usuario_autenticado(db_session, current, 99999, "pedidos.cobrar") == current.id_usuario
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            login = client.post(
                "/auth/login",
                json={"usuario_login": "cajero_test", "password": "test1234"},
            )
            assert login.status_code == 200
            token = login.json()["access_token"]
            antes = _contar_efectos(db_session)
            cobro = client.post(
                f"/pedidos/{pedido.id_pedido}/cobrar",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "id_usuario": 99999,
                    "forma_pago": "EFECTIVO",
                    "confirmar_recalculo": False,
                    "operation_id": "recalc-jwt",
                },
            )
        assert cobro.status_code == 409
        cuerpo = cobro.json()["detail"]
        assert cuerpo["codigo"] == "RECALCULO"
        assert _contar_efectos(db_session) == antes
        fresco = db_session.get(PedidoModel, pedido.id_pedido)
        assert fresco.estado == "ABIERTO"
        assert dinero(fresco.detalles[0].subtotal) == Decimal("70")
    finally:
        app.dependency_overrides.clear()


def test_para_llevar_comandera_y_puntos_cuadran(db_session, refs):
    _cafe(db_session, refs)
    promo = _promo(db_session, refs, nombre="2 x 70 canales", requerida=2, precio=Decimal("70"))
    pedido, _ = _vender_pedido(
        db_session, refs, MESA_PARA_LLEVAR, 3, promo.id_promocion, para_llevar=True
    )
    resp = cobrar_pedido(
        db_session,
        pedido,
        refs.id_usuario,
        "EFECTIVO",
        origen_cobro="VENTAS",
    )
    _assert_venta_exacta(db_session, resp, Decimal("112"))
    assert resp.para_llevar is True

    pedido_c, _ = _vender_pedido(db_session, refs, 41, 3, promo.id_promocion)
    pedido_c.detalles[0].en_comanda = True
    db_session.commit()
    resp_c = cobrar_pedido(
        db_session, pedido_c, refs.id_usuario, "TARJETA", origen_cobro="COMANDERA"
    )
    _assert_venta_exacta(db_session, resp_c, Decimal("112"))

    cliente = db_session.get(ClienteModel, refs.id_cliente)
    cliente.puntos_saldo = 2000
    db_session.commit()
    pedido_m, _ = _vender_pedido(db_session, refs, 42, 3, promo.id_promocion)
    pedido_m.id_cliente = cliente.id_cliente
    db_session.commit()
    mixto = cobrar_pedido(
        db_session,
        pedido_m,
        refs.id_usuario,
        "EFECTIVO",
        id_cliente=cliente.id_cliente,
        puntos_canje=100,
    )
    _assert_venta_exacta(db_session, mixto, Decimal("112"))
    assert dinero(mixto.equivalencia_puntos) == Decimal("10")
    assert dinero(mixto.importe_monetario) == Decimal("102")

    cliente.puntos_saldo = 2000
    db_session.commit()
    pedido_p, _ = _vender_pedido(db_session, refs, 43, 3, promo.id_promocion)
    pedido_p.id_cliente = cliente.id_cliente
    db_session.commit()
    completo = cobrar_pedido(
        db_session,
        pedido_p,
        refs.id_usuario,
        "EFECTIVO",
        id_cliente=cliente.id_cliente,
        puntos_canje=1120,
    )
    _assert_venta_exacta(db_session, completo, Decimal("112"))
    assert dinero(completo.importe_monetario) == Decimal("0")
    assert dinero(completo.equivalencia_puntos) == Decimal("112")
    assert completo.puntos_generados == 0


def test_combo_completo_con_sobrante_y_quitar_producto(db_session, refs):
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
    pedido = obtener_pedido_abierto_mesa(db_session, 38, refs.id_usuario)
    agregar_combo_pedido(db_session, pedido, promo.id_promocion, 1)
    db_session.refresh(pedido)
    assert {d.id_producto for d in pedido.detalles} == {refs.id_cafe, refs.id_refresco}
    cafe = next(d for d in pedido.detalles if d.id_producto == refs.id_cafe)
    cafe.cantidad = 2
    recalcular_promociones_pedido(db_session, pedido)
    db_session.refresh(pedido)
    total = sum((dinero(d.subtotal) for d in pedido.detalles), Decimal("0"))
    assert total == Decimal("92")
    refresco = next(d for d in pedido.detalles if d.id_producto == refs.id_refresco)
    db_session.delete(refresco)
    db_session.flush()
    recalcular_promociones_pedido(db_session, pedido)
    db_session.refresh(pedido)
    restante = sum((dinero(d.subtotal) for d in pedido.detalles if float(d.cantidad) > 0), Decimal("0"))
    assert restante == Decimal("84")
    resp = cobrar_pedido(db_session, pedido, refs.id_usuario, "EFECTIVO")
    _assert_venta_exacta(db_session, resp, Decimal("84"))
