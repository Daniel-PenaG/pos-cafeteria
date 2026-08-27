from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import (
    PromocionModel,
    PromocionProductoModel,
    PromocionCategoriaModel,
    ProductoModel,
    CategoriaModel,
)
from app.schemas.promocion import (
    Promocion,
    PromocionCreate,
    PromocionUpdate,
    PromocionCalculada,
    PromocionCalcularRequest,
    PromocionResumen,
    ComboCalculado,
    ComboCalcularRequest,
    ComboPromo,
    PromocionOpciones,
)
from app.exceptions import DatosInvalidosException, RecursoNoEncontradoException
from app.services.promocion_service import (
    calcular_linea,
    calcular_combo,
    listar_aplicables,
    listar_combos_producto,
    combo_a_dict,
    resumen_promociones_ventas,
)
from app.utils.deps import require_admin, require_pos

router = APIRouter(
    prefix="/promociones",
    tags=["Promociones"],
    dependencies=[Depends(require_pos)],
)


def _promo_a_dict(p: PromocionModel) -> dict:
    return {
        "id_promocion": p.id_promocion,
        "nombre": p.nombre,
        "descripcion": p.descripcion,
        "tipo": p.tipo,
        "valor": float(p.valor),
        "activa": p.activa,
        "aplica_toda_tienda": p.aplica_toda_tienda,
        "fecha_inicio": p.fecha_inicio,
        "fecha_fin": p.fecha_fin,
        "hora_inicio": p.hora_inicio,
        "hora_fin": p.hora_fin,
        "dias_semana": p.dias_semana,
        "margen_minimo": float(p.margen_minimo) if p.margen_minimo is not None else None,
        "ids_productos": [x.id_producto for x in p.productos],
        "ids_categorias": [x.id_categoria for x in p.categorias],
    }


def _sync_enlaces(db: Session, promo: PromocionModel, data) -> None:
    db.query(PromocionProductoModel).filter(
        PromocionProductoModel.id_promocion == promo.id_promocion
    ).delete()
    db.query(PromocionCategoriaModel).filter(
        PromocionCategoriaModel.id_promocion == promo.id_promocion
    ).delete()
    if not data.aplica_toda_tienda:
        for id_p in data.ids_productos:
            if db.query(ProductoModel).filter(ProductoModel.id_producto == id_p).first():
                db.add(PromocionProductoModel(id_promocion=promo.id_promocion, id_producto=id_p))
        for id_c in data.ids_categorias:
            if db.query(CategoriaModel).filter(CategoriaModel.id_categoria == id_c).first():
                db.add(
                    PromocionCategoriaModel(
                        id_promocion=promo.id_promocion, id_categoria=id_c
                    )
                )


@router.get("/", response_model=List[Promocion])
def listar_promociones(db: Session = Depends(get_db)):
    promos = db.query(PromocionModel).order_by(PromocionModel.nombre).all()
    return [_promo_a_dict(p) for p in promos]


