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
