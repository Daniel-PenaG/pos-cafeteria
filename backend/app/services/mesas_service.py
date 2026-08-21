import json
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.models import ConfiguracionModel, PedidoModel
from app.services.venta_service import MESA_PARA_LLEVAR
from app.exceptions import DatosInvalidosException

DEFAULT_MESAS: List[int] = list(range(1, 10))
MAX_MESAS = 50


def _get_or_create_config(db: Session) -> ConfiguracionModel:
    config = db.query(ConfiguracionModel).first()
    if not config:
        config = ConfiguracionModel(
            margen_ganancia=15.0,
            gastos_fijos=1000.0,
            mesas_json=json.dumps(DEFAULT_MESAS),
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    elif not config.mesas_json:
        config.mesas_json = json.dumps(DEFAULT_MESAS)
        db.commit()
        db.refresh(config)
    return config


def _parse_mesas(raw: str | None) -> List[int]:
    if not raw:
        return DEFAULT_MESAS.copy()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return DEFAULT_MESAS.copy()
    if not isinstance(data, list):
        return DEFAULT_MESAS.copy()
    mesas = sorted({int(n) for n in data if isinstance(n, (int, float)) and int(n) >= 1})
    return mesas or DEFAULT_MESAS.copy()


def _validar_lista_mesas(mesas: List[int]) -> List[int]:
    if not mesas:
        raise DatosInvalidosException("Debe haber al menos una mesa")
    if len(mesas) > MAX_MESAS:
        raise DatosInvalidosException(f"Máximo {MAX_MESAS} mesas")
    normalizadas = sorted({int(n) for n in mesas})
    for n in normalizadas:
        if n < 1:
            raise DatosInvalidosException("Número de mesa inválido")
        if n == MESA_PARA_LLEVAR:
            raise DatosInvalidosException("El número 99 está reservado para llevar")
    return normalizadas


def _pedido_abierto_en_mesa(db: Session, numero_mesa: int) -> bool:
    pedido = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.detalles))
        .filter(
            PedidoModel.estado == "ABIERTO",
            PedidoModel.numero_mesa == numero_mesa,
            PedidoModel.para_llevar == False,
        )
        .first()
    )
    if not pedido:
        return False
    return len(pedido.detalles or []) > 0


def obtener_mesas(db: Session) -> List[int]:
    config = _get_or_create_config(db)
    return _parse_mesas(config.mesas_json)


def _guardar_mesas(db: Session, mesas: List[int]) -> List[int]:
    normalizadas = _validar_lista_mesas(mesas)
    config = _get_or_create_config(db)
    config.mesas_json = json.dumps(normalizadas)
    db.commit()
    return normalizadas


def validar_mesa_operacion(db: Session, numero_mesa: int, para_llevar: bool = False) -> None:
    if para_llevar:
        if numero_mesa != MESA_PARA_LLEVAR:
            raise DatosInvalidosException("Mesa inválida para venta para llevar")
        return
    mesas = obtener_mesas(db)
    if numero_mesa not in mesas:
        raise DatosInvalidosException("Mesa no configurada o no disponible")


def agregar_mesa(db: Session, numero: Optional[int] = None) -> List[int]:
    mesas = obtener_mesas(db)
    if len(mesas) >= MAX_MESAS:
        raise DatosInvalidosException(f"Máximo {MAX_MESAS} mesas")

    if numero is None:
        numero = max(mesas, default=0) + 1
    else:
        numero = int(numero)

    if numero in mesas:
        raise DatosInvalidosException(f"La mesa {numero} ya existe")
    if numero == MESA_PARA_LLEVAR:
        raise DatosInvalidosException("El número 99 está reservado para llevar")
    if numero < 1:
        raise DatosInvalidosException("Número de mesa inválido")

    mesas.append(numero)
    return _guardar_mesas(db, mesas)


def quitar_mesa(db: Session, numero: int) -> List[int]:
    numero = int(numero)
    mesas = obtener_mesas(db)
    if numero not in mesas:
        raise DatosInvalidosException("Mesa no encontrada")
    if len(mesas) <= 1:
        raise DatosInvalidosException("Debe quedar al menos una mesa")
    if _pedido_abierto_en_mesa(db, numero):
        raise DatosInvalidosException(
            f"No se puede quitar la mesa {numero}: tiene un pedido abierto con productos"
        )
    mesas = [n for n in mesas if n != numero]
    return _guardar_mesas(db, mesas)
