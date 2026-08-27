from typing import List

from sqlalchemy.orm import Session

from app.models import ExtraVentaModel, InsumoModel
from app.schemas.pedido import ExtraLineaPedido
from app.schemas.ventas import ExtraVentaLinea
from app.services.extras_precio import precio_desde_modelo
from app.services.extras_venta_service import extras_para_producto
from app.exceptions import DatosInvalidosException


def _ids_permitidos_producto(db: Session, id_producto: int) -> set[int]:
    return {e.id_extra for e in extras_para_producto(db, id_producto)}


def _normalizar_extra_model(
    db: Session, id_producto: int, extra: ExtraLineaPedido | ExtraVentaLinea
) -> dict:
    permitidos = _ids_permitidos_producto(db, id_producto)
    if extra.id_extra not in permitidos:
        raise DatosInvalidosException(
            f"El extra «{extra.nombre}» no está permitido para este producto"
        )

    model = (
        db.query(ExtraVentaModel)
        .filter(ExtraVentaModel.id_extra == extra.id_extra)
        .first()
    )
    if not model or not model.activo:
        raise DatosInvalidosException(f"El extra «{extra.nombre}» no está disponible")

    if not model.id_insumo_origen:
        raise DatosInvalidosException(
            f"El extra «{model.nombre}» no tiene insumo configurado. "
            "Configúralo en Extras de venta (importar desde insumo)."
        )

    insumo = (
        db.query(InsumoModel)
        .filter(InsumoModel.id_insumo == model.id_insumo_origen)
        .first()
    )
    if not insumo:
        raise DatosInvalidosException(
            f"El insumo del extra «{model.nombre}» ya no existe en inventario"
        )

    precio_esperado = precio_desde_modelo(model)
    if abs(float(extra.precio) - precio_esperado) > 0.02:
        raise DatosInvalidosException(
            f"Precio inválido para «{model.nombre}». "
            f"Esperado: {precio_esperado:.2f}, recibido: {float(extra.precio):.2f}"
        )

    cantidad_insumo = float(model.cantidad or 1)
    if cantidad_insumo <= 0:
        raise DatosInvalidosException(
            f"La cantidad de inventario del extra «{model.nombre}» debe ser mayor a 0"
        )

    costo_extra = round(float(model.costo_unitario or 0) * cantidad_insumo, 4)

    return {
        "id_extra": model.id_extra,
        "id_insumo": int(model.id_insumo_origen),
        "nombre": model.nombre,
        "precio": precio_esperado,
        "costo": costo_extra,
        "cantidad_insumo": cantidad_insumo,
    }


def validar_extras_producto(
    db: Session,
    id_producto: int,
    extras: List[ExtraLineaPedido] | List[ExtraVentaLinea],
) -> List[dict]:
    if not extras:
        return []
    return [_normalizar_extra_model(db, id_producto, ex) for ex in extras]


def extras_json_desde_normalizados(extras: List[dict]) -> str | None:
    import json

    if not extras:
        return None
    return json.dumps(extras, ensure_ascii=False)


def parsear_extras_json(extras_json: str | None) -> List[dict]:
    import json

    if not extras_json:
        return []
    try:
        data = json.loads(extras_json)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def extras_linea_desde_json(raw: List[dict]) -> List[ExtraVentaLinea]:
    lineas = []
    for e in raw:
        lineas.append(
            ExtraVentaLinea(
                id_extra=e["id_extra"],
                nombre=e["nombre"],
                precio=float(e["precio"]),
                id_insumo=e.get("id_insumo"),
                cantidad_insumo=float(e.get("cantidad_insumo") or 1),
            )
        )
    return lineas
