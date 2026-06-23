import secrets
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.models import (
    ClienteModel,
    FidelidadConfigModel,
    FidelidadMovimientoModel,
)


def normalizar_telefono(telefono: str) -> str:
    return "".join(c for c in telefono if c.isdigit())


def generar_codigo_fidelidad(db: Session) -> str:
    for _ in range(20):
        codigo = f"CAFE-{secrets.token_hex(3).upper()}"
        existe = (
            db.query(ClienteModel)
            .filter(ClienteModel.codigo_fidelidad == codigo)
            .first()
        )
        if not existe:
            return codigo
    raise ValueError("No se pudo generar código de fidelidad único")


def obtener_config(db: Session) -> FidelidadConfigModel:
    config = db.query(FidelidadConfigModel).first()
    if not config:
        config = FidelidadConfigModel(
            pesos_por_punto=10.0,
            minimo_compra_acumular=0.0,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def calcular_puntos_ganados(total: float, config: FidelidadConfigModel) -> int:
    pesos_por_punto = float(config.pesos_por_punto)
    minimo = float(config.minimo_compra_acumular)
    if total < minimo or pesos_por_punto <= 0:
        return 0
    return int(total // pesos_por_punto)


def acumular_puntos_venta(
    db: Session,
    cliente: ClienteModel,
    puntos: int,
    id_venta: int,
    id_usuario: int,
) -> None:
    if puntos <= 0:
        return
    nuevo_saldo = int(cliente.puntos_saldo) + puntos
    cliente.puntos_saldo = nuevo_saldo
    mov = FidelidadMovimientoModel(
        id_cliente=cliente.id_cliente,
        tipo="ACUMULACION",
        puntos=puntos,
        saldo_despues=nuevo_saldo,
        id_venta=id_venta,
        notas=f"Venta #{id_venta}",
        fecha_hora=datetime.now(),
        id_usuario=id_usuario,
    )
    db.add(mov)


def ajustar_puntos(
    db: Session,
    cliente: ClienteModel,
    puntos: int,
    notas: str,
    id_usuario: int,
) -> FidelidadMovimientoModel:
    nuevo_saldo = int(cliente.puntos_saldo) + puntos
    if nuevo_saldo < 0:
        raise ValueError("El saldo no puede quedar negativo")
    cliente.puntos_saldo = nuevo_saldo
    mov = FidelidadMovimientoModel(
        id_cliente=cliente.id_cliente,
        tipo="AJUSTE",
        puntos=puntos,
        saldo_despues=nuevo_saldo,
        notas=notas,
        fecha_hora=datetime.now(),
        id_usuario=id_usuario,
    )
    db.add(mov)
    return mov
