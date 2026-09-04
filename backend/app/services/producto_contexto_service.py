"""Contexto operativo de un producto para el modal de ventas (una sola consulta)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.exceptions import RecursoNoEncontradoException
from app.models.models import ProductoModel
from app.services.extras_venta_service import extras_para_producto
from app.services.promocion_service import (
    calcular_linea,
    combo_a_dict,
    listar_aplicables,
    listar_combos_producto,
)


def _promo_a_dict(p) -> dict:
    return {
        "id_promocion": p.id_promocion,
        "nombre": p.nombre,
        "descripcion": p.descripcion,
        "tipo": p.tipo,
        "valor": float(p.valor),
        "activa": p.activa,
        "aplica_toda_tienda": p.aplica_toda_tienda,
        "fecha_inicio": p.fecha_inicio,
        "fecha_fin": p.fecha_fin,
        "hora_inicio": p.hora_inicio,
        "hora_fin": p.hora_fin,
        "dias_semana": p.dias_semana,
        "margen_minimo": float(p.margen_minimo) if p.margen_minimo is not None else None,
        "cantidad_requerida": int(p.cantidad_requerida or 1),
        "limite_usos_por_ticket": int(p.limite_usos_por_ticket) if p.limite_usos_por_ticket is not None else None,
        "acumulable": bool(p.acumulable),
        "fecha_creacion": p.fecha_creacion,
        "ids_productos": [x.id_producto for x in p.productos],
        "ids_categorias": [x.id_categoria for x in p.categorias],
    }


def obtener_contexto_producto(db: Session, id_producto: int) -> dict:
    producto = db.query(ProductoModel).filter(ProductoModel.id_producto == id_producto).first()
    if not producto:
        raise RecursoNoEncontradoException("Producto no encontrado")
    if not producto.activo:
        raise RecursoNoEncontradoException("Producto no activo")

    extras = extras_para_producto(db, id_producto)
    paquetes = [combo_a_dict(p, db) for p in listar_combos_producto(db, id_producto)]
    promociones = [_promo_a_dict(p) for p in listar_aplicables(db, producto)]
    calculo_inicial = calcular_linea(db, producto, 1, 0, None)

    return {
        "producto": {
            "id_producto": producto.id_producto,
            "nombre": producto.nombre,
            "precio": float(producto.precio_venta),
            "id_categoria": producto.id_categoria,
            "activo": bool(producto.activo),
        },
        "extras": extras,
        "promociones": promociones,
        "paquetes": paquetes,
        "calculo_inicial": calculo_inicial,
    }
