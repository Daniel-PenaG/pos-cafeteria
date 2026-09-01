"""Agregaciones de ventas por forma de pago para reportes."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import VentaModel, UsuarioModel, ClienteModel
from app.utils.forma_pago import agregar_por_forma_pago, bucket_forma_pago, etiqueta_forma_pago
from app.utils.timezone_mx import isoformat_utc, filtro_rango_mx


def desglose_pagos_periodo(
    db: Session,
    fecha_inicio: date,
    fecha_fin: date,
) -> dict:
    ventas = (
        db.query(VentaModel)
        .filter(*filtro_rango_mx(VentaModel.fecha_hora, fecha_inicio, fecha_fin))
        .all()
    )
    agg = agregar_por_forma_pago(ventas)
    total = agg["total_general"]
    por_metodo = {}
    for clave, datos in agg["por_metodo"].items():
        importe = datos["importe"]
        por_metodo[clave] = {
            **datos,
            "etiqueta": etiqueta_forma_pago(clave),
            "porcentaje": round((importe / total * 100) if total else 0, 1),
        }
    return {
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "total_general": total,
        "num_ventas": agg["num_ventas"],
        "por_metodo": por_metodo,
    }
