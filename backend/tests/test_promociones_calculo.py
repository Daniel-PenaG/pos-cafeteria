"""Pruebas unitarias de cálculo de promociones (sin venta completa)."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.exceptions import DatosInvalidosException
from app.services.promocion_service import (
    aplicar_promo_base,
    calcular_linea,
    calcular_combo,
    listar_aplicables,
    promocion_vigente,
)
from app.services.promocion_ticket_service import _aplicar_promo_unidades, recalcular_lineas_ticket
from tests.promo_seed import crear_promo, promo_vigente_siempre


# --- aplicar_promo_base ---


@pytest.mark.parametrize(
    "cantidad, esperado_unitario, esperado_total",
    [
        (1, 100.0, 100.0),
        (2, 50.0, 100.0),
        (3, 66.67, 200.01),
        (4, 50.0, 200.0),
        (5, 60.0, 300.0),
    ],
)
def test_dos_x_uno_cantidades(cantidad, esperado_unitario, esperado_total):
    """2×1: se cobra ceil(cantidad/2) × precio base; unitario = total/cantidad."""
    unit = aplicar_promo_base(100, "DOS_X_UNO", 0, cantidad)
    assert unit == esperado_unitario
    assert round(unit * cantidad, 2) == pytest.approx(esperado_total, abs=0.02)


def test_porcentaje_20_porciento():
    assert aplicar_promo_base(100, "PORCENTAJE", 20, 1) == 80.0


def test_precio_fijo():
    assert aplicar_promo_base(65, "PRECIO_FIJO", 49, 1) == 49.0


def test_sin_promo_devuelve_precio_base():
    assert aplicar_promo_base(65, "OTRO", 0, 1) == 65.0


# --- Redondeo Decimal ---


def test_redondeo_porcentaje_centavos():
    base = Decimal("33.33")
    desc = Decimal("15") / Decimal("100")
    final = (base * (Decimal("1") - desc)).quantize(Decimal("0.01"))
    assert float(final) == 28.33
    assert float(final * 3) == 84.99


def test_suma_subtotales_coincide_total_ticket(db_session, refs):
    crear_promo(
        db_session,
        nombre="20%",
        tipo="PORCENTAJE",
        valor=20,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    recalc = recalcular_lineas_ticket(
        db_session,
        [
            {"id_producto": refs.id_malteada, "cantidad": 2, "precio_extras": 0, "extras": []},
            {"id_producto": refs.id_cafe, "cantidad": 1, "precio_extras": 0, "extras": []},
        ],
    )
    suma = sum(
        Decimal(str(l["cantidad"])) * Decimal(str(l["precio_unitario"]))
        for l in recalc["lineas"]
    )
    assert float(suma.quantize(Decimal("0.01"))) == recalc["total"]


# --- CANTIDAD_PRECIO ticket (65 individual, 2×90) ---


def _unit_malteada(precio=65, producto_id=1, cat_id=1):
    prod = SimpleNamespace(id_producto=producto_id, id_categoria=cat_id, precio_venta=precio)
    return {
        "line_index": 0,
        "id_producto": producto_id,
        "precio_full": precio,
        "precio_final": precio,
        "id_promocion": None,
        "nombre_promocion": None,
        "tipo_promocion": None,
        "valor_promocion": None,
        "_producto": prod,
    }


def _promo_cantidad(**kwargs):
    defaults = dict(
        id_promocion=1,
        nombre="2 Malteadas",
        tipo="CANTIDAD_PRECIO",
        valor=90,
        cantidad_requerida=2,
        limite_usos_por_ticket=None,
        acumulable=False,
        productos=[],
        categorias=[SimpleNamespace(id_categoria=1)],
        aplica_toda_tienda=False,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.mark.parametrize(
    "n_unidades, total_esperado",
    [(1, 65), (2, 90), (3, 155), (4, 180), (5, 245)],
)
def test_cantidad_precio_malteadas(n_unidades, total_esperado):
    promo = _promo_cantidad()
    units = [_unit_malteada(65, i + 1) for i in range(n_unidades)]
    import app.services.promocion_ticket_service as pts

    orig = pts.producto_elegible
    pts.producto_elegible = lambda _p, prod: prod.id_categoria == 1
    try:
        _aplicar_promo_unidades(units, promo)
        assert round(sum(u["precio_final"] for u in units), 2) == float(total_esperado)
    finally:
        pts.producto_elegible = orig


def test_cantidad_precio_limite_usos_por_ticket():
    promo = _promo_cantidad(limite_usos_por_ticket=1)
    units = [_unit_malteada(65, i + 1) for i in range(4)]
    import app.services.promocion_ticket_service as pts

    orig = pts.producto_elegible
    pts.producto_elegible = lambda _p, prod: prod.id_categoria == 1
    try:
        _aplicar_promo_unidades(units, promo)
        assert round(sum(u["precio_final"] for u in units), 2) == 220.0
    finally:
        pts.producto_elegible = orig


def test_descuento_fijo_ticket(db_session, refs):
    crear_promo(
        db_session,
        nombre="Desc $10",
        tipo="DESCUENTO_FIJO",
        valor=10,
        cantidad_requerida=1,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    recalc = recalcular_lineas_ticket(
        db_session,
        [{"id_producto": refs.id_malteada, "cantidad": 1, "precio_extras": 0, "extras": []}],
    )
    assert recalc["lineas"][0]["precio_unitario"] == 55.0


# --- calcular_linea ---


def test_venta_sin_promocion(db_session, refs):
    producto = db_session.get(__import__("app.models.models", fromlist=["ProductoModel"]).ProductoModel, refs.id_malteada)
    calc = calcular_linea(db_session, producto, 2, sin_promocion=True)
    assert calc["id_promocion"] is None
    assert calc["precio_unitario"] == 65.0
    assert calc["descuento_unitario"] == 0


def test_porcentaje_una_y_varias_unidades(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="20%",
        tipo="PORCENTAJE",
        valor=20,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    producto = db_session.get(__import__("app.models.models", fromlist=["ProductoModel"]).ProductoModel, refs.id_malteada)
    c1 = calcular_linea(db_session, producto, 1, id_promocion=promo.id_promocion)
    c3 = calcular_linea(db_session, producto, 3, id_promocion=promo.id_promocion)
    assert c1["precio_unitario"] == 52.0
    assert c3["precio_unitario"] == 52.0


def test_precio_fijo_con_snapshot(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Fijo 49",
        tipo="PRECIO_FIJO",
        valor=49,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    producto = db_session.get(__import__("app.models.models", fromlist=["ProductoModel"]).ProductoModel, refs.id_malteada)
    calc = calcular_linea(db_session, producto, 1, id_promocion=promo.id_promocion)
    assert calc["precio_unitario"] == 49.0
    assert calc["descuento_unitario"] == 16.0
    assert calc["nombre_promocion"] == "Fijo 49"


def test_margen_minimo_rechaza(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Margen alto",
        tipo="PORCENTAJE",
        valor=50,
        id_producto=refs.id_malteada,
        margen_minimo=80,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    producto = db_session.get(__import__("app.models.models", fromlist=["ProductoModel"]).ProductoModel, refs.id_malteada)
    calc = calcular_linea(db_session, producto, 1, id_promocion=promo.id_promocion)
    assert calc["margen_ok"] is False


def test_producto_no_elegible(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Solo cafe",
        tipo="PORCENTAJE",
        valor=10,
        id_producto=refs.id_cafe,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    producto = db_session.get(__import__("app.models.models", fromlist=["ProductoModel"]).ProductoModel, refs.id_malteada)
    with pytest.raises(DatosInvalidosException):
        calcular_linea(db_session, producto, 1, id_promocion=promo.id_promocion)


def test_extras_no_afectados_por_promo_producto(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="20%",
        tipo="PORCENTAJE",
        valor=20,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    producto = db_session.get(__import__("app.models.models", fromlist=["ProductoModel"]).ProductoModel, refs.id_malteada)
    calc = calcular_linea(db_session, producto, 1, precio_extras=15, id_promocion=promo.id_promocion)
    assert calc["precio_base_promo"] == 52.0
    assert calc["precio_unitario"] == 67.0


def test_promocion_vencida(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Vencida",
        tipo="PORCENTAJE",
        valor=20,
        id_producto=refs.id_malteada,
        fecha_inicio=datetime(2020, 1, 1),
        fecha_fin=datetime(2020, 12, 31),
    )
    db_session.commit()
    assert promocion_vigente(promo) is False


def test_promocion_inactiva(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Inactiva",
        tipo="PORCENTAJE",
        valor=20,
        id_producto=refs.id_malteada,
        activa=False,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    assert promocion_vigente(promo) is False


def test_dos_promos_elige_mejor_precio(db_session, refs):
    crear_promo(
        db_session,
        nombre="10%",
        tipo="PORCENTAJE",
        valor=10,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    crear_promo(
        db_session,
        nombre="30%",
        tipo="PORCENTAJE",
        valor=30,
        id_producto=refs.id_malteada,
        **promo_vigente_siempre(),
    )
    db_session.commit()
    producto = db_session.get(__import__("app.models.models", fromlist=["ProductoModel"]).ProductoModel, refs.id_malteada)
    aplicables = listar_aplicables(db_session, producto)
    assert len(aplicables) == 2
    calc_auto = calcular_linea(db_session, producto, 1)
    assert calc_auto["precio_unitario"] == 45.5


def test_combo_paquete(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Combo AB",
        tipo="COMBO",
        valor=60,
        productos_combo=[refs.id_combo_a, refs.id_combo_b],
        **promo_vigente_siempre(),
    )
    db_session.commit()
    combo = calcular_combo(db_session, promo.id_promocion, 1)
    assert combo["precio_paquete"] == 60.0
    assert len(combo["items"]) == 2
    assert round(sum(i["precio_unitario"] * i["cantidad"] for i in combo["items"]), 2) == 60.0


def test_combo_producto_faltante(db_session, refs):
    from app.models.models import ProductoModel

    combo_b = db_session.get(ProductoModel, refs.id_combo_b)
    combo_b.activo = False
    promo = crear_promo(
        db_session,
        nombre="Combo AB",
        tipo="COMBO",
        valor=60,
        productos_combo=[refs.id_combo_a, refs.id_combo_b],
        **promo_vigente_siempre(),
    )
    db_session.commit()
    with pytest.raises(DatosInvalidosException):
        calcular_combo(db_session, promo.id_promocion, 1)
