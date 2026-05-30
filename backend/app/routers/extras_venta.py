from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import CategoriaModel, CategoriaExtraModel, ExtraVentaModel, InsumoModel
from app.schemas.extras import (
    ExtraVentaCatalogo,
    ExtraVentaCatalogoCreate,
    ExtraVentaCatalogoUpdate,
    ExtraVentaDesdeInsumo,
    InsumoParaImportar,
    CategoriaExtrasConfig,
    CategoriaExtrasConfigResponse,
)
from app.exceptions import DatosInvalidosException, RecursoNoEncontradoException
from app.services.extras_precio import extra_a_catalogo, sincronizar_precio_guardado

router = APIRouter(prefix="/extras-venta", tags=["Extras de venta"])

TIPOS_VALIDOS = {"CAFE", "LECHE", "SABORIZANTE", "OTRO"}


def _validar_tipo(tipo: str) -> str:
    t = (tipo or "OTRO").strip().upper()
    if t not in TIPOS_VALIDOS:
        raise DatosInvalidosException(f"Tipo debe ser: {', '.join(sorted(TIPOS_VALIDOS))}")
    return t


def _aplicar_datos_precio(extra: ExtraVentaModel, data) -> None:
    extra.cantidad = data.cantidad
    extra.costo_unitario = data.costo_unitario
    extra.usar_precio_manual = data.usar_precio_manual
    extra.precio_personalizado = (
        data.precio_personalizado if data.usar_precio_manual else None
    )
    sincronizar_precio_guardado(extra)


@router.get("/", response_model=List[ExtraVentaCatalogo])
def listar_catalogo(db: Session = Depends(get_db)):
    extras = (
        db.query(ExtraVentaModel)
        .order_by(ExtraVentaModel.tipo, ExtraVentaModel.nombre)
        .all()
    )
    return [extra_a_catalogo(e) for e in extras]


@router.get("/insumos-importables", response_model=List[InsumoParaImportar])
def listar_insumos_para_importar(db: Session = Depends(get_db)):
    insumos = db.query(InsumoModel).order_by(InsumoModel.nombre).all()
    return [
        InsumoParaImportar(
            id_insumo=i.id_insumo,
            nombre=i.nombre,
            unidad=i.unidad,
            costo_unitario=float(i.costo_unitario or 0),
        )
        for i in insumos
    ]


@router.post("/", response_model=ExtraVentaCatalogo, status_code=201)
def crear_extra_manual(data: ExtraVentaCatalogoCreate, db: Session = Depends(get_db)):
    if not data.nombre.strip():
        raise DatosInvalidosException("El nombre es obligatorio")
    extra = ExtraVentaModel(
        nombre=data.nombre.strip(),
        unidad=(data.unidad or "").strip() or None,
        tipo=_validar_tipo(data.tipo),
        activo=data.activo,
        id_insumo_origen=None,
        cantidad=data.cantidad,
        costo_unitario=data.costo_unitario,
        usar_precio_manual=data.usar_precio_manual,
        precio_personalizado=data.precio_personalizado if data.usar_precio_manual else None,
        precio=0,
    )
    sincronizar_precio_guardado(extra)
    db.add(extra)
    db.commit()
    db.refresh(extra)
    return extra_a_catalogo(extra)


@router.post("/desde-insumo/{id_insumo}", response_model=ExtraVentaCatalogo, status_code=201)
def crear_extra_desde_insumo(
    id_insumo: int,
    data: ExtraVentaDesdeInsumo,
    db: Session = Depends(get_db),
):
    insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == id_insumo).first()
    if not insumo:
        raise RecursoNoEncontradoException("Insumo no encontrado")
    costo = (
        data.costo_unitario
        if data.costo_unitario is not None
        else float(insumo.costo_unitario or 0)
    )
    extra = ExtraVentaModel(
        nombre=insumo.nombre,
        unidad=insumo.unidad,
        tipo=_validar_tipo(data.tipo),
        activo=data.activo,
        id_insumo_origen=insumo.id_insumo,
        cantidad=data.cantidad,
        costo_unitario=costo,
        usar_precio_manual=data.usar_precio_manual,
        precio_personalizado=data.precio_personalizado if data.usar_precio_manual else None,
        precio=0,
    )
    sincronizar_precio_guardado(extra)
    db.add(extra)
    db.commit()
    db.refresh(extra)
    return extra_a_catalogo(extra)


@router.put("/{id_extra}", response_model=ExtraVentaCatalogo)
def actualizar_extra(
    id_extra: int, data: ExtraVentaCatalogoUpdate, db: Session = Depends(get_db)
):
    extra = db.query(ExtraVentaModel).filter(ExtraVentaModel.id_extra == id_extra).first()
    if not extra:
        raise RecursoNoEncontradoException("Extra no encontrado")
    if not data.nombre.strip():
        raise DatosInvalidosException("El nombre es obligatorio")
    extra.nombre = data.nombre.strip()
    extra.unidad = (data.unidad or "").strip() or None
    extra.tipo = _validar_tipo(data.tipo)
    extra.activo = data.activo
    _aplicar_datos_precio(extra, data)
    db.commit()
    db.refresh(extra)
    return extra_a_catalogo(extra)


@router.delete("/{id_extra}")
def eliminar_extra(id_extra: int, db: Session = Depends(get_db)):
    extra = db.query(ExtraVentaModel).filter(ExtraVentaModel.id_extra == id_extra).first()
    if not extra:
        raise RecursoNoEncontradoException("Extra no encontrado")
    db.query(CategoriaExtraModel).filter(CategoriaExtraModel.id_extra == id_extra).delete()
    db.delete(extra)
    db.commit()
    return {"message": "Extra eliminado del catálogo"}


@router.get("/categorias/{id_categoria}/config", response_model=CategoriaExtrasConfigResponse)
def obtener_config_categoria(id_categoria: int, db: Session = Depends(get_db)):
    cat = db.query(CategoriaModel).filter(CategoriaModel.id_categoria == id_categoria).first()
    if not cat:
        raise RecursoNoEncontradoException("Categoría no encontrada")

    ids = [
        r.id_extra
        for r in db.query(CategoriaExtraModel)
        .filter(CategoriaExtraModel.id_categoria == id_categoria)
        .all()
    ]
    extras = []
    if ids:
        filas = (
            db.query(ExtraVentaModel)
            .filter(ExtraVentaModel.id_extra.in_(ids))
            .order_by(ExtraVentaModel.nombre)
            .all()
        )
        extras = [extra_a_catalogo(e) for e in filas]

    return CategoriaExtrasConfigResponse(
        id_categoria=cat.id_categoria,
        nombre_categoria=cat.nombre,
        ids_extras=ids,
        extras=extras,
    )


@router.put("/categorias/{id_categoria}/config", response_model=CategoriaExtrasConfigResponse)
def guardar_config_categoria(
    id_categoria: int, data: CategoriaExtrasConfig, db: Session = Depends(get_db)
):
    cat = db.query(CategoriaModel).filter(CategoriaModel.id_categoria == id_categoria).first()
    if not cat:
        raise RecursoNoEncontradoException("Categoría no encontrada")

    db.query(CategoriaExtraModel).filter(
        CategoriaExtraModel.id_categoria == id_categoria
    ).delete()

    for id_extra in data.ids_extras:
        existe = db.query(ExtraVentaModel).filter(ExtraVentaModel.id_extra == id_extra).first()
        if existe:
            db.add(CategoriaExtraModel(id_categoria=id_categoria, id_extra=id_extra))

    db.commit()
    return obtener_config_categoria(id_categoria, db)
