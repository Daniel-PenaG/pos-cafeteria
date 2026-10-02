from fastapi import HTTPException, status


class RecursoNoEncontradoException(HTTPException):
    def __init__(self, detalle: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detalle
        )


class RecursoYaExisteException(HTTPException):
    def __init__(self, detalle: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detalle
        )


class ConflictoOperacionException(HTTPException):
    def __init__(self, detalle: str = "La clave de operación no corresponde a esta solicitud"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detalle,
        )


class RecalculoTotalException(HTTPException):
    """El recálculo cambiaría el total. El cobro no continúa sin confirmación del cajero."""

    CODIGO = "RECALCULO"

    def __init__(self, total_anterior, total_nuevo):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "codigo": self.CODIGO,
                "detail": (
                    f"El total cambió de ${total_anterior} a ${total_nuevo} "
                    "por vigencia o promociones. Confirma el nuevo total."
                ),
                "total_anterior": f"{total_anterior}",
                "total_nuevo": f"{total_nuevo}",
            },
        )


class SaldoPuntosCambioException(HTTPException):
    """El canje era válido con el saldo leído; otra operación lo consumió al esperar el bloqueo."""

    def __init__(self, saldo_actual: int):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "detail": "El saldo de puntos cambió; revisa nuevamente.",
                "codigo": "SALDO_PUNTOS_CAMBIO",
                "saldo_actual": int(saldo_actual),
            },
        )


class DatosInvalidosException(HTTPException):
    def __init__(self, detalle: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detalle
        )


class StockInsuficienteException(HTTPException):
    def __init__(self, detalle: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detalle
        )


class AccesoNegadoException(HTTPException):
    def __init__(self, detalle: str = "Acceso denegado"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detalle
        )


class CredencialesInvalidasException(HTTPException):
    def __init__(self, detalle: str = "Credenciales inválidas"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detalle,
            headers={"WWW-Authenticate": "Bearer"}
        )
