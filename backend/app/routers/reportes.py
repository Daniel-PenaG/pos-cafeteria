from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, and_
from datetime import date
from typing import Optional

from app.database import get_db
from app.models.models import (
    VentaModel,
    DetalleVentaModel,
    ProductoModel,
    CategoriaModel,
    RecetaModel,
    RecetaInsumoModel,
    InsumoModel,
    DetallePedidoModel,
    PedidoModel,
    UsuarioModel,
    ClienteModel,
)
from app.services.comanda_tiempo_service import formatear_duracion, segundos_entre
from app.utils.deps import get_current_user, require_admin
from app.constants.roles import ADMIN, normalizar_rol

router = APIRouter(prefix="/reportes", tags=["Reportes"])

MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _productos_vendidos(db: Session, venta_ids: list[int]):
    if not venta_ids:
        return []

    detalles = (
        db.query(
            DetalleVentaModel.id_producto,
            func.sum(DetalleVentaModel.cantidad).label("cantidad"),
            func.sum(DetalleVentaModel.subtotal).label("subtotal"),
        )
        .filter(DetalleVentaModel.id_venta.in_(venta_ids))
        .group_by(DetalleVentaModel.id_producto)
        .all()
    )

    productos = []
    for d in detalles:
        producto = db.query(ProductoModel).filter(ProductoModel.id_producto == d.id_producto).first()
        if not producto:
            continue

        receta = db.query(RecetaModel).filter(
            RecetaModel.id_producto == producto.id_producto,
            RecetaModel.activo == True,
        ).first()

        costo_total = receta.costo_total if receta else 0
        precio_venta = float(producto.precio_venta)
        margen = precio_venta - float(costo_total)

        productos.append({
            "id_producto": producto.id_producto,
            "nombre": producto.nombre,
            "cantidad": float(d.cantidad),
            "subtotal": float(d.subtotal),
            "precio_venta": precio_venta,
            "costo_receta": float(costo_total),
            "margen_unitario": margen,
            "margen_total": margen * float(d.cantidad),
        })

    productos.sort(key=lambda p: (-p["cantidad"], -p["subtotal"]))
    return productos


def _productos_ranking(db: Session, filtro, orden: str = "cantidad"):
    query = (
        db.query(
            DetalleVentaModel.id_producto,
            func.sum(DetalleVentaModel.cantidad).label("cantidad"),
            func.sum(DetalleVentaModel.subtotal).label("subtotal"),
        )
        .join(VentaModel, VentaModel.id_venta == DetalleVentaModel.id_venta)
        .filter(filtro)
        .group_by(DetalleVentaModel.id_producto)
    )
    if orden == "subtotal":
        query = query.order_by(
            func.sum(DetalleVentaModel.subtotal).desc(),
            func.sum(DetalleVentaModel.cantidad).desc(),
        )
    else:
        query = query.order_by(
            func.sum(DetalleVentaModel.cantidad).desc(),
            func.sum(DetalleVentaModel.subtotal).desc(),
        )

    detalles = query.all()
    if not detalles:
        return [], 0, 0

    total_cantidad = sum(float(d.cantidad) for d in detalles)
    total_subtotal = sum(float(d.subtotal) for d in detalles)

    ranking = []
    for pos, d in enumerate(detalles, start=1):
        producto = (
            db.query(ProductoModel)
            .options()
            .filter(ProductoModel.id_producto == d.id_producto)
            .first()
        )
        if not producto:
            continue

        categoria = (
            db.query(CategoriaModel)
            .filter(CategoriaModel.id_categoria == producto.id_categoria)
            .first()
        )
        cant = float(d.cantidad)
        sub = float(d.subtotal)
        pct_base = total_subtotal if orden == "subtotal" else total_cantidad
        pct_val = sub if orden == "subtotal" else cant

        ranking.append({
            "posicion": pos,
            "id_producto": producto.id_producto,
            "nombre": producto.nombre,
            "categoria": categoria.nombre if categoria else None,
            "cantidad": cant,
            "subtotal": sub,
            "porcentaje": round((pct_val / pct_base * 100) if pct_base else 0, 1),
        })

    return ranking, total_cantidad, total_subtotal


