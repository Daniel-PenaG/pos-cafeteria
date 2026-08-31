"""Seed reproducible para benchmarks y pruebas de rendimiento."""
from __future__ import annotations

from datetime import timedelta

from app.models.models import (
    UsuarioModel,
    CategoriaModel,
    ProductoModel,
    InsumoModel,
    RecetaModel,
    RecetaInsumoModel,
    VentaModel,
    DetalleVentaModel,
    PromocionModel,
)
from app.constants.roles import ADMIN
from app.utils.security import hash_password
from app.utils.timezone_mx import now_utc_naive


def seed_perf_db(db, num_ventas: int = 120) -> None:
    admin = UsuarioModel(
        nombre="Admin Test",
        usuario_login="admintest",
        hash_password=hash_password("test1234"),
        rol=ADMIN,
    )
    db.add(admin)
    db.flush()

    cat = CategoriaModel(nombre="Bebidas")
    db.add(cat)
    db.flush()

    insumo_a = InsumoModel(
        nombre="Leche", unidad="ml", stock_actual=5000, stock_minimo=500, costo_unitario=0.02
    )
    insumo_b = InsumoModel(
        nombre="Cafe", unidad="g", stock_actual=3000, stock_minimo=300, costo_unitario=0.05
    )
    db.add_all([insumo_a, insumo_b])
    db.flush()

    prod_a = ProductoModel(
        nombre="Latte", id_categoria=cat.id_categoria, precio_venta=48, activo=True
    )
    prod_b = ProductoModel(
        nombre="Americano", id_categoria=cat.id_categoria, precio_venta=35, activo=True
    )
    db.add_all([prod_a, prod_b])
    db.flush()

    rec_a = RecetaModel(id_producto=prod_a.id_producto, nombre="Latte", activo=True, costo_total=12)
    rec_b = RecetaModel(id_producto=prod_b.id_producto, nombre="Americano", activo=True, costo_total=8)
    db.add_all([rec_a, rec_b])
    db.flush()

    db.add_all(
        [
            RecetaInsumoModel(id_receta=rec_a.id_receta, id_insumo=insumo_a.id_insumo, cantidad=200),
            RecetaInsumoModel(id_receta=rec_a.id_receta, id_insumo=insumo_b.id_insumo, cantidad=18),
            RecetaInsumoModel(id_receta=rec_b.id_receta, id_insumo=insumo_b.id_insumo, cantidad=15),
            RecetaInsumoModel(id_receta=rec_b.id_receta, id_insumo=insumo_a.id_insumo, cantidad=50),
        ]
    )

    promo = PromocionModel(
        nombre="2x1 test",
        tipo="DESCUENTO_FIJO",
        valor=5,
        activa=True,
        aplica_toda_tienda=True,
    )
    if hasattr(PromocionModel, "cantidad_requerida"):
        promo.cantidad_requerida = 1
    db.add(promo)
    db.flush()

    fin = now_utc_naive()
    for i in range(num_ventas):
        fh = fin - timedelta(hours=(num_ventas - i) * 2, minutes=i % 60)
        venta = VentaModel(
            id_usuario=admin.id_usuario,
            total=48 + (i % 3) * 35,
            forma_pago="EFECTIVO",
            fecha_hora=fh,
            numero_mesa=(i % 5) + 1,
        )
        db.add(venta)
        db.flush()
        usar_promo = i % 4 == 0
        db.add(
            DetalleVentaModel(
                id_venta=venta.id_venta,
                id_producto=prod_a.id_producto,
                cantidad=1,
                precio_unitario=48,
                subtotal=48,
                id_promocion=promo.id_promocion if usar_promo else None,
                descuento_unitario=5 if usar_promo else 0,
            )
        )
        if i % 2 == 0:
            db.add(
                DetalleVentaModel(
                    id_venta=venta.id_venta,
                    id_producto=prod_b.id_producto,
                    cantidad=1,
                    precio_unitario=35,
                    subtotal=35,
                )
            )