@router.get("/resumen", response_model=PromocionResumen)
def resumen_promociones(
    periodo: Optional[str] = Query(None, description="dia, mes, anio o vacío (histórico)"),
    fecha: Optional[date] = None,
    anio: Optional[int] = None,
    mes: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return resumen_promociones_ventas(db, periodo, fecha, anio, mes)


@router.get("/aplicables/{id_producto}", response_model=List[Promocion])
def promociones_aplicables(id_producto: int, db: Session = Depends(get_db)):
    producto = db.query(ProductoModel).filter(ProductoModel.id_producto == id_producto).first()
    if not producto:
        raise RecursoNoEncontradoException("Producto no encontrado")
    return [_promo_a_dict(p) for p in listar_aplicables(db, producto)]


@router.get("/opciones/{id_producto}", response_model=PromocionOpciones)
def opciones_promo_producto(id_producto: int, db: Session = Depends(get_db)):
    producto = db.query(ProductoModel).filter(ProductoModel.id_producto == id_producto).first()
    if not producto:
        raise RecursoNoEncontradoException("Producto no encontrado")
    paquetes = [combo_a_dict(p, db) for p in listar_combos_producto(db, id_producto)]
    promos = [_promo_a_dict(p) for p in listar_aplicables(db, producto)]
    return {"paquetes": paquetes, "promos": promos}


@router.get("/combos/{id_producto}", response_model=List[ComboPromo])
def combos_producto(id_producto: int, db: Session = Depends(get_db)):
    producto = db.query(ProductoModel).filter(ProductoModel.id_producto == id_producto).first()
    if not producto:
        raise RecursoNoEncontradoException("Producto no encontrado")
    return [combo_a_dict(p, db) for p in listar_combos_producto(db, id_producto)]


@router.post("/calcular-combo", response_model=ComboCalculado)
def calcular_precio_combo(data: ComboCalcularRequest, db: Session = Depends(get_db)):
    return calcular_combo(db, data.id_promocion, data.cantidad)


@router.post("/calcular", response_model=PromocionCalculada)
def calcular_precio_promo(data: PromocionCalcularRequest, db: Session = Depends(get_db)):
    producto = (
        db.query(ProductoModel).filter(ProductoModel.id_producto == data.id_producto).first()
    )
    if not producto:
        raise RecursoNoEncontradoException("Producto no encontrado")
    return calcular_linea(
        db,
        producto,
        data.cantidad,
        data.precio_extras,
        data.id_promocion,
        sin_promocion=data.sin_promocion,
    )


@router.post("/", response_model=Promocion, status_code=201, dependencies=[Depends(require_admin)])
def crear_promocion(data: PromocionCreate, db: Session = Depends(get_db)):
    promo = PromocionModel(
        nombre=data.nombre.strip(),
        descripcion=(data.descripcion or "").strip() or None,
        tipo=data.tipo,
        valor=data.valor,
        activa=data.activa,
        aplica_toda_tienda=data.aplica_toda_tienda,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        hora_inicio=data.hora_inicio,
        hora_fin=data.hora_fin,
        dias_semana=data.dias_semana,
        margen_minimo=data.margen_minimo,
    )
    db.add(promo)
    db.flush()
    _sync_enlaces(db, promo, data)
    db.commit()
    db.refresh(promo)
    return _promo_a_dict(promo)


@router.put("/{id_promocion}", response_model=Promocion, dependencies=[Depends(require_admin)])
def actualizar_promocion(
    id_promocion: int, data: PromocionUpdate, db: Session = Depends(get_db)
):
    promo = db.query(PromocionModel).filter(PromocionModel.id_promocion == id_promocion).first()
    if not promo:
        raise RecursoNoEncontradoException("Promoción no encontrada")
    promo.nombre = data.nombre.strip()
    promo.descripcion = (data.descripcion or "").strip() or None
    promo.tipo = data.tipo
    promo.valor = data.valor
    promo.activa = data.activa
    promo.aplica_toda_tienda = data.aplica_toda_tienda
    promo.fecha_inicio = data.fecha_inicio
    promo.fecha_fin = data.fecha_fin
    promo.hora_inicio = data.hora_inicio
    promo.hora_fin = data.hora_fin
    promo.dias_semana = data.dias_semana
    promo.margen_minimo = data.margen_minimo
    _sync_enlaces(db, promo, data)
    db.commit()
    db.refresh(promo)
    return _promo_a_dict(promo)


@router.delete("/{id_promocion}", dependencies=[Depends(require_admin)])
def eliminar_promocion(id_promocion: int, db: Session = Depends(get_db)):
    promo = db.query(PromocionModel).filter(PromocionModel.id_promocion == id_promocion).first()
    if not promo:
        raise RecursoNoEncontradoException("Promoción no encontrada")
    db.delete(promo)
    db.commit()
    return {"message": "Promoción eliminada"}
