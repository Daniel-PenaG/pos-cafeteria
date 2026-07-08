#!/usr/bin/env python3
"""
Genera el SQL para crear el primer administrador en PostgreSQL (Neon).

Uso (Windows):
  cd backend
  .\\install-deps.ps1
  .\\venv\\Scripts\\Activate.ps1
  python scripts/crear_admin.py --login admin --password "TuClaveSegura123"

Uso (Linux/macOS):
  cd backend
  python3 -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  python3 scripts/crear_admin.py --login admin --password "TuClaveSegura123"

Si en Windows ves WinError 5 / Acceso denegado en _cffi_backend*.pyd:
  cierra uvicorn/python, borra venv si hace falta y usa Python 3.12 + install-deps.ps1.
"""
from __future__ import annotations

import argparse
import sys

try:
    from passlib.context import CryptContext
except ImportError:
    print(
        "Falta passlib/argon2. En Windows: .\\install-deps.ps1\n"
        "En Linux/macOS: pip install -r requirements.txt\n"
        "Si WinError 5 en _cffi_backend: cierra Python/uvicorn, usa Python 3.12 y recrea el venv.",
        file=sys.stderr,
    )
    sys.exit(1)

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera SQL del primer usuario ADMIN")
    parser.add_argument("--nombre", default="Admin", help="Nombre visible")
    parser.add_argument("--login", default="admin", help="Usuario de login")
    parser.add_argument("--password", required=True, help="Contraseña (mín. 8 caracteres)")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("Error: usa una contraseña de al menos 8 caracteres.", file=sys.stderr)
        sys.exit(1)

    hashed = pwd_context.hash(args.password)
    login = args.login.replace("'", "''")
    nombre = args.nombre.replace("'", "''")

    print("-- Pega esto en el SQL Editor de Neon (después de schema.sql):\n")
    print(
        "INSERT INTO usuarios (nombre, usuario_login, hash_password, rol)\n"
        f"VALUES ('{nombre}', '{login}', '{hashed}', 'ADMIN');"
    )


if __name__ == "__main__":
    main()
