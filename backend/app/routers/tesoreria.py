from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.constants.acciones import (
    TESORERIA_ACTIVAR,
    TESORERIA_AJUSTAR,
    TESORERIA_APORTAR,
    TESORERIA_CONCILIAR,
    TESORERIA_REGISTRAR_GASTO,
    TESORERIA_RETIRAR,
    TESORERIA_REVERTIR,
    TESORERIA_TRASPASAR,
    TESORERIA_VER,
)
from app.database import get_db
from app.exceptions import DatosInvalidosException
from app.models.models import (
    ConciliacionTesoreriaModel,
    CuentaTesoreriaModel,
    MovimientoTesoreriaModel,
    OperacionTesoreriaModel,
    UsuarioModel,
)
from app.schemas.tesoreria import (
    ActivarTesoreria,
    AjusteIn,
    ConciliacionIn,
    MovimientoCuentaIn,
    RevisionConciliacionIn,
    ReversaIn,
    TraspasoIn,
)
from app.services import tesoreria_service as T
from app.utils.deps import get_current_user
from app.utils.permisos import require_accion, require_module

router = APIRouter(prefix="/tesoreria", tags=["Tesorería"])


def _usuario(current: UsuarioModel = Depends(get_current_user)) -> UsuarioModel:
    return current


@router.get("/estado", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_VER))])
def estado(db: Session = Depends(get_db)):
    T.asegurar_cuentas(db)
    activacion = T.activacion_actual(db)
    db.commit()
    return {
        "activa": activacion is not None,
        "fecha_corte": activacion.fecha_corte.isoformat() if activacion else None,
    }


@router.post("/activar", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_ACTIVAR))])
def activar(
    data: ActivarTesoreria,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(_usuario),
):
    if not data.confirmar:
        raise DatosInvalidosException("Confirma la activación")
    T.exigir_admin(current)
    resultado = T.activar(
        db,
        current,
        fecha_corte=data.fecha_corte,
        efectivo_cafeteria=T.dinero(data.efectivo_cafeteria),
        efectivo_casa=T.dinero(data.efectivo_casa),
        saldo_banco=T.dinero(data.saldo_banco),
        observacion=data.observacion,
        operation_id=data.operation_id,
    )
    db.commit()
    return resultado


@router.get("/resumen", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_VER))])
def resumen(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    data = T.resumen(db, desde, hasta)
    db.commit()
    return data


@router.get("/cuentas", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_VER))])
def cuentas(db: Session = Depends(get_db)):
    return T.resumen(db)["cuentas"]


@router.get("/movimientos", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_VER))])
def movimientos(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    codigo_cuenta: Optional[str] = None,
    tipo: Optional[str] = None,
    id_usuario: Optional[int] = None,
    origen_tipo: Optional[str] = None,
    referencia: Optional[str] = None,
    estado: Optional[str] = None,
    limite: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = (
        db.query(MovimientoTesoreriaModel, OperacionTesoreriaModel, CuentaTesoreriaModel)
        .join(OperacionTesoreriaModel, OperacionTesoreriaModel.id_operacion == MovimientoTesoreriaModel.id_operacion)
        .join(CuentaTesoreriaModel, CuentaTesoreriaModel.id_cuenta == MovimientoTesoreriaModel.id_cuenta)
    )
    if desde:
        q = q.filter(OperacionTesoreriaModel.fecha_operacion >= desde)
    if hasta:
        q = q.filter(OperacionTesoreriaModel.fecha_operacion <= hasta)
    if codigo_cuenta:
        q = q.filter(CuentaTesoreriaModel.codigo == codigo_cuenta)
    if tipo:
        q = q.filter(OperacionTesoreriaModel.tipo == tipo)
    if id_usuario:
        q = q.filter(OperacionTesoreriaModel.id_usuario == id_usuario)
    if origen_tipo:
        q = q.filter(OperacionTesoreriaModel.origen_tipo == origen_tipo)
    if referencia:
        q = q.filter(OperacionTesoreriaModel.referencia == referencia)
    if estado:
        q = q.filter(OperacionTesoreriaModel.estado == estado)
    total = q.count()
    filas = (
        q.order_by(MovimientoTesoreriaModel.id_movimiento.desc())
        .offset(offset)
        .limit(limite)
        .all()
    )
    return {
        "total": total,
        "limite": limite,
        "offset": offset,
        "items": [
            {
                "id_movimiento": mov.id_movimiento,
                "id_operacion": op.id_operacion,
                "fecha_operacion": op.fecha_operacion.isoformat() if op.fecha_operacion else None,
                "tipo": op.tipo,
                "estado": op.estado,
                "codigo_cuenta": cuenta.codigo,
                "direccion": mov.direccion,
                "importe": str(T.dinero(mov.importe)),
                "concepto": op.concepto,
                "id_usuario": op.id_usuario,
                "origen_tipo": op.origen_tipo,
                "origen_id": op.origen_id,
                "referencia": op.referencia,
            }
            for mov, op, cuenta in filas
        ],
    }


@router.get("/operaciones/{id_operacion}", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_VER))])
def operacion(id_operacion: int, db: Session = Depends(get_db)):
    op = db.query(OperacionTesoreriaModel).filter_by(id_operacion=id_operacion).first()
    if not op:
        from app.exceptions import RecursoNoEncontradoException
        raise RecursoNoEncontradoException("Operación no encontrada")
    return T.operacion_a_dict(db, op)


