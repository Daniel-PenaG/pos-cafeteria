"""Casos de prueba para promociones CANTIDAD_PRECIO (ticket)."""
from types import SimpleNamespace

from app.services.promocion_ticket_service import _aplicar_promo_unidades


def _unit(precio, producto_id=1):
    prod = SimpleNamespace(id_producto=producto_id, id_categoria=1, precio_venta=precio)
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


def _promo(**kwargs):
    defaults = dict(
        id_promocion=1,
        nombre="Lunes de Malteadas",
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
    p = SimpleNamespace(**defaults)

    def elegible(prod):
        if p.aplica_toda_tienda:
            return True
        ids = {x.id_categoria for x in p.categorias}
        return prod.id_categoria in ids

    import app.services.promocion_ticket_service as pts

    orig = pts.producto_elegible
    pts.producto_elegible = lambda promo, prod: elegible(prod)
    return p, pts, orig


def test_caso2_dos_malteadas_90():
    promo, pts, orig = _promo()
    try:
        units = [_unit(50, 1), _unit(50, 2)]
        desc = _aplicar_promo_unidades(units, promo)
        assert round(sum(u["precio_final"] for u in units), 2) == 90.0
        assert desc == 10.0
    finally:
        pts.producto_elegible = orig


def test_caso1_una_malteada_sin_promo():
    promo, pts, orig = _promo()
    try:
        units = [_unit(50)]
        desc = _aplicar_promo_unidades(units, promo)
        assert sum(u["precio_final"] for u in units) == 50.0
        assert desc == 0.0
    finally:
        pts.producto_elegible = orig


def test_caso3_tres_malteadas():
    promo, pts, orig = _promo()
    try:
        units = [_unit(50), _unit(50), _unit(50)]
        _aplicar_promo_unidades(units, promo)
        assert round(sum(u["precio_final"] for u in units), 2) == 140.0
    finally:
        pts.producto_elegible = orig


def test_caso4_cuatro_malteadas():
    promo, pts, orig = _promo()
    try:
        units = [_unit(50) for _ in range(4)]
        _aplicar_promo_unidades(units, promo)
        assert round(sum(u["precio_final"] for u in units), 2) == 180.0
    finally:
        pts.producto_elegible = orig


def test_caso7_sabores_diferentes():
    promo, pts, orig = _promo()
    try:
        units = [_unit(50, 1), _unit(50, 2)]
        _aplicar_promo_unidades(units, promo)
        assert round(sum(u["precio_final"] for u in units), 2) == 90.0
    finally:
        pts.producto_elegible = orig
