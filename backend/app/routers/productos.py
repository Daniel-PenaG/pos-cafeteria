from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import CategoriaModel, ProductoModel , InsumoModel
from app.schemas.productos import (
    CategoriaCreate, Categoria,
    ProductoCreate, Producto,
    InsumoCreate, Insumo
)

router = APIRouter(prefix="/catalogo", tags=["Catálogo"])

# ============================
# CATEGORÍAS
# ============================
@router.post("/categorias", response_model=Categoria)
def crear_categoria(data: CategoriaCreate, db: Session = Depends(get_db)):
    nueva = CategoriaModel(nombre=data.nombre)
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva

@router.get("/categorias", response_model=list[Categoria])
def listar_categorias(db: Session = Depends(get_db)):
    return db.query(CategoriaModel).all()


# ============================
# PRODUCTOS
# ============================
@router.post("/productos", response_model=Producto)
def crear_producto(data: ProductoCreate, db: Session = Depends(get_db)):
    categoria = db.query(CategoriaModel).filter(CategoriaModel.id_categoria == data.id_categoria).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="La categoría no existe")

    nuevo = ProductoModel(
        nombre=data.nombre,
        id_categoria=data.id_categoria,
        precio_venta=data.precio_venta,
        activo=data.activo
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.get("/productos", response_model=list[Producto])
def listar_productos(db: Session = Depends(get_db)):
    return db.query(ProductoModel).all()


# ============================
# INSUMOS
# ============================
@router.post("/insumos", response_model=Insumo)
def crear_insumo(data: InsumoCreate, db: Session = Depends(get_db)):
    nuevo = InsumoModel (
        nombre=data.nombre,
        unidad=data.unidad,
        stock_actual=data.stock_actual,
        stock_minimo=data.stock_minimo,
        costo_unitario=data.costo_unitario
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.get("/insumos", response_model=list[Insumo])
def listar_insumos(db: Session = Depends(get_db)):
    return db.query(InsumoModel).all()