@router.get("/reportes", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_VER))])
def reportes(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    data = T.resumen(db, desde, hasta)
    return {
        "saldo_por_cuenta": data["cuentas"],
        "total_disponible": data["total_disponible"],
        "ingresos_monetarios": data["ingresos"],
        "gastos_operativos": data["gastos_operativos"],
        "gastos_financieros": data["comisiones"],
        "retiros_propietario": data["retiros_propietario"],
        "aportaciones": data["aportaciones"],
        "traspasos": data["traspasos"],
        "diferencias_pendientes": data["diferencias_pendientes"],
        "nota": "Puntos, traspasos, saldos iniciales y retiros del propietario no se suman como venta ni como gasto operativo.",
    }


@router.post("/traspasos", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_TRASPASAR))])
def traspasos(
    data: TraspasoIn,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(_usuario),
):
    op = T.traspasar(
        db,
        current,
        codigo_origen=data.codigo_origen,
        codigo_destino=data.codigo_destino,
        importe=T.dinero(data.importe),
        concepto=data.concepto,
        observacion=data.observacion,
        operation_id=data.operation_id,
        fecha_operacion=data.fecha_operacion,
    )
    db.commit()
    return T.operacion_a_dict(db, op)


@router.post("/aportaciones", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_APORTAR))])
def aportaciones(
    data: MovimientoCuentaIn,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(_usuario),
):
    T.exigir_admin(current)
    op = T.movimiento_simple(
        db,
        current,
        codigo_cuenta=data.codigo_cuenta,
        importe=T.dinero(data.importe),
        direccion=T.ENTRADA,
        tipo=T.TIPO_APORTACION,
        concepto=data.concepto,
        observacion=data.observacion,
        operation_id=data.operation_id,
        fecha_operacion=data.fecha_operacion,
    )
    db.commit()
    return T.operacion_a_dict(db, op)


@router.post("/retiros", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_RETIRAR))])
def retiros(
    data: MovimientoCuentaIn,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(_usuario),
):
    T.exigir_admin(current)
    op = T.movimiento_simple(
        db,
        current,
        codigo_cuenta=data.codigo_cuenta,
        importe=T.dinero(data.importe),
        direccion=T.SALIDA,
        tipo=T.TIPO_RETIRO,
        concepto=data.concepto,
        observacion=data.observacion,
        operation_id=data.operation_id,
        fecha_operacion=data.fecha_operacion,
    )
    db.commit()
    return T.operacion_a_dict(db, op)


