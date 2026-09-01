"""Datos semilla mínimos para pruebas de promociones."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models.models import (
    CategoriaModel,
    ClienteModel,
    ExtraVentaModel,
    FidelidadConfigModel,
    InsumoModel,
    ProductoExtraModel,
    ProductoModel,
    PromocionCategoriaModel,
    PromocionModel,
    PromocionProductoModel,
    RecetaInsumoModel,
    RecetaModel,
    UsuarioModel,
)
from app.utils.security import hash_password
from app.utils.timezone_mx import now_utc_naive


class PromoSeed:
    """IDs y referencias del catálogo sembrado."""

    id_usuario: int
    id_cliente: int
    id_cat_bebidas: int
    id_malteada: int
    id_cafe: int
    id_refresco: int
    id_combo_a: int
    id_combo_b: int
    id_insumo_leche: int
    id_extra_leche: int


def seed_promo_catalog(db) -> PromoSeed:
    refs = PromoSeed()

    usuario = UsuarioModel(
        nombre="Cajero Test",
        usuario_login="cajero_test",
        hash_password=hash_password("test1234"),
        rol="CAJERO",
    )
    db.add(usuario)
    db.flush()
    refs.id_usuario = usuario.id_usuario

    cat = CategoriaModel(nombre="Bebidas")
    db.add(cat)
    db.flush()
    refs.id_cat_bebidas = cat.id_categoria

    malteada = ProductoModel(
        nombre="Malteada",
        id_categoria=cat.id_categoria,
        precio_venta=65,
        activo=True,
    )
    cafe = ProductoModel(
        nombre="Cafe",
        id_categoria=cat.id_categoria,
        precio_venta=50,
        activo=True,
    )
    refresco = ProductoModel(
        nombre="Refresco",
        id_categoria=cat.id_categoria,
        precio_venta=30,
        activo=True,
    )
    combo_a = ProductoModel(
        nombre="Combo A",
        id_categoria=cat.id_categoria,
        precio_venta=40,
        activo=True,
    )
    combo_b = ProductoModel(
        nombre="Combo B",
        id_categoria=cat.id_categoria,
        precio_venta=35,
        activo=True,
    )
    db.add_all([malteada, cafe, refresco, combo_a, combo_b])
    db.flush()
    refs.id_malteada = malteada.id_producto
    refs.id_cafe = cafe.id_producto
    refs.id_refresco = refresco.id_producto
    refs.id_combo_a = combo_a.id_producto
    refs.id_combo_b = combo_b.id_producto

    insumo = InsumoModel(
        nombre="Leche",
        unidad="L",
        stock_actual=100,
        stock_minimo=5,
        costo_unitario=10,
    )
    db.add(insumo)
    db.flush()
    refs.id_insumo_leche = insumo.id_insumo

    receta = RecetaModel(
        id_producto=malteada.id_producto,
        nombre="Receta Malteada",
        costo_total=13,
        activo=True,
    )
    db.add(receta)
    db.flush()
    db.add(
        RecetaInsumoModel(
            id_receta=receta.id_receta,
            id_insumo=insumo.id_insumo,
            cantidad=0.2,
        )
    )

    extra = ExtraVentaModel(
        nombre="Extra Leche",
        precio=15,
        tipo="LACTEO",
        activo=True,
        id_insumo_origen=insumo.id_insumo,
        cantidad=0.1,
        costo_unitario=10,
    )
    db.add(extra)
    db.flush()
    refs.id_extra_leche = extra.id_extra
    db.add(
        ProductoExtraModel(id_producto=malteada.id_producto, id_extra=extra.id_extra)
    )

    cliente = ClienteModel(
        nombre="Cliente Test",
        telefono="5512345678",
        codigo_fidelidad="CAFE-TEST01",
        puntos_saldo=0,
        activo=True,
    )
    db.add(cliente)
    db.flush()
    refs.id_cliente = cliente.id_cliente

    db.add(
        FidelidadConfigModel(
            pesos_por_punto=10,
            minimo_compra_acumular=0,
        )
    )
    db.flush()
    return refs


def crear_promo(
    db,
    *,
    nombre: str,
    tipo: str,
    valor: float,
    id_producto: int | None = None,
    id_categoria: int | None = None,
    aplica_toda_tienda: bool = False,
    cantidad_requerida: int = 1,
    limite_usos_por_ticket: int | None = None,
    acumulable: bool = False,
    margen_minimo: float | None = None,
    activa: bool = True,
    fecha_inicio: datetime | None = None,
    fecha_fin: datetime | None = None,
    hora_inicio: str | None = None,
    hora_fin: str | None = None,
    dias_semana: str | None = None,
    productos_combo: list[int] | None = None,
) -> PromocionModel:
    promo = PromocionModel(
        nombre=nombre,
        tipo=tipo,
        valor=valor,
        activa=activa,
        aplica_toda_tienda=aplica_toda_tienda,
        cantidad_requerida=cantidad_requerida,
        limite_usos_por_ticket=limite_usos_por_ticket,
        acumulable=acumulable,
        margen_minimo=margen_minimo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        dias_semana=dias_semana,
    )
    db.add(promo)
    db.flush()
    if id_producto:
        db.add(
            PromocionProductoModel(
                id_promocion=promo.id_promocion, id_producto=id_producto
            )
        )
    if id_categoria:
        db.add(
            PromocionCategoriaModel(
                id_promocion=promo.id_promocion, id_categoria=id_categoria
            )
        )
    if productos_combo:
        for pid in productos_combo:
            db.add(
                PromocionProductoModel(id_promocion=promo.id_promocion, id_producto=pid)
            )
    db.flush()
    return promo


def promo_vigente_siempre() -> dict:
    """Kwargs para promoción siempre vigente en pruebas."""
    ahora = now_utc_naive()
    return {
        "fecha_inicio": ahora - timedelta(days=1),
        "fecha_fin": ahora + timedelta(days=30),
    }
