from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import CategoriaModel, ProductoModel , InsumoModel
from app.schemas.productos import (
    CategoriaCreate, CategoriaUpdate, Categoria,
    ProductoCreate, ProductoUpdate, Producto,
    InsumoCreate, InsumoUpdate, Insumo, InsumoActualizado,
)
from app.services import RecetaService
from app.exceptions import (
    RecursoNoEncontradoException,
    RecursoYaExisteException,
    DatosInvalidosException,
)

router = APIRouter(prefix="/catalogo", tags=["Catálogo"])

# ============================
# CATEGORÍAS
# ============================
@router.post("/categorias", response_model=Categoria)
def crear_categoria(data: CategoriaCreate, db: Session = Depends(get_db)):
    if not data.nombre or data.nombre.strip() == "":
        raise DatosInvalidosException("El nombre de la categoría es requerido")
    
    nueva = CategoriaModel(nombre=data.nombre.strip())
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva

@router.get("/categorias", response_model=list[Categoria])
def listar_categorias(db: Session = Depends(get_db)):
    return db.query(CategoriaModel).all()

@router.get("/categorias/{id_categoria}", response_model=Categoria)
def obtener_categoria(id_categoria: int, db: Session = Depends(get_db)):
    categoria = db.query(CategoriaModel).filter(CategoriaModel.id_categoria == id_categoria).first()
    if not categoria:
        raise RecursoNoEncontradoException("Categoría no encontrada")
    return categoria

@router.put("/categorias/{id_categoria}", response_model=Categoria)
def actualizar_categoria(id_categoria: int, data: CategoriaUpdate, db: Session = Depends(get_db)):
    if not data.nombre or data.nombre.strip() == "":
        raise DatosInvalidosException("El nombre de la categoría es requerido")
    
    categoria = db.query(CategoriaModel).filter(CategoriaModel.id_categoria == id_categoria).first()
    if not categoria:
        raise RecursoNoEncontradoException("Categoría no encontrada")
    
    categoria.nombre = data.nombre.strip()
    db.commit()
    db.refresh(categoria)
    return categoria

@router.delete("/categorias/{id_categoria}")
def eliminar_categoria(id_categoria: int, db: Session = Depends(get_db)):
    categoria = db.query(CategoriaModel).filter(CategoriaModel.id_categoria == id_categoria).first()
    if not categoria:
        raise RecursoNoEncontradoException("Categoría no encontrada")
    
    db.delete(categoria)
    db.commit()
    return {"message": "Categoría eliminada correctamente"}


# ============================
# PRODUCTOS
# ============================
@router.post("/productos", response_model=Producto)
def crear_producto(data: ProductoCreate, db: Session = Depends(get_db)):
    if not data.nombre or data.nombre.strip() == "":
        raise DatosInvalidosException("El nombre del producto es requerido")
    
    if data.precio_venta <= 0:
        raise DatosInvalidosException("El precio de venta debe ser positivo")
    
    categoria = db.query(CategoriaModel).filter(CategoriaModel.id_categoria == data.id_categoria).first()
    if not categoria:
        raise RecursoNoEncontradoException("Categoría no encontrada")
    
    nuevo_producto = ProductoModel(
        nombre=data.nombre.strip(),
        id_categoria=data.id_categoria,
        precio_venta=data.precio_venta,
        activo=data.activo
    )
    db.add(nuevo_producto)
    db.commit()
    db.refresh(nuevo_producto)
    return nuevo_producto

@router.get("/productos", response_model=list[Producto])
def listar_productos(db: Session = Depends(get_db)):
    return db.query(ProductoModel).all()

@router.get("/productos/{id_producto}", response_model=Producto)
def obtener_producto(id_producto: int, db: Session = Depends(get_db)):
    producto = db.query(ProductoModel).filter(ProductoModel.id_producto == id_producto).first()
    if not producto:
        raise RecursoNoEncontradoException("Producto no encontrado")
    return producto

@router.put("/productos/{id_producto}", response_model=Producto)
def actualizar_producto(id_producto: int, data: ProductoUpdate, db: Session = Depends(get_db)):
    if not data.nombre or data.nombre.strip() == "":
        raise DatosInvalidosException("El nombre del producto es requerido")
    
    if data.precio_venta <= 0:
        raise DatosInvalidosException("El precio de venta debe ser positivo")
    
    producto = db.query(ProductoModel).filter(ProductoModel.id_producto == id_producto).first()
    if not producto:
        raise RecursoNoEncontradoException("Producto no encontrado")
    
    categoria = db.query(CategoriaModel).filter(CategoriaModel.id_categoria == data.id_categoria).first()
    if not categoria:
        raise RecursoNoEncontradoException("Categoría no encontrada")
    
    producto.nombre = data.nombre.strip()
    producto.id_categoria = data.id_categoria
    producto.precio_venta = data.precio_venta
    producto.activo = data.activo
    db.commit()
    db.refresh(producto)
    return producto

