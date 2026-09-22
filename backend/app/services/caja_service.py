"""Sesiones de caja: apertura, movimientos, arqueo y conciliación."""
from __future__ import annotations

import os
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.constants import auditoria as A
from app.constants.acciones import (
    ABRIR_CAJA,
    ANULAR_CIERRE_CAJA,
    CERRAR_CAJA,
    FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS,
    REGISTRAR_MOVIMIENTO_CAJA,
    REVISAR_CIERRE_CAJA,
)
from app.constants.caja import (
    DENOMS_BILLETES,
    DENOMS_MONEDAS,
    ESTADO_ABIERTA,
    ESTADO_ANULADA,
    ESTADO_CERRADA_CONCILIADA,
    ESTADO_CERRADA_CON_DIFERENCIA,
    ESTADO_EN_ARQUEO,
    ESTADO_MOV_ACTIVO,
    ESTADO_MOV_REVERSADO,
    ESTADO_REVISADA,
    ESTADOS_ACTIVOS,
    ESTADOS_CERRADOS,
    MOV_AJUSTE,
    MOV_DEVOLUCION,
    MOV_ENTRADA,
    MOV_FONDO_INICIAL,
    MOV_GASTO_CAJA,
    MOV_RETIRO,
    MOV_REVERSO,
    MOV_AUMENTAN_EFECTIVO,
    MOV_REDUCEN_EFECTIVO,
    MSG_AJENA,
    MSG_CAJA_CERRADA,
    MSG_CAJA_CERRANDO,
    MSG_DOBLE_APERTURA,
    MSG_IMPORTE,
    MSG_NO_REVISAR_PROPIO,
    MSG_OBS_DIFERENCIA,
    MSG_PAYLOAD,
    MSG_PEDIDOS_ABIERTOS,
    MSG_SIN_CAJA,
    MSG_STALE_CAJA,
    MSG_TERMINAL_OCUPADA,
    TERMINALES_CAJA,
    TIPOS_MOVIMIENTO,
    TOLERANCIA_EFECTIVO_DEFAULT,
)
from app.constants.roles import ADMIN, normalizar_rol
from app.exceptions import (
    AccesoNegadoException,
    ConflictoOperacionException,
    DatosInvalidosException,
    RecursoNoEncontradoException,
)
from app.models.models import (
    ArqueoDenominacionModel,
    CierreCajaModel,
    ConfiguracionModel,
    MovimientoCajaModel,
    PedidoModel,
    SesionCajaModel,
    UsuarioModel,
    VentaModel,
    VentaPagoModel,
)
from app.services.auditoria_service import registrar_auditoria
from app.utils.acciones import tiene_accion
from app.utils.forma_pago import FORMAS_PAGO_VALIDAS, FORMA_DESCONOCIDO, bucket_forma_pago
from app.utils.timezone_mx import isoformat_utc, now_utc_naive, today_mx


def caja_requerida_para_cobrar() -> bool:
    return os.getenv("CAJA_REQUERIDA_PARA_COBRAR", "0").strip().lower() in ("1", "true", "yes")


