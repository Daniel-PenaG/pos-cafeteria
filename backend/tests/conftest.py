"""Fixtures SQLite en memoria para pruebas de promociones."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")

from app.database import Base

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    from tests.promo_seed import seed_promo_catalog

    refs = seed_promo_catalog(db)
    db.commit()
    db._promo_refs = refs  # type: ignore[attr-defined]
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def refs(db_session):
    return db_session._promo_refs  # type: ignore[attr-defined]
