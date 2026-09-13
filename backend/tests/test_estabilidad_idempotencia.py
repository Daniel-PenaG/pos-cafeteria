"""Idempotencia al agregar producto y combo."""
from __future__ import annotations

import json
import threading
import uuid

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.exceptions import ConflictoOperacionException
from app.models.models import DetallePedidoModel, PedidoModel, PedidoOperacionModel
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


def _sqlite_file_engine(path):
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


def _pedidos_vacios(db):
    vacios = []
    for pedido in db.query(PedidoModel).all():
        n = db.query(DetallePedidoModel).filter_by(id_pedido=pedido.id_pedido).count()
        if n == 0:
            vacios.append(pedido.id_pedido)
    return vacios


def test_misma_clave_concurrente_agrega_una_vez(tmp_path):
    """Dos conexiones reales (archivo SQLite) con la misma clave."""
    from app.database import Base
    from tests.promo_seed import seed_promo_catalog

    engine = _sqlite_file_engine(tmp_path / "idemp.db")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_pedidos_abierto_mesa
                ON pedidos (numero_mesa, para_llevar)
                WHERE estado = 'ABIERTO'
                """
            )
        )
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
    ops = verify.query(PedidoOperacionModel).filter_by(operation_id=key).all()
    vacios = _pedidos_vacios(verify)
    ids_pedido_resp = {r["id_pedido"] for r in respuestas}
    verify.close()
    engine.dispose()

    assert errores == [], errores
    assert len(respuestas) == 2
    assert ids_pedido_resp == {pedido_id}
    assert len(lineas) == 1
    assert float(lineas[0].cantidad) == 1
    assert vacios == []
    assert len(ops) == 1


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


def test_reintento_misma_clave_mismo_payload_replay(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 14, refs.id_usuario)
    key = str(uuid.uuid4())
    r1, det1 = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_malteada, operation_id=key)
    )
    db_session.refresh(pedido)
    r2, det2 = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_malteada, operation_id=key)
    )
    assert len(r2["lineas"]) == 1
    assert r2["lineas"][0]["cantidad"] == 1
    assert det2.id_detalle_pedido == det1.id_detalle_pedido
    assert r1["id_pedido"] == r2["id_pedido"]


def test_misma_clave_payload_diferente_409(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 17, refs.id_usuario)
    key = str(uuid.uuid4())
    agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe, operation_id=key)
    )
    db_session.refresh(pedido)
    with pytest.raises(ConflictoOperacionException) as exc:
        agregar_linea_pedido_con_respuesta(
            db_session, pedido, _data(db_session, refs.id_malteada, operation_id=key)
        )
    assert exc.value.status_code == 409
    n = db_session.query(DetallePedidoModel).filter_by(id_pedido=pedido.id_pedido).count()
    assert n == 1


def test_timeout_producto_a_luego_producto_b(db_session, refs):
    """A se procesó (timeout en cliente); B usa clave nueva y sí se agrega."""
    pedido = obtener_pedido_abierto_mesa(db_session, 18, refs.id_usuario)
    key_a = str(uuid.uuid4())
    key_b = str(uuid.uuid4())
    _, det_a = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe, operation_id=key_a)
    )
    db_session.refresh(pedido)
    resp, det_b = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_malteada, operation_id=key_b)
    )
    assert key_a != key_b
    assert det_a.id_producto == refs.id_cafe
    assert det_b.id_producto == refs.id_malteada
    assert len(resp["lineas"]) == 2
    assert {d["id_producto"] for d in resp["lineas"]} == {refs.id_cafe, refs.id_malteada}


def test_timeout_producto_luego_combo(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Combo tras timeout",
        tipo="COMBO",
        valor=80,
        productos_combo=[refs.id_combo_a, refs.id_combo_b],
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = obtener_pedido_abierto_mesa(db_session, 19, refs.id_usuario)
    key_linea = str(uuid.uuid4())
    key_combo = str(uuid.uuid4())
    agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe, operation_id=key_linea)
    )
    db_session.refresh(pedido)
    resp = agregar_combo_pedido(
        db_session, pedido, promo.id_promocion, 1, operation_id=key_combo
    )
    assert key_linea != key_combo
    productos = {d["id_producto"] for d in resp["lineas"]}
    assert refs.id_cafe in productos
    assert refs.id_combo_a in productos
    assert refs.id_combo_b in productos


def test_misma_clave_producto_luego_combo_409(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Combo conflicto clave",
        tipo="COMBO",
        valor=80,
        productos_combo=[refs.id_combo_a, refs.id_combo_b],
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = obtener_pedido_abierto_mesa(db_session, 20, refs.id_usuario)
    key = str(uuid.uuid4())
    agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe, operation_id=key)
    )
    db_session.refresh(pedido)
    with pytest.raises(ConflictoOperacionException) as exc:
        agregar_combo_pedido(db_session, pedido, promo.id_promocion, 1, operation_id=key)
    assert exc.value.status_code == 409


def test_dos_acciones_intencionales_dos_claves(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 21, refs.id_usuario)
    k1, k2 = str(uuid.uuid4()), str(uuid.uuid4())
    agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe, operation_id=k1)
    )
    db_session.refresh(pedido)
    resp, _ = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe, operation_id=k2)
    )
    assert k1 != k2
    assert resp["lineas"][0]["cantidad"] == 2
    ops = db_session.query(PedidoOperacionModel).filter_by(id_pedido=pedido.id_pedido).count()
    assert ops == 2


def test_replay_detalle_no_es_primera_linea(db_session, refs):
    pedido = obtener_pedido_abierto_mesa(db_session, 22, refs.id_usuario)
    key_a = str(uuid.uuid4())
    _, det_a = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe, operation_id=key_a)
    )
    db_session.refresh(pedido)
    agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_malteada, operation_id=str(uuid.uuid4()))
    )
    db_session.refresh(pedido)
    resp, det_replay = agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe, operation_id=key_a)
    )
    assert det_replay.id_detalle_pedido == det_a.id_detalle_pedido
    assert det_replay.id_producto == refs.id_cafe
    assert len(resp["lineas"]) == 2
    primera = resp["lineas"][0]
    assert primera["id_detalle_pedido"] != det_a.id_detalle_pedido or primera["id_producto"] == refs.id_cafe


def test_replay_combo_identifica_operacion_completa(db_session, refs):
    promo = crear_promo(
        db_session,
        nombre="Combo replay ids",
        tipo="COMBO",
        valor=80,
        productos_combo=[refs.id_combo_a, refs.id_combo_b],
        **promo_vigente_siempre(),
    )
    db_session.commit()
    pedido = obtener_pedido_abierto_mesa(db_session, 23, refs.id_usuario)
    key = str(uuid.uuid4())
    r1 = agregar_combo_pedido(db_session, pedido, promo.id_promocion, 1, operation_id=key)
    ids_combo = sorted(d["id_detalle_pedido"] for d in r1["lineas"])
    db_session.refresh(pedido)
    agregar_linea_pedido_con_respuesta(
        db_session, pedido, _data(db_session, refs.id_cafe, operation_id=str(uuid.uuid4()))
    )
    db_session.refresh(pedido)
    r2 = agregar_combo_pedido(db_session, pedido, promo.id_promocion, 1, operation_id=key)
    op = (
        db_session.query(PedidoOperacionModel)
        .filter_by(operation_id=key)
        .one()
    )
    ids_op = json.loads(op.detalle_ids_json)
    assert sorted(ids_op) == ids_combo
    assert op.tipo == "combo"
    assert len(r2["lineas"]) == len(r1["lineas"]) + 1
    assert {d["id_detalle_pedido"] for d in r1["lineas"]}.issubset(
        {d["id_detalle_pedido"] for d in r2["lineas"]}
    )


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


def test_dos_sesiones_primer_producto_un_pedido(tmp_path):
    """Dos dispositivos agregan el primer producto a la misma mesa."""
    from app.database import Base
    from tests.promo_seed import seed_promo_catalog

    engine = _sqlite_file_engine(tmp_path / "mesa_unica.db")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_pedidos_abierto_mesa
                ON pedidos (numero_mesa, para_llevar)
                WHERE estado = 'ABIERTO'
                """
            )
        )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    setup = Session()
    refs = seed_promo_catalog(setup)
    setup.commit()
    id_usuario = refs.id_usuario
    id_cafe = refs.id_cafe
    id_malteada = refs.id_malteada
    setup.close()

    mesa = 31
    errores = []
    respuestas = []
    barrier = threading.Barrier(2)

    def worker(id_producto, key):
        db = Session()
        try:
            barrier.wait(timeout=5)
            pedido = obtener_pedido_abierto_mesa(db, mesa, id_usuario)
            data = _data(db, id_producto, operation_id=key)
            resp, _ = agregar_linea_pedido_con_respuesta(db, pedido, data)
            respuestas.append(resp)
        except Exception as exc:
            errores.append(exc)
        finally:
            db.close()

    t1 = threading.Thread(target=worker, args=(id_cafe, str(uuid.uuid4())))
    t2 = threading.Thread(target=worker, args=(id_malteada, str(uuid.uuid4())))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    verify = Session()
    abiertos = (
        verify.query(PedidoModel)
        .filter_by(numero_mesa=mesa, estado="ABIERTO", para_llevar=False)
        .all()
    )
    lineas = []
    if abiertos:
        lineas = verify.query(DetallePedidoModel).filter_by(id_pedido=abiertos[0].id_pedido).all()
    ops = verify.query(PedidoOperacionModel).all()
    vacios = _pedidos_vacios(verify)
    verify.close()
    engine.dispose()

    assert errores == [], errores
    assert len(respuestas) == 2
    assert {r["id_pedido"] for r in respuestas} == {abiertos[0].id_pedido}
    assert len(abiertos) == 1
    assert len(lineas) == 2
    assert {d.id_producto for d in lineas} == {id_cafe, id_malteada}
    assert vacios == []
    assert len(ops) == 2
