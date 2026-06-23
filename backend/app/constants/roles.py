ADMIN = "ADMIN"
CAJERO = "CAJERO"
COCINA = "COCINA"

ROLES_VALIDOS = [ADMIN, CAJERO, COCINA]

ROLES_LABELS = {
    ADMIN: "Administrador",
    CAJERO: "Cajero",
    COCINA: "Cocina",
}


def normalizar_rol(rol: str | None) -> str:
    """Unifica variantes legacy (admin, Admin, Administrador) al código canónico."""
    if not rol:
        return ""
    clave = rol.strip().upper()
    if clave in ROLES_VALIDOS:
        return clave
    lower = rol.strip().lower()
    if lower in ("admin", "administrador", "cafeteria admin"):
        return ADMIN
    if lower == "cajero":
        return CAJERO
    if lower == "cocina":
        return COCINA
    return clave
