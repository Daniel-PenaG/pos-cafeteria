"""Idempotencia del cobro. La clave la envía el cliente; el servidor guarda la huella."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import ConflictoOperacionException
from app.models.models import (
    ClienteModel,
    CobroOperacionModel,
    FidelidadMovimientoModel,
    VentaModel,
    VentaPagoModel,
)
from app.schemas.ventas import VentaResponse
from app.utils.timezone_mx import now_utc_naive


def huella_cobro(
    *,
    id_pedido: int | None,
    id_cliente: int | None,
    forma_pago: str,
    puntos_canje: int,
    lineas: list[dict],
) -> str:
    payload = {
        "tipo": "cobro",
        "id_pedido": id_pedido,
        "id_cliente": id_cliente,
        "forma_pago": forma_pago,
        "puntos_canje": int(puntos_canje or 0),
        "lineas": lineas,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canon_decimal(valor) -> str:
    return str(Decimal(str(valor or 0)).quantize(Decimal("0.01")))


def lineas_huella(detalles) -> list[dict]:
    filas = []
    for d in detalles:
        filas.append(
            {
                "id_detalle": int(d.id_detalle_pedido),
                "id_producto": int(d.id_producto),
                "cantidad": _canon_decimal(d.cantidad),
                "precio_unitario": _canon_decimal(d.precio_unitario),
                "id_promocion": d.id_promocion,
            }
        )
    return sorted(filas, key=lambda x: x["id_detalle"])


def reclamar_cobro(
    db: Session,
    operation_id: str,
    payload_hash: str,
    id_usuario: int,
    id_pedido: int | None,
) -> CobroOperacionModel:
    existente = (
        db.query(CobroOperacionModel)
        .filter(CobroOperacionModel.operation_id == operation_id)
        .first()
    )
    if existente:
        _exigir_misma_huella(existente, payload_hash)
        return existente
    op = CobroOperacionModel(
        operation_id=operation_id,
        payload_hash=payload_hash,
        id_pedido=id_pedido,
        id_usuario=id_usuario,
        fecha=now_utc_naive(),
    )
    db.add(op)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existente = (
            db.query(CobroOperacionModel)
            .filter(CobroOperacionModel.operation_id == operation_id)
            .first()
        )
        if not existente:
            raise
        _exigir_misma_huella(existente, payload_hash)
        return existente
    return op


def _exigir_misma_huella(op: CobroOperacionModel, payload_hash: str) -> None:
    if op.payload_hash != payload_hash:
        raise ConflictoOperacionException(
            "Esta clave de cobro ya se usó con otro cliente, puntos, método o pedido"
        )


def completar_cobro(db: Session, operation_id: str | None, id_venta: int, saldo_anterior, saldo_final) -> None:
    if not operation_id:
        return
    op = (
        db.query(CobroOperacionModel)
        .filter(CobroOperacionModel.operation_id == operation_id)
        .first()
    )
    if not op:
        return
    op.id_venta = id_venta
    op.saldo_anterior = saldo_anterior
    op.saldo_final = saldo_final


def respuesta_cobro_guardado(db: Session, operation_id: str) -> VentaResponse | None:
    op = (
        db.query(CobroOperacionModel)
        .filter(CobroOperacionModel.operation_id == operation_id)
        .first()
    )
    if not op or not op.id_venta:
        return None
    venta = db.get(VentaModel, op.id_venta)
    if not venta:
        return None
    pagos = db.query(VentaPagoModel).filter(VentaPagoModel.id_venta == venta.id_venta).all()
    puntos = next((p for p in pagos if str(p.metodo).upper() == "PUNTOS"), None)
    monetario = next((p for p in pagos if str(p.metodo).upper() != "PUNTOS"), None)
    cliente = db.get(ClienteModel, venta.id_cliente) if venta.id_cliente else None
    return VentaResponse(
        id_venta=venta.id_venta,
        fecha_hora=venta.fecha_hora,
        id_usuario=venta.id_usuario,
        numero_mesa=int(venta.numero_mesa),
        total=float(venta.total),
        forma_pago=venta.forma_pago,
        id_cliente=venta.id_cliente,
        puntos_generados=int(venta.puntos_generados or 0),
        puntos_canje=int(puntos.cantidad_puntos or 0) if puntos else 0,
        equivalencia_puntos=float(puntos.equivalencia_puntos or 0) if puntos else 0,
        importe_monetario=float(monetario.importe_monetario or 0) if monetario else 0,
        forma_pago_monetaria=monetario.metodo if monetario else None,
        saldo_anterior=op.saldo_anterior,
        saldo_final=op.saldo_final,
        cliente_nombre=cliente.nombre if cliente else None,
        cliente_puntos_saldo=op.saldo_final if op.saldo_final is not None else (
            int(cliente.puntos_saldo) if cliente else None
        ),
        para_llevar=bool(venta.para_llevar),
        advertencias_stock=[],
    )


def movimientos_venta(db: Session, id_venta: int) -> list[FidelidadMovimientoModel]:
    return (
        db.query(FidelidadMovimientoModel)
        .filter(FidelidadMovimientoModel.id_venta == id_venta)
        .order_by(FidelidadMovimientoModel.id_movimiento)
        .all()
    )
