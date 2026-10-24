"""Restauración de precio_venta desde historial de ventas/pedidos."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.models import (
    CategoriaModel,
    DetallePedidoModel,
    DetalleVentaModel,
    PedidoModel,
    ProductoModel,
    UsuarioModel,
    VentaModel,
)
from app.services.precio_historial_service import (
    previsualizar_restauracion_precios,
    restaurar_precios_desde_historial,
)
from app.utils.security import hash_password
from datetime import datetime


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def test_restaura_precio_menu_cuando_actual_fue_recalculado():
    db, engine = _session()
    try:
        cat = CategoriaModel(nombre="Cafés")
        db.add(cat)
        db.flush()
        cafe = ProductoModel(
            nombre="Americano",
            id_categoria=cat.id_categoria,
            precio_venta=Decimal("37.33"),  # recalculado por receta
            activo=True,
        )
        db.add(cafe)
        user = UsuarioModel(
            nombre="Admin",
            usuario_login="adminhist",
            hash_password=hash_password("x"),
            rol="ADMIN",
        )
        db.add(user)
        db.flush()

        venta = VentaModel(
            fecha_hora=datetime.utcnow(),
            id_usuario=user.id_usuario,
            numero_mesa=1,
            total=Decimal("105.00"),
            forma_pago="EFECTIVO",
        )
        db.add(venta)
        db.flush()
        # Historial con precio de menú correcto
        for _ in range(3):
            db.add(
                DetalleVentaModel(
                    id_venta=venta.id_venta,
                    id_producto=cafe.id_producto,
                    cantidad=1,
                    precio_unitario=Decimal("35.00"),
                    precio_original=Decimal("35.00"),
                    subtotal=Decimal("35.00"),
                )
            )
        # Una venta reciente con el precio malo
        db.add(
            DetalleVentaModel(
                id_venta=venta.id_venta,
                id_producto=cafe.id_producto,
                cantidad=1,
                precio_unitario=Decimal("37.33"),
                precio_original=Decimal("37.33"),
                subtotal=Decimal("37.33"),
            )
        )
        db.commit()

        preview = previsualizar_restauracion_precios(db)
        assert len(preview) == 1
        assert preview[0]["precio_sugerido"] == 35.0
        assert preview[0]["precio_actual"] == 37.33

        res = restaurar_precios_desde_historial(db)
        db.refresh(cafe)
        assert res["actualizados"] == 1
        assert Decimal(str(cafe.precio_venta)) == Decimal("35.00")
    finally:
        db.close()
        engine.dispose()


def test_no_cambia_si_historial_coincide_con_actual():
    db, engine = _session()
    try:
        cat = CategoriaModel(nombre="Cafés")
        db.add(cat)
        db.flush()
        latte = ProductoModel(
            nombre="Latte",
            id_categoria=cat.id_categoria,
            precio_venta=Decimal("48.00"),
            activo=True,
        )
        db.add(latte)
        user = UsuarioModel(
            nombre="Admin",
            usuario_login="adminhist2",
            hash_password=hash_password("x"),
            rol="ADMIN",
        )
        db.add(user)
        db.flush()
        venta = VentaModel(
            fecha_hora=datetime.utcnow(),
            id_usuario=user.id_usuario,
            numero_mesa=1,
            total=Decimal("48.00"),
            forma_pago="EFECTIVO",
        )
        db.add(venta)
        db.flush()
        db.add(
            DetalleVentaModel(
                id_venta=venta.id_venta,
                id_producto=latte.id_producto,
                cantidad=1,
                precio_unitario=Decimal("48.00"),
                precio_original=Decimal("48.00"),
                subtotal=Decimal("48.00"),
            )
        )
        db.commit()

        assert previsualizar_restauracion_precios(db) == []
        res = restaurar_precios_desde_historial(db)
        assert res["actualizados"] == 0
        db.refresh(latte)
        assert Decimal(str(latte.precio_venta)) == Decimal("48.00")
    finally:
        db.close()
        engine.dispose()


def test_usa_detalle_pedido_activo():
    db, engine = _session()
    try:
        cat = CategoriaModel(nombre="Cafés")
        db.add(cat)
        db.flush()
        capu = ProductoModel(
            nombre="Capuccino",
            id_categoria=cat.id_categoria,
            precio_venta=Decimal("51.20"),
            activo=True,
        )
        db.add(capu)
        user = UsuarioModel(
            nombre="Admin",
            usuario_login="adminhist3",
            hash_password=hash_password("x"),
            rol="ADMIN",
        )
        db.add(user)
        db.flush()
        pedido = PedidoModel(
            numero_mesa=2,
            id_usuario=user.id_usuario,
            estado="ABIERTO",
        )
        db.add(pedido)
        db.flush()
        for _ in range(2):
            db.add(
                DetallePedidoModel(
                    id_pedido=pedido.id_pedido,
                    id_producto=capu.id_producto,
                    nombre_producto="Capuccino",
                    cantidad=1,
                    precio_unitario=Decimal("45.00"),
                    precio_original=Decimal("45.00"),
                    subtotal=Decimal("45.00"),
                    line_key=f"k-{_}",
                    estado_linea="ACTIVA",
                )
            )
        db.commit()

        preview = previsualizar_restauracion_precios(db)
        assert len(preview) == 1
        assert preview[0]["precio_sugerido"] == 45.0
    finally:
        db.close()
        engine.dispose()
