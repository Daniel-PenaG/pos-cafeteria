"""Precios desde menú físico (JSON)."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.models import CategoriaModel, ProductoModel
from app.services.precio_menu_service import (
    cargar_menu,
    precio_desde_menu,
    previsualizar_restauracion_precios_menu,
    restaurar_precios_desde_menu,
)


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def test_te_no_matchea_chocolate_ni_agua_embotellada():
    data = cargar_menu()
    p1, _ = precio_desde_menu("Chocolate caliente", data)
    assert p1 is None or p1 == 39  # si hay exact, no regla te
    p2, origen2 = precio_desde_menu("Agua embotellada 600 ml", data)
    assert p2 == 15
    assert origen2 in ("exact", "rule:['agua', '600']")


def test_tisana_menu_55():
    data = cargar_menu()
    precio, _ = precio_desde_menu("Tisana", data)
    assert precio == 55


def test_restaurar_precios_desde_menu_en_bd():
    db, engine = _session()
    try:
        cat = CategoriaModel(nombre="Bebidas")
        db.add(cat)
        db.flush()
        tisana = ProductoModel(
            nombre="Tisana",
            id_categoria=cat.id_categoria,
            precio_venta=Decimal("53.00"),
            activo=True,
        )
        db.add(tisana)
        db.commit()

        prev = previsualizar_restauracion_precios_menu(db)
        assert prev["actualizados"] == 1
        assert prev["cambios"][0]["precio_menu"] == 55

        out = restaurar_precios_desde_menu(db)
        assert out["actualizados"] == 1
        db.refresh(tisana)
        assert float(tisana.precio_venta) == 55
    finally:
        db.close()
        engine.dispose()
