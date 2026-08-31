"""Pruebas de regresión y presupuesto de consultas para reportes optimizados."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.services.reporte_ventas_service import (
    resumen_ventas_rango,
    rendimiento_dia_semana,
    rendimiento_por_hora,
    rango_fechas_mes,
)
from app.models.models import VentaModel
from app.utils.timezone_mx import today_mx, filtro_rango_mx
from app.utils.sql_counter import reset_sql_count, get_sql_count
import app.utils.sql_counter  # noqa: F401


def _ventas_rango(db: Session, inicio: date, fin: date):
    return (
        db.query(VentaModel)
        .filter(*filtro_rango_mx(VentaModel.fecha_hora, inicio, fin))
        .all()
    )


def test_resumen_rango_estructura(db_session: Session):
    hoy = today_mx()
    inicio = hoy - timedelta(days=20)
    res = resumen_ventas_rango(db_session, inicio, hoy)

    assert "rendimiento_dia_semana" in res
    assert "rendimiento_por_hora" in res
    assert "ventas_por_hora" in res
    assert "variantes" in res["rendimiento_por_hora"]
    assert "todos" in res["rendimiento_por_hora"]["variantes"]
    assert "filas" in res["rendimiento_dia_semana"]
    assert "destacados" in res["rendimiento_por_hora"]["variantes"]["todos"]
    assert "promedio_venta_diaria_calendario" in res
    assert res["dias_calendario_efectivos"] <= (hoy - inicio).days + 1


def test_rango_vacio(db_session: Session):
    res = resumen_ventas_rango(db_session, date(2010, 1, 1), date(2010, 1, 7))
    assert res["numero_tickets"] == 0
    assert res["venta_total"] == 0.0
    assert res["desglose_dias"] == []


def test_consumo_insumos_agrupado(client, auth_headers):
    hoy = today_mx()
    res = client.get(f"/reportes/consumo-insumos?fecha={hoy}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    ids = [x["id_insumo"] for x in data["consumo"]]
    assert len(ids) == len(set(ids))


def test_presupuesto_consultas_no_lineal(db_session: Session):
    hoy = today_mx()
    inicio = hoy - timedelta(days=30)
    ventas = _ventas_rango(db_session, inicio, hoy)

    reset_sql_count()
    rendimiento_dia_semana(db_session, ventas, inicio, hoy)
    q_pequeno = get_sql_count()

    reset_sql_count()
    rendimiento_por_hora(db_session, ventas, inicio, hoy)
    q_hora = get_sql_count()

    assert q_pequeno <= 3, f"rendimiento_dia_semana ejecutó {q_pequeno} consultas"
    assert q_hora <= 3, f"rendimiento_por_hora ejecutó {q_hora} consultas (esperado O(1), no por hora/día)"


def test_mes_actual_campos(client, auth_headers):
    hoy = today_mx()
    res = client.get(
        f"/reportes/ventas-mes?anio={hoy.year}&mes={hoy.month}",
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert "rendimiento_por_hora" in body
    assert body["rendimiento_por_hora"]["hora_inicio"] is not None


def test_dashboard_responde(client, auth_headers):
    res = client.get("/reportes/resumen-dashboard", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "top_productos" in body
    assert "cuentas_hoy" in body


def test_endpoints_benchmark_headers(client, auth_headers):
    endpoints = [
        "/reportes/resumen-dashboard",
        "/catalogo/productos",
        "/catalogo/insumos",
        "/pedidos/activos",
    ]
    hoy = today_mx()
    endpoints.append(f"/reportes/consumo-insumos?fecha={hoy}")
    endpoints.append(f"/reportes/ventas-mes?anio={hoy.year}&mes={hoy.month}")
    endpoints.append(
        f"/reportes/ventas-rango?fecha_inicio={hoy.replace(day=1)}&fecha_fin={hoy}"
    )

    for path in endpoints:
        res = client.get(path, headers=auth_headers)
        assert res.status_code == 200, path
        assert "X-Process-Time-Ms" in res.headers or res.headers.get("X-Process-Time-Ms") is not None