@router.post("/comisiones", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_REGISTRAR_GASTO))])
def comisiones(
    data: MovimientoCuentaIn,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(_usuario),
):
    if data.codigo_cuenta != T.CODIGO_BANCO:
        raise DatosInvalidosException("La comisión bancaria solo disminuye BANCO")
    op = T.movimiento_simple(
        db,
        current,
        codigo_cuenta=T.CODIGO_BANCO,
        importe=T.dinero(data.importe),
        direccion=T.SALIDA,
        tipo=T.TIPO_COMISION,
        concepto=data.concepto,
        observacion=data.observacion,
        operation_id=data.operation_id,
        fecha_operacion=data.fecha_operacion,
    )
    db.commit()
    return T.operacion_a_dict(db, op)


@router.post("/ajustes", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_AJUSTAR))])
def ajustes(
    data: AjusteIn,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(_usuario),
):
    T.exigir_admin(current)
    if not (data.observacion or "").strip():
        raise DatosInvalidosException("El ajuste requiere observación")
    tipo = (data.tipo or "").strip().upper()
    if tipo == T.TIPO_SOBRANTE:
        direccion = T.ENTRADA
    elif tipo == T.TIPO_FALTANTE:
        direccion = T.SALIDA
    else:
        raise DatosInvalidosException("Tipo de ajuste inválido")
    op = T.movimiento_simple(
        db,
        current,
        codigo_cuenta=data.codigo_cuenta,
        importe=T.dinero(data.importe),
        direccion=direccion,
        tipo=tipo,
        concepto=data.concepto,
        observacion=data.observacion,
        operation_id=data.operation_id,
        fecha_operacion=data.fecha_operacion,
    )
    db.commit()
    return T.operacion_a_dict(db, op)


@router.post("/operaciones/{id_operacion}/revertir", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_REVERTIR))])
def revertir(
    id_operacion: int,
    data: ReversaIn,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(_usuario),
):
    T.exigir_admin(current)
    op = T.revertir(db, current, id_operacion, motivo=data.motivo, operation_id=data.operation_id)
    db.commit()
    return T.operacion_a_dict(db, op)


@router.get("/conciliaciones", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_VER))])
def listar_conciliaciones(db: Session = Depends(get_db)):
    filas = (
        db.query(ConciliacionTesoreriaModel, CuentaTesoreriaModel)
        .join(CuentaTesoreriaModel, CuentaTesoreriaModel.id_cuenta == ConciliacionTesoreriaModel.id_cuenta)
        .order_by(ConciliacionTesoreriaModel.id_conciliacion.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id_conciliacion": fila.id_conciliacion,
            "codigo_cuenta": cuenta.codigo,
            "saldo_sistema": str(T.dinero(fila.saldo_sistema)),
            "saldo_fisico": str(T.dinero(fila.saldo_fisico)),
            "diferencia": str(T.dinero(fila.diferencia)),
            "observacion": fila.observacion,
            "estado": fila.estado,
            "id_operacion_ajuste": fila.id_operacion_ajuste,
        }
        for fila, cuenta in filas
    ]


@router.post("/conciliaciones", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_CONCILIAR))])
def crear_conciliacion(
    data: ConciliacionIn,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(_usuario),
):
    T.exigir_admin(current)
    fila = T.conciliar(
        db,
        current,
        codigo_cuenta=data.codigo_cuenta,
        saldo_fisico=T.dinero(data.saldo_fisico),
        observacion=data.observacion,
    )
    db.commit()
    return {
        "id_conciliacion": fila.id_conciliacion,
        "diferencia": str(T.dinero(fila.diferencia)),
        "estado": fila.estado,
    }


@router.post("/conciliaciones/{id_conciliacion}/revisar", dependencies=[Depends(require_module("/tesoreria")), Depends(require_accion(TESORERIA_AJUSTAR))])
def revisar(
    id_conciliacion: int,
    data: RevisionConciliacionIn,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(_usuario),
):
    T.exigir_admin(current)
    fila = T.revisar_conciliacion(
        db,
        current,
        id_conciliacion,
        generar_ajuste=data.generar_ajuste,
        operation_id=data.operation_id,
    )
    db.commit()
    return {"id_conciliacion": fila.id_conciliacion, "estado": fila.estado, "id_operacion_ajuste": fila.id_operacion_ajuste}
