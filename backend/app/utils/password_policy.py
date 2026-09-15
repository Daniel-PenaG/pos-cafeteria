PASSWORD_MIN_LENGTH = 8


def validar_password_nueva(password: str | None) -> str:
    """Valida contraseña nueva. No aplica a hashes existentes."""
    if password is None or not str(password):
        raise ValueError("La contraseña es obligatoria")
    if len(str(password)) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres")
    return str(password)