def _tiempo_comanda_pedido(db: Session, pedido_id: int) -> dict:
    """Duración desde envío a comanda hasta que todas las líneas quedan listas."""
    lineas = (
        db.query(DetallePedidoModel)
        .filter(
            DetallePedidoModel.id_pedido == pedido_id,
            DetallePedidoModel.en_comanda == True,
            DetallePedidoModel.fecha_envio_comanda.isnot(None),
        )
        .all()
    )
    if not lineas:
        return {
            "estado": "no_aplica",
            "segundos": None,
            "texto": "—",
            "inicio": None,
            "fin": None,
        }

    inicios = [l.fecha_envio_comanda for l in lineas if l.fecha_envio_comanda]
    fines = [l.fecha_listo_comanda for l in lineas if l.fecha_listo_comanda]
    pendientes = any(l.fecha_listo_comanda is None for l in lineas)

    if pendientes or not inicios:
        return {
            "estado": "en_preparacion",
            "segundos": None,
            "texto": "En preparación",
            "inicio": min(inicios).isoformat() if inicios else None,
            "fin": None,
        }

    inicio = min(inicios)
    fin = max(fines)
    seg = segundos_entre(inicio, fin) or 0
    return {
        "estado": "completada",
        "segundos": seg,
        "texto": formatear_duracion(seg),
        "inicio": inicio.isoformat(),
        "fin": fin.isoformat(),
    }


def _mesa_label_venta(venta: VentaModel) -> str:
    if venta.para_llevar or venta.numero_mesa == 99:
        return "Para llevar"
    return f"Mesa {venta.numero_mesa}"


# ============================
# REPORTE DE VENTAS POR DÍA
# ============================
@router.get("/ventas-dia", dependencies=[Depends(require_admin)])
def ventas_por_dia(fecha: date, db: Session = Depends(get_db)):

    ventas = (
        db.query(VentaModel)
        .filter(func.date(VentaModel.fecha_hora) == fecha)
        .all()
    )

    if not ventas:
        return {
            "fecha": fecha,
            "total_dia": 0,
            "numero_ventas": 0,
            "productos": []
        }

    total_dia = sum(float(v.total) for v in ventas)
    venta_ids = [v.id_venta for v in ventas]
    productos = _productos_vendidos(db, venta_ids)

    return {
        "fecha": fecha,
        "total_dia": total_dia,
        "numero_ventas": len(ventas),
        "productos": productos
    }


# ============================
# CUENTAS POR CAJERO (DÍA)
# ============================
@router.get("/cuentas-por-cajero", dependencies=[Depends(require_admin)])
def cuentas_por_cajero(fecha: date, db: Session = Depends(get_db)):
    ventas = (
        db.query(VentaModel, UsuarioModel, ClienteModel)
        .join(UsuarioModel, UsuarioModel.id_usuario == VentaModel.id_usuario)
        .outerjoin(ClienteModel, ClienteModel.id_cliente == VentaModel.id_cliente)
        .filter(func.date(VentaModel.fecha_hora) == fecha)
        .order_by(VentaModel.fecha_hora)
        .all()
    )

    if not ventas:
        return {
            "fecha": fecha,
            "total_dia": 0,
            "numero_ventas": 0,
            "numero_cajeros": 0,
            "por_cajero": [],
        }

    total_dia = sum(float(v.total) for v, _, _ in ventas)
    por_usuario = {}

    for venta, usuario, cliente in ventas:
        uid = usuario.id_usuario
        if uid not in por_usuario:
            por_usuario[uid] = {
                "id_usuario": uid,
                "nombre": usuario.nombre,
                "usuario_login": usuario.usuario_login,
                "rol": normalizar_rol(usuario.rol),
                "numero_ventas": 0,
                "total": 0.0,
                "ventas": [],
            }

        entry = por_usuario[uid]
        entry["numero_ventas"] += 1
        entry["total"] += float(venta.total)

        if venta.para_llevar or venta.numero_mesa == 99:
            mesa_label = "Para llevar"
        else:
            mesa_label = f"Mesa {venta.numero_mesa}"

        entry["ventas"].append({
            "id_venta": venta.id_venta,
            "fecha_hora": venta.fecha_hora.isoformat(),
            "numero_mesa": venta.numero_mesa,
            "mesa_label": mesa_label,
            "para_llevar": bool(venta.para_llevar),
            "total": float(venta.total),
            "forma_pago": venta.forma_pago,
            "cliente_nombre": cliente.nombre if cliente else None,
            "puntos_generados": int(venta.puntos_generados or 0),
        })

    por_cajero = sorted(por_usuario.values(), key=lambda x: -x["total"])
    for cajero in por_cajero:
        cajero["porcentaje_dia"] = round(
            (cajero["total"] / total_dia * 100) if total_dia else 0,
            1,
        )
        cajero["ventas"].sort(key=lambda v: v["fecha_hora"], reverse=True)

    return {
        "fecha": fecha,
        "total_dia": total_dia,
        "numero_ventas": len(ventas),
        "numero_cajeros": len(por_cajero),
        "por_cajero": por_cajero,
    }


