from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import RecetaModel, ProductoModel, InsumoModel
from app.schemas.recetas import RecetaCreate, Receta

router = APIRouter(prefix="/recetas", tags=["Recetas"])

# Crear receta
@router.post("/", response_model=Receta)
def crear_receta(data: RecetaCreate, db: Session = Depends(get_db)):

    producto = db.query(ProductoModel).filter(ProductoModel.id_producto == data.id_producto).first()
    if not producto:
        raise HTTPException(status_code=404, detail="El producto no existe")

    insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == data.id_insumo).first()
    if not insumo:
        raise HTTPException(status_code=404, detail="El insumo no existe")

    nueva = RecetaModel(
        id_producto=data.id_producto,
        id_insumo=data.id_insumo,
        cantidad_por_producto=data.cantidad_por_producto
    )

    db.add(nueva)
    db.commit()
    db.refresh(nueva)

    return nueva

# Listar recetas por producto
@router.get("/producto/{id_producto}", response_model=list[Receta])
def listar_recetas(id_producto: int, db: Session = Depends(get_db)):
    return db.query(RecetaModel).filter(RecetaModel.id_producto == id_producto).all()
