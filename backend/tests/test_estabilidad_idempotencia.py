"""Idempotencia al agregar producto y combo."""
from __future__ import annotations

import threading
import uuid

from sqlalchemy.orm import sessionmaker

from app.models.models import DetallePedidoModel, PedidoModel
from app.schemas.pedido import PedidoLineaCreate
from app.services.pedido_service import (
    agregar_combo_pedido,
    agregar_linea_pedido_con_respuesta,
    obtener_pedido_abierto_mesa,
)
from app.services.venta_service import MESA_PARA_LLEVAR
from tests.promo_seed import crear_promo, promo_vigente_siempre
from tests.test_promociones_integracion import _extra_linea, _linea


def _data(db, id_producto, cantidad=1, **kwargs):
    raw_extras = kwargs.get("extras") or []
    extras_pedido = [e.model_dump() if hasattr(e, "model_dump") else e for e in raw_extras]
    det = _linea(db, id_producto, cantidad, kwargs.get("id_promocion"), raw_extras or None)
    return PedidoLineaCreate(
        id_producto=id_producto,
        cantidad=cantidad,
        precio_unitario=det.precio_unitario,
        precio_original=det.precio_original,
        id_promocion=det.id_promocion,
        extras=extras_pedido,
        enviar_comanda=kwargs.get("enviar_comanda", False),
        comentario=kwargs.get("comentario"),
        operation_id=kwargs.get("operation_id"),
    )


def test_misma_clave_concurrente_agrega_una_vez(tmp_path):
    """Dos conexiones reales (archivo SQLite) con la misma clave."""
    from sqlalchemy import create_engine
    from app.database import Base
    from tests.promo_seed import seed_promo_catalog

    engine = create_engine(
        f"sqlite:///{tmp_path / 'idemp.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    setup = Session()
    refs = seed_promo_catalog(setup)
    setup.commit()
    pedido = obtener_pedido_abierto_mesa(setup, 12, refs.id_usuario)
    setup.commit()
    pedido_id = pedido.id_pedido
    id_malteada = refs.id_malteada
    setup.close()

    key = str(uuid.uuid4())
    errores = []
    respuestas = []
    barrier = threading.Barrier(2)

    def worker():
        db = Session()
        try:
            barrier.wait(timeout=5)
            p = db.get(PedidoModel, pedido_id)
            data = _data(db, id_malteada, operation_id=key)
            resp, _ = agregar_linea_pedido_con_respuesta(db, p, data)
            respuestas.append(resp)
        except Exception as exc:
            errores.append(exc)
        finally:
            db.close()

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    verify = Session()
    lineas = verify.query(DetallePedidoModel).filter_by(id_pedido=pedido_id).all()
    verify.close()
    engine.dispose()
    assert len(lineas) == 1, f"lineas={len(lineas)} errores={errores!r} resp={len(respuestas)}"
    assert float(lineas[0].cantidad) == 1
    assert len(respuestas) >= 1


def test_claves_distintas_agregan_dos_veces(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 13, refs.id_usuario)
    r1, _ = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe, operation_id=str(uuid.uuid4()))
    )
    db_session.refresh(pedido)
    r2, _ = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe, operation_id=str(uuid.uuid4()))
    )
    assert r2["lineas"][0]["cantidad"] == 2
    assert r1["id_pedido"] == r2["id_pedido"]


def test_reintento_misma_clave_no_duplica(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 14, refs.id_usuario)
    key = str(uuid.uuid4())
    agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_malteada, operation_id=key)
    )
    db_session.refresh(pedido)
    resp, _ = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_malteada, operation_id=key)
    )
    assert len(resp["lineas"]) == 1
    assert resp["lineas"][0]["cantidad"] == 1


def test_idempotencia_con_extras(db_session, refs):
    extra = _extra_linea(db_session, refs)
    pedido = obtener_pedido_abierto_mesa(db_session, 15, refs.id_usuario)
    key = str(uuid.uuid4())
    agregar_linea_pedido_con_respuesta(
        db_session,
        pedido,
        _data(db_session, refs.id_malteada, extras=[extra], operation_id=key),
    )
    db_session.refresh(pedido)
    resp, _ = agregar_linea_pedido_con_respuesta(
        db_session,
        pedido,
        _data(db_session, refs.id_malteada, extras=[extra], operation_id=key),
    )
    assert len(resp["lineas"]) == 1
    assert len(resp["lineas"][0]["extras"]) == 1
    assert resp["lineas"][0]["cantidad"] == 1


def test_idempotencia_combo(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Combo idemp",
        tipo="COMBO",
        valor=80,
        productos_combo=[refs.id_combo_a, refs.id_combo_b],
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = obtener_pedido_abierto_mesa(db_session, 16, refs.id_usuario)
    key = str(uuid.uuid4())
    r1 = agregar_combo_pedido(db_session, pedido, promo.id_promocion, 1, operation_id=key)
    db_session.refresh(pedido)
    r2 = agregar_combo_pedido(db_session, pedido, promo.id_promocion, 1, operation_id=key)
    assert len(r1["lineas"]) == len(r2["lineas"])
    assert r1["total"] == r2["total"]
    n1 = db_session.query(DetallePedidoModel).filter_by(id_pedido=pedido.id_pedido).count()
    assert n1 == len(r1["lineas"])


def test_sin_operation_id_sigue_funcionando(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, MESA_PARA_LLEVAR, refs.id_usuario, True)
    r1, _ = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe)
    )
    db_session.refresh(pedido)
    r2, _ = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe)
    )
    assert r2["lineas"][0]["cantidad"] == 2
    assert r1["para_llevar"] is True