# ============================
# REPORTE DE VENTAS POR MES
# ============================
@router.get("/ventas-mes", dependencies=[Depends(require_admin)])
def ventas_por_mes(anio: int, mes: int, db: Session = Depends(get_db)):
    if mes < 1 or mes > 12:
        raise HTTPException(status_code=400, detail="Mes inválido")

    ventas = (
        db.query(VentaModel)
        .filter(
            extract("year", VentaModel.fecha_hora) == anio,
            extract("month", VentaModel.fecha_hora) == mes,
        )
        .all()
    )

    total_mes = sum(float(v.total) for v in ventas)
    venta_ids = [v.id_venta for v in ventas]

    desglose_dias = (
        db.query(
            func.date(VentaModel.fecha_hora).label("fecha"),
            func.coalesce(func.sum(VentaModel.total), 0).label("total"),
            func.count(VentaModel.id_venta).label("numero_ventas"),
        )
        .filter(
            extract("year", VentaModel.fecha_hora) == anio,
            extract("month", VentaModel.fecha_hora) == mes,
        )
        .group_by(func.date(VentaModel.fecha_hora))
        .order_by(func.date(VentaModel.fecha_hora))
        .all()
    )

    return {
        "anio": anio,
        "mes": mes,
        "nombre_mes": MESES[mes],
        "total_mes": float(total_mes),
        "numero_ventas": len(ventas),
        "desglose_dias": [
            {
                "fecha": str(r.fecha),
                "total": float(r.total),
                "numero_ventas": int(r.numero_ventas),
            }
            for r in desglose_dias
        ],
        "productos": _productos_vendidos(db, venta_ids),
    }


# ============================
# REPORTE DE VENTAS POR AÑO
# ============================
@router.get("/ventas-anio", dependencies=[Depends(require_admin)])
def ventas_por_anio(anio: int, db: Session = Depends(get_db)):
    ventas = (
        db.query(VentaModel)
        .filter(extract("year", VentaModel.fecha_hora) == anio)
        .all()
    )

    total_anio = sum(float(v.total) for v in ventas)
    venta_ids = [v.id_venta for v in ventas]

    desglose_meses = (
        db.query(
            extract("month", VentaModel.fecha_hora).label("mes"),
            func.coalesce(func.sum(VentaModel.total), 0).label("total"),
            func.count(VentaModel.id_venta).label("numero_ventas"),
        )
        .filter(extract("year", VentaModel.fecha_hora) == anio)
        .group_by(extract("month", VentaModel.fecha_hora))
        .order_by(extract("month", VentaModel.fecha_hora))
        .all()
    )

    return {
        "anio": anio,
        "total_anio": float(total_anio),
        "numero_ventas": len(ventas),
        "desglose_meses": [
            {
                "mes": int(r.mes),
                "nombre_mes": MESES[int(r.mes)],
                "total": float(r.total),
                "numero_ventas": int(r.numero_ventas),
            }
            for r in desglose_meses
        ],
        "productos": _productos_vendidos(db, venta_ids),
    }


