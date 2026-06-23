from datetime import datetime


def segundos_entre(inicio: datetime | None, fin: datetime | None) -> int | None:
    if not inicio or not fin:
        return None
    return max(0, int((fin - inicio).total_seconds()))


def formatear_duracion(segundos: int | None) -> str:
    if segundos is None:
        return "—"
    m, s = divmod(segundos, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