def _money(val) -> float:
    return float(Decimal(str(val or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _oid(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = str(raw).strip()
    return key[:64] if key else None


def _for_update(db: Session, query):
    if db.bind.dialect.name != "sqlite":
        return query.with_for_update()
    return query


def lock_sesion(db: Session, id_sesion: int) -> SesionCajaModel | None:
    q = db.query(SesionCajaModel).filter(SesionCajaModel.id_sesion_caja == id_sesion)
    return _for_update(db, q).first()


def sesion_activa_usuario(db: Session, id_usuario: int) -> SesionCajaModel | None:
    return (
        db.query(SesionCajaModel)
        .filter(
            SesionCajaModel.id_usuario == id_usuario,
            SesionCajaModel.estado.in_(ESTADOS_ACTIVOS),
        )
        .first()
    )


def tolerancia_efectivo(db: Session) -> float:
    cfg = db.query(ConfiguracionModel).first()
    if cfg and getattr(cfg, "tolerancia_efectivo", None) is not None:
        return _money(cfg.tolerancia_efectivo)
    return TOLERANCIA_EFECTIVO_DEFAULT


def _exigir_propia_o_admin(sesion: SesionCajaModel, current: UsuarioModel) -> None:
    if int(sesion.id_usuario) == int(current.id_usuario):
        return
    if normalizar_rol(current.rol) == ADMIN:
        return
    raise AccesoNegadoException(MSG_AJENA)


def _replay_sesion(db: Session, operation_id: str, payload: str) -> dict | None:
    fila = db.query(SesionCajaModel).filter_by(operation_id=operation_id).first()
    if not fila:
        return None
    esperado = f"open:{fila.terminal}:{_money(fila.fondo_inicial)}"
    if esperado != payload:
        raise ConflictoOperacionException(MSG_PAYLOAD)
    return sesion_a_dict(db, fila)


def _replay_mov(db: Session, operation_id: str, payload: str) -> dict | None:
    fila = db.query(MovimientoCajaModel).filter_by(operation_id=operation_id).first()
    if not fila:
        return None
    esperado = f"{fila.tipo}:{_money(fila.importe)}:{fila.metodo}"
    if esperado != payload:
        raise ConflictoOperacionException(MSG_PAYLOAD)
    return movimiento_a_dict(fila)


def abrir_caja(
    db: Session,
    current: UsuarioModel,
    *,
    fondo_inicial: float,
    terminal: str,
    observacion: str | None = None,
    operation_id: str | None = None,
) -> dict:
    if not tiene_accion(current, ABRIR_CAJA):
        raise AccesoNegadoException("No tienes permiso para abrir caja")
    fondo = _money(fondo_inicial)
    if fondo < 0:
        raise DatosInvalidosException("El fondo inicial no puede ser negativo")
    term = (terminal or "").strip().upper()
    if term not in TERMINALES_CAJA:
        raise DatosInvalidosException("Terminal/caja inválida")
    oid = _oid(operation_id)
    payload = f"open:{term}:{fondo}"
    if oid:
        replay = _replay_sesion(db, oid, payload)
        if replay is not None:
            return replay
    if sesion_activa_usuario(db, current.id_usuario):
        raise ConflictoOperacionException(MSG_DOBLE_APERTURA)
    ocupada = (
        db.query(SesionCajaModel)
        .filter(SesionCajaModel.terminal == term, SesionCajaModel.estado.in_(ESTADOS_ACTIVOS))
        .first()
    )
    if ocupada:
        raise ConflictoOperacionException(MSG_TERMINAL_OCUPADA)
    ahora = now_utc_naive()
    try:
        sesion = SesionCajaModel(
            id_usuario=current.id_usuario,
            terminal=term,
            estado=ESTADO_ABIERTA,
            fondo_inicial=fondo,
            observacion_apertura=(observacion or "").strip() or None,
            fecha_apertura=ahora,
            operation_id=oid or f"open-{current.id_usuario}-{int(ahora.timestamp() * 1000)}",
        )
        db.add(sesion)
        db.flush()
        db.add(
            MovimientoCajaModel(
                id_sesion_caja=sesion.id_sesion_caja,
                tipo=MOV_FONDO_INICIAL,
                importe=fondo,
                metodo="EFECTIVO",
                motivo="Fondo inicial",
                id_usuario=current.id_usuario,
                fecha_hora=ahora,
                estado=ESTADO_MOV_ACTIVO,
                operation_id=f"fondo-{sesion.id_sesion_caja}",
            )
        )
        db.flush()
        registrar_auditoria(
            db,
            usuario=current,
            accion=A.CAJA_ABIERTA,
            entidad="sesion_caja",
            entidad_id=sesion.id_sesion_caja,
            detalles={"terminal": term, "fondo_inicial": fondo},
            origen="CAJA",
        )
        db.commit()
        db.refresh(sesion)
    except IntegrityError:
        db.rollback()
        if oid:
            replay = _replay_sesion(db, oid, payload)
            if replay is not None:
                return replay
        raise ConflictoOperacionException(MSG_DOBLE_APERTURA)
    return sesion_a_dict(db, sesion)


def registrar_movimiento(
    db: Session,
    current: UsuarioModel,
    *,
    tipo: str,
    importe: float,
    motivo: str,
    metodo: str = "EFECTIVO",
    referencia: str | None = None,
    id_gasto: int | None = None,
    operation_id: str | None = None,
) -> dict:
    if not tiene_accion(current, REGISTRAR_MOVIMIENTO_CAJA):
        raise AccesoNegadoException("No tienes permiso para registrar movimientos")
    tipo_n = (tipo or "").strip().upper()
    if tipo_n not in TIPOS_MOVIMIENTO or tipo_n in (MOV_FONDO_INICIAL, MOV_REVERSO):
        raise DatosInvalidosException("Tipo de movimiento inválido")
    if tipo_n == MOV_AJUSTE and normalizar_rol(current.rol) != ADMIN:
        raise AccesoNegadoException("Solo administración puede registrar ajustes")
    monto = _money(importe)
    if monto <= 0:
        raise DatosInvalidosException(MSG_IMPORTE)
    metodo_n = (metodo or "EFECTIVO").strip().upper()
    if metodo_n not in FORMAS_PAGO_VALIDAS:
        raise DatosInvalidosException("Método de movimiento inválido")
    motivo_n = (motivo or "").strip()
    if not motivo_n:
        raise DatosInvalidosException("Indica el motivo")
    oid = _oid(operation_id)
    payload = f"{tipo_n}:{monto}:{metodo_n}"
    if oid:
        replay = _replay_mov(db, oid, payload)
        if replay is not None:
            return replay
    sesion = sesion_activa_usuario(db, current.id_usuario)
    if not sesion:
        raise DatosInvalidosException(MSG_SIN_CAJA)
    locked = lock_sesion(db, sesion.id_sesion_caja)
    if not locked or locked.estado != ESTADO_ABIERTA:
        raise ConflictoOperacionException(MSG_CAJA_CERRADA)
    ahora = now_utc_naive()
    try:
        fila = MovimientoCajaModel(
            id_sesion_caja=locked.id_sesion_caja,
            tipo=tipo_n,
            importe=monto,
            metodo=metodo_n,
            motivo=motivo_n,
            referencia=(referencia or "").strip() or None,
            id_usuario=current.id_usuario,
            fecha_hora=ahora,
            estado=ESTADO_MOV_ACTIVO,
            id_gasto=id_gasto,
            operation_id=oid or f"mov-{locked.id_sesion_caja}-{int(ahora.timestamp() * 1000)}",
        )
        db.add(fila)
        db.flush()
        registrar_auditoria(
            db,
            usuario=current,
            accion=A.CAJA_MOVIMIENTO,
            entidad="movimiento_caja",
            entidad_id=locked.id_sesion_caja,
            detalles={"tipo": tipo_n, "importe": monto, "metodo": metodo_n},
            origen="CAJA",
        )
        db.commit()
        db.refresh(fila)
    except IntegrityError:
        db.rollback()
        if oid:
            replay = _replay_mov(db, oid, payload)
            if replay is not None:
                return replay
        raise ConflictoOperacionException(MSG_STALE_CAJA)
    return movimiento_a_dict(fila)


def reversar_movimiento(db: Session, current: UsuarioModel, id_movimiento: int, operation_id: str | None = None) -> dict:
    if not tiene_accion(current, REGISTRAR_MOVIMIENTO_CAJA):
        raise AccesoNegadoException("No tienes permiso para registrar movimientos")
    mov = db.query(MovimientoCajaModel).filter_by(id_movimiento=id_movimiento).first()
    if not mov:
        raise RecursoNoEncontradoException("Movimiento no encontrado")
    sesion = lock_sesion(db, mov.id_sesion_caja)
    _exigir_propia_o_admin(sesion, current)
    if sesion.estado != ESTADO_ABIERTA:
        raise ConflictoOperacionException(MSG_CAJA_CERRADA)
    if mov.estado != ESTADO_MOV_ACTIVO or mov.tipo == MOV_FONDO_INICIAL:
        raise DatosInvalidosException("Ese movimiento no se puede reversar")
    ahora = now_utc_naive()
    reverso = MovimientoCajaModel(
        id_sesion_caja=sesion.id_sesion_caja,
        tipo=MOV_REVERSO,
        importe=mov.importe,
        metodo=mov.metodo,
        motivo=f"Reverso de {mov.tipo} #{mov.id_movimiento}",
        id_usuario=current.id_usuario,
        fecha_hora=ahora,
        estado=ESTADO_MOV_ACTIVO,
        id_movimiento_reverso=mov.id_movimiento,
        operation_id=_oid(operation_id) or f"rev-{mov.id_movimiento}",
    )
    mov.estado = ESTADO_MOV_REVERSADO
    db.add(reverso)
    db.commit()
    return movimiento_a_dict(reverso)


def _totales_sesion(db: Session, sesion: SesionCajaModel) -> dict:
    ventas = db.query(VentaModel).filter(VentaModel.id_sesion_caja == sesion.id_sesion_caja).all()
    efectivo = trans = tarjeta = 0.0
    desconocido = 0.0
    for v in ventas:
        bucket = bucket_forma_pago(v.forma_pago)
        monto = _money(v.total)
        if bucket == "EFECTIVO":
            efectivo += monto
        elif bucket == "TRANSFERENCIA":
            trans += monto
        elif bucket == "TARJETA":
            tarjeta += monto
        else:
            desconocido += monto
    movs = (
        db.query(MovimientoCajaModel)
        .filter(
            MovimientoCajaModel.id_sesion_caja == sesion.id_sesion_caja,
            MovimientoCajaModel.estado == ESTADO_MOV_ACTIVO,
        )
        .all()
    )
    entradas = retiros = gastos = devoluciones = ajustes = fondo = 0.0
    for m in movs:
        if m.metodo != "EFECTIVO" and m.tipo != MOV_FONDO_INICIAL:
            continue
        imp = _money(m.importe)
        if m.tipo == MOV_FONDO_INICIAL:
            fondo += imp
        elif m.tipo == MOV_ENTRADA:
            entradas += imp
        elif m.tipo == MOV_RETIRO:
            retiros += imp
        elif m.tipo == MOV_GASTO_CAJA:
            gastos += imp
        elif m.tipo == MOV_DEVOLUCION:
            devoluciones += imp
        elif m.tipo == MOV_AJUSTE:
            ajustes += imp
        elif m.tipo == MOV_REVERSO:
            orig = db.get(MovimientoCajaModel, m.id_movimiento_reverso) if m.id_movimiento_reverso else None
            if orig and orig.tipo in MOV_AUMENTAN_EFECTIVO:
                ajustes -= imp
            elif orig and orig.tipo in MOV_REDUCEN_EFECTIVO:
                ajustes += imp
    esperado = _money(fondo + efectivo + entradas - retiros - gastos - devoluciones + ajustes)
    return {
        "fondo_inicial": _money(fondo or sesion.fondo_inicial),
        "ventas_efectivo": _money(efectivo),
        "ventas_transferencia": _money(trans),
        "ventas_tarjeta": _money(tarjeta),
        "ventas_desconocido": _money(desconocido),
        "entradas": _money(entradas),
        "retiros": _money(retiros),
        "gastos_caja": _money(gastos),
        "devoluciones": _money(devoluciones),
        "ajustes": _money(ajustes),
        "efectivo_esperado": esperado,
        "ventas_total": _money(efectivo + trans + tarjeta + desconocido),
        "num_ventas": len(ventas),
        "ingreso_monetario": _money(efectivo + trans + tarjeta),
    }


def pedidos_abiertos_cajero(db: Session, id_usuario: int) -> list[dict]:
    filas = (
        db.query(PedidoModel)
        .filter(PedidoModel.id_usuario == id_usuario, PedidoModel.estado == "ABIERTO")
        .order_by(PedidoModel.numero_mesa)
        .all()
    )
    return [
        {
            "id_pedido": p.id_pedido,
            "numero_mesa": p.numero_mesa,
            "para_llevar": bool(p.para_llevar),
            "fecha_apertura": isoformat_utc(p.fecha_apertura),
        }
        for p in filas
    ]


def iniciar_arqueo(db: Session, current: UsuarioModel, operation_id: str | None = None) -> dict:
    if not tiene_accion(current, CERRAR_CAJA):
        raise AccesoNegadoException("No tienes permiso para cerrar caja")
    sesion = sesion_activa_usuario(db, current.id_usuario)
    if not sesion:
        raise RecursoNoEncontradoException("No hay caja abierta")
    locked = lock_sesion(db, sesion.id_sesion_caja)
    if locked.estado == ESTADO_EN_ARQUEO:
        return sesion_a_dict(db, locked, ciego=True)
    if locked.estado != ESTADO_ABIERTA:
        raise ConflictoOperacionException(MSG_CAJA_CERRADA)
    locked.estado = ESTADO_EN_ARQUEO
    locked.fecha_inicio_arqueo = now_utc_naive()
    registrar_auditoria(
        db,
        usuario=current,
        accion=A.CAJA_ARQUEO,
        entidad="sesion_caja",
        entidad_id=locked.id_sesion_caja,
        detalles={},
        origen="CAJA",
    )
    db.commit()
    return sesion_a_dict(db, locked, ciego=True)


def _efectivo_desde_denoms(items: list[dict]) -> float:
    total = Decimal("0")
    valid = {f"B{int(v)}" for v in DENOMS_BILLETES} | {
        "M20", "M10", "M5", "M2", "M1", "M050",
    }
    valores = {f"B{int(v)}": Decimal(str(v)) for v in DENOMS_BILLETES}
    valores.update({
        "M20": Decimal("20"),
        "M10": Decimal("10"),
        "M5": Decimal("5"),
        "M2": Decimal("2"),
        "M1": Decimal("1"),
        "M050": Decimal("0.5"),
    })
    for item in items or []:
        codigo = str(item.get("codigo") or "").upper()
        if codigo not in valid:
            raise DatosInvalidosException(f"Denominación inválida: {codigo}")
        cant = int(item.get("cantidad") or 0)
        if cant < 0:
            raise DatosInvalidosException("La cantidad por denominación no puede ser negativa")
        total += valores[codigo] * cant
    return _money(total)


def cerrar_caja(
    db: Session,
    current: UsuarioModel,
    *,
    denominaciones: list[dict] | None,
    declarado_efectivo: float | None,
    declarado_transferencia: float,
    declarado_tarjeta: float,
    captura_directa: bool = False,
    ref_terminal: str | None = None,
    lote_terminal: str | None = None,
    ref_transferencia: str | None = None,
    observacion: str | None = None,
    forzar: bool = False,
    operation_id: str | None = None,
) -> dict:
    if not tiene_accion(current, CERRAR_CAJA):
        raise AccesoNegadoException("No tienes permiso para cerrar caja")
    oid = _oid(operation_id)
    sesion = sesion_activa_usuario(db, current.id_usuario)
    if not sesion:
        ultima = (
            db.query(SesionCajaModel)
            .filter(SesionCajaModel.id_usuario == current.id_usuario)
            .order_by(SesionCajaModel.fecha_apertura.desc())
            .first()
        )
        if ultima and ultima.estado in ESTADOS_CERRADOS:
            if oid and ultima.operation_id == oid:
                return sesion_a_dict(db, ultima)
            raise ConflictoOperacionException(MSG_CAJA_CERRADA)
        raise RecursoNoEncontradoException("No hay caja abierta")
    locked = lock_sesion(db, sesion.id_sesion_caja)
    if oid and locked.estado in ESTADOS_CERRADOS and locked.operation_id == oid:
        return sesion_a_dict(db, locked)
    if locked.estado not in (ESTADO_ABIERTA, ESTADO_EN_ARQUEO):
        raise ConflictoOperacionException(MSG_CAJA_CERRADA)
    abiertos = pedidos_abiertos_cajero(db, current.id_usuario)
    if abiertos and not forzar:
        raise DatosInvalidosException(MSG_PEDIDOS_ABIERTOS)
    if forzar:
        if not tiene_accion(current, FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS):
            raise AccesoNegadoException("No tienes permiso para forzar el cierre")
        if not (observacion or "").strip():
            raise DatosInvalidosException("El cierre forzado requiere motivo")
    if captura_directa:
        if declarado_efectivo is None or float(declarado_efectivo) < 0:
            raise DatosInvalidosException("Indica el efectivo contado")
        dec_ef = _money(declarado_efectivo)
    else:
        dec_ef = _efectivo_desde_denoms(denominaciones or [])
    dec_tr = _money(declarado_transferencia)
    dec_ta = _money(declarado_tarjeta)
    if dec_tr < 0 or dec_ta < 0:
        raise DatosInvalidosException("Los importes declarados no pueden ser negativos")
    tot = _totales_sesion(db, locked)
    exp_ef = tot["efectivo_esperado"]
    exp_tr = tot["ventas_transferencia"]
    exp_ta = tot["ventas_tarjeta"]
    dif_ef = _money(dec_ef - exp_ef)
    dif_tr = _money(dec_tr - exp_tr)
    dif_ta = _money(dec_ta - exp_ta)
    tol = tolerancia_efectivo(db)
    fuera = abs(dif_ef) > tol + 0.001 or abs(dif_tr) > 0.001 or abs(dif_ta) > 0.001
    if fuera and not (observacion or "").strip():
        raise DatosInvalidosException(MSG_OBS_DIFERENCIA)
    estado = ESTADO_CERRADA_CON_DIFERENCIA if fuera else ESTADO_CERRADA_CONCILIADA
    ahora = now_utc_naive()
    if not captura_directa:
        db.query(ArqueoDenominacionModel).filter_by(id_sesion_caja=locked.id_sesion_caja).delete()
        valores = {f"B{int(v)}": v for v in DENOMS_BILLETES}
        valores.update({"M20": 20, "M10": 10, "M5": 5, "M2": 2, "M1": 1, "M050": 0.5})
        for item in denominaciones or []:
            codigo = str(item.get("codigo") or "").upper()
            db.add(
                ArqueoDenominacionModel(
                    id_sesion_caja=locked.id_sesion_caja,
                    codigo=codigo,
                    valor=valores[codigo],
                    cantidad=int(item.get("cantidad") or 0),
                )
            )
    locked.estado = estado
    locked.fecha_cierre = ahora
    locked.id_usuario_cierre = current.id_usuario
    locked.esperado_efectivo = exp_ef
    locked.esperado_transferencia = exp_tr
    locked.esperado_tarjeta = exp_ta
    locked.declarado_efectivo = dec_ef
    locked.declarado_transferencia = dec_tr
    locked.declarado_tarjeta = dec_ta
    locked.diferencia_efectivo = dif_ef
    locked.diferencia_transferencia = dif_tr
    locked.diferencia_tarjeta = dif_ta
    locked.ventas_total = tot["ventas_total"]
    locked.num_ventas = tot["num_ventas"]
    locked.ref_terminal = (ref_terminal or "").strip() or None
    locked.lote_terminal = (lote_terminal or "").strip() or None
    locked.ref_transferencia = (ref_transferencia or "").strip() or None
    locked.observacion_cierre = (observacion or "").strip() or None
    locked.forzado = bool(forzar)
    locked.captura_directa = bool(captura_directa)
    if oid:
        locked.operation_id = oid
    snapshot = CierreCajaModel(
        id_usuario=locked.id_usuario,
        fecha=today_mx(),
        num_ventas=tot["num_ventas"],
        total_ventas=tot["ventas_total"],
        total_efectivo=exp_ef,
        total_tarjeta=exp_ta,
        total_transferencia=exp_tr,
        efectivo_contado=dec_ef,
        diferencia=dif_ef,
        notas=locked.observacion_cierre,
        fecha_hora_registro=ahora,
        id_sesion_caja=locked.id_sesion_caja,
    )
    db.add(snapshot)
    registrar_auditoria(
        db,
        usuario=current,
        accion=A.CAJA_DIFERENCIA if fuera else A.CAJA_CERRADA,
        entidad="sesion_caja",
        entidad_id=locked.id_sesion_caja,
        detalles={
            "estado": estado,
            "diferencia_efectivo": dif_ef,
            "forzado": bool(forzar),
        },
        origen="CAJA",
    )
    if forzar:
        registrar_auditoria(
            db,
            usuario=current,
            accion=A.CAJA_FORZAR,
            entidad="sesion_caja",
            entidad_id=locked.id_sesion_caja,
            detalles={"pedidos_abiertos": len(abiertos)},
            origen="CAJA",
        )
    db.commit()
    return sesion_a_dict(db, locked)


def revisar_cierre(db: Session, current: UsuarioModel, id_sesion: int) -> dict:
    if not tiene_accion(current, REVISAR_CIERRE_CAJA):
        raise AccesoNegadoException("No tienes permiso para revisar cierres")
    locked = lock_sesion(db, id_sesion)
    if not locked:
        raise RecursoNoEncontradoException("Sesión no encontrada")
    if locked.estado not in (ESTADO_CERRADA_CONCILIADA, ESTADO_CERRADA_CON_DIFERENCIA):
        raise DatosInvalidosException("Solo se revisan cierres cerrados")
    if int(locked.id_usuario) == int(current.id_usuario):
        raise AccesoNegadoException(MSG_NO_REVISAR_PROPIO)
    locked.estado = ESTADO_REVISADA
    locked.id_usuario_revision = current.id_usuario
    locked.fecha_revision = now_utc_naive()
    registrar_auditoria(
        db,
        usuario=current,
        accion=A.CAJA_REVISADA,
        entidad="sesion_caja",
        entidad_id=locked.id_sesion_caja,
        detalles={},
        origen="CAJA",
    )
    db.commit()
    return sesion_a_dict(db, locked)


def anular_cierre(db: Session, current: UsuarioModel, id_sesion: int, motivo: str) -> dict:
    if not tiene_accion(current, ANULAR_CIERRE_CAJA):
        raise AccesoNegadoException("No tienes permiso para anular cierres")
    if not (motivo or "").strip():
        raise DatosInvalidosException("Indica el motivo de anulación")
    locked = lock_sesion(db, id_sesion)
    if not locked:
        raise RecursoNoEncontradoException("Sesión no encontrada")
    if locked.estado == ESTADO_ANULADA:
        return sesion_a_dict(db, locked)
    locked.estado = ESTADO_ANULADA
    locked.motivo_anulacion = motivo.strip()
    registrar_auditoria(
        db,
        usuario=current,
        accion=A.CAJA_ANULADA,
        entidad="sesion_caja",
        entidad_id=locked.id_sesion_caja,
        detalles={"motivo": motivo.strip()},
        origen="CAJA",
    )
    db.commit()
    return sesion_a_dict(db, locked)


def asociar_venta_a_caja(db: Session, current: UsuarioModel, venta: VentaModel) -> SesionCajaModel | None:
    """Bloquea la sesión ABIERTA del cajero. None si no hay y el flag lo permite."""
    sesion = sesion_activa_usuario(db, current.id_usuario)
    if sesion:
        locked = lock_sesion(db, sesion.id_sesion_caja)
        if not locked or locked.estado != ESTADO_ABIERTA:
            raise ConflictoOperacionException(MSG_CAJA_CERRANDO)
        venta.id_sesion_caja = locked.id_sesion_caja
        return locked
    if caja_requerida_para_cobrar():
        raise DatosInvalidosException(MSG_SIN_CAJA)
    return None


def registrar_pago_venta(db: Session, venta: VentaModel) -> None:
    existe = (
        db.query(VentaPagoModel)
        .filter(VentaPagoModel.operation_id == f"venta-{venta.id_venta}")
        .first()
    )
    if existe:
        return
    db.add(
        VentaPagoModel(
            id_venta=venta.id_venta,
            metodo=venta.forma_pago,
            importe_monetario=venta.total,
            fecha_hora=venta.fecha_hora,
            id_usuario=venta.id_usuario,
            id_sesion_caja=venta.id_sesion_caja,
            operation_id=f"venta-{venta.id_venta}",
        )
    )


def movimiento_a_dict(m: MovimientoCajaModel) -> dict:
    return {
        "id_movimiento": m.id_movimiento,
        "id_sesion_caja": m.id_sesion_caja,
        "tipo": m.tipo,
        "importe": _money(m.importe),
        "metodo": m.metodo,
        "motivo": m.motivo,
        "referencia": m.referencia,
        "fecha_hora": isoformat_utc(m.fecha_hora),
        "estado": m.estado,
        "id_gasto": m.id_gasto,
    }


def sesion_a_dict(db: Session, s: SesionCajaModel, ciego: bool = False) -> dict:
    tot = _totales_sesion(db, s)
    base = {
        "id_sesion_caja": s.id_sesion_caja,
        "id_usuario": s.id_usuario,
        "terminal": s.terminal,
        "estado": s.estado,
        "fondo_inicial": _money(s.fondo_inicial),
        "observacion_apertura": s.observacion_apertura,
        "fecha_apertura": isoformat_utc(s.fecha_apertura),
        "fecha_inicio_arqueo": isoformat_utc(s.fecha_inicio_arqueo) if s.fecha_inicio_arqueo else None,
        "fecha_cierre": isoformat_utc(s.fecha_cierre) if s.fecha_cierre else None,
        "caja_requerida": caja_requerida_para_cobrar(),
        "pedidos_abiertos": pedidos_abiertos_cajero(db, s.id_usuario),
        "tolerancia_efectivo": tolerancia_efectivo(db),
        "movimientos": [movimiento_a_dict(m) for m in s.movimientos],
        "forzado": bool(s.forzado),
        "observacion_cierre": s.observacion_cierre,
        "ref_terminal": s.ref_terminal,
        "lote_terminal": s.lote_terminal,
        "ref_transferencia": s.ref_transferencia,
        "motivo_anulacion": s.motivo_anulacion,
        "id_usuario_revision": s.id_usuario_revision,
        "fecha_revision": isoformat_utc(s.fecha_revision) if s.fecha_revision else None,
        "captura_directa": bool(s.captura_directa),
        "num_ventas": tot["num_ventas"] if s.num_ventas is None else s.num_ventas,
        "ventas_total": tot["ventas_total"] if s.ventas_total is None else _money(s.ventas_total),
        "usuario_nombre": s.usuario.nombre if s.usuario else None,
        "duracion_minutos": (
            int(((s.fecha_cierre or now_utc_naive()) - s.fecha_apertura).total_seconds() // 60)
            if s.fecha_apertura
            else 0
        ),
    }
    if ciego and s.estado == ESTADO_EN_ARQUEO:
        base["ciego"] = True
        base.pop("ventas_total", None)
        base.pop("num_ventas", None)
        base.pop("ingreso_monetario", None)
        return base
    base.update(tot)
    if s.esperado_efectivo is not None:
        base["esperado_efectivo"] = _money(s.esperado_efectivo)
        base["esperado_transferencia"] = _money(s.esperado_transferencia)
        base["esperado_tarjeta"] = _money(s.esperado_tarjeta)
        base["declarado_efectivo"] = _money(s.declarado_efectivo)
        base["declarado_transferencia"] = _money(s.declarado_transferencia)
        base["declarado_tarjeta"] = _money(s.declarado_tarjeta)
        base["diferencia_efectivo"] = _money(s.diferencia_efectivo)
        base["diferencia_transferencia"] = _money(s.diferencia_transferencia)
        base["diferencia_tarjeta"] = _money(s.diferencia_tarjeta)
    return base


def listar_sesiones(db: Session, estado: str | None = None, id_usuario: int | None = None) -> list[dict]:
    q = db.query(SesionCajaModel)
    if estado:
        q = q.filter(SesionCajaModel.estado == estado)
    if id_usuario:
        q = q.filter(SesionCajaModel.id_usuario == id_usuario)
    filas = q.order_by(SesionCajaModel.fecha_apertura.desc()).limit(200).all()
    return [sesion_a_dict(db, s) for s in filas]
