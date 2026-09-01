"""Formas de pago válidas y etiquetas de presentación."""
from __future__ import annotations

from app.exceptions import DatosInvalidosException

FORMAS_PAGO_VALIDAS = frozenset({"EFECTIVO", "TRANSFERENCIA", "TARJETA"})

ETIQUETAS_FORMA_PAGO = {
    "EFECTIVO": "Efectivo",
    "TRANSFERENCIA": "Transferencia",
    "TARJETA": "Terminal",
}


def normalizar_forma_pago(forma: str) -> str:
    fp = (forma or "").strip().upper()
    if fp not in FORMAS_PAGO_VALIDAS:
        raise DatosInvalidosException(
            f"Forma de pago inválida: '{forma}'. Use EFECTIVO, TRANSFERENCIA o TARJETA."
        )
    return fp


def etiqueta_forma_pago(forma: str | None) -> str:
    fp = (forma or "EFECTIVO").upper()
    return ETIQUETAS_FORMA_PAGO.get(fp, fp)


def bucket_forma_pago(forma: str | None) -> str:
    """Agrupa ventas históricas; desconocidos van a EFECTIVO (compatibilidad)."""
    fp = (forma or "EFECTIVO").upper()
    if fp in FORMAS_PAGO_VALIDAS:
        return fp
    return "EFECTIVO"


def agregar_por_forma_pago(ventas) -> dict:
    """Totales e importes por método desde iterable de VentaModel."""
    ventas_list = list(ventas)
    por_metodo = {
        "EFECTIVO": {"importe": 0.0, "cantidad": 0},
        "TRANSFERENCIA": {"importe": 0.0, "cantidad": 0},
        "TARJETA": {"importe": 0.0, "cantidad": 0},
    }
    total = 0.0
    for v in ventas_list:
        fp = bucket_forma_pago(v.forma_pago)
        monto = float(v.total or 0)
        por_metodo[fp]["importe"] += monto
        por_metodo[fp]["cantidad"] += 1
        total += monto
    for metodo in por_metodo:
        por_metodo[metodo]["importe"] = round(por_metodo[metodo]["importe"], 2)
    return {
        "total_general": round(total, 2),
        "num_ventas": len(ventas_list),
        "por_metodo": por_metodo,
        "total_efectivo": por_metodo["EFECTIVO"]["importe"],
        "total_transferencia": por_metodo["TRANSFERENCIA"]["importe"],
        "total_tarjeta": por_metodo["TARJETA"]["importe"],
        "num_efectivo": por_metodo["EFECTIVO"]["cantidad"],
        "num_transferencia": por_metodo["TRANSFERENCIA"]["cantidad"],
        "num_tarjeta": por_metodo["TARJETA"]["cantidad"],
    }
