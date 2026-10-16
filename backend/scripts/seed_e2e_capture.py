"""Seed desechable para capturas E2E (usuario/contraseña desde entorno)."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import ClienteModel
from app.utils.timezone_mx import now_utc_naive
from tests.seed_perf import seed_perf_db

PROD_HOST_PATTERNS = re.compile(
    r"(amazonaws|rds\.|neon\.tech|supabase\.co|railway\.app|render\.com|azure|cloud\.google|elephantsql|heroku)",
    re.I,
)


def _assert_safe_db_url(url: str) -> None:
    if not url:
        raise SystemExit("PERF_DATABASE_URL requerida")
    if url.startswith("sqlite:") and "memory" not in url:
        p = Path(url.replace("sqlite:///", "").split("?")[0])
        if p.name in ("test_pos.db", "test_pos_perf.db") or "test_pos" in p.name:
            raise SystemExit(f"Refusing to seed archivo SQLite de pruebas existente: {p}")
    low = url.lower()
    if PROD_HOST_PATTERNS.search(low):
        raise SystemExit("PERF_DATABASE_URL parece producción remota; abortando.")
    if "127.0.0.1" not in low and "localhost" not in low and ":memory:" not in low:
        raise SystemExit("PERF_DATABASE_URL debe ser local (127.0.0.1/localhost) o :memory:")


def main() -> int:
    login = (os.environ.get("CAPTURE_LOGIN") or os.environ.get("E2E_CAPTURE_LOGIN") or "").strip()
    password = (os.environ.get("CAPTURE_PASSWORD") or os.environ.get("E2E_CAPTURE_PASSWORD") or "").strip()
    if not login or not password:
        raise SystemExit("CAPTURE_LOGIN y CAPTURE_PASSWORD requeridos para seed E2E")

    url = os.environ.get("PERF_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    prod = (os.environ.get("DATABASE_URL") or "").strip()
    if prod and prod == url.strip():
        raise SystemExit("PERF_DATABASE_URL no puede ser igual a DATABASE_URL")

    _assert_safe_db_url(url)

    kw = {}
    if url.startswith("sqlite"):
        kw = {"connect_args": {"check_same_thread": False}}
    engine = create_engine(url, **kw)
    if not url.startswith("sqlite:///:memory:"):
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        seed_perf_db(db, num_ventas=30, admin_login=login, admin_password=password)
        from app.services.mesas_service import obtener_mesas

        obtener_mesas(db)
        db.add(
            ClienteModel(
                nombre="Cliente Captura E2E",
                telefono="5550009999",
                codigo_fidelidad="CAP-E2E-01",
                puntos_saldo=500,
                activo=True,
                fecha_alta=now_utc_naive(),
            )
        )
        db.commit()
    finally:
        db.close()
    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
