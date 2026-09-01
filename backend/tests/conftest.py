"""Fixtures SQLite en memoria para pruebas de promociones y rendimiento."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("PERF_LOG_SQL", "1")
os.environ.setdefault("PERF_LOG", "1")

from app.database import Base, get_db
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


def _make_engine():
    return create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


engine = _make_engine()
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_perf_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        from tests.seed_perf import seed_perf_db

        seed_perf_db(db, num_ventas=40)
        db.commit()
    finally:
        db.close()
    yield
    engine.dispose()


def _uses_promo_seed(basename: str) -> bool:
    return basename.startswith(("test_promociones", "test_pagos", "test_comandera"))


@pytest.fixture()
def db_session(request):
    if _uses_promo_seed(request.node.fspath.basename):
        promo_engine = _make_engine()
        PromoSession = sessionmaker(autocommit=False, autoflush=False, bind=promo_engine)
        Base.metadata.create_all(bind=promo_engine)
        db = PromoSession()
        from tests.promo_seed import seed_promo_catalog

        refs = seed_promo_catalog(db)
        db.commit()
        db._promo_refs = refs  # type: ignore[attr-defined]
        try:
            yield db
        finally:
            db.close()
            promo_engine.dispose()
    else:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()


@pytest.fixture()
def refs(db_session):
    if not hasattr(db_session, "_promo_refs"):
        raise RuntimeError("Fixture refs requiere db_session con promo_seed")
    return db_session._promo_refs  # type: ignore[attr-defined]


@pytest.fixture()
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    res = client.post("/auth/login", json={"usuario_login": "admintest", "password": "test1234"})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
