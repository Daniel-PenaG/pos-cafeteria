import secrets
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.exceptions import DatosInvalidosException, SaldoPuntosCambioException
from app.models.models import (
    ClienteModel,
    FidelidadConfigModel,
    FidelidadMovimientoModel,
)

# 10 puntos = $1 MXN. El mínimo de canje es 50 puntos ($5).
PUNTOS_POR_PESO_CANJE = 10
MINIMO_PUNTOS_CANJE = 50
_CENTAVO = Decimal("0.01")


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
        db.flush()
    return config


def _dinero(val) -> Decimal:
    return Decimal(str(val or 0)).quantize(_CENTAVO, rounding=ROUND_HALF_UP)


def calcular_puntos_ganados(total: float, config: FidelidadConfigModel) -> int:
    """Puntos sobre el importe monetario. La parte pagada con puntos no acumula."""
    monto = _dinero(total)
    pesos = _dinero(config.pesos_por_punto)
    minimo = _dinero(config.minimo_compra_acumular)
    if monto < minimo or pesos <= 0:
        return 0
    return int(monto // pesos)


@dataclass(frozen=True)
class ResolucionPuntos:
    puntos_usados: int
    equivalencia: Decimal
    importe_monetario: Decimal
    forma_pago: str
    metodo_monetario: str | None
    puntos_generados: int


def resolver_pago_puntos(
    *,
    cliente: ClienteModel | None,
    puntos_solicitados: int,
    total,
    forma_monetaria: str,
    config: FidelidadConfigModel,
    saldo_visto: int | None = None,
) -> ResolucionPuntos:
    """El backend recalcula canje y remanente. Ignora cualquier equivalencia del cliente."""
    total_d = _dinero(total)
    puntos = int(puntos_solicitados or 0)
    if puntos < 0:
        raise DatosInvalidosException("La cantidad de puntos no puede ser negativa")
    if puntos == 0:
        return ResolucionPuntos(
            puntos_usados=0,
            equivalencia=Decimal("0.00"),
            importe_monetario=total_d,
            forma_pago=forma_monetaria,
            metodo_monetario=forma_monetaria,
            puntos_generados=calcular_puntos_ganados(total_d, config) if cliente else 0,
        )
    if cliente is None or not cliente.activo:
        raise DatosInvalidosException("Selecciona un cliente activo para usar puntos")
    if total_d < _dinero(MINIMO_PUNTOS_CANJE / PUNTOS_POR_PESO_CANJE):
        raise DatosInvalidosException("El ticket es menor a $5. No se puede canjear puntos.")
    if puntos < MINIMO_PUNTOS_CANJE:
        raise DatosInvalidosException(f"El canje mínimo es {MINIMO_PUNTOS_CANJE} puntos")
    if puntos % PUNTOS_POR_PESO_CANJE != 0:
        raise DatosInvalidosException("Solo se canjean múltiplos de 10 puntos")
    saldo = int(cliente.puntos_saldo or 0)
    if puntos > saldo:
        visto = saldo if saldo_visto is None else int(saldo_visto)
        if puntos <= visto:
            raise SaldoPuntosCambioException(saldo)
        raise DatosInvalidosException("Los puntos superan el saldo del cliente")
    equivalencia = (Decimal(puntos) / Decimal(PUNTOS_POR_PESO_CANJE)).quantize(
        _CENTAVO, rounding=ROUND_HALF_UP
    )
    if equivalencia > total_d:
        raise DatosInvalidosException("Los puntos no pueden exceder el total del ticket")
    importe = (total_d - equivalencia).quantize(_CENTAVO, rounding=ROUND_HALF_UP)
    if importe + equivalencia != total_d:
        raise DatosInvalidosException("El pago no cuadra con el total del ticket")
    if importe == 0:
        forma = "PUNTOS"
        metodo = None
    else:
        forma = "MIXTO"
        metodo = forma_monetaria
    return ResolucionPuntos(
        puntos_usados=puntos,
        equivalencia=equivalencia,
        importe_monetario=importe,
        forma_pago=forma,
        metodo_monetario=metodo,
        puntos_generados=calcular_puntos_ganados(importe, config),
    )


def canjear_puntos_venta(
    db: Session,
    cliente: ClienteModel,
    puntos: int,
    id_venta: int,
    id_usuario: int,
) -> None:
    if puntos <= 0:
        return
    saldo = int(cliente.puntos_saldo or 0)
    if puntos > saldo:
        raise DatosInvalidosException("Los puntos superan el saldo del cliente")
    nuevo = saldo - puntos
    cliente.puntos_saldo = nuevo
    db.add(
        FidelidadMovimientoModel(
            id_cliente=cliente.id_cliente,
            tipo="REDENCION",
            puntos=-puntos,
            saldo_despues=nuevo,
            id_venta=id_venta,
            notas=f"Canje venta #{id_venta}",
            fecha_hora=datetime.now(),
            id_usuario=id_usuario,
        )
    )


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
