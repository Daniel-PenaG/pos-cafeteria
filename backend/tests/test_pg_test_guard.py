"""La guarda de PostgreSQL de prueba no debe coincidir con DATABASE_URL."""
from tests.pg_test_guard import misma_base


def test_misma_base_ignora_driver_y_localhost():
    assert misma_base(
        "postgresql+psycopg2://u:p@localhost:5432/cafeteria_db",
        "postgresql://u:otro@127.0.0.1/cafeteria_db",
    )


def test_sqlite_no_es_la_misma_base_que_postgres():
    assert not misma_base(
        "postgresql+psycopg2://u@127.0.0.1:5432/pos_test",
        "sqlite:///:memory:",
    )


def test_bases_postgres_distintas_no_coinciden():
    assert not misma_base(
        "postgresql+psycopg2://u@127.0.0.1:5432/pos_test",
        "postgresql+psycopg2://u@127.0.0.1:5432/cafeteria_db",
    )
