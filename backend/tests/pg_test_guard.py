"""Evita pruebas PostgreSQL destructivas contra DATABASE_URL o producción.

No imprime URLs ni credenciales.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse


def identidad_base(url: str) -> tuple | None:
    raw = (url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").split("+")[0].lower()
    if scheme in ("sqlite",):
        path = (parsed.path or "").replace("\\", "/").lower()
        return ("sqlite", path)
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "::1"):
        host = "127.0.0.1"
    port = parsed.port
    if port is None and scheme in ("postgres", "postgresql"):
        port = 5432
    dbname = (parsed.path or "").lstrip("/").split("?")[0]
    return (scheme, host, port, dbname)


def misma_base(url_a: str, url_b: str) -> bool:
    a = identidad_base(url_a)
    b = identidad_base(url_b)
    if a is None or b is None:
        return False
    return a == b


def exigir_postgres_desechable(test_url: str) -> None:
    import pytest

    ident = identidad_base(test_url)
    if ident is None:
        return
    if ident[0] not in ("postgres", "postgresql"):
        pytest.fail(
            "POSTGRES_TEST_URL debe apuntar a PostgreSQL desechable. "
            "No se muestran credenciales."
        )
    db_url = os.getenv("DATABASE_URL", "").strip()
    if misma_base(test_url, db_url):
        pytest.fail(
            "POSTGRES_TEST_URL no puede ser la misma base que DATABASE_URL. "
            "Usa una base PostgreSQL desechable. No se muestran credenciales."
        )
