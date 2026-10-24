"""El precio_venta del catálogo solo se cambia desde Productos, no por recetas/config."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.models import (
    CategoriaModel,
    ConfiguracionModel,
    InsumoModel,
    ProductoModel,
    RecetaInsumoModel,
    RecetaModel,
)
from app.services.receta_service import RecetaService


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def test_actualizar_por_configuracion_no_toca_precio_venta():
    db, engine = _session()
    try:
        db.add(ConfiguracionModel(margen_ganancia=50.0, gastos_fijos=1000.0))
        cat = CategoriaModel(nombre="Bebidas")
        db.add(cat)
        db.flush()
        producto = ProductoModel(
            nombre="Café",
            id_categoria=cat.id_categoria,
            precio_venta=Decimal("42.00"),
            activo=True,
        )
        db.add(producto)
        insumo = InsumoModel(
            nombre="Café molido",
            unidad="g",
            stock_actual=1000,
            stock_minimo=100,
            costo_unitario=Decimal("0.10"),
        )
        db.add(insumo)
        db.flush()
        receta = RecetaModel(
            id_producto=producto.id_producto,
            nombre="Receta café",
            activo=True,
            costo_total=Decimal("1.00"),
        )
        db.add(receta)
        db.flush()
        db.add(
            RecetaInsumoModel(
                id_receta=receta.id_receta,
                id_insumo=insumo.id_insumo,
                cantidad=Decimal("20"),
            )
        )
        db.commit()

        precio_antes = Decimal(str(producto.precio_venta))
        resultado = RecetaService.actualizar_precios_productos_por_configuracion(db)
        db.commit()
        db.refresh(producto)
        db.refresh(receta)

        assert Decimal(str(producto.precio_venta)) == precio_antes
        assert resultado["productos_precio_actualizados"] == 0
        assert resultado["recetas_costo_actualizados"] == 1
        assert Decimal(str(receta.costo_total)) == Decimal("2.00")
    finally:
        db.close()
        engine.dispose()
