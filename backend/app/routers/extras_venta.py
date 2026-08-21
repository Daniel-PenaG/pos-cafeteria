from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import CategoriaModel, CategoriaExtraModel, ExtraVentaModel, InsumoModel, ProductoModel, ProductoExtraModel
from app.schemas.extras import (
    ExtraVentaCatalogo,
    ExtraVentaCatalogoCreate,
    ExtraVentaCatalogoUpdate,
    ExtraVentaDesdeInsumo,
    InsumoParaImportar,
    CategoriaExtrasConfig,
    CategoriaExtrasConfigResponse,
    ProductoExtrasConfig,
    ProductoExtrasConfigResponse,
    ExtraTipoPos,
    ExtraTipoPosCreate,
)
from app.exceptions import DatosInvalidosException, RecursoNoEncontradoException
from app.services.extras_precio import extra_a_catalogo, sincronizar_precio_guardado
from app.services.extras_tipo_service import listar_tipos, crear_tipo, validar_tipo_codigo
from app.utils.deps import require_admin, require_pos

router = APIRouter(
    prefix="/extras-venta",
    tags=["Extras de venta"],
    dependencies=[Depends(require_pos)],
)


def _validar_tipo(db: Session, tipo: str) -> str:
    return validar_tipo_codigo(db, tipo)


def _aplicar_datos_precio(extra: ExtraVentaModel, data) -> None:
    extra.cantidad = data.cantidad
    extra.costo_unitario = data.costo_unitario
    extra.usar_precio_manual = data.usar_precio_manual
    extra.precio_personalizado = (
        data.precio_personalizado if data.usar_precio_manual else None
    )
    sincronizar_precio_guardado(extra)


@router.get("/tipos", response_model=List[ExtraTipoPos])
def listar_tipos_pos(db: Session = Depends(get_db)):
    return listar_tipos(db)


@router.post("/tipos", response_model=ExtraTipoPos, status_code=201, dependencies=[Depends(require_admin)])
def crear_tipo_pos(data: ExtraTipoPosCreate, db: Session = Depends(get_db)):
    return crear_tipo(db, data.etiqueta)


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


@router.post("/", response_model=ExtraVentaCatalogo, status_code=201, dependencies=[Depends(require_admin)])
def crear_extra_manual(data: ExtraVentaCatalogoCreate, db: Session = Depends(get_db)):
    if not data.nombre.strip():
        raise DatosInvalidosException("El nombre es obligatorio")
    insumo = (
        db.query(InsumoModel)
        .filter(InsumoModel.id_insumo == data.id_insumo_origen)
        .first()
    )
    if not insumo:
        raise RecursoNoEncontradoException("Insumo no encontrado")
    extra = ExtraVentaModel(
        nombre=data.nombre.strip(),
        unidad=(data.unidad or insumo.unidad or "").strip() or None,
        tipo=_validar_tipo(db, data.tipo),
        activo=data.activo,
        id_insumo_origen=insumo.id_insumo,
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


@router.post("/desde-insumo/{id_insumo}", response_model=ExtraVentaCatalogo, status_code=201, dependencies=[Depends(require_admin)])
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
        tipo=_validar_tipo(db, data.tipo),
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


@router.put("/{id_extra}", response_model=ExtraVentaCatalogo, dependencies=[Depends(require_admin)])
def actualizar_extra(
    id_extra: int, data: ExtraVentaCatalogoUpdate, db: Session = Depends(get_db)
):
    extra = db.query(ExtraVentaModel).filter(ExtraVentaModel.id_extra == id_extra).first()
    if not extra:
        raise RecursoNoEncontradoException("Extra no encontrado")
    if not data.nombre.strip():
        raise DatosInvalidosException("El nombre es obligatorio")
    insumo = (
        db.query(InsumoModel)
        .filter(InsumoModel.id_insumo == data.id_insumo_origen)
        .first()
    )
    if not insumo:
        raise RecursoNoEncontradoException("Insumo no encontrado")
    extra.nombre = data.nombre.strip()
    extra.unidad = (data.unidad or insumo.unidad or "").strip() or None
    extra.tipo = _validar_tipo(db, data.tipo)
    extra.activo = data.activo
    extra.id_insumo_origen = insumo.id_insumo
    _aplicar_datos_precio(extra, data)
    db.commit()
    db.refresh(extra)
    return extra_a_catalogo(extra)


@router.delete("/{id_extra}", dependencies=[Depends(require_admin)])
def eliminar_extra(id_extra: int, db: Session = Depends(get_db)):
    extra = db.query(ExtraVentaModel).filter(ExtraVentaModel.id_extra == id_extra).first()
    if not extra:
        raise RecursoNoEncontradoException("Extra no encontrado")
    db.query(CategoriaExtraModel).filter(CategoriaExtraModel.id_extra == id_extra).delete()
    db.query(ProductoExtraModel).filter(ProductoExtraModel.id_extra == id_extra).delete()
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


@router.put("/categorias/{id_categoria}/config", response_model=CategoriaExtrasConfigResponse, dependencies=[Depends(require_admin)])
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


@router.get("/productos/{id_producto}/config", response_model=ProductoExtrasConfigResponse)
def obtener_config_producto(id_producto: int, db: Session = Depends(get_db)):
    prod = (
        db.query(ProductoModel)
        .filter(ProductoModel.id_producto == id_producto)
        .first()
    )
    if not prod:
        raise RecursoNoEncontradoException("Producto no encontrado")

    cat = db.query(CategoriaModel).filter(CategoriaModel.id_categoria == prod.id_categoria).first()

    ids = [
        r.id_extra
        for r in db.query(ProductoExtraModel)
        .filter(ProductoExtraModel.id_producto == id_producto)
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

    return ProductoExtrasConfigResponse(
        id_producto=prod.id_producto,
        nombre_producto=prod.nombre,
        id_categoria=prod.id_categoria,
        nombre_categoria=cat.nombre if cat else "",
        ids_extras=ids,
        extras=extras,
    )


@router.put("/productos/{id_producto}/config", response_model=ProductoExtrasConfigResponse, dependencies=[Depends(require_admin)])
def guardar_config_producto(
    id_producto: int, data: ProductoExtrasConfig, db: Session = Depends(get_db)
):
    prod = db.query(ProductoModel).filter(ProductoModel.id_producto == id_producto).first()
    if not prod:
        raise RecursoNoEncontradoException("Producto no encontrado")

    db.query(ProductoExtraModel).filter(
        ProductoExtraModel.id_producto == id_producto
    ).delete()

    for id_extra in data.ids_extras:
        existe = db.query(ExtraVentaModel).filter(ExtraVentaModel.id_extra == id_extra).first()
        if existe:
            db.add(ProductoExtraModel(id_producto=id_producto, id_extra=id_extra))

    db.commit()
    return obtener_config_producto(id_producto, db)
