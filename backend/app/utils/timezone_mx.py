"""Hora y fechas del negocio (Ciudad de México)."""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

MX = ZoneInfo("America/Mexico_City")


def now_utc_naive() -> datetime:
    """Timestamp naive en UTC (consistente en Render y local)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today_mx() -> date:
    """Fecha calendario actual en México."""
    return datetime.now(MX).date()


def bounds_utc_naive_for_mx_date(d: date) -> tuple[datetime, datetime]:
    """
    Inicio y fin del día `d` en México, como datetimes naive UTC
    para comparar con fecha_hora guardada en UTC.
    """
    start_mx = datetime.combine(d, time.min, tzinfo=MX)
    end_mx = datetime.combine(d, time.max, tzinfo=MX)
    start_utc = start_mx.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_mx.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def filtro_dia_mx(column, d: date):
    """SQLAlchemy: columna datetime dentro del día `d` (hora México)."""
    start, end = bounds_utc_naive_for_mx_date(d)
    return column >= start, column <= end


def filtro_mes_mx(column, anio: int, mes: int):
    """SQLAlchemy: columna datetime dentro del mes calendario México."""
    from calendar import monthrange

    inicio, _ = bounds_utc_naive_for_mx_date(date(anio, mes, 1))
    ultimo = date(anio, mes, monthrange(anio, mes)[1])
    _, fin = bounds_utc_naive_for_mx_date(ultimo)
    return column >= inicio, column <= fin


def filtro_anio_mx(column, anio: int):
    """SQLAlchemy: columna datetime dentro del año calendario México."""
    inicio, _ = bounds_utc_naive_for_mx_date(date(anio, 1, 1))
    _, fin = bounds_utc_naive_for_mx_date(date(anio, 12, 31))
    return column >= inicio, column <= fin


def filtro_rango_mx(column, fecha_inicio: date, fecha_fin: date):
    """SQLAlchemy: columna datetime dentro del rango [fecha_inicio, fecha_fin] (MX)."""
    if fecha_fin < fecha_inicio:
        raise ValueError("fecha_fin debe ser >= fecha_inicio")
    inicio, _ = bounds_utc_naive_for_mx_date(fecha_inicio)
    _, fin = bounds_utc_naive_for_mx_date(fecha_fin)
    return column >= inicio, column <= fin


def isoformat_utc(dt: datetime | None) -> str | None:
    """Serializa datetime UTC naive con sufijo Z para el frontend."""
    if dt is None:
        return None
    return dt.isoformat() + "Z"


def fecha_mx_desde_utc_naive(dt: datetime) -> date:
    """Convierte timestamp UTC naive a fecha calendario México."""
    return dt.replace(tzinfo=timezone.utc).astimezone(MX).date()


def segundos_desde(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    return max(0, int((now_utc_naive() - dt).total_seconds()))