# ============================
# RANKING DE PRODUCTOS VENDIDOS
# ============================
@router.get("/productos-ranking", dependencies=[Depends(require_admin)])
def productos_ranking(
    periodo: str,
    fecha: date | None = None,
    anio: int | None = None,
    mes: int | None = None,
    orden: str = "cantidad",
    db: Session = Depends(get_db),
):
    if periodo not in ("dia", "mes", "anio"):
        raise HTTPException(status_code=400, detail="Periodo inválido. Use: dia, mes, anio")
    if orden not in ("cantidad", "subtotal"):
        raise HTTPException(status_code=400, detail="Orden inválido. Use: cantidad, subtotal")

    if periodo == "dia":
        if not fecha:
            raise HTTPException(status_code=400, detail="Indica la fecha")
        filtro = func.date(VentaModel.fecha_hora) == fecha
        periodo_label = str(fecha)
    elif periodo == "mes":
        if not anio or not mes:
            raise HTTPException(status_code=400, detail="Indica año y mes")
        if mes < 1 or mes > 12:
            raise HTTPException(status_code=400, detail="Mes inválido")
        filtro = and_(
            extract("year", VentaModel.fecha_hora) == anio,
            extract("month", VentaModel.fecha_hora) == mes,
        )
        periodo_label = f"{MESES[mes]} {anio}"
    else:
        if not anio:
            raise HTTPException(status_code=400, detail="Indica el año")
        filtro = extract("year", VentaModel.fecha_hora) == anio
        periodo_label = str(anio)

    ranking, total_cantidad, total_subtotal = _productos_ranking(db, filtro, orden)

    num_ventas = (
        db.query(func.count(VentaModel.id_venta))
        .filter(filtro)
        .scalar()
    )

    return {
        "periodo": periodo,
        "periodo_label": periodo_label,
        "fecha": str(fecha) if fecha else None,
        "anio": anio,
        "mes": mes,
        "nombre_mes": MESES[mes] if mes else None,
        "orden": orden,
        "numero_ventas": int(num_ventas or 0),
        "total_unidades": float(total_cantidad),
        "total_ingresos": float(total_subtotal),
        "productos": ranking,
    }


# ============================
# REPORTE DE CONSUMO DE INSUMOS
# ============================
@router.get("/consumo-insumos", dependencies=[Depends(require_admin)])
def consumo_insumos(fecha: date, db: Session = Depends(get_db)):

    detalles = (
        db.query(
            DetalleVentaModel.id_producto,
            func.sum(DetalleVentaModel.cantidad).label("cantidad")
        )
        .join(VentaModel, VentaModel.id_venta == DetalleVentaModel.id_venta)
        .filter(func.date(VentaModel.fecha_hora) == fecha)
        .group_by(DetalleVentaModel.id_producto)
        .all()
    )

    consumo = []

    for d in detalles:
        receta = db.query(RecetaModel).filter(
            RecetaModel.id_producto == d.id_producto,
            RecetaModel.activo == True
        ).first()

        if not receta:
            continue

        receta_insumos = db.query(RecetaInsumoModel).filter(
            RecetaInsumoModel.id_receta == receta.id_receta
        ).all()

        for ri in receta_insumos:
            insumo = db.query(InsumoModel).filter(InsumoModel.id_insumo == ri.id_insumo).first()

            cantidad_total = float(ri.cantidad) * float(d.cantidad)

            consumo.append({
                "id_insumo": insumo.id_insumo,
                "nombre": insumo.nombre,
                "unidad": insumo.unidad,
                "cantidad_consumida": cantidad_total,
                "stock_actual": float(insumo.stock_actual),
                "stock_minimo": float(insumo.stock_minimo),
                "alerta": cantidad_total >= float(insumo.stock_actual)
            })

    return {
        "fecha": fecha,
        "consumo": consumo
    }


