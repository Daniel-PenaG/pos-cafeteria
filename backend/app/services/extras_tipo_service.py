import re
import unicodedata

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import DatosInvalidosException
from app.models import ExtraTipoPosModel

DEFAULTS = [
    ("CAFE", "Café", 1),
    ("LECHE", "Leche", 2),
    ("SABORIZANTE", "Saborizante", 3),
    ("OTRO", "Otro", 99),
]


def _slug_codigo(etiqueta: str) -> str:
    s = etiqueta.strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").upper()
    if not s:
        raise DatosInvalidosException("Nombre de categoría inválido")
    return s[:30]


def asegurar_tipos_default(db: Session) -> None:
    if db.query(ExtraTipoPosModel).count() > 0:
        return
    for codigo, etiqueta, orden in DEFAULTS:
        db.add(ExtraTipoPosModel(codigo=codigo, etiqueta=etiqueta, orden=orden))
    db.commit()


def listar_tipos(db: Session):
    asegurar_tipos_default(db)
    return (
        db.query(ExtraTipoPosModel)
        .order_by(ExtraTipoPosModel.orden, ExtraTipoPosModel.etiqueta)
        .all()
    )


def crear_tipo(db: Session, etiqueta: str) -> ExtraTipoPosModel:
    asegurar_tipos_default(db)
    etiqueta = etiqueta.strip()
    if not etiqueta:
        raise DatosInvalidosException("El nombre es obligatorio")
    codigo = _slug_codigo(etiqueta)
    existe = (
        db.query(ExtraTipoPosModel)
        .filter(ExtraTipoPosModel.codigo == codigo)
        .first()
    )
    if existe:
        raise DatosInvalidosException(f"Ya existe la categoría «{existe.etiqueta}»")
    max_orden = db.query(func.max(ExtraTipoPosModel.orden)).scalar() or 0
    tipo = ExtraTipoPosModel(codigo=codigo, etiqueta=etiqueta, orden=max_orden + 1)
    db.add(tipo)
    db.commit()
    db.refresh(tipo)
    return tipo


def validar_tipo_codigo(db: Session, tipo: str) -> str:
    asegurar_tipos_default(db)
    t = (tipo or "OTRO").strip().upper()
    existe = (
        db.query(ExtraTipoPosModel)
        .filter(ExtraTipoPosModel.codigo == t)
        .first()
    )
    if not existe:
        raise DatosInvalidosException(
            "Tipo no válido. Configura las categorías en Extras de venta."
        )
    return t
