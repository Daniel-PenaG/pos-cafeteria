"""Cancelación atómica de líneas de pedido (enviadas a comandera)."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.constants import auditoria as A
from app.constants.acciones import CANCELAR_PRODUCTO_EN_COMANDA
from app.constants.cancelacion import (
    ESTADO_ACTIVA,
    ESTADO_CANCELADA,
    MOTIVOS_CANCELACION,
    MSG_COBRADO,
    MSG_COMANDA_STALE,
    MSG_ENVIADA,
    MSG_LINEA_CANCELADA,
    MSG_NEGATIVA,
    MSG_SIN_PERMISO,
    MSG_STALE,
    aviso_cancelacion,
)
from app.exceptions import (
    AccesoNegadoException,
    ConflictoOperacionException,
    DatosInvalidosException,
    RecursoNoEncontradoException,
)
from app.models.models import (
    DetallePedidoModel,
    PedidoCancelacionModel,
    PedidoModel,
    PedidoOperacionModel,
    UsuarioModel,
)
from app.services.auditoria_service import registrar_auditoria
from app.services.pedido_locks import lock_pedido_y_detalle
from app.services.pedido_service import pedido_respuesta
from app.utils.acciones import tiene_accion
from app.utils.permisos import exigir_modulo_pedido
from app.utils.timezone_mx import now_utc_naive


def exigir_pedido_abierto(pedido: PedidoModel | None) -> PedidoModel:
    if not pedido:
        raise RecursoNoEncontradoException("Pedido no encontrado")
    if pedido.estado != "ABIERTO":
        raise DatosInvalidosException(MSG_COBRADO)
    return pedido


def exigir_cantidad_actual(detalle: DetallePedidoModel, cantidad_actual: float | None) -> None:
    if cantidad_actual is None:
        return
    if abs(float(detalle.cantidad) - float(cantidad_actual)) > 0.02:
        raise ConflictoOperacionException(MSG_STALE)


def _asegurar_invariantes_cantidad(detalle: DetallePedidoModel) -> None:
    cant = float(detalle.cantidad or 0)
    lista = float(detalle.cantidad_lista or 0)
    cancelada = float(getattr(detalle, "cantidad_cancelada", 0) or 0)
    if cant < 0 or lista < 0 or cancelada < 0 or lista > cant + 0.001:
        raise DatosInvalidosException(MSG_NEGATIVA)
    if lista > cant:
        detalle.cantidad_lista = cant


def desvincular_operaciones(db: Session, id_detalle: int) -> None:
    db.query(PedidoOperacionModel).filter(
        PedidoOperacionModel.id_detalle_pedido == id_detalle
    ).update({PedidoOperacionModel.id_detalle_pedido: None}, synchronize_session=False)


def eliminar_linea_no_enviada(
    db: Session,
    *,
    id_detalle: int,
    current: UsuarioModel,
) -> dict:
    pedido, detalle = lock_pedido_y_detalle(db, id_detalle)
    if not detalle:
        raise RecursoNoEncontradoException("Línea no encontrada")
    exigir_pedido_abierto(pedido)
    exigir_modulo_pedido(current, bool(pedido.para_llevar))
    if bool(detalle.en_comanda):
        raise DatosInvalidosException(MSG_ENVIADA)
    if getattr(detalle, "estado_linea", ESTADO_ACTIVA) == ESTADO_CANCELADA:
        raise DatosInvalidosException(MSG_LINEA_CANCELADA)
    try:
        desvincular_operaciones(db, id_detalle)
        db.delete(detalle)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"ok": True}


def actualizar_linea_no_enviada(
    db: Session,
    *,
    detalle: DetallePedidoModel,
    pedido: PedidoModel,
    cantidad: float | None,
    cantidad_actual: float | None,
) -> DetallePedidoModel:
    exigir_pedido_abierto(pedido)
    if getattr(detalle, "estado_linea", ESTADO_ACTIVA) == ESTADO_CANCELADA:
        raise DatosInvalidosException(MSG_LINEA_CANCELADA)
    if cantidad is not None:
        exigir_cantidad_actual(detalle, cantidad_actual)
        if bool(detalle.en_comanda) and float(cantidad) < float(detalle.cantidad):
            raise DatosInvalidosException(MSG_ENVIADA)
        if float(cantidad) < 1:
            raise DatosInvalidosException("Cantidad inválida")
    return detalle


def cancelar_linea_enviada(
    db: Session,
    *,
    id_detalle: int,
    current: UsuarioModel,
    cantidad: float,
    motivo: str,
    motivo_detalle: str | None = None,
    cantidad_actual: float | None = None,
) -> dict:
    if not tiene_accion(current, CANCELAR_PRODUCTO_EN_COMANDA):
        raise AccesoNegadoException(MSG_SIN_PERMISO)

    motivo_n = (motivo or "").strip()
    if motivo_n not in MOTIVOS_CANCELACION:
        raise DatosInvalidosException("Motivo de cancelación inválido")
    if motivo_n == "Otro" and not (motivo_detalle or "").strip():
        raise DatosInvalidosException("Indica el detalle del motivo")

    cant_cancel = float(cantidad)
    if cant_cancel <= 0:
        raise DatosInvalidosException(MSG_NEGATIVA)

    try:
        pedido, detalle = lock_pedido_y_detalle(db, id_detalle)
        if not detalle or not pedido:
            raise RecursoNoEncontradoException("Línea no encontrada")
        if detalle.id_pedido != pedido.id_pedido:
            raise ConflictoOperacionException(MSG_STALE)
        exigir_pedido_abierto(pedido)
        exigir_modulo_pedido(current, bool(pedido.para_llevar))
        if not bool(detalle.en_comanda):
            raise DatosInvalidosException(
                "La línea aún no fue enviada a comandera; elimínala o reduce la cantidad"
            )
        if getattr(detalle, "estado_linea", ESTADO_ACTIVA) == ESTADO_CANCELADA:
            raise DatosInvalidosException(MSG_LINEA_CANCELADA)

        exigir_cantidad_actual(detalle, cantidad_actual)
        actual = float(detalle.cantidad)
        if cant_cancel > actual + 0.001:
            raise DatosInvalidosException("No se puede cancelar más de la cantidad actual")

        nueva = round(actual - cant_cancel, 2)
        if nueva < 0:
            raise DatosInvalidosException(MSG_NEGATIVA)

        estado_ant = getattr(detalle, "estado_linea", ESTADO_ACTIVA) or ESTADO_ACTIVA
        estado_nuevo = ESTADO_CANCELADA if nueva <= 0 else ESTADO_ACTIVA
        aviso, aviso_texto = aviso_cancelacion(actual, nueva, cant_cancel)

        detalle.cantidad = nueva
        detalle.cantidad_cancelada = float(getattr(detalle, "cantidad_cancelada", 0) or 0) + cant_cancel
        detalle.estado_linea = estado_nuevo
        if float(detalle.cantidad_lista or 0) > nueva:
            detalle.cantidad_lista = nueva
        if nueva <= 0:
            detalle.fecha_listo_comanda = now_utc_naive()
        _asegurar_invariantes_cantidad(detalle)

        fila = PedidoCancelacionModel(
            id_pedido=pedido.id_pedido,
            id_detalle_pedido=detalle.id_detalle_pedido,
            cantidad=cant_cancel,
            cantidad_anterior=actual,
            cantidad_nueva=nueva,
            motivo=motivo_n,
            motivo_detalle=(motivo_detalle or "").strip() or None,
            estado_anterior=estado_ant,
            estado_nuevo=estado_nuevo,
            aviso=aviso,
            aviso_texto=aviso_texto,
            id_usuario=current.id_usuario,
            fecha_hora=now_utc_naive(),
        )
        db.add(fila)
        db.flush()
        registrar_auditoria(
            db,
            usuario=current,
            accion=A.CANCELACION,
            entidad="detalle_pedido",
            entidad_id=detalle.id_detalle_pedido,
            detalles={
                "id_pedido": pedido.id_pedido,
                "id_detalle_pedido": detalle.id_detalle_pedido,
                "cantidad_cancelada": cant_cancel,
                "cantidad_anterior": actual,
                "cantidad_nueva": nueva,
                "motivo": motivo_n,
                "estado_anterior": estado_ant,
                "estado_nuevo": estado_nuevo,
            },
            origen="VENTAS",
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return pedido_respuesta(db, pedido)


def marcar_cancelacion_vista(
    db: Session,
    *,
    id_cancelacion: int,
    current: UsuarioModel,
) -> dict:
    try:
        q = db.query(PedidoCancelacionModel).filter(
            PedidoCancelacionModel.id_cancelacion == id_cancelacion
        )
        if db.bind.dialect.name != "sqlite":
            q = q.with_for_update()
        fila = q.first()
        if not fila:
            raise RecursoNoEncontradoException("Cancelación no encontrada")
        if fila.vista_comandera:
            return {
                "ok": True,
                "id_cancelacion": fila.id_cancelacion,
                "vista_comandera": True,
                "ya_atendida": True,
                "id_usuario_vista": fila.id_usuario_vista,
                "fecha_vista": fila.fecha_vista.isoformat() if fila.fecha_vista else None,
            }
        fila.vista_comandera = True
        fila.fecha_vista = now_utc_naive()
        fila.id_usuario_vista = current.id_usuario
        db.commit()
        return {
            "ok": True,
            "id_cancelacion": fila.id_cancelacion,
            "vista_comandera": True,
            "ya_atendida": False,
            "id_usuario_vista": fila.id_usuario_vista,
            "fecha_vista": fila.fecha_vista.isoformat() if fila.fecha_vista else None,
        }
    except Exception:
        db.rollback()
        raise


def cancelaciones_pendientes_comandera(db: Session) -> list[PedidoCancelacionModel]:
    return (
        db.query(PedidoCancelacionModel)
        .options(joinedload(PedidoCancelacionModel.detalle), joinedload(PedidoCancelacionModel.pedido))
        .filter(PedidoCancelacionModel.vista_comandera.is_(False))
        .order_by(PedidoCancelacionModel.fecha_hora.asc())
        .all()
    )


def marcar_linea_comanda_listo(
    db: Session,
    *,
    id_detalle: int,
    cantidad: float,
    cantidad_actual: float | None = None,
    cantidad_lista_actual: float | None = None,
    pedido_permite_listo,
) -> DetallePedidoModel:
    """Marca unidades listas. Bloquea Pedido y luego Detalle. Rollback si falla."""
    try:
        pedido, detalle = lock_pedido_y_detalle(db, id_detalle)
        if not detalle or not pedido:
            raise RecursoNoEncontradoException("Línea no encontrada")
        if detalle.id_pedido != pedido.id_pedido:
            raise ConflictoOperacionException(MSG_COMANDA_STALE)
        if not pedido_permite_listo(pedido):
            raise DatosInvalidosException("Pedido ya cerrado")
        if getattr(detalle, "estado_linea", ESTADO_ACTIVA) == ESTADO_CANCELADA:
            raise ConflictoOperacionException(MSG_COMANDA_STALE)
        cant = float(detalle.cantidad or 0)
        if cant <= 0:
            raise ConflictoOperacionException(MSG_COMANDA_STALE)
        lista = float(detalle.cantidad_lista or 0)
        if cantidad_actual is not None and abs(cant - float(cantidad_actual)) > 0.02:
            raise ConflictoOperacionException(MSG_COMANDA_STALE)
        if cantidad_lista_actual is not None and abs(lista - float(cantidad_lista_actual)) > 0.02:
            raise ConflictoOperacionException(MSG_COMANDA_STALE)
        if lista > cant + 0.001:
            raise ConflictoOperacionException(MSG_COMANDA_STALE)
        pendiente = cant - lista
        if pendiente <= 0:
            raise DatosInvalidosException("Esta línea ya está completa en comanda")
        avanzar = min(float(cantidad), pendiente)
        if avanzar <= 0:
            raise DatosInvalidosException("Cantidad inválida")
        detalle.cantidad_lista = lista + avanzar
        if float(detalle.cantidad_lista) > cant:
            detalle.cantidad_lista = cant
        if float(detalle.cantidad_lista) >= cant:
            detalle.fecha_listo_comanda = now_utc_naive()
        _asegurar_invariantes_cantidad(detalle)
        db.commit()
        return (
            db.query(DetallePedidoModel)
            .options(joinedload(DetallePedidoModel.pedido))
            .filter(DetallePedidoModel.id_detalle_pedido == id_detalle)
            .first()
        )
    except Exception:
        db.rollback()
        raise
