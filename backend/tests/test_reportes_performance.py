"""Pruebas de regresión y presupuesto de consultas para reportes optimizados."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.services.reporte_ventas_service import (
    resumen_ventas_rango,
    rendimiento_dia_semana,
    rendimiento_por_hora,
)
from app.models.models import VentaModel
from app.utils.timezone_mx import today_mx, filtro_rango_mx, datetime_mx_desde_utc_naive
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


def test_mes_actual_sin_dias_futuros_en_divisor(db_session: Session):
    """El promedio calendario no debe usar días posteriores a hoy (MX)."""
    hoy = today_mx()
    inicio = hoy.replace(day=1)
    res = resumen_ventas_rango(db_session, inicio, hoy)
    dias_calendario = (hoy - inicio).days + 1
    assert res["dias_calendario_efectivos"] == dias_calendario
    if res["venta_total"] > 0:
        esperado = round(res["venta_total"] / dias_calendario, 2)
        assert res["promedio_venta_diaria_calendario"] == esperado


def test_promedio_calendario_vs_operacion(db_session: Session):
    hoy = today_mx()
    inicio = hoy - timedelta(days=20)
    res = resumen_ventas_rango(db_session, inicio, hoy)
    assert "promedio_venta_diaria" in res
    assert "promedio_venta_diaria_calendario" in res
    assert "promedio_venta_diaria_operacion" in res
    assert "promedio_tickets_diarios_calendario" in res
    assert "promedio_tickets_diarios_operacion" in res
    if res["dias_con_ventas"] > 0:
        assert res["promedio_venta_diaria_operacion"] == round(
            res["venta_total"] / res["dias_con_ventas"], 2
        )


def test_horario_operacion_configurable(monkeypatch, db_session: Session):
    monkeypatch.setenv("HORA_OPERACION_INICIO", "10")
    monkeypatch.setenv("HORA_OPERACION_FIN", "18")
    import importlib
    import app.utils.operacion_config as oc
    import app.services.reporte_ventas_service as rvs

    importlib.reload(oc)
    importlib.reload(rvs)

    hoy = today_mx()
    inicio = hoy - timedelta(days=7)
    ventas = _ventas_rango(db_session, inicio, hoy)
    res = rvs.rendimiento_por_hora(db_session, ventas, inicio, hoy)
    assert res["hora_inicio"] == 10
    assert res["hora_fin"] == 18
    assert len(res["variantes"]["todos"]["filas"]) == 9


def test_zona_horaria_mexico_en_agrupacion(db_session: Session):
    hoy = today_mx()
    inicio = hoy - timedelta(days=14)
    ventas = _ventas_rango(db_session, inicio, hoy)
    assert ventas, "Se requiere seed con ventas"
    for v in ventas[:5]:
        dow_api = datetime_mx_desde_utc_naive(v.fecha_hora).weekday()
        assert 0 <= dow_api <= 6
    res = rendimiento_dia_semana(db_session, ventas, inicio, hoy)
    assert len(res["filas"]) == 7
    assert all("dia_semana" in f and "dia" in f for f in res["filas"])


def test_consumo_insumo_en_varias_recetas(db_session: Session, client, auth_headers):
    """Leche aparece en Latte y Americano: una sola fila con suma total."""
    hoy = today_mx()
    res = client.get(f"/reportes/consumo-insumos?fecha={hoy}", headers=auth_headers)
    assert res.status_code == 200
    consumo = res.json()["consumo"]
    leche = [x for x in consumo if x["nombre"] == "Leche"]
    assert len(leche) == 1
    assert leche[0]["cantidad_consumida"] > 0


def test_compatibilidad_json_campos_legacy(client, auth_headers):
    """Campos existentes del frontend siguen presentes."""
    hoy = today_mx()
    inicio = hoy.replace(day=1)
    rango = client.get(
        f"/reportes/ventas-rango?fecha_inicio={inicio}&fecha_fin={hoy}",
        headers=auth_headers,
    ).json()
    for key in (
        "fecha_inicio",
        "fecha_fin",
        "venta_total",
        "numero_tickets",
        "ticket_promedio",
        "unidades_vendidas",
        "productos_por_ticket",
        "promociones_utilizadas",
        "venta_por_promociones",
        "desglose_dias",
        "productos",
        "rendimiento_dia_semana",
        "rendimiento_por_hora",
        "ventas_por_hora",
        "promedio_venta_diaria",
        "promedio_tickets_diarios",
        "dias_con_ventas",
    ):
        assert key in rango, f"Falta campo legacy: {key}"
    rd = rango["rendimiento_dia_semana"]
    assert "filas" in rd and "destacados" in rd
    rp = rango["rendimiento_por_hora"]
    assert "variantes" in rp and "hora_inicio" in rp and "hora_fin" in rp
