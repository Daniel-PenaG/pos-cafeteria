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
