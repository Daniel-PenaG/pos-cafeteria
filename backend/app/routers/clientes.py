from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional

from app.database import get_db
from app.models.models import ClienteModel, FidelidadMovimientoModel
from app.schemas.cliente import (
    Cliente,
    ClienteCreate,
    ClienteUpdate,
    ClienteDetalle,
    ClienteBusqueda,
    FidelidadConfig,
    FidelidadConfigUpdate,
    FidelidadMovimiento,
    AjustePuntosRequest,
    PuntosPreview,
)
from app.services.fidelidad_service import (
    normalizar_telefono,
    generar_codigo_fidelidad,
    obtener_config,
    calcular_puntos_ganados,
    ajustar_puntos,
)
from app.exceptions import DatosInvalidosException, RecursoNoEncontradoException, RecursoYaExisteException

router = APIRouter(prefix="/clientes", tags=["Clientes / Fidelidad"])


def _cliente_a_dict(c: ClienteModel) -> dict:
    return {
        "id_cliente": c.id_cliente,
        "nombre": c.nombre,
        "telefono": c.telefono,
        "codigo_fidelidad": c.codigo_fidelidad,
        "puntos_saldo": int(c.puntos_saldo),
        "activo": c.activo,
        "fecha_alta": c.fecha_alta,
    }


# ============================
# CONFIG FIDELIDAD
# ============================
@router.get("/fidelidad/config", response_model=FidelidadConfig)
def get_fidelidad_config(db: Session = Depends(get_db)):
    config = obtener_config(db)
    return {
        "pesos_por_punto": float(config.pesos_por_punto),
        "minimo_compra_acumular": float(config.minimo_compra_acumular),
        "fecha_actualizacion": config.fecha_actualizacion,
    }


@router.put("/fidelidad/config", response_model=FidelidadConfig)
def update_fidelidad_config(data: FidelidadConfigUpdate, db: Session = Depends(get_db)):
    config = obtener_config(db)
    config.pesos_por_punto = data.pesos_por_punto
    config.minimo_compra_acumular = data.minimo_compra_acumular
    from datetime import datetime
    config.fecha_actualizacion = datetime.now()
    db.commit()
    db.refresh(config)
    return {
        "pesos_por_punto": float(config.pesos_por_punto),
        "minimo_compra_acumular": float(config.minimo_compra_acumular),
        "fecha_actualizacion": config.fecha_actualizacion,
    }


