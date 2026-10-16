"""Elimina usuario sintético de captura (best-effort)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.models import UsuarioModel


def main() -> int:
    login = (os.environ.get("CAPTURE_LOGIN") or "").strip()
    url = os.environ.get("PERF_DATABASE_URL") or ""
    if not login or not url:
        return 0
    engine = create_engine(url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        row = db.query(UsuarioModel).filter(UsuarioModel.usuario_login == login).first()
        if row and login.startswith("capture_"):
            db.delete(row)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
