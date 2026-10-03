"""Libro de Tesorería. El saldo es entradas menos salidas. El frontend no lo escribe.

Orden de bloqueo al disminuir una cuenta: ids de cuenta ascendentes, después de
los bloqueos ya tomados por el cobro (sesión, pedido, detalle, cliente).
Un traspaso no toma sesión ni pedido; solo cuentas, en ese mismo orden.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.constants import auditoria as A
from app.exceptions import (
    AccesoNegadoException,
    ConflictoOperacionException,
    DatosInvalidosException,
    RecursoNoEncontradoException,
)
from app.models.models import (
    ActivacionTesoreriaModel,
    ConciliacionTesoreriaModel,
    CuentaTesoreriaModel,
    MovimientoTesoreriaModel,
    OperacionTesoreriaModel,
    UsuarioModel,
    VentaModel,
    VentaPagoModel,
)
from app.services.auditoria_service import registrar_auditoria
from app.utils.timezone_mx import now_utc_naive

CODIGO_CAFE = "EFECTIVO_CAFETERIA"
CODIGO_CASA = "EFECTIVO_CASA"
CODIGO_BANCO = "BANCO"
CUENTAS_SISTEMA = (CODIGO_CAFE, CODIGO_CASA, CODIGO_BANCO)

TIPO_SALDO_INICIAL = "SALDO_INICIAL"
TIPO_VENTA = "VENTA"
TIPO_DEVOLUCION = "DEVOLUCION"
TIPO_COMPRA = "COMPRA"
TIPO_GASTO_OPERATIVO = "GASTO_OPERATIVO"
TIPO_GASTO_CAJA = "GASTO_CAJA"
TIPO_TRASPASO = "TRASPASO"
TIPO_APORTACION = "APORTACION_PROPIETARIO"
TIPO_RETIRO = "RETIRO_PROPIETARIO"
TIPO_COMISION = "COMISION_BANCARIA"
TIPO_SOBRANTE = "AJUSTE_SOBRANTE"
TIPO_FALTANTE = "AJUSTE_FALTANTE"
TIPO_REVERSA = "REVERSA"

ENTRADA = "ENTRADA"
SALIDA = "SALIDA"
ESTADO_CONFIRMADA = "CONFIRMADA"
ESTADO_REVERTIDA = "REVERTIDA"

GASTOS_OPERATIVOS = (TIPO_GASTO_OPERATIVO, TIPO_COMPRA, TIPO_GASTO_CAJA)
MAPA_PAGO = {
    "EFECTIVO": CODIGO_CAFE,
    "TRANSFERENCIA": CODIGO_BANCO,
    "TARJETA": CODIGO_BANCO,
    "TERMINAL": CODIGO_BANCO,
}


def dinero(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


def _hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _auditar(db: Session, usuario: UsuarioModel | None, accion: str, entidad_id: int | None, detalles: dict) -> None:
    try:
        registrar_auditoria(
            db,
            usuario=usuario,
            accion=accion,
            entidad="tesoreria",
            entidad_id=entidad_id,
            detalles=detalles,
            origen="TESORERIA",
        )
    except Exception:
        return


def asegurar_cuentas(db: Session) -> None:
    ahora = now_utc_naive()
    semillas = (
        (CODIGO_CAFE, "Efectivo en cafetería", "EFECTIVO"),
        (CODIGO_CASA, "Efectivo del negocio en casa", "EFECTIVO"),
        (CODIGO_BANCO, "Cuenta bancaria", "BANCO"),
    )
    for codigo, nombre, tipo in semillas:
        if db.query(CuentaTesoreriaModel).filter_by(codigo=codigo).first():
            continue
        db.add(
            CuentaTesoreriaModel(
                codigo=codigo,
                nombre=nombre,
                tipo=tipo,
                moneda="MXN",
                activa=True,
                es_sistema=True,
                fecha_creacion=ahora,
            )
        )
    db.flush()


def activacion_actual(db: Session) -> ActivacionTesoreriaModel | None:
    return (
        db.query(ActivacionTesoreriaModel)
        .filter(ActivacionTesoreriaModel.estado == "ACTIVA")
        .order_by(ActivacionTesoreriaModel.id_activacion.asc())
        .first()
    )


def tesoreria_activa(db: Session) -> bool:
    return activacion_actual(db) is not None


def cuenta_por_codigo(db: Session, codigo: str) -> CuentaTesoreriaModel:
    asegurar_cuentas(db)
    cuenta = db.query(CuentaTesoreriaModel).filter_by(codigo=codigo).first()
    if not cuenta or not cuenta.activa:
        raise RecursoNoEncontradoException("Cuenta de tesorería no encontrada")
    return cuenta


def _bloquear_cuentas(db: Session, cuentas: list[CuentaTesoreriaModel]) -> dict[int, CuentaTesoreriaModel]:
    """Bloquea por id ascendente. No invierte el orden del cobro: se llama al final."""
    ordenadas = sorted(cuentas, key=lambda c: int(c.id_cuenta))
    bloqueadas: dict[int, CuentaTesoreriaModel] = {}
    for cuenta in ordenadas:
        q = db.query(CuentaTesoreriaModel).filter(CuentaTesoreriaModel.id_cuenta == cuenta.id_cuenta)
        if db.bind is not None and db.bind.dialect.name != "sqlite":
            q = q.with_for_update()
        fila = q.one()
        bloqueadas[int(fila.id_cuenta)] = fila
    return bloqueadas


def saldo_cuenta(db: Session, id_cuenta: int) -> Decimal:
    entradas = (
        db.query(func.coalesce(func.sum(MovimientoTesoreriaModel.importe), 0))
        .filter(
            MovimientoTesoreriaModel.id_cuenta == id_cuenta,
            MovimientoTesoreriaModel.direccion == ENTRADA,
        )
        .scalar()
    )
    salidas = (
        db.query(func.coalesce(func.sum(MovimientoTesoreriaModel.importe), 0))
        .filter(
            MovimientoTesoreriaModel.id_cuenta == id_cuenta,
            MovimientoTesoreriaModel.direccion == SALIDA,
        )
        .scalar()
    )
    return (dinero(entradas) - dinero(salidas)).quantize(Decimal("0.01"))


def _bloquear_clave(db: Session, clave: str) -> None:
    """Serializa la misma operación en PostgreSQL. SQLite no tiene este candado."""
    bind = db.get_bind()
    if bind is None or bind.dialect.name == "sqlite":
        return
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:clave))"), {"clave": clave})


def _buscar_operacion(db: Session, operation_id: str) -> OperacionTesoreriaModel | None:
    return db.query(OperacionTesoreriaModel).filter_by(operation_id=operation_id).first()


def _exigir_idempotencia(db: Session, operation_id: str, payload_hash: str, usuario: UsuarioModel | None):
    previa = _buscar_operacion(db, operation_id)
    if not previa:
        return None
    if previa.payload_hash != payload_hash:
        _auditar(
            db,
            usuario,
            A.TESORERIA_CONFLICTO,
            previa.id_operacion,
            {"operation_id": operation_id},
        )
        raise ConflictoOperacionException(
            "La clave de operación ya se usó con otros datos"
        )
    return previa


def _insertar(
    db: Session,
    *,
    usuario: UsuarioModel,
    operation_id: str,
    payload: dict,
    tipo: str,
    concepto: str,
    observacion: str | None,
    fecha_operacion: datetime | None,
    origen_tipo: str | None,
    origen_id: int | None,
    referencia: str | None,
    lineas: list[tuple[CuentaTesoreriaModel, str, Decimal]],
) -> OperacionTesoreriaModel:
    _bloquear_clave(db, operation_id)
    payload_hash = _hash(payload)
    previa = _exigir_idempotencia(db, operation_id, payload_hash, usuario)
    if previa:
        return previa
    if origen_tipo and origen_id is not None and tipo != TIPO_REVERSA:
        ya = (
            db.query(OperacionTesoreriaModel)
            .filter(
                OperacionTesoreriaModel.origen_tipo == origen_tipo,
                OperacionTesoreriaModel.origen_id == origen_id,
                OperacionTesoreriaModel.tipo != TIPO_REVERSA,
                OperacionTesoreriaModel.estado == ESTADO_CONFIRMADA,
            )
            .first()
        )
        if ya:
            if ya.payload_hash == payload_hash or ya.operation_id == operation_id:
                return ya
            raise ConflictoOperacionException("Ese origen ya tiene un movimiento de tesorería")
    cuentas = _bloquear_cuentas(db, [linea[0] for linea in lineas])
    salidas: dict[int, Decimal] = {}
    for cuenta, direccion, importe in lineas:
        monto = dinero(importe)
        if monto <= 0:
            raise DatosInvalidosException("El importe debe ser mayor a cero")
        if direccion == SALIDA:
            salidas[int(cuenta.id_cuenta)] = salidas.get(int(cuenta.id_cuenta), dinero(0)) + monto
    for id_cuenta, monto in salidas.items():
        disponible = saldo_cuenta(db, id_cuenta)
        if disponible < monto:
            _auditar(
                db,
                usuario,
                A.TESORERIA_SALDO_INSUFICIENTE,
                id_cuenta,
                {"importe": str(monto), "saldo": str(disponible)},
            )
            raise DatosInvalidosException("Saldo insuficiente en la cuenta de tesorería")
    ahora = now_utc_naive()
    operacion = OperacionTesoreriaModel(
        operation_id=operation_id,
        payload_hash=payload_hash,
        tipo=tipo,
        estado=ESTADO_CONFIRMADA,
        fecha_operacion=fecha_operacion or ahora,
        id_usuario=usuario.id_usuario,
        origen_tipo=origen_tipo,
        origen_id=origen_id,
        referencia=referencia,
        concepto=concepto.strip(),
        observacion=(observacion or "").strip() or None,
        fecha_creacion=ahora,
    )
    db.add(operacion)
    db.flush()
    for cuenta, direccion, importe in lineas:
        db.add(
            MovimientoTesoreriaModel(
                id_operacion=operacion.id_operacion,
                id_cuenta=cuentas[int(cuenta.id_cuenta)].id_cuenta,
                direccion=direccion,
                importe=dinero(importe),
                fecha_creacion=ahora,
            )
        )
    db.flush()
    return operacion


def registrar_venta_tesoreria(db: Session, venta: VentaModel, usuario_id: int) -> None:
    """Entrada monetaria según venta_pagos. No corre si Tesorería está apagada o la venta es anterior al corte."""
    activacion = activacion_actual(db)
    if not activacion:
        return
    if venta.fecha_hora and venta.fecha_hora < activacion.fecha_corte:
        return
    db.flush()
    pagos = (
        db.query(VentaPagoModel)
        .filter(VentaPagoModel.id_venta == venta.id_venta)
        .all()
    )
    usuario = db.query(UsuarioModel).filter_by(id_usuario=usuario_id).one()
    for pago in pagos:
        metodo = (pago.metodo or "").strip().upper()
        if metodo == "PUNTOS":
            continue
        importe = dinero(pago.importe_monetario)
        if importe <= 0:
            continue
        codigo = MAPA_PAGO.get(metodo)
        if not codigo:
            raise DatosInvalidosException("Forma de pago sin cuenta de tesorería")
        cuenta = cuenta_por_codigo(db, codigo)
        _insertar(
            db,
            usuario=usuario,
            operation_id=f"tesoreria-venta-pago-{pago.id_pago}",
            payload={
                "tipo": TIPO_VENTA,
                "id_pago": int(pago.id_pago),
                "metodo": metodo,
                "importe": str(importe),
            },
            tipo=TIPO_VENTA,
            concepto=f"Venta {venta.id_venta}",
            observacion=None,
            fecha_operacion=venta.fecha_hora,
            origen_tipo="VENTA_PAGO",
            origen_id=int(pago.id_pago),
            referencia=str(venta.id_venta),
            lineas=[(cuenta, ENTRADA, importe)],
        )


def registrar_salida_origen(
    db: Session,
    *,
    usuario: UsuarioModel,
    codigo_cuenta: str,
    importe: Decimal,
    tipo: str,
    concepto: str,
    operation_id: str,
    origen_tipo: str,
    origen_id: int,
    fecha_operacion: datetime | None = None,
    observacion: str | None = None,
) -> OperacionTesoreriaModel | None:
    if not tesoreria_activa(db):
        return None
    cuenta = cuenta_por_codigo(db, codigo_cuenta)
    return _insertar(
        db,
        usuario=usuario,
        operation_id=operation_id,
        payload={
            "tipo": tipo,
            "origen_tipo": origen_tipo,
            "origen_id": origen_id,
            "cuenta": codigo_cuenta,
            "importe": str(dinero(importe)),
        },
        tipo=tipo,
        concepto=concepto,
        observacion=observacion,
        fecha_operacion=fecha_operacion,
        origen_tipo=origen_tipo,
        origen_id=origen_id,
        referencia=str(origen_id),
        lineas=[(cuenta, SALIDA, dinero(importe))],
    )


def activar(
    db: Session,
    usuario: UsuarioModel,
    *,
    fecha_corte: datetime,
    efectivo_cafeteria: Decimal,
    efectivo_casa: Decimal,
    saldo_banco: Decimal,
    observacion: str,
    operation_id: str,
) -> dict:
    asegurar_cuentas(db)
    montos = {
        CODIGO_CAFE: dinero(efectivo_cafeteria),
        CODIGO_CASA: dinero(efectivo_casa),
        CODIGO_BANCO: dinero(saldo_banco),
    }
    if any(m < 0 for m in montos.values()):
        raise DatosInvalidosException("Los saldos iniciales no pueden ser negativos")
    if not (observacion or "").strip():
        raise DatosInvalidosException("La observación es obligatoria")
    payload = {
        "fecha_corte": fecha_corte.isoformat(),
        "montos": {k: str(v) for k, v in montos.items()},
        "observacion": observacion.strip(),
    }
    payload_hash = _hash(payload)
    _bloquear_clave(db, "tesoreria-activacion")
    _bloquear_clave(db, operation_id)
    previa = _exigir_idempotencia(db, operation_id, payload_hash, usuario)
    if previa:
        return {
            "activa": True,
            "fecha_corte": fecha_corte.isoformat(),
            "operaciones": [previa.id_operacion],
        }
    existente = activacion_actual(db)
    if existente:
        raise ConflictoOperacionException("Tesorería ya está activa")
    ahora = now_utc_naive()
    fila = ActivacionTesoreriaModel(
        fecha_corte=fecha_corte,
        id_usuario=usuario.id_usuario,
        fecha_confirmacion=ahora,
        estado="ACTIVA",
        efectivo_cafeteria=montos[CODIGO_CAFE],
        efectivo_casa=montos[CODIGO_CASA],
        saldo_banco=montos[CODIGO_BANCO],
        observacion=observacion.strip(),
        unica=1,
    )
    db.add(fila)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictoOperacionException("Tesorería ya está activa")
    operaciones = []
    primero = True
    for codigo, monto in montos.items():
        if monto <= 0:
            continue
        cuenta = cuenta_por_codigo(db, codigo)
        op = _insertar(
            db,
            usuario=usuario,
            operation_id=operation_id if primero else f"{operation_id}:{codigo}",
            payload=payload if primero else {"activacion": payload_hash, "cuenta": codigo, "importe": str(monto)},
            tipo=TIPO_SALDO_INICIAL,
            concepto=f"Saldo inicial {codigo}",
            observacion=observacion.strip(),
            fecha_operacion=fecha_corte,
            origen_tipo="ACTIVACION",
            origen_id=None,
            referencia=codigo,
            lineas=[(cuenta, ENTRADA, monto)],
        )
        operaciones.append(op)
        primero = False
    _auditar(
        db,
        usuario,
        A.TESORERIA_ACTIVADA,
        fila.id_activacion,
        {"fecha_corte": fecha_corte.isoformat()},
    )
    return {
        "activa": True,
        "fecha_corte": fecha_corte.isoformat(),
        "operaciones": [op.id_operacion for op in operaciones],
    }


def traspasar(
    db: Session,
    usuario: UsuarioModel,
    *,
    codigo_origen: str,
    codigo_destino: str,
    importe: Decimal,
    concepto: str,
    observacion: str | None,
    operation_id: str,
    fecha_operacion: datetime | None = None,
) -> OperacionTesoreriaModel:
    if not tesoreria_activa(db):
        raise DatosInvalidosException("Tesorería no está activa")
    if codigo_origen == codigo_destino:
        raise DatosInvalidosException("La cuenta origen y la destino no pueden ser la misma")
    if codigo_origen not in CUENTAS_SISTEMA or codigo_destino not in CUENTAS_SISTEMA:
        raise DatosInvalidosException("Cuenta de tesorería inválida")
    monto = dinero(importe)
    origen = cuenta_por_codigo(db, codigo_origen)
    destino = cuenta_por_codigo(db, codigo_destino)
    op = _insertar(
        db,
        usuario=usuario,
        operation_id=operation_id,
        payload={
            "tipo": TIPO_TRASPASO,
            "origen": codigo_origen,
            "destino": codigo_destino,
            "importe": str(monto),
        },
        tipo=TIPO_TRASPASO,
        concepto=concepto,
        observacion=observacion,
        fecha_operacion=fecha_operacion,
        origen_tipo=None,
        origen_id=None,
        referencia=None,
        lineas=[(origen, SALIDA, monto), (destino, ENTRADA, monto)],
    )
    _auditar(db, usuario, A.TESORERIA_TRASPASO, op.id_operacion, {"importe": str(monto)})
    return op


def movimiento_simple(
    db: Session,
    usuario: UsuarioModel,
    *,
    codigo_cuenta: str,
    importe: Decimal,
    direccion: str,
    tipo: str,
    concepto: str,
    observacion: str | None,
    operation_id: str,
    fecha_operacion: datetime | None = None,
) -> OperacionTesoreriaModel:
    if not tesoreria_activa(db):
        raise DatosInvalidosException("Tesorería no está activa")
    if not (concepto or "").strip():
        raise DatosInvalidosException("El concepto es obligatorio")
    cuenta = cuenta_por_codigo(db, codigo_cuenta)
    op = _insertar(
        db,
        usuario=usuario,
        operation_id=operation_id,
        payload={
            "tipo": tipo,
            "cuenta": codigo_cuenta,
            "importe": str(dinero(importe)),
            "direccion": direccion,
        },
        tipo=tipo,
        concepto=concepto,
        observacion=observacion,
        fecha_operacion=fecha_operacion,
        origen_tipo=None,
        origen_id=None,
        referencia=None,
        lineas=[(cuenta, direccion, dinero(importe))],
    )
    accion = {
        TIPO_APORTACION: A.TESORERIA_APORTACION,
        TIPO_RETIRO: A.TESORERIA_RETIRO,
        TIPO_COMISION: A.TESORERIA_COMISION,
        TIPO_SOBRANTE: A.TESORERIA_AJUSTE,
        TIPO_FALTANTE: A.TESORERIA_AJUSTE,
    }.get(tipo, A.TESORERIA_AJUSTE)
    _auditar(db, usuario, accion, op.id_operacion, {"tipo": tipo, "importe": str(dinero(importe))})
    return op


def revertir(
    db: Session,
    usuario: UsuarioModel,
    id_operacion: int,
    *,
    motivo: str,
    operation_id: str,
) -> OperacionTesoreriaModel:
    if not (motivo or "").strip():
        raise DatosInvalidosException("El motivo de la reversa es obligatorio")
    _bloquear_clave(db, f"tesoreria-reversa-{int(id_operacion)}")
    consulta = db.query(OperacionTesoreriaModel).filter_by(id_operacion=id_operacion)
    bind = db.get_bind()
    if bind is not None and bind.dialect.name != "sqlite":
        consulta = consulta.with_for_update()
    original = consulta.first()
    if not original:
        raise RecursoNoEncontradoException("Operación no encontrada")
    if original.tipo == TIPO_REVERSA:
        raise DatosInvalidosException("Una reversa no se revierte por este camino")
    if original.estado == ESTADO_REVERTIDA:
        raise ConflictoOperacionException("La operación ya fue revertida")
    ya = (
        db.query(OperacionTesoreriaModel)
        .filter(
            OperacionTesoreriaModel.tipo == TIPO_REVERSA,
            OperacionTesoreriaModel.id_operacion_revertida == original.id_operacion,
        )
        .first()
    )
    if ya:
        raise ConflictoOperacionException("La operación ya fue revertida")
    movimientos = (
        db.query(MovimientoTesoreriaModel)
        .filter_by(id_operacion=original.id_operacion)
        .all()
    )
    if not movimientos:
        raise DatosInvalidosException("La operación no tiene movimientos")
    lineas = []
    for mov in movimientos:
        cuenta = db.query(CuentaTesoreriaModel).filter_by(id_cuenta=mov.id_cuenta).one()
        opuesta = SALIDA if mov.direccion == ENTRADA else ENTRADA
        lineas.append((cuenta, opuesta, dinero(mov.importe)))
    op = _insertar(
        db,
        usuario=usuario,
        operation_id=operation_id,
        payload={"reversa_de": int(original.id_operacion), "motivo": motivo.strip()},
        tipo=TIPO_REVERSA,
        concepto=f"Reversa de {original.tipo}",
        observacion=motivo.strip(),
        fecha_operacion=now_utc_naive(),
        origen_tipo="REVERSA",
        origen_id=int(original.id_operacion),
        referencia=str(original.id_operacion),
        lineas=lineas,
    )
    op.id_operacion_revertida = original.id_operacion
    original.estado = ESTADO_REVERTIDA
    db.flush()
    _auditar(
        db,
        usuario,
        A.TESORERIA_REVERSA,
        op.id_operacion,
        {"original": int(original.id_operacion)},
    )
    return op


def conciliar(
    db: Session,
    usuario: UsuarioModel,
    *,
    codigo_cuenta: str,
    saldo_fisico: Decimal,
    observacion: str | None,
) -> ConciliacionTesoreriaModel:
    if not tesoreria_activa(db):
        raise DatosInvalidosException("Tesorería no está activa")
    cuenta = cuenta_por_codigo(db, codigo_cuenta)
    sistema = saldo_cuenta(db, cuenta.id_cuenta)
    fisico = dinero(saldo_fisico)
    if fisico < 0:
        raise DatosInvalidosException("El saldo físico no puede ser negativo")
    fila = ConciliacionTesoreriaModel(
        id_cuenta=cuenta.id_cuenta,
        saldo_sistema=sistema,
        saldo_fisico=fisico,
        diferencia=(fisico - sistema).quantize(Decimal("0.01")),
        observacion=(observacion or "").strip() or None,
        estado="PENDIENTE",
        id_usuario=usuario.id_usuario,
        fecha_creacion=now_utc_naive(),
    )
    db.add(fila)
    db.flush()
    _auditar(
        db,
        usuario,
        A.TESORERIA_CONCILIACION,
        fila.id_conciliacion,
        {"diferencia": str(fila.diferencia)},
    )
    return fila


def revisar_conciliacion(
    db: Session,
    usuario: UsuarioModel,
    id_conciliacion: int,
    *,
    generar_ajuste: bool,
    operation_id: str | None,
) -> ConciliacionTesoreriaModel:
    fila = db.query(ConciliacionTesoreriaModel).filter_by(id_conciliacion=id_conciliacion).first()
    if not fila:
        raise RecursoNoEncontradoException("Conciliación no encontrada")
    if fila.estado != "PENDIENTE":
        raise ConflictoOperacionException("La conciliación ya fue revisada")
    if not (fila.observacion or "").strip() and generar_ajuste and dinero(fila.diferencia) != 0:
        raise DatosInvalidosException("El ajuste requiere observación")
    fila.estado = "REVISADA"
    fila.id_usuario_revision = usuario.id_usuario
    fila.fecha_revision = now_utc_naive()
    diferencia = dinero(fila.diferencia)
    if generar_ajuste and diferencia != 0:
        if not operation_id:
            raise DatosInvalidosException("El ajuste requiere operation_id")
        cuenta = db.query(CuentaTesoreriaModel).filter_by(id_cuenta=fila.id_cuenta).one()
        if diferencia > 0:
            tipo, direccion, monto = TIPO_SOBRANTE, ENTRADA, diferencia
        else:
            tipo, direccion, monto = TIPO_FALTANTE, SALIDA, abs(diferencia)
        op = movimiento_simple(
            db,
            usuario,
            codigo_cuenta=cuenta.codigo,
            importe=monto,
            direccion=direccion,
            tipo=tipo,
            concepto=f"Ajuste de conciliación {fila.id_conciliacion}",
            observacion=fila.observacion,
            operation_id=operation_id,
        )
        fila.id_operacion_ajuste = op.id_operacion
    db.flush()
    return fila


def operacion_a_dict(db: Session, op: OperacionTesoreriaModel) -> dict:
    movimientos = (
        db.query(MovimientoTesoreriaModel, CuentaTesoreriaModel)
        .join(CuentaTesoreriaModel, CuentaTesoreriaModel.id_cuenta == MovimientoTesoreriaModel.id_cuenta)
        .filter(MovimientoTesoreriaModel.id_operacion == op.id_operacion)
        .all()
    )
    return {
        "id_operacion": op.id_operacion,
        "operation_id": op.operation_id,
        "tipo": op.tipo,
        "estado": op.estado,
        "fecha_operacion": op.fecha_operacion.isoformat() if op.fecha_operacion else None,
        "id_usuario": op.id_usuario,
        "origen_tipo": op.origen_tipo,
        "origen_id": op.origen_id,
        "referencia": op.referencia,
        "concepto": op.concepto,
        "observacion": op.observacion,
        "id_operacion_revertida": op.id_operacion_revertida,
        "movimientos": [
            {
                "id_movimiento": mov.id_movimiento,
                "codigo_cuenta": cuenta.codigo,
                "direccion": mov.direccion,
                "importe": str(dinero(mov.importe)),
            }
            for mov, cuenta in movimientos
        ],
    }


def resumen(db: Session, desde: datetime | None = None, hasta: datetime | None = None) -> dict:
    asegurar_cuentas(db)
    activacion = activacion_actual(db)
    cuentas = []
    total = dinero(0)
    for codigo in CUENTAS_SISTEMA:
        cuenta = cuenta_por_codigo(db, codigo)
        saldo = saldo_cuenta(db, cuenta.id_cuenta)
        total += saldo
        cuentas.append(
            {
                "id_cuenta": cuenta.id_cuenta,
                "codigo": cuenta.codigo,
                "nombre": cuenta.nombre,
                "tipo": cuenta.tipo,
                "moneda": cuenta.moneda,
                "saldo": str(saldo),
            }
        )
    def suma_tipo(tipos: tuple[str, ...], direccion: str) -> Decimal:
        q = (
            db.query(func.coalesce(func.sum(MovimientoTesoreriaModel.importe), 0))
            .join(OperacionTesoreriaModel, OperacionTesoreriaModel.id_operacion == MovimientoTesoreriaModel.id_operacion)
            .filter(
                OperacionTesoreriaModel.tipo.in_(tipos),
                MovimientoTesoreriaModel.direccion == direccion,
                OperacionTesoreriaModel.estado == ESTADO_CONFIRMADA,
            )
        )
        if desde:
            q = q.filter(OperacionTesoreriaModel.fecha_operacion >= desde)
        if hasta:
            q = q.filter(OperacionTesoreriaModel.fecha_operacion <= hasta)
        return dinero(q.scalar())

    pendientes = (
        db.query(func.count(ConciliacionTesoreriaModel.id_conciliacion))
        .filter(ConciliacionTesoreriaModel.estado == "PENDIENTE")
        .scalar()
    )
    return {
        "activa": activacion is not None,
        "fecha_corte": activacion.fecha_corte.isoformat() if activacion else None,
        "cuentas": cuentas,
        "total_disponible": str(total.quantize(Decimal("0.01"))),
        "ingresos": str(suma_tipo((TIPO_VENTA,), ENTRADA)),
        "gastos_operativos": str(suma_tipo(GASTOS_OPERATIVOS, SALIDA)),
        "comisiones": str(suma_tipo((TIPO_COMISION,), SALIDA)),
        "retiros_propietario": str(suma_tipo((TIPO_RETIRO,), SALIDA)),
        "aportaciones": str(suma_tipo((TIPO_APORTACION,), ENTRADA)),
        "traspasos": str(suma_tipo((TIPO_TRASPASO,), SALIDA)),
        "diferencias_pendientes": int(pendientes or 0),
    }


def exigir_activa(db: Session) -> None:
    if not tesoreria_activa(db):
        raise DatosInvalidosException("Tesorería no está activa")


def exigir_admin(usuario: UsuarioModel) -> None:
    from app.constants.roles import ADMIN, normalizar_rol

    if normalizar_rol(usuario.rol) != ADMIN:
        raise AccesoNegadoException("Solo administración puede hacer esta operación")
