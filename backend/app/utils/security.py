from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt
import os
import warnings
from dotenv import load_dotenv

from app.utils.config import is_production

load_dotenv()

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

SECRET_KEY = os.getenv("SECRET_KEY") or "cambia-esta-clave-en-local"
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

_WEAK_SECRET_KEYS = {
    "cambia-esta-clave-en-local",
    "secret",
    "changeme",
    "your-secret-key",
}


def validate_secret_key() -> None:
    key = SECRET_KEY or ""
    weak = len(key) < 32 or key.lower() in _WEAK_SECRET_KEYS
    if not weak:
        return

    msg = (
        "SECRET_KEY débil o ausente. En producción usa una clave de al menos 32 caracteres. "
        'Genera una con: python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )
    if is_production():
        raise RuntimeError(msg)
    warnings.warn(msg, stacklevel=2)


validate_secret_key()

# HASH DE LA CONTRASEÑA
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: int = ACCESS_TOKEN_EXPIRE_MINUTES):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
