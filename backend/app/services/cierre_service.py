from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import VentaModel, CierreCajaModel, UsuarioModel
from app.utils.timezone_mx import bounds_utc_naive_for_mx_date, today_mx, isoformat_utc, filtro_dia_mx, filtro_mes_mx, filtro_anio_mx
from app.exceptions import DatosInvalidosException, RecursoNoEncontradoException


def _filtro_dia_mx(fecha: date):
    inicio, fin = bounds_utc_naive_for_mx_date(fecha)
    return VentaModel.fecha_hora >= inicio, VentaModel.fecha_hora < fin


def _venta_resumen_item(v: VentaModel) -> dict:
    return {
        "id_venta": v.id_venta,
        "fecha_hora": isoformat_utc(v.fecha_hora),
        "total": float(v.total or 0),
        "forma_pago": (v.forma_pago or "EFECTIVO").upper(),
        "numero_mesa": int(v.numero_mesa) if v.numero_mesa is not None else 0,
        "para_llevar": bool(v.para_llevar),
    }


def resumen_ventas_usuario(
    db: Session, id_usuario: int, fecha: Optional[date] = None
) -> dict:
    hoy = fecha or today_mx()
    usuario = db.query(UsuarioModel).filter(UsuarioModel.id_usuario == id_usuario).first()
    if not usuario:
        raise RecursoNoEncontradoException("Usuario no encontrado")

    inicio, fin = _filtro_dia_mx(hoy)
    ventas = (
        db.query(VentaModel)
        .filter(
            VentaModel.id_usuario == id_usuario,
            VentaModel.fecha_hora >= inicio,
            VentaModel.fecha_hora < fin,
        )
        .order_by(VentaModel.fecha_hora.desc())
        .all()
    )

    totales = {"EFECTIVO": 0.0, "TARJETA": 0.0, "TRANSFERENCIA": 0.0}
    for v in ventas:
        fp = (v.forma_pago or "").upper()
        if fp in totales:
            totales[fp] += float(v.total)
        else:
            totales["EFECTIVO"] += float(v.total)

    total_ventas = sum(totales.values())
    cierre_existente = (
        db.query(CierreCajaModel)
        .filter(
            CierreCajaModel.id_usuario == id_usuario,
            CierreCajaModel.fecha == hoy,
        )
        .first()
    )

    return {
        "fecha": hoy,
        "id_usuario": id_usuario,
        "nombre_usuario": usuario.nombre,
        "usuario_login": usuario.usuario_login,
        "num_ventas": len(ventas),
        "total_ventas": round(total_ventas, 2),
        "total_efectivo": round(totales["EFECTIVO"], 2),
        "total_tarjeta": round(totales["TARJETA"], 2),
        "total_transferencia": round(totales["TRANSFERENCIA"], 2),
        "ya_cerrado": cierre_existente is not None,
        "cierre": _cierre_a_dict(cierre_existente) if cierre_existente else None,
        "ventas": [_venta_resumen_item(v) for v in ventas],
    }


def _cierre_a_dict(c: CierreCajaModel) -> dict:
    return {
        "id_cierre": c.id_cierre,
        "fecha": c.fecha,
        "id_usuario": c.id_usuario,
        "num_ventas": int(c.num_ventas or 0),
        "total_ventas": float(c.total_ventas or 0),
        "total_efectivo": float(c.total_efectivo or 0),
        "total_tarjeta": float(c.total_tarjeta or 0),
        "total_transferencia": float(c.total_transferencia or 0),
        "efectivo_contado": float(c.efectivo_contado or 0),
        "diferencia": float(c.diferencia or 0),
        "notas": c.notas,
        "fecha_hora_registro": c.fecha_hora_registro,
    }


def registrar_cierre(
    db: Session,
    id_usuario: int,
    efectivo_contado: float,
    notas: Optional[str] = None,
    fecha: Optional[date] = None,
) -> dict:
    hoy = fecha or today_mx()
    resumen = resumen_ventas_usuario(db, id_usuario, hoy)

    if resumen["ya_cerrado"]:
        raise DatosInvalidosException("Ya registraste el cierre de caja para este día")

    if efectivo_contado < 0:
        raise DatosInvalidosException("El efectivo contado no puede ser negativo")

    diferencia = round(float(efectivo_contado) - resumen["total_efectivo"], 2)

    from app.utils.timezone_mx import now_utc_naive

    cierre = CierreCajaModel(
        id_usuario=id_usuario,
        fecha=hoy,
        num_ventas=resumen["num_ventas"],
        total_ventas=resumen["total_ventas"],
        total_efectivo=resumen["total_efectivo"],
        total_tarjeta=resumen["total_tarjeta"],
        total_transferencia=resumen["total_transferencia"],
        efectivo_contado=efectivo_contado,
        diferencia=diferencia,
        notas=(notas or "").strip() or None,
        fecha_hora_registro=now_utc_naive(),
    )
    db.add(cierre)
    db.commit()
    db.refresh(cierre)
    return _cierre_a_dict(cierre)


def listar_cierres_dia(db: Session, fecha: Optional[date] = None) -> list:
    hoy = fecha or today_mx()
    cierres = (
        db.query(CierreCajaModel, UsuarioModel)
        .join(UsuarioModel, UsuarioModel.id_usuario == CierreCajaModel.id_usuario)
        .filter(CierreCajaModel.fecha == hoy)
        .order_by(CierreCajaModel.fecha_hora_registro.desc())
        .all()
    )
    return [
        {
            **_cierre_a_dict(c),
            "nombre_usuario": u.nombre,
            "usuario_login": u.usuario_login,
            "rol": u.rol,
        }
        for c, u in cierres
    ]