@router.delete("/productos/{id_producto}")
def eliminar_producto(id_producto: int, db: Session = Depends(get_db)):
    producto = db.query(ProductoModel).filter(ProductoModel.id_producto == id_producto).first()
    if not producto:
        raise RecursoNoEncontradoException("Producto no encontrado")
    
    db.delete(producto)
    db.commit()
    return {"message": "Producto eliminado correctamente"}


# ============================
# INSUMOS
# ============================
@router.post("/insumos", response_model=Insumo)
def crear_insumo(data: InsumoCreate, db: Session = Depends(get_db)):
    if not data.nombre or data.nombre.strip() == "":
        raise DatosInvalidosException("El nombre del insumo es requerido")
    
    if not data.unidad or data.unidad.strip() == "":
        raise DatosInvalidosException("La unidad del insumo es requerida")
    
    if data.stock_minimo < 0 or data.stock_actual < 0:
        raise DatosInvalidosException("Stock no puede ser negativo")
    
    nuevo_insumo = InsumoModel(
        nombre=data.nombre.strip(),
        unidad=data.unidad.strip(),
        stock_actual=data.stock_actual,
        stock_minimo=data.stock_minimo,
        costo_unitario=data.costo_unitario,
    )
    db.add(nuevo_insumo)
    db.commit()
    db.refresh(nuevo_insumo)
    return nuevo_insumo

@router.get("/insumos", response_model=list[Insumo])
def listar_insumos(db: Session = Depends(get_db)):
    return db.query(InsumoModel).all()

@router.get("/insumos/{id_insumo}", response_model=Insumo)
def obtener_insumo(id_insumo: int, db: Session = Depends(get_db)):
    insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == id_insumo).first()
    if not insumo:
        raise RecursoNoEncontradoException("Insumo no encontrado")
    return insumo

@router.put("/insumos/{id_insumo}", response_model=InsumoActualizado)
def actualizar_insumo(id_insumo: int, data: InsumoUpdate, db: Session = Depends(get_db)):
    if not data.nombre or data.nombre.strip() == "":
        raise DatosInvalidosException("El nombre del insumo es requerido")
    
    if not data.unidad or data.unidad.strip() == "":
        raise DatosInvalidosException("La unidad del insumo es requerida")
    
    if data.stock_minimo < 0 or data.stock_actual < 0:
        raise DatosInvalidosException("Stock no puede ser negativo")
    
    insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == id_insumo).first()
    if not insumo:
        raise RecursoNoEncontradoException("Insumo no encontrado")

    costo_anterior = float(insumo.costo_unitario or 0)
    costo_nuevo = float(data.costo_unitario or 0)
    
    insumo.nombre = data.nombre.strip()
    insumo.unidad = data.unidad.strip()
    insumo.stock_actual = data.stock_actual
    insumo.stock_minimo = data.stock_minimo
    insumo.costo_unitario = data.costo_unitario
    db.commit()
    db.refresh(insumo)

    productos_actualizados = 0
    if costo_anterior != costo_nuevo:
        resultado = RecetaService.actualizar_precios_productos_por_configuracion(db)
        db.commit()
        productos_actualizados = resultado["productos_precio_actualizados"]

    return InsumoActualizado(
        id_insumo=insumo.id_insumo,
        nombre=insumo.nombre,
        unidad=insumo.unidad,
        stock_actual=float(insumo.stock_actual),
        stock_minimo=float(insumo.stock_minimo),
        costo_unitario=float(insumo.costo_unitario) if insumo.costo_unitario is not None else None,
        productos_precio_actualizados=productos_actualizados,
    )

@router.delete("/insumos/{id_insumo}")
def eliminar_insumo(id_insumo: int, db: Session = Depends(get_db)):
    insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == id_insumo).first()
    if not insumo:
        raise RecursoNoEncontradoException("Insumo no encontrado")
    
    db.delete(insumo)
    db.commit()
    return {"message": "Insumo eliminado correctamente"}
