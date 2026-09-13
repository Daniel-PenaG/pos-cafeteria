"""UTC de Comandera y cálculo de tiempo transcurrido."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.routers.comandera import listar_pendientes, marcar_listo
from app.schemas.pedido import ComandaMarcarListo
from app.schemas.pedido import PedidoLineaCreate
from app.services.pedido_service import (
    agregar_linea_pedido,
    confirmar_comanda_pedido,
    obtener_pedido_abierto_mesa,
)
from app.utils.timezone_mx import isoformat_utc, now_utc_naive, segundos_desde


def _pedido_con_comanda(db, refs, hace_segundos=65):
    pedido = obtener_pedido_abierto_mesa(db, 3, refs.id_usuario, para_llevar=False)
    agregar_linea_pedido(
        db,
        pedido,
        PedidoLineaCreate(
            id_producto=refs.id_malteada,
            cantidad=1,
            precio_unitario=65,
            enviar_comanda=False,
        ),
    )
    confirmar_comanda_pedido(db, pedido)
    db.refresh(pedido)
    detalle = pedido.detalles[0]
    detalle.fecha_envio_comanda = now_utc_naive() - timedelta(seconds=hace_segundos)
    db.commit()
    db.refresh(detalle)
    return pedido, detalle


def test_isoformat_utc_termina_en_z():
    naive = datetime(2026, 9, 13, 3, 21, 5)
    s = isoformat_utc(naive)
    assert s.endswith("Z")
    assert "+" not in s
    aware = datetime(2026, 9, 13, 3, 21, 5, tzinfo=timezone.utc)
    assert isoformat_utc(aware).endswith("Z")


def test_segundos_desde_nunca_negativo():
    futuro = now_utc_naive() + timedelta(hours=2)
    assert segundos_desde(futuro) == 0
    assert segundos_desde(None) is None


def test_segundos_desde_65s():
    inicio = now_utc_naive() - timedelta(seconds=65)
    secs = segundos_desde(inicio)
    assert 64 <= secs <= 67


def test_comandera_fecha_con_z(db_session, refs):
    _pedido_con_comanda(db_session, refs, 65)
    pendientes = listar_pendientes(db_session)
    assert pendientes
    fecha = pendientes[0]["fecha_envio_comanda"]
    assert isinstance(fecha, str)
    assert fecha.endswith("Z")
    assert 64 <= pendientes[0]["segundos_en_preparacion"] <= 67


def test_comandera_reciente_cerca_de_cero(db_session, refs):
    _pedido_con_comanda(db_session, refs, 1)
    pendientes = listar_pendientes(db_session)
    assert pendientes[0]["segundos_en_preparacion"] <= 3


def test_marcar_listo_no_altera_fecha_envio(db_session, refs):
    pedido, detalle = _pedido_con_comanda(db_session, refs, 90)
    fecha_antes = detalle.fecha_envio_comanda
    marcar_listo(detalle.id_detalle_pedido, ComandaMarcarListo(cantidad=1), db_session)
    db_session.refresh(detalle)
    assert detalle.fecha_envio_comanda == fecha_antes
    assert detalle.fecha_listo_comanda is not None


def test_segundos_independiente_de_datetime_now_local(monkeypatch):
    """El cálculo usa UTC naive, no datetime.now() local."""
    inicio = datetime(2026, 9, 13, 0, 0, 0)
    fixed_now = datetime(2026, 9, 13, 0, 1, 5)

    monkeypatch.setattr("app.utils.timezone_mx.now_utc_naive", lambda: fixed_now)
    assert segundos_desde(inicio) == 65