@router.get("/fidelidad/preview", response_model=PuntosPreview)
def preview_puntos(
    total: float = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    config = obtener_config(db)
    puntos = calcular_puntos_ganados(total, config)
    return {
        "total_compra": total,
        "puntos_a_ganar": puntos,
        "pesos_por_punto": float(config.pesos_por_punto),
        "minimo_compra_acumular": float(config.minimo_compra_acumular),
    }


# ============================
# BÚSQUEDA (teléfono, nombre, código QR)
# ============================
@router.get("/buscar", response_model=ClienteBusqueda)
def buscar_clientes(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    termino = q.strip()
    if not termino:
        raise DatosInvalidosException("Indica teléfono, nombre o código")

    query = db.query(ClienteModel).filter(ClienteModel.activo == True)

    if termino.upper().startswith("CAFE-"):
        query = query.filter(ClienteModel.codigo_fidelidad == termino.upper())
    else:
        tel = normalizar_telefono(termino)
        if tel and len(tel) >= 3:
            query = query.filter(
                or_(
                    ClienteModel.telefono.contains(tel),
                    ClienteModel.nombre.ilike(f"%{termino}%"),
                    ClienteModel.codigo_fidelidad == termino.upper(),
                )
            )
        else:
            query = query.filter(ClienteModel.nombre.ilike(f"%{termino}%"))

    clientes = query.order_by(ClienteModel.nombre).limit(15).all()
    return {"resultados": [_cliente_a_dict(c) for c in clientes]}


@router.get("/codigo/{codigo}", response_model=Cliente)
def obtener_por_codigo(codigo: str, db: Session = Depends(get_db)):
    cliente = (
        db.query(ClienteModel)
        .filter(
            ClienteModel.codigo_fidelidad == codigo.strip().upper(),
            ClienteModel.activo == True,
        )
        .first()
    )
    if not cliente:
        raise RecursoNoEncontradoException("Cliente no encontrado con ese código")
    return _cliente_a_dict(cliente)


# ============================
# CRUD
# ============================
@router.get("/", response_model=List[Cliente])
def listar_clientes(db: Session = Depends(get_db)):
    clientes = db.query(ClienteModel).order_by(ClienteModel.nombre).all()
    return [_cliente_a_dict(c) for c in clientes]


@router.get("/{id_cliente}", response_model=ClienteDetalle)
def obtener_cliente(id_cliente: int, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == id_cliente).first()
    if not cliente:
        raise RecursoNoEncontradoException("Cliente no encontrado")
    movs = (
        db.query(FidelidadMovimientoModel)
        .filter(FidelidadMovimientoModel.id_cliente == id_cliente)
        .order_by(FidelidadMovimientoModel.fecha_hora.desc())
        .limit(50)
        .all()
    )
    data = _cliente_a_dict(cliente)
    data["movimientos"] = [
        {
            "id_movimiento": m.id_movimiento,
            "tipo": m.tipo,
            "puntos": int(m.puntos),
            "saldo_despues": int(m.saldo_despues),
            "id_venta": m.id_venta,
            "notas": m.notas,
            "fecha_hora": m.fecha_hora,
        }
        for m in movs
    ]
    return data


@router.post("/", response_model=Cliente)
def crear_cliente(data: ClienteCreate, db: Session = Depends(get_db)):
    nombre = data.nombre.strip()
    if not nombre:
        raise DatosInvalidosException("El nombre es requerido")
    telefono = normalizar_telefono(data.telefono)
    if len(telefono) < 10:
        raise DatosInvalidosException("Teléfono inválido (mínimo 10 dígitos)")

    existe = db.query(ClienteModel).filter(ClienteModel.telefono == telefono).first()
    if existe:
        raise RecursoYaExisteException(f"Ya existe un cliente con teléfono {telefono}")

    cliente = ClienteModel(
        nombre=nombre,
        telefono=telefono,
        codigo_fidelidad=generar_codigo_fidelidad(db),
        puntos_saldo=0,
        activo=True,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return _cliente_a_dict(cliente)


@router.put("/{id_cliente}", response_model=Cliente)
def actualizar_cliente(id_cliente: int, data: ClienteUpdate, db: Session = Depends(get_db)):
    cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == id_cliente).first()
    if not cliente:
        raise RecursoNoEncontradoException("Cliente no encontrado")

    if data.nombre is not None:
        nombre = data.nombre.strip()
        if not nombre:
            raise DatosInvalidosException("El nombre no puede estar vacío")
        cliente.nombre = nombre

    if data.telefono is not None:
        telefono = normalizar_telefono(data.telefono)
        if len(telefono) < 10:
            raise DatosInvalidosException("Teléfono inválido")
        otro = (
            db.query(ClienteModel)
            .filter(ClienteModel.telefono == telefono, ClienteModel.id_cliente != id_cliente)
            .first()
        )
        if otro:
            raise RecursoYaExisteException("Ese teléfono ya está registrado")
        cliente.telefono = telefono

    if data.activo is not None:
        cliente.activo = data.activo

    db.commit()
    db.refresh(cliente)
    return _cliente_a_dict(cliente)


@router.post("/{id_cliente}/ajustar-puntos", response_model=FidelidadMovimiento)
def ajustar_puntos_cliente(
    id_cliente: int,
    data: AjustePuntosRequest,
    db: Session = Depends(get_db),
):
    if data.puntos == 0:
        raise DatosInvalidosException("Indica puntos distintos de cero")

    cliente = db.query(ClienteModel).filter(ClienteModel.id_cliente == id_cliente).first()
    if not cliente:
        raise RecursoNoEncontradoException("Cliente no encontrado")

    try:
        mov = ajustar_puntos(db, cliente, data.puntos, data.notas.strip(), data.id_usuario)
        db.commit()
        db.refresh(mov)
    except ValueError as e:
        raise DatosInvalidosException(str(e))

    return {
        "id_movimiento": mov.id_movimiento,
        "tipo": mov.tipo,
        "puntos": int(mov.puntos),
        "saldo_despues": int(mov.saldo_despues),
        "id_venta": mov.id_venta,
        "notas": mov.notas,
        "fecha_hora": mov.fecha_hora,
    }
