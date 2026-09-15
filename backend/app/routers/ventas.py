from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from app.constants.acciones import ORIGEN_VENTAS
from app.database import get_db
from app.exceptions import ConflictoOperacionException, DatosInvalidosException, RecursoNoEncontradoException
from app.models.models import PedidoModel, UsuarioModel
from app.schemas.ventas import VentaCreate, VentaResponse, ExtraVenta, ProductoContextoResponse
from app.services.extras_venta_service import extras_para_producto, extras_para_categoria
from app.services.producto_contexto_service import obtener_contexto_producto
from app.services.venta_service import registrar_venta
from app.utils.deps import get_current_user
from app.utils.identidad import id_usuario_autenticado
from app.utils.permisos import exigir_modulo_pedido, require_module

_mod_pos = Depends(require_module("/ventas", "/ventas-para-llevar"))

router = APIRouter(
    prefix="/ventas",
    tags=["Ventas"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/extras", response_model=List[ExtraVenta], dependencies=[_mod_pos])
def listar_extras_venta(
    id_producto: Optional[int] = None,
    id_categoria: Optional[int] = None,
    db: Session = Depends(get_db),
):
    if id_producto:
        return extras_para_producto(db, id_producto)
    if id_categoria:
        return extras_para_categoria(db, id_categoria)
    raise DatosInvalidosException("Indica id_producto o id_categoria")


@router.get(
    "/productos/{id_producto}/contexto",
    response_model=ProductoContextoResponse,
    dependencies=[_mod_pos],
)
def producto_contexto(id_producto: int, db: Session = Depends(get_db)):
    return obtener_contexto_producto(db, id_producto)


def _pedido_para_venta(db: Session, id_pedido: int) -> PedidoModel:
    pedido = db.query(PedidoModel).filter(PedidoModel.id_pedido == id_pedido).first()
    if not pedido:
        raise RecursoNoEncontradoException("Pedido no encontrado")
    return pedido


def _exigir_coherencia_pedido(data: VentaCreate, pedido: PedidoModel) -> None:
    if bool(data.para_llevar) != bool(pedido.para_llevar) or int(data.numero_mesa) != int(
        pedido.numero_mesa
    ):
        raise ConflictoOperacionException(
            "Los datos de la venta no coinciden con el pedido"
        )


@router.post("/", response_model=VentaResponse)
def registrar_venta_endpoint(
    data: VentaCreate,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    """Venta directa: origen siempre VENTAS. COMANDERA solo via POST /pedidos/{id}/cobrar."""
    data.origen_cobro = ORIGEN_VENTAS
    if data.id_pedido is not None:
        pedido = _pedido_para_venta(db, data.id_pedido)
        exigir_modulo_pedido(current, bool(pedido.para_llevar))
        _exigir_coherencia_pedido(data, pedido)
        data.para_llevar = bool(pedido.para_llevar)
        data.numero_mesa = int(pedido.numero_mesa)
    else:
        exigir_modulo_pedido(current, bool(data.para_llevar))
    data.id_usuario = id_usuario_autenticado(db, current, data.id_usuario, "ventas.registrar")
    return registrar_venta(db, data)