# ============================
# TIEMPOS DE PREPARACIÓN (COMANDERA)
# ============================
@router.get("/tiempos-preparacion", dependencies=[Depends(require_admin)])
def tiempos_preparacion_dia(fecha: date, db: Session = Depends(get_db)):
    lineas = (
        db.query(DetallePedidoModel, PedidoModel)
        .join(PedidoModel, PedidoModel.id_pedido == DetallePedidoModel.id_pedido)
        .filter(
            DetallePedidoModel.en_comanda == True,
            DetallePedidoModel.fecha_listo_comanda.isnot(None),
            DetallePedidoModel.fecha_envio_comanda.isnot(None),
            func.date(DetallePedidoModel.fecha_listo_comanda) == fecha,
        )
        .order_by(PedidoModel.numero_mesa, DetallePedidoModel.fecha_listo_comanda)
        .all()
    )

    if not lineas:
        return {
            "fecha": fecha,
            "promedio_general_segundos": 0,
            "promedio_general_texto": "0s",
            "por_mesa": [],
        }

    pedidos_map: dict[int, dict] = {}
    for detalle, pedido in lineas:
        pid = pedido.id_pedido
        if pid not in pedidos_map:
            pedidos_map[pid] = {
                "id_pedido": pid,
                "numero_mesa": pedido.numero_mesa,
                "lineas": [],
                "_inicios": [],
                "_fines": [],
            }

        seg = segundos_entre(detalle.fecha_envio_comanda, detalle.fecha_listo_comanda) or 0
        pedidos_map[pid]["lineas"].append({
            "nombre_producto": detalle.nombre_producto,
            "cantidad": float(detalle.cantidad),
            "inicio": detalle.fecha_envio_comanda.isoformat(),
            "fin": detalle.fecha_listo_comanda.isoformat(),
            "segundos": seg,
            "duracion_texto": formatear_duracion(seg),
        })
        pedidos_map[pid]["_inicios"].append(detalle.fecha_envio_comanda)
        pedidos_map[pid]["_fines"].append(detalle.fecha_listo_comanda)

    pedidos_list = []
    for ped in pedidos_map.values():
        inicio_ped = min(ped["_inicios"])
        fin_ped = max(ped["_fines"])
        seg_ped = segundos_entre(inicio_ped, fin_ped) or 0
        pedidos_list.append({
            "id_pedido": ped["id_pedido"],
            "numero_mesa": ped["numero_mesa"],
            "inicio": inicio_ped.isoformat(),
            "fin": fin_ped.isoformat(),
            "segundos_pedido": seg_ped,
            "duracion_pedido_texto": formatear_duracion(seg_ped),
            "num_lineas": len(ped["lineas"]),
            "lineas": ped["lineas"],
        })

    mesas_map: dict[int, list] = {}
    for ped in pedidos_list:
        mesas_map.setdefault(ped["numero_mesa"], []).append(ped)

    por_mesa = []
    todos_segundos = []
    for mesa in sorted(mesas_map.keys()):
        pedidos_mesa = mesas_map[mesa]
        segundos_mesa = [p["segundos_pedido"] for p in pedidos_mesa]
        promedio = sum(segundos_mesa) / len(segundos_mesa)
        todos_segundos.extend(segundos_mesa)
        por_mesa.append({
            "numero_mesa": mesa,
            "total_pedidos": len(pedidos_mesa),
            "promedio_segundos": round(promedio),
            "promedio_texto": formatear_duracion(round(promedio)),
            "max_segundos": max(segundos_mesa),
            "max_texto": formatear_duracion(max(segundos_mesa)),
            "pedidos": pedidos_mesa,
        })

    promedio_general = sum(todos_segundos) / len(todos_segundos)

    return {
        "fecha": fecha,
        "total_pedidos": len(pedidos_list),
        "promedio_general_segundos": round(promedio_general),
        "promedio_general_texto": formatear_duracion(round(promedio_general)),
        "por_mesa": por_mesa,
    }


