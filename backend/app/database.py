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
    migraciones_promos = [
        """CREATE TABLE IF NOT EXISTS promociones (
            id_promocion SERIAL PRIMARY KEY,
            nombre VARCHAR(150) NOT NULL,
            descripcion VARCHAR(300),
            tipo VARCHAR(30) NOT NULL,
            valor NUMERIC(10, 2) NOT NULL,
            activa BOOLEAN DEFAULT TRUE,
            aplica_toda_tienda BOOLEAN DEFAULT FALSE,
            fecha_inicio TIMESTAMP,
            fecha_fin TIMESTAMP,
            hora_inicio VARCHAR(5),
            hora_fin VARCHAR(5),
            dias_semana VARCHAR(20),
            margen_minimo NUMERIC(5, 2)
        )""",
        """CREATE TABLE IF NOT EXISTS promocion_productos (
            id SERIAL PRIMARY KEY,
            id_promocion INTEGER NOT NULL REFERENCES promociones(id_promocion) ON DELETE CASCADE,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto)
        )""",
        """CREATE TABLE IF NOT EXISTS promocion_categorias (
            id SERIAL PRIMARY KEY,
            id_promocion INTEGER NOT NULL REFERENCES promociones(id_promocion) ON DELETE CASCADE,
            id_categoria INTEGER NOT NULL REFERENCES categorias(id_categoria)
        )""",
        "ALTER TABLE detalle_venta ADD COLUMN IF NOT EXISTS id_promocion INTEGER REFERENCES promociones(id_promocion)",
        "ALTER TABLE detalle_venta ADD COLUMN IF NOT EXISTS precio_original NUMERIC(10, 2)",
        "ALTER TABLE detalle_venta ADD COLUMN IF NOT EXISTS descuento_unitario NUMERIC(10, 2)",
        "ALTER TABLE detalle_venta ADD COLUMN IF NOT EXISTS costo_unitario_snapshot NUMERIC(10, 4)",
    ]
    migraciones_sqlite_promos = [
        """CREATE TABLE IF NOT EXISTS promociones (
            id_promocion INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre VARCHAR(150) NOT NULL,
            descripcion VARCHAR(300),
            tipo VARCHAR(30) NOT NULL,
            valor NUMERIC(10, 2) NOT NULL,
            activa BOOLEAN DEFAULT 1,
            aplica_toda_tienda BOOLEAN DEFAULT 0,
            fecha_inicio TIMESTAMP,
            fecha_fin TIMESTAMP,
            hora_inicio VARCHAR(5),
            hora_fin VARCHAR(5),
            dias_semana VARCHAR(20),
            margen_minimo NUMERIC(5, 2)
        )""",
        """CREATE TABLE IF NOT EXISTS promocion_productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_promocion INTEGER NOT NULL REFERENCES promociones(id_promocion),
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto)
        )""",
        """CREATE TABLE IF NOT EXISTS promocion_categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_promocion INTEGER NOT NULL REFERENCES promociones(id_promocion),
            id_categoria INTEGER NOT NULL REFERENCES categorias(id_categoria)
        )""",
        "ALTER TABLE detalle_venta ADD COLUMN id_promocion INTEGER REFERENCES promociones(id_promocion)",
        "ALTER TABLE detalle_venta ADD COLUMN precio_original NUMERIC(10, 2)",
        "ALTER TABLE detalle_venta ADD COLUMN descuento_unitario NUMERIC(10, 2)",
        "ALTER TABLE detalle_venta ADD COLUMN costo_unitario_snapshot NUMERIC(10, 4)",
    ]
    migraciones_fidelidad_pg = [
        """CREATE TABLE IF NOT EXISTS clientes (
            id_cliente SERIAL PRIMARY KEY,
            nombre VARCHAR(150) NOT NULL,
            telefono VARCHAR(20) NOT NULL UNIQUE,
            codigo_fidelidad VARCHAR(20) NOT NULL UNIQUE,
            puntos_saldo INTEGER NOT NULL DEFAULT 0,
            activo BOOLEAN DEFAULT TRUE,
            fecha_alta TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS fidelidad_movimientos (
            id_movimiento SERIAL PRIMARY KEY,
            id_cliente INTEGER NOT NULL REFERENCES clientes(id_cliente),
            tipo VARCHAR(30) NOT NULL,
            puntos INTEGER NOT NULL,
            saldo_despues INTEGER NOT NULL,
            id_venta INTEGER REFERENCES ventas(id_venta),
            notas VARCHAR(300),
            fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            id_usuario INTEGER REFERENCES usuarios(id_usuario)
        )""",
        """CREATE TABLE IF NOT EXISTS fidelidad_config (
            id SERIAL PRIMARY KEY,
            pesos_por_punto NUMERIC(10, 2) NOT NULL DEFAULT 10,
            minimo_compra_acumular NUMERIC(10, 2) NOT NULL DEFAULT 0,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS id_cliente INTEGER REFERENCES clientes(id_cliente)",
        "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS puntos_generados INTEGER DEFAULT 0",
    ]
    migraciones_fidelidad_sqlite = [
        """CREATE TABLE IF NOT EXISTS clientes (
            id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre VARCHAR(150) NOT NULL,
            telefono VARCHAR(20) NOT NULL UNIQUE,
            codigo_fidelidad VARCHAR(20) NOT NULL UNIQUE,
            puntos_saldo INTEGER NOT NULL DEFAULT 0,
            activo BOOLEAN DEFAULT 1,
            fecha_alta TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS fidelidad_movimientos (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER NOT NULL REFERENCES clientes(id_cliente),
            tipo VARCHAR(30) NOT NULL,
            puntos INTEGER NOT NULL,
            saldo_despues INTEGER NOT NULL,
            id_venta INTEGER REFERENCES ventas(id_venta),
            notas VARCHAR(300),
            fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            id_usuario INTEGER REFERENCES usuarios(id_usuario)
        )""",
        """CREATE TABLE IF NOT EXISTS fidelidad_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pesos_por_punto NUMERIC(10, 2) NOT NULL DEFAULT 10,
            minimo_compra_acumular NUMERIC(10, 2) NOT NULL DEFAULT 0,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        "ALTER TABLE ventas ADD COLUMN id_cliente INTEGER REFERENCES clientes(id_cliente)",
        "ALTER TABLE ventas ADD COLUMN puntos_generados INTEGER DEFAULT 0",
    ]
    migraciones_pedidos_pg = [
        """CREATE TABLE IF NOT EXISTS pedidos (
            id_pedido SERIAL PRIMARY KEY,
            numero_mesa INTEGER NOT NULL,
            estado VARCHAR(20) NOT NULL DEFAULT 'ABIERTO',
            id_cliente INTEGER REFERENCES clientes(id_cliente),
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            id_venta INTEGER REFERENCES ventas(id_venta),
            fecha_apertura TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_cierre TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS detalle_pedido (
            id_detalle_pedido SERIAL PRIMARY KEY,
            id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            nombre_producto VARCHAR(150) NOT NULL,
            cantidad NUMERIC(10, 2) NOT NULL,
            cantidad_lista NUMERIC(10, 2) NOT NULL DEFAULT 0,
            precio_unitario NUMERIC(10, 2) NOT NULL,
            precio_original NUMERIC(10, 2),
            descuento_unitario NUMERIC(10, 2),
            id_promocion INTEGER REFERENCES promociones(id_promocion),
            nombre_promocion VARCHAR(150),
            extras_json VARCHAR(500),
            en_comanda BOOLEAN DEFAULT TRUE,
            fecha_envio_comanda TIMESTAMP,
            line_key VARCHAR(120) NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_mesa_estado ON pedidos(numero_mesa, estado)",
    ]
    migraciones_pedidos_sqlite = [
        """CREATE TABLE IF NOT EXISTS pedidos (
            id_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_mesa INTEGER NOT NULL,
            estado VARCHAR(20) NOT NULL DEFAULT 'ABIERTO',
            id_cliente INTEGER REFERENCES clientes(id_cliente),
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            id_venta INTEGER REFERENCES ventas(id_venta),
            fecha_apertura TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fecha_cierre TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS detalle_pedido (
            id_detalle_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
            id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido),
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            nombre_producto VARCHAR(150) NOT NULL,
            cantidad NUMERIC(10, 2) NOT NULL,
            cantidad_lista NUMERIC(10, 2) NOT NULL DEFAULT 0,
            precio_unitario NUMERIC(10, 2) NOT NULL,
            precio_original NUMERIC(10, 2),
            descuento_unitario NUMERIC(10, 2),
            id_promocion INTEGER REFERENCES promociones(id_promocion),
            nombre_promocion VARCHAR(150),
            extras_json VARCHAR(500),
            en_comanda BOOLEAN DEFAULT 1,
            fecha_envio_comanda TIMESTAMP,
            line_key VARCHAR(120) NOT NULL
        )""",
    ]
    migraciones_comanda_tiempos_pg = [
        "ALTER TABLE detalle_pedido ADD COLUMN IF NOT EXISTS fecha_listo_comanda TIMESTAMP",
    ]
    migraciones_comanda_tiempos_sqlite = [
        "ALTER TABLE detalle_pedido ADD COLUMN fecha_listo_comanda TIMESTAMP",
    ]
    migraciones = (
        migraciones_postgres + migraciones_sqlite_extras + migraciones_promos
        + migraciones_fidelidad_pg + migraciones_pedidos_pg + migraciones_comanda_tiempos_pg
        if dialect == "postgresql"
        else migraciones_sqlite + migraciones_sqlite_extras + migraciones_sqlite_promos
        + migraciones_fidelidad_sqlite + migraciones_pedidos_sqlite + migraciones_comanda_tiempos_sqlite
    )
    for sql in migraciones:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception:
            pass

    normalizar_roles_usuarios()


def normalizar_roles_usuarios():
    """Corrige roles legacy en BD (admin → ADMIN, etc.)."""
    from app.models.models import UsuarioModel
    from app.constants.roles import normalizar_rol

    db = SessionLocal()
    try:
        cambio = False
        for usuario in db.query(UsuarioModel).all():
            rol_nuevo = normalizar_rol(usuario.rol)
            if rol_nuevo and rol_nuevo != usuario.rol:
                usuario.rol = rol_nuevo
                cambio = True
        if cambio:
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
