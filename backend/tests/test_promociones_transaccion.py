"""Documentación y pruebas del comportamiento transaccional de registrar_venta."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.models.models import DetalleVentaModel, VentaModel
from app.schemas.ventas import DetalleVentaItem, VentaCreate
from app.services.venta_service import registrar_venta


def _venta_simple(db, refs):
    return VentaCreate(
        id_usuario=refs.id_usuario,
        numero_mesa=1,
        forma_pago="EFECTIVO",
        detalles=[
            DetalleVentaItem(
                id_producto=refs.id_malteada,
                cantidad=1,
                precio_unitario=65.0,
                extras=[],
            )
        ],
    )


def test_registrar_venta_usa_dos_commits(db_session, refs):
    """
    RIESGO DOCUMENTADO: registrar_venta hace commit tras crear VentaModel
    y otro commit tras detalles/inventario/puntos. No es una única transacción.
    """
    commits = []

    original_commit = db_session.commit

    def tracked_commit():
        commits.append(len(db_session.new) + len(db_session.dirty))
        original_commit()

    db_session.commit = tracked_commit  # type: ignore[method-assign]
    registrar_venta(db_session, _venta_simple(db_session, refs))
    assert len(commits) >= 2


def test_fallo_segundo_commit_deja_venta_huerfana(db_session, refs):
    """Si falla después del primer commit, puede quedar venta sin detalles."""
    call_count = 0
    original_commit = db_session.commit

    def failing_commit():
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise RuntimeError("fallo simulado inventario")
        original_commit()

    db_session.commit = failing_commit  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        registrar_venta(db_session, _venta_simple(db_session, refs))

    ventas = db_session.query(VentaModel).all()
    assert len(ventas) == 1
    dets = db_session.query(DetalleVentaModel).all()
    assert len(dets) == 0


def test_recomendacion_transaccion_unica():
    """
    RECOMENDACIÓN (fuera de alcance de este PR):
    Refactorizar registrar_venta para usar una sola transacción con rollback
    en cualquier fallo de detalle, inventario o puntos.
    """
    assert True