@router.get("/resumen-dashboard")
def resumen_dashboard(
    fecha: Optional[date] = None,
    db: Session = Depends(get_db),
    current: UsuarioModel = Depends(get_current_user),
):
    hoy = fecha or date.today()
    es_admin = normalizar_rol(current.rol) == ADMIN

    total_hoy = (
        db.query(func.coalesce(func.sum(VentaModel.total), 0))
        .filter(func.date(VentaModel.fecha_hora) == hoy)
        .scalar()
    )

    num_ventas_hoy = (
        db.query(func.count(VentaModel.id_venta))
        .filter(func.date(VentaModel.fecha_hora) == hoy)
        .scalar()
    )

    if not es_admin:
        total_hoy = (
            db.query(func.coalesce(func.sum(VentaModel.total), 0))
            .filter(
                func.date(VentaModel.fecha_hora) == hoy,
                VentaModel.id_usuario == current.id_usuario,
            )
            .scalar()
        )
        num_ventas_hoy = (
            db.query(func.count(VentaModel.id_venta))
            .filter(
                func.date(VentaModel.fecha_hora) == hoy,
                VentaModel.id_usuario == current.id_usuario,
            )
            .scalar()
        )

    total_general = (
        db.query(func.coalesce(func.sum(VentaModel.total), 0))
        .scalar()
    )

    ventas_query = (
        db.query(VentaModel, UsuarioModel, ClienteModel)
        .join(UsuarioModel, UsuarioModel.id_usuario == VentaModel.id_usuario)
        .outerjoin(ClienteModel, ClienteModel.id_cliente == VentaModel.id_cliente)
        .filter(func.date(VentaModel.fecha_hora) == hoy)
        .order_by(VentaModel.fecha_hora.desc())
    )
    if not es_admin:
        ventas_query = ventas_query.filter(VentaModel.id_usuario == current.id_usuario)

    cuentas_hoy = []
    segundos_comanda = []
    for venta, usuario, cliente in ventas_query.all():
        pedido = (
            db.query(PedidoModel)
            .filter(PedidoModel.id_venta == venta.id_venta)
            .first()
        )
        if venta.para_llevar or not pedido:
            comanda = {
                "estado": "no_aplica",
                "segundos": None,
                "texto": "—",
                "inicio": None,
                "fin": None,
            }
        else:
            comanda = _tiempo_comanda_pedido(db, pedido.id_pedido)
            if comanda["estado"] == "completada" and comanda["segundos"] is not None:
                segundos_comanda.append(comanda["segundos"])

        cuentas_hoy.append({
            "id_venta": venta.id_venta,
            "fecha_hora": venta.fecha_hora.isoformat(),
            "mesa_label": _mesa_label_venta(venta),
            "para_llevar": bool(venta.para_llevar),
            "total": float(venta.total),
            "forma_pago": venta.forma_pago,
            "cajero_nombre": usuario.nombre,
            "cajero_login": usuario.usuario_login,
            "cliente_nombre": cliente.nombre if cliente else None,
            "comanda_estado": comanda["estado"],
            "comanda_inicio": comanda["inicio"],
            "comanda_fin": comanda["fin"],
            "comanda_segundos": comanda["segundos"],
            "comanda_texto": comanda["texto"],
        })

    comanda_promedio_segundos = (
        round(sum(segundos_comanda) / len(segundos_comanda))
        if segundos_comanda
        else 0
    )

    # Top 5 productos por ventas (histórico)
    top_productos = (
        db.query(
            DetalleVentaModel.id_producto,
            func.sum(DetalleVentaModel.cantidad).label("cantidad"),
            func.sum(DetalleVentaModel.subtotal).label("subtotal"),
        )
        .join(VentaModel, VentaModel.id_venta == DetalleVentaModel.id_venta)
        .group_by(DetalleVentaModel.id_producto)
        .order_by(func.sum(DetalleVentaModel.subtotal).desc())
        .limit(5)
        .all()
    )

    productos_data = []
    for p in top_productos:
        prod = db.query(ProductoModel).filter(ProductoModel.id_producto == p.id_producto).first()
        productos_data.append({
            "id_producto": prod.id_producto,
            "nombre": prod.nombre,
            "cantidad": float(p.cantidad),
            "subtotal": float(p.subtotal),
        })

    return {
        "hoy": str(hoy),
        "total_hoy": float(total_hoy),
        "num_ventas_hoy": int(num_ventas_hoy),
        "total_general": float(total_general),
        "top_productos": productos_data,
        "cuentas_hoy": cuentas_hoy,
        "comanda_promedio_segundos": comanda_promedio_segundos,
        "comanda_promedio_texto": formatear_duracion(comanda_promedio_segundos),
        "comanda_completadas_hoy": len(segundos_comanda),
    }
