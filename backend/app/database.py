from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def aplicar_migraciones_sqlite():
    """Agrega columnas nuevas en bases ya existentes (SQLite y PostgreSQL)."""
    dialect = engine.dialect.name
    migraciones_sqlite = [
        "ALTER TABLE ventas ADD COLUMN numero_mesa INTEGER DEFAULT 1",
        "ALTER TABLE detalle_venta ADD COLUMN extras_json VARCHAR(500)",
    ]
    migraciones_postgres = [
        "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS numero_mesa INTEGER DEFAULT 1",
        "ALTER TABLE detalle_venta ADD COLUMN IF NOT EXISTS extras_json VARCHAR(500)",
        """CREATE TABLE IF NOT EXISTS extras_venta (
            id_extra SERIAL PRIMARY KEY,
            nombre VARCHAR(150) NOT NULL,
            unidad VARCHAR(20),
            cantidad NUMERIC(12, 3) NOT NULL DEFAULT 1,
            costo_unitario NUMERIC(10, 4) NOT NULL DEFAULT 0,
            usar_precio_manual BOOLEAN DEFAULT FALSE,
            precio_personalizado NUMERIC(10, 2),
            precio NUMERIC(10, 2) NOT NULL,
            tipo VARCHAR(30) NOT NULL DEFAULT 'OTRO',
            activo BOOLEAN DEFAULT TRUE,
            id_insumo_origen INTEGER
        )""",
        "ALTER TABLE extras_venta ADD COLUMN IF NOT EXISTS unidad VARCHAR(20)",
        "ALTER TABLE extras_venta ADD COLUMN IF NOT EXISTS id_insumo_origen INTEGER",
        "ALTER TABLE extras_venta ADD COLUMN IF NOT EXISTS cantidad NUMERIC(12, 3) DEFAULT 1",
        "ALTER TABLE extras_venta ADD COLUMN IF NOT EXISTS costo_unitario NUMERIC(10, 4) DEFAULT 0",
        "ALTER TABLE extras_venta ADD COLUMN IF NOT EXISTS usar_precio_manual BOOLEAN DEFAULT FALSE",
        "ALTER TABLE extras_venta ADD COLUMN IF NOT EXISTS precio_personalizado NUMERIC(10, 2)",
        "UPDATE extras_venta SET cantidad = 1 WHERE cantidad IS NULL",
        "UPDATE extras_venta SET costo_unitario = precio WHERE costo_unitario IS NULL OR costo_unitario = 0",
        "ALTER TABLE categoria_extras ADD COLUMN IF NOT EXISTS id_extra INTEGER REFERENCES extras_venta(id_extra)",
        "ALTER TABLE categoria_extras DROP CONSTRAINT IF EXISTS categoria_extras_id_insumo_fkey",
        "ALTER TABLE categoria_extras DROP COLUMN IF EXISTS id_insumo",
    ]
    migraciones_sqlite_extras = [
        """CREATE TABLE IF NOT EXISTS extras_venta (
            id_extra INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre VARCHAR(150) NOT NULL,
            unidad VARCHAR(20),
            precio NUMERIC(10, 2) NOT NULL,
            tipo VARCHAR(30) NOT NULL DEFAULT 'OTRO',
            activo BOOLEAN DEFAULT 1,
            id_insumo_origen INTEGER,
            cantidad NUMERIC(12, 3) NOT NULL DEFAULT 1,
            costo_unitario NUMERIC(10, 4) NOT NULL DEFAULT 0,
            usar_precio_manual BOOLEAN DEFAULT 0,
            precio_personalizado NUMERIC(10, 2)
        )""",
        "ALTER TABLE extras_venta ADD COLUMN cantidad NUMERIC(12, 3) DEFAULT 1",
        "ALTER TABLE extras_venta ADD COLUMN costo_unitario NUMERIC(10, 4) DEFAULT 0",
        "ALTER TABLE extras_venta ADD COLUMN usar_precio_manual BOOLEAN DEFAULT 0",
        "ALTER TABLE extras_venta ADD COLUMN precio_personalizado NUMERIC(10, 2)",
        "ALTER TABLE categoria_extras ADD COLUMN id_extra INTEGER REFERENCES extras_venta(id_extra)",
    ]
    migraciones = (
        migraciones_postgres + migraciones_sqlite_extras
        if dialect == "postgresql"
        else migraciones_sqlite + migraciones_sqlite_extras
    )
    for sql in migraciones:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
