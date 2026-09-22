from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
import logging
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL no está configurada. "
        "Local: copia backend/.env.example a backend/.env. "
        "Producción (AWS EB): Configuration → Software → Environment properties."
    )

_engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300")),
            "pool_size": int(os.getenv("DB_POOL_SIZE", "3")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "2")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "15")),
        }
    )

engine = create_engine(DATABASE_URL, **_engine_kwargs)

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
        """CREATE TABLE IF NOT EXISTS producto_extras (
            id SERIAL PRIMARY KEY,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto) ON DELETE CASCADE,
            id_extra INTEGER NOT NULL REFERENCES extras_venta(id_extra) ON DELETE CASCADE,
            UNIQUE (id_producto, id_extra)
        )""",
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
        """CREATE TABLE IF NOT EXISTS producto_extras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_producto INTEGER NOT NULL REFERENCES productos(id_producto),
            id_extra INTEGER NOT NULL REFERENCES extras_venta(id_extra),
            UNIQUE (id_producto, id_extra)
        )""",
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
        "ALTER TABLE promociones ADD COLUMN IF NOT EXISTS cantidad_requerida INTEGER DEFAULT 1",
        "ALTER TABLE promociones ADD COLUMN IF NOT EXISTS limite_usos_por_ticket INTEGER",
        "ALTER TABLE promociones ADD COLUMN IF NOT EXISTS acumulable BOOLEAN DEFAULT FALSE",
        "ALTER TABLE promociones ADD COLUMN IF NOT EXISTS fecha_creacion TIMESTAMP",
        "ALTER TABLE detalle_venta ADD COLUMN IF NOT EXISTS nombre_promocion VARCHAR(150)",
        "ALTER TABLE detalle_venta ADD COLUMN IF NOT EXISTS tipo_promocion VARCHAR(30)",
        "ALTER TABLE detalle_venta ADD COLUMN IF NOT EXISTS valor_promocion NUMERIC(10, 2)",
        "ALTER TABLE detalle_venta ADD COLUMN IF NOT EXISTS promocion_aplicaciones INTEGER",
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
        "ALTER TABLE promociones ADD COLUMN cantidad_requerida INTEGER DEFAULT 1",
        "ALTER TABLE promociones ADD COLUMN limite_usos_por_ticket INTEGER",
        "ALTER TABLE promociones ADD COLUMN acumulable BOOLEAN DEFAULT 0",
        "ALTER TABLE promociones ADD COLUMN fecha_creacion TIMESTAMP",
        "ALTER TABLE detalle_venta ADD COLUMN nombre_promocion VARCHAR(150)",
        "ALTER TABLE detalle_venta ADD COLUMN tipo_promocion VARCHAR(30)",
        "ALTER TABLE detalle_venta ADD COLUMN valor_promocion NUMERIC(10, 2)",
        "ALTER TABLE detalle_venta ADD COLUMN promocion_aplicaciones INTEGER",
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
        "ALTER TABLE detalle_pedido ADD COLUMN IF NOT EXISTS comentario VARCHAR(300)",
    ]
    migraciones_comanda_tiempos_sqlite = [
        "ALTER TABLE detalle_pedido ADD COLUMN fecha_listo_comanda TIMESTAMP",
        "ALTER TABLE detalle_pedido ADD COLUMN comentario VARCHAR(300)",
    ]
    # Misma 002 que backend/migrations/002_pedido_operaciones.up.sql (idempotente).
    # No es una migración distinta: arranque aplica el esquema canónico si falta.
    migraciones_operaciones_pg = [
        "UPDATE pedidos SET para_llevar = FALSE WHERE para_llevar IS NULL",
        """CREATE TABLE IF NOT EXISTS pedido_operaciones (
            id_operacion SERIAL PRIMARY KEY,
            operation_id VARCHAR(64) NOT NULL,
            id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
            tipo VARCHAR(20) NOT NULL DEFAULT 'linea',
            payload_hash VARCHAR(64) NOT NULL DEFAULT '',
            id_detalle_pedido INTEGER REFERENCES detalle_pedido(id_detalle_pedido),
            detalle_ids_json VARCHAR(500),
            fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        "ALTER TABLE pedido_operaciones ADD COLUMN IF NOT EXISTS payload_hash VARCHAR(64) NOT NULL DEFAULT ''",
        "ALTER TABLE pedido_operaciones ADD COLUMN IF NOT EXISTS id_detalle_pedido INTEGER REFERENCES detalle_pedido(id_detalle_pedido)",
        "ALTER TABLE pedido_operaciones ADD COLUMN IF NOT EXISTS detalle_ids_json VARCHAR(500)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_pedido_operaciones_operation_id ON pedido_operaciones (operation_id)",
        "CREATE INDEX IF NOT EXISTS idx_pedido_operaciones_id_pedido ON pedido_operaciones (id_pedido)",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_pedidos_abierto_mesa
            ON pedidos (numero_mesa, para_llevar)
            WHERE estado = 'ABIERTO'""",
    ]
    migraciones_operaciones_sqlite = [
        """CREATE TABLE IF NOT EXISTS pedido_operaciones (
            id_operacion INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id VARCHAR(64) NOT NULL,
            id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido),
            tipo VARCHAR(20) NOT NULL DEFAULT 'linea',
            payload_hash VARCHAR(64) NOT NULL DEFAULT '',
            id_detalle_pedido INTEGER REFERENCES detalle_pedido(id_detalle_pedido),
            detalle_ids_json VARCHAR(500),
            fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        "ALTER TABLE pedido_operaciones ADD COLUMN payload_hash VARCHAR(64) DEFAULT ''",
        "ALTER TABLE pedido_operaciones ADD COLUMN id_detalle_pedido INTEGER REFERENCES detalle_pedido(id_detalle_pedido)",
        "ALTER TABLE pedido_operaciones ADD COLUMN detalle_ids_json VARCHAR(500)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_pedido_operaciones_operation_id ON pedido_operaciones (operation_id)",
        "CREATE INDEX IF NOT EXISTS idx_pedido_operaciones_id_pedido ON pedido_operaciones (id_pedido)",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_pedidos_abierto_mesa
            ON pedidos (numero_mesa, para_llevar)
            WHERE estado = 'ABIERTO'""",
    ]
    # Esquema nuevo: recetas (cabecera) + receta_insumos (detalle).
    # Producción puede tener aún id_insumo/cantidad en recetas (NOT NULL) → falla el INSERT.
    migraciones_recetas_pg = [
        "ALTER TABLE recetas ADD COLUMN IF NOT EXISTS nombre VARCHAR(150)",
        "ALTER TABLE recetas ADD COLUMN IF NOT EXISTS descripcion VARCHAR(300)",
        "ALTER TABLE recetas ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE",
        "ALTER TABLE recetas ADD COLUMN IF NOT EXISTS costo_total NUMERIC(12, 4) DEFAULT 0",
        """CREATE TABLE IF NOT EXISTS receta_insumos (
            id SERIAL PRIMARY KEY,
            id_receta INTEGER REFERENCES recetas(id_receta) ON DELETE CASCADE,
            id_insumo INTEGER REFERENCES insumos(id_insumo),
            cantidad NUMERIC(12, 3) NOT NULL
        )""",
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'recetas' AND column_name = 'id_insumo'
            ) THEN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'recetas' AND column_name = 'cantidad'
                ) THEN
                    INSERT INTO receta_insumos (id_receta, id_insumo, cantidad)
                    SELECT r.id_receta, r.id_insumo, COALESCE(NULLIF(r.cantidad, 0), 1)
                    FROM recetas r
                    WHERE r.id_insumo IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM receta_insumos ri
                          WHERE ri.id_receta = r.id_receta AND ri.id_insumo = r.id_insumo
                      );
                ELSIF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'recetas' AND column_name = 'cantidad_por_producto'
                ) THEN
                    INSERT INTO receta_insumos (id_receta, id_insumo, cantidad)
                    SELECT r.id_receta, r.id_insumo, COALESCE(NULLIF(r.cantidad_por_producto, 0), 1)
                    FROM recetas r
                    WHERE r.id_insumo IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM receta_insumos ri
                          WHERE ri.id_receta = r.id_receta AND ri.id_insumo = r.id_insumo
                      );
                ELSE
                    INSERT INTO receta_insumos (id_receta, id_insumo, cantidad)
                    SELECT r.id_receta, r.id_insumo, 1
                    FROM recetas r
                    WHERE r.id_insumo IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM receta_insumos ri
                          WHERE ri.id_receta = r.id_receta AND ri.id_insumo = r.id_insumo
                      );
                END IF;
            END IF;
        END $$;
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'recetas' AND column_name = 'nombre'
            ) THEN
                UPDATE recetas r
                SET nombre = COALESCE(NULLIF(r.nombre, ''), p.nombre, 'Receta')
                FROM productos p
                WHERE r.id_producto = p.id_producto
                  AND (r.nombre IS NULL OR r.nombre = '');
            END IF;
        END $$;
        """,
        "UPDATE recetas SET nombre = 'Receta' WHERE nombre IS NULL OR nombre = ''",
        "ALTER TABLE recetas ALTER COLUMN nombre SET DEFAULT 'Receta'",
        """
        DO $$
        DECLARE
            fk_name text;
        BEGIN
            FOR fk_name IN
                SELECT con.conname
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                WHERE rel.relname = 'recetas'
                  AND con.contype = 'f'
                  AND pg_get_constraintdef(con.oid) ILIKE '%id_insumo%'
            LOOP
                EXECUTE format('ALTER TABLE recetas DROP CONSTRAINT IF EXISTS %I', fk_name);
            END LOOP;
        END $$;
        """,
        "ALTER TABLE recetas DROP COLUMN IF EXISTS id_insumo",
        "ALTER TABLE recetas DROP COLUMN IF EXISTS cantidad",
        "ALTER TABLE recetas DROP COLUMN IF EXISTS cantidad_por_producto",
    ]
    migraciones_extra_tipos_pg = [
        """CREATE TABLE IF NOT EXISTS extra_tipos_pos (
            id_tipo SERIAL PRIMARY KEY,
            codigo VARCHAR(30) NOT NULL UNIQUE,
            etiqueta VARCHAR(80) NOT NULL,
            orden INTEGER NOT NULL DEFAULT 0
        )""",
    ]
    migraciones_extra_tipos_sqlite = [
        """CREATE TABLE IF NOT EXISTS extra_tipos_pos (
            id_tipo INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo VARCHAR(30) NOT NULL UNIQUE,
            etiqueta VARCHAR(80) NOT NULL,
            orden INTEGER NOT NULL DEFAULT 0
        )""",
    ]
    migraciones_para_llevar_pg = [
        "ALTER TABLE productos ADD COLUMN IF NOT EXISTS para_llevar BOOLEAN DEFAULT FALSE",
        "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS para_llevar BOOLEAN DEFAULT FALSE",
        "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS para_llevar BOOLEAN DEFAULT FALSE",
        "UPDATE productos SET para_llevar = TRUE WHERE activo = TRUE AND (para_llevar IS NULL OR para_llevar = FALSE)",
    ]
    migraciones_para_llevar_sqlite = [
        "ALTER TABLE productos ADD COLUMN para_llevar BOOLEAN DEFAULT 0",
        "ALTER TABLE pedidos ADD COLUMN para_llevar BOOLEAN DEFAULT 0",
        "ALTER TABLE ventas ADD COLUMN para_llevar BOOLEAN DEFAULT 0",
        "UPDATE productos SET para_llevar = 1 WHERE activo = 1",
    ]
    migraciones_mesas_pg = [
        "ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS mesas_json TEXT",
    ]
    migraciones_mesas_sqlite = [
        "ALTER TABLE configuracion ADD COLUMN mesas_json TEXT",
    ]
    migraciones_cierres_modulos_pg = [
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS modulos_json TEXT",
        """CREATE TABLE IF NOT EXISTS cierres_caja (
            id_cierre SERIAL PRIMARY KEY,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            fecha DATE NOT NULL,
            num_ventas INTEGER NOT NULL DEFAULT 0,
            total_ventas NUMERIC(12, 2) NOT NULL DEFAULT 0,
            total_efectivo NUMERIC(12, 2) NOT NULL DEFAULT 0,
            total_tarjeta NUMERIC(12, 2) NOT NULL DEFAULT 0,
            total_transferencia NUMERIC(12, 2) NOT NULL DEFAULT 0,
            efectivo_contado NUMERIC(12, 2) NOT NULL DEFAULT 0,
            diferencia NUMERIC(12, 2) NOT NULL DEFAULT 0,
            notas VARCHAR(500),
            fecha_hora_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_cierres_usuario_fecha ON cierres_caja(id_usuario, fecha)",
    ]
    migraciones_cierres_modulos_sqlite = [
        "ALTER TABLE usuarios ADD COLUMN modulos_json TEXT",
        """CREATE TABLE IF NOT EXISTS cierres_caja (
            id_cierre INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            fecha DATE NOT NULL,
            num_ventas INTEGER NOT NULL DEFAULT 0,
            total_ventas NUMERIC(12, 2) NOT NULL DEFAULT 0,
            total_efectivo NUMERIC(12, 2) NOT NULL DEFAULT 0,
            total_tarjeta NUMERIC(12, 2) NOT NULL DEFAULT 0,
            total_transferencia NUMERIC(12, 2) NOT NULL DEFAULT 0,
            efectivo_contado NUMERIC(12, 2) NOT NULL DEFAULT 0,
            diferencia NUMERIC(12, 2) NOT NULL DEFAULT 0,
            notas VARCHAR(500),
            fecha_hora_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_cierres_usuario_fecha ON cierres_caja(id_usuario, fecha)",
    ]
    # Misma 003 que backend/migrations/003_usuarios_permisos_auditoria.up.sql
    migraciones_seguridad_pg = [
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS permisos_acciones_json TEXT",
        "UPDATE usuarios SET activo = TRUE WHERE activo IS NULL",
        "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS origen_cobro VARCHAR(20)",
        """CREATE TABLE IF NOT EXISTS auditoria (
            id_auditoria SERIAL PRIMARY KEY,
            id_usuario INTEGER REFERENCES usuarios(id_usuario),
            usuario_login_intentado VARCHAR(80),
            accion VARCHAR(40) NOT NULL,
            entidad VARCHAR(40),
            entidad_id INTEGER,
            detalles_json VARCHAR(2000),
            origen VARCHAR(40),
            fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ip VARCHAR(64),
            user_agent VARCHAR(300)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria (fecha_hora)",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_accion ON auditoria (accion)",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria (id_usuario)",
        """CREATE TABLE IF NOT EXISTS login_bloqueos (
            id SERIAL PRIMARY KEY,
            usuario_login VARCHAR(80) NOT NULL,
            ip VARCHAR(64) NOT NULL DEFAULT '',
            intentos INTEGER NOT NULL DEFAULT 0,
            bloqueado_hasta TIMESTAMP,
            actualizado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_login_bloqueos_usuario_ip ON login_bloqueos (usuario_login, ip)",
    ]
    migraciones_seguridad_sqlite = [
        "ALTER TABLE usuarios ADD COLUMN activo BOOLEAN DEFAULT 1",
        "ALTER TABLE usuarios ADD COLUMN permisos_acciones_json TEXT",
        "ALTER TABLE ventas ADD COLUMN origen_cobro VARCHAR(20)",
        """CREATE TABLE IF NOT EXISTS auditoria (
            id_auditoria INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario INTEGER REFERENCES usuarios(id_usuario),
            usuario_login_intentado VARCHAR(80),
            accion VARCHAR(40) NOT NULL,
            entidad VARCHAR(40),
            entidad_id INTEGER,
            detalles_json VARCHAR(2000),
            origen VARCHAR(40),
            fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ip VARCHAR(64),
            user_agent VARCHAR(300)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria (fecha_hora)",
        """CREATE TABLE IF NOT EXISTS login_bloqueos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_login VARCHAR(80) NOT NULL,
            ip VARCHAR(64) NOT NULL DEFAULT '',
            intentos INTEGER NOT NULL DEFAULT 0,
            bloqueado_hasta TIMESTAMP,
            actualizado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_login_bloqueos_usuario_ip ON login_bloqueos (usuario_login, ip)",
    ]
    # Misma 004 que backend/migrations/004_cancelacion_lineas.up.sql
    migraciones_cancelacion_pg = [
        "ALTER TABLE detalle_pedido ADD COLUMN IF NOT EXISTS estado_linea VARCHAR(20) NOT NULL DEFAULT 'ACTIVA'",
        "ALTER TABLE detalle_pedido ADD COLUMN IF NOT EXISTS cantidad_cancelada NUMERIC(10, 2) NOT NULL DEFAULT 0",
        "UPDATE detalle_pedido SET estado_linea = 'ACTIVA' WHERE estado_linea IS NULL",
        "UPDATE detalle_pedido SET cantidad_cancelada = 0 WHERE cantidad_cancelada IS NULL",
        """CREATE TABLE IF NOT EXISTS pedido_cancelaciones (
            id_cancelacion SERIAL PRIMARY KEY,
            id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido),
            id_detalle_pedido INTEGER NOT NULL REFERENCES detalle_pedido(id_detalle_pedido),
            cantidad NUMERIC(10, 2) NOT NULL,
            cantidad_anterior NUMERIC(10, 2) NOT NULL,
            cantidad_nueva NUMERIC(10, 2) NOT NULL,
            motivo VARCHAR(80) NOT NULL,
            motivo_detalle VARCHAR(300),
            estado_anterior VARCHAR(20) NOT NULL,
            estado_nuevo VARCHAR(20) NOT NULL,
            aviso VARCHAR(40) NOT NULL,
            aviso_texto VARCHAR(80) NOT NULL,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            vista_comandera BOOLEAN NOT NULL DEFAULT FALSE,
            fecha_vista TIMESTAMP,
            id_usuario_vista INTEGER REFERENCES usuarios(id_usuario)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_cancelaciones_pedido ON pedido_cancelaciones (id_pedido)",
        "CREATE INDEX IF NOT EXISTS idx_cancelaciones_detalle ON pedido_cancelaciones (id_detalle_pedido)",
        "CREATE INDEX IF NOT EXISTS idx_cancelaciones_vista ON pedido_cancelaciones (vista_comandera)",
    ]
    migraciones_cancelacion_sqlite = [
        "ALTER TABLE detalle_pedido ADD COLUMN estado_linea VARCHAR(20) DEFAULT 'ACTIVA'",
        "ALTER TABLE detalle_pedido ADD COLUMN cantidad_cancelada NUMERIC(10, 2) DEFAULT 0",
        """CREATE TABLE IF NOT EXISTS pedido_cancelaciones (
            id_cancelacion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido),
            id_detalle_pedido INTEGER NOT NULL REFERENCES detalle_pedido(id_detalle_pedido),
            cantidad NUMERIC(10, 2) NOT NULL,
            cantidad_anterior NUMERIC(10, 2) NOT NULL,
            cantidad_nueva NUMERIC(10, 2) NOT NULL,
            motivo VARCHAR(80) NOT NULL,
            motivo_detalle VARCHAR(300),
            estado_anterior VARCHAR(20) NOT NULL,
            estado_nuevo VARCHAR(20) NOT NULL,
            aviso VARCHAR(40) NOT NULL,
            aviso_texto VARCHAR(80) NOT NULL,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            vista_comandera INTEGER NOT NULL DEFAULT 0,
            fecha_vista TIMESTAMP,
            id_usuario_vista INTEGER REFERENCES usuarios(id_usuario)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_cancelaciones_pedido ON pedido_cancelaciones (id_pedido)",
        "CREATE INDEX IF NOT EXISTS idx_cancelaciones_detalle ON pedido_cancelaciones (id_detalle_pedido)",
    ]
    # Misma 005 que backend/migrations/005_cierre_caja_conciliacion.up.sql (SQLite sin equivalencia de FOR UPDATE)
    migraciones_caja_pg = [
        "ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS tolerancia_efectivo NUMERIC(10, 2) NOT NULL DEFAULT 5",
        "UPDATE configuracion SET tolerancia_efectivo = 5 WHERE tolerancia_efectivo IS NULL",
        """CREATE TABLE IF NOT EXISTS sesiones_caja (
            id_sesion_caja SERIAL PRIMARY KEY,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            terminal VARCHAR(40) NOT NULL,
            estado VARCHAR(30) NOT NULL DEFAULT 'ABIERTA',
            fondo_inicial NUMERIC(12, 2) NOT NULL DEFAULT 0,
            observacion_apertura VARCHAR(500),
            fecha_apertura TIMESTAMP NOT NULL,
            fecha_inicio_arqueo TIMESTAMP,
            fecha_cierre TIMESTAMP,
            id_usuario_cierre INTEGER REFERENCES usuarios(id_usuario),
            esperado_efectivo NUMERIC(12, 2),
            esperado_transferencia NUMERIC(12, 2),
            esperado_tarjeta NUMERIC(12, 2),
            declarado_efectivo NUMERIC(12, 2),
            declarado_transferencia NUMERIC(12, 2),
            declarado_tarjeta NUMERIC(12, 2),
            diferencia_efectivo NUMERIC(12, 2),
            diferencia_transferencia NUMERIC(12, 2),
            diferencia_tarjeta NUMERIC(12, 2),
            ventas_total NUMERIC(12, 2),
            num_ventas INTEGER,
            ref_terminal VARCHAR(80),
            lote_terminal VARCHAR(80),
            ref_transferencia VARCHAR(80),
            observacion_cierre VARCHAR(500),
            id_usuario_revision INTEGER REFERENCES usuarios(id_usuario),
            fecha_revision TIMESTAMP,
            motivo_anulacion VARCHAR(500),
            forzado BOOLEAN NOT NULL DEFAULT FALSE,
            operation_id VARCHAR(64) NOT NULL,
            captura_directa BOOLEAN NOT NULL DEFAULT FALSE
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_sesion_caja_operation_id ON sesiones_caja (operation_id)",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_sesion_caja_usuario_activa
            ON sesiones_caja (id_usuario) WHERE estado IN ('ABIERTA', 'EN_ARQUEO')""",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_sesion_caja_terminal_activa
            ON sesiones_caja (terminal) WHERE estado IN ('ABIERTA', 'EN_ARQUEO')""",
        "CREATE INDEX IF NOT EXISTS idx_sesiones_caja_estado ON sesiones_caja (estado)",
        "CREATE INDEX IF NOT EXISTS idx_sesiones_caja_usuario ON sesiones_caja (id_usuario)",
        "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS id_sesion_caja INTEGER REFERENCES sesiones_caja(id_sesion_caja)",
        "CREATE INDEX IF NOT EXISTS idx_ventas_sesion_caja ON ventas (id_sesion_caja)",
        "ALTER TABLE cierres_caja ADD COLUMN IF NOT EXISTS id_sesion_caja INTEGER REFERENCES sesiones_caja(id_sesion_caja)",
        "DROP INDEX IF EXISTS idx_cierres_usuario_fecha",
        "CREATE INDEX IF NOT EXISTS idx_cierres_usuario_fecha ON cierres_caja (id_usuario, fecha)",
        """CREATE TABLE IF NOT EXISTS movimientos_caja (
            id_movimiento SERIAL PRIMARY KEY,
            id_sesion_caja INTEGER NOT NULL REFERENCES sesiones_caja(id_sesion_caja),
            tipo VARCHAR(30) NOT NULL,
            importe NUMERIC(12, 2) NOT NULL,
            metodo VARCHAR(30) NOT NULL DEFAULT 'EFECTIVO',
            motivo VARCHAR(200) NOT NULL,
            referencia VARCHAR(80),
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            fecha_hora TIMESTAMP NOT NULL,
            estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVO',
            id_movimiento_reverso INTEGER REFERENCES movimientos_caja(id_movimiento),
            id_gasto INTEGER REFERENCES gastos(id_gasto),
            operation_id VARCHAR(64) NOT NULL
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_movimiento_caja_operation_id ON movimientos_caja (operation_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_movimiento_caja_gasto ON movimientos_caja (id_gasto) WHERE id_gasto IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_movimientos_caja_sesion ON movimientos_caja (id_sesion_caja)",
        """CREATE TABLE IF NOT EXISTS arqueo_denominaciones (
            id_denominacion SERIAL PRIMARY KEY,
            id_sesion_caja INTEGER NOT NULL REFERENCES sesiones_caja(id_sesion_caja),
            codigo VARCHAR(10) NOT NULL,
            valor NUMERIC(10, 2) NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            UNIQUE (id_sesion_caja, codigo)
        )""",
        """CREATE TABLE IF NOT EXISTS venta_pagos (
            id_pago SERIAL PRIMARY KEY,
            id_venta INTEGER NOT NULL REFERENCES ventas(id_venta),
            metodo VARCHAR(30) NOT NULL,
            importe_monetario NUMERIC(12, 2) NOT NULL,
            cantidad_puntos INTEGER,
            equivalencia_puntos NUMERIC(12, 2),
            referencia VARCHAR(80),
            fecha_hora TIMESTAMP NOT NULL,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            id_sesion_caja INTEGER REFERENCES sesiones_caja(id_sesion_caja),
            operation_id VARCHAR(64) NOT NULL
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_venta_pago_operation_id ON venta_pagos (operation_id)",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_venta_pago_backfill ON venta_pagos (id_venta)
            WHERE operation_id LIKE 'backfill-venta-%'""",
        "CREATE INDEX IF NOT EXISTS idx_venta_pagos_venta ON venta_pagos (id_venta)",
        """INSERT INTO venta_pagos (
            id_venta, metodo, importe_monetario, fecha_hora, id_usuario, id_sesion_caja, operation_id
        )
        SELECT
            v.id_venta,
            CASE
                WHEN v.forma_pago IS NULL OR btrim(v.forma_pago) = '' THEN 'EFECTIVO'
                WHEN upper(v.forma_pago) IN ('EFECTIVO', 'TRANSFERENCIA', 'TARJETA') THEN upper(v.forma_pago)
                ELSE 'DESCONOCIDO'
            END,
            v.total,
            v.fecha_hora,
            v.id_usuario,
            v.id_sesion_caja,
            'backfill-venta-' || v.id_venta::text
        FROM ventas v
        WHERE NOT EXISTS (
            SELECT 1 FROM venta_pagos p
            WHERE p.operation_id = 'backfill-venta-' || v.id_venta::text
        )""",
    ]
    migraciones_caja_sqlite = [
        "ALTER TABLE configuracion ADD COLUMN tolerancia_efectivo NUMERIC(10, 2) DEFAULT 5",
        """CREATE TABLE IF NOT EXISTS sesiones_caja (
            id_sesion_caja INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            terminal VARCHAR(40) NOT NULL,
            estado VARCHAR(30) NOT NULL DEFAULT 'ABIERTA',
            fondo_inicial NUMERIC(12, 2) NOT NULL DEFAULT 0,
            observacion_apertura VARCHAR(500),
            fecha_apertura TIMESTAMP NOT NULL,
            fecha_inicio_arqueo TIMESTAMP,
            fecha_cierre TIMESTAMP,
            id_usuario_cierre INTEGER REFERENCES usuarios(id_usuario),
            esperado_efectivo NUMERIC(12, 2),
            esperado_transferencia NUMERIC(12, 2),
            esperado_tarjeta NUMERIC(12, 2),
            declarado_efectivo NUMERIC(12, 2),
            declarado_transferencia NUMERIC(12, 2),
            declarado_tarjeta NUMERIC(12, 2),
            diferencia_efectivo NUMERIC(12, 2),
            diferencia_transferencia NUMERIC(12, 2),
            diferencia_tarjeta NUMERIC(12, 2),
            ventas_total NUMERIC(12, 2),
            num_ventas INTEGER,
            ref_terminal VARCHAR(80),
            lote_terminal VARCHAR(80),
            ref_transferencia VARCHAR(80),
            observacion_cierre VARCHAR(500),
            id_usuario_revision INTEGER REFERENCES usuarios(id_usuario),
            fecha_revision TIMESTAMP,
            motivo_anulacion VARCHAR(500),
            forzado INTEGER NOT NULL DEFAULT 0,
            operation_id VARCHAR(64) NOT NULL,
            captura_directa INTEGER NOT NULL DEFAULT 0
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_sesion_caja_operation_id ON sesiones_caja (operation_id)",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_sesion_caja_usuario_activa
            ON sesiones_caja (id_usuario) WHERE estado IN ('ABIERTA', 'EN_ARQUEO')""",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_sesion_caja_terminal_activa
            ON sesiones_caja (terminal) WHERE estado IN ('ABIERTA', 'EN_ARQUEO')""",
        "CREATE INDEX IF NOT EXISTS idx_sesiones_caja_estado ON sesiones_caja (estado)",
        "CREATE INDEX IF NOT EXISTS idx_sesiones_caja_usuario ON sesiones_caja (id_usuario)",
        "ALTER TABLE ventas ADD COLUMN id_sesion_caja INTEGER REFERENCES sesiones_caja(id_sesion_caja)",
        "CREATE INDEX IF NOT EXISTS idx_ventas_sesion_caja ON ventas (id_sesion_caja)",
        "ALTER TABLE cierres_caja ADD COLUMN id_sesion_caja INTEGER REFERENCES sesiones_caja(id_sesion_caja)",
        "DROP INDEX IF EXISTS idx_cierres_usuario_fecha",
        "CREATE INDEX IF NOT EXISTS idx_cierres_usuario_fecha ON cierres_caja (id_usuario, fecha)",
        """CREATE TABLE IF NOT EXISTS movimientos_caja (
            id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
            id_sesion_caja INTEGER NOT NULL REFERENCES sesiones_caja(id_sesion_caja),
            tipo VARCHAR(30) NOT NULL,
            importe NUMERIC(12, 2) NOT NULL,
            metodo VARCHAR(30) NOT NULL DEFAULT 'EFECTIVO',
            motivo VARCHAR(200) NOT NULL,
            referencia VARCHAR(80),
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            fecha_hora TIMESTAMP NOT NULL,
            estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVO',
            id_movimiento_reverso INTEGER REFERENCES movimientos_caja(id_movimiento),
            id_gasto INTEGER REFERENCES gastos(id_gasto),
            operation_id VARCHAR(64) NOT NULL
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_movimiento_caja_operation_id ON movimientos_caja (operation_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_movimiento_caja_gasto ON movimientos_caja (id_gasto) WHERE id_gasto IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_movimientos_caja_sesion ON movimientos_caja (id_sesion_caja)",
        """CREATE TABLE IF NOT EXISTS arqueo_denominaciones (
            id_denominacion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_sesion_caja INTEGER NOT NULL REFERENCES sesiones_caja(id_sesion_caja),
            codigo VARCHAR(10) NOT NULL,
            valor NUMERIC(10, 2) NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            UNIQUE (id_sesion_caja, codigo)
        )""",
        """CREATE TABLE IF NOT EXISTS venta_pagos (
            id_pago INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venta INTEGER NOT NULL REFERENCES ventas(id_venta),
            metodo VARCHAR(30) NOT NULL,
            importe_monetario NUMERIC(12, 2) NOT NULL,
            cantidad_puntos INTEGER,
            equivalencia_puntos NUMERIC(12, 2),
            referencia VARCHAR(80),
            fecha_hora TIMESTAMP NOT NULL,
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
            id_sesion_caja INTEGER REFERENCES sesiones_caja(id_sesion_caja),
            operation_id VARCHAR(64) NOT NULL
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_venta_pago_operation_id ON venta_pagos (operation_id)",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_venta_pago_backfill ON venta_pagos (id_venta)
            WHERE operation_id LIKE 'backfill-venta-%'""",
        "CREATE INDEX IF NOT EXISTS idx_venta_pagos_venta ON venta_pagos (id_venta)",
        """INSERT INTO venta_pagos (
            id_venta, metodo, importe_monetario, fecha_hora, id_usuario, id_sesion_caja, operation_id
        )
        SELECT
            v.id_venta,
            CASE
                WHEN v.forma_pago IS NULL OR trim(v.forma_pago) = '' THEN 'EFECTIVO'
                WHEN upper(v.forma_pago) IN ('EFECTIVO', 'TRANSFERENCIA', 'TARJETA') THEN upper(v.forma_pago)
                ELSE 'DESCONOCIDO'
            END,
            v.total,
            v.fecha_hora,
            v.id_usuario,
            v.id_sesion_caja,
            'backfill-venta-' || v.id_venta
        FROM ventas v
        WHERE NOT EXISTS (
            SELECT 1 FROM venta_pagos p
            WHERE p.operation_id = 'backfill-venta-' || v.id_venta
        )""",
    ]
    migraciones = (
        migraciones_postgres + migraciones_sqlite_extras + migraciones_promos
        + migraciones_fidelidad_pg + migraciones_pedidos_pg + migraciones_comanda_tiempos_pg
        + migraciones_recetas_pg + migraciones_extra_tipos_pg + migraciones_para_llevar_pg
        + migraciones_mesas_pg + migraciones_cierres_modulos_pg + migraciones_operaciones_pg
        + migraciones_seguridad_pg
        + migraciones_cancelacion_pg
        + migraciones_caja_pg
        if dialect == "postgresql"
        else migraciones_sqlite + migraciones_sqlite_extras + migraciones_sqlite_promos
        + migraciones_fidelidad_sqlite + migraciones_pedidos_sqlite + migraciones_comanda_tiempos_sqlite
        + migraciones_extra_tipos_sqlite + migraciones_para_llevar_sqlite
        + migraciones_mesas_sqlite + migraciones_cierres_modulos_sqlite + migraciones_operaciones_sqlite
        + migraciones_seguridad_sqlite
        + migraciones_cancelacion_sqlite
        + migraciones_caja_sqlite
    )
    for sql in migraciones:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as exc:
            # Algunas ALTER fallan si la columna ya existe (SQLite).
            snippet = " ".join(sql.split())[:80]
            lower = sql.lower()
            es_005 = (
                "sesiones_caja" in lower
                or "movimientos_caja" in lower
                or "arqueo_denominaciones" in lower
                or "venta_pagos" in lower
                or "tolerancia_efectivo" in lower
                or "id_sesion_caja" in lower
                or "uq_sesion_caja" in lower
                or "uq_movimiento_caja" in lower
                or "uq_venta_pago" in lower
            )
            es_004 = (
                "pedido_cancelaciones" in lower
                or "estado_linea" in lower
                or "cantidad_cancelada" in lower
                or "idx_cancelaciones_" in lower
            )
            if es_005:
                msg = str(exc).lower()
                if dialect == "sqlite" and "duplicate column" in msg:
                    continue
                logging.error(
                    "Migración 005 de cierre de caja falló (%s). "
                    "Aplica backend/migrations/005_cierre_caja_conciliacion.up.sql. "
                    "No se muestran credenciales.",
                    type(exc).__name__,
                )
                raise RuntimeError(
                    "Esquema de cierre de caja incompleto (migración 005). "
                    "Detén el arranque, aplica 005_cierre_caja_conciliacion.up.sql y vuelve a iniciar."
                ) from None
            if es_004:
                msg = str(exc).lower()
                if dialect == "sqlite" and "duplicate column" in msg:
                    continue
                logging.error(
                    "Migración 004 de cancelación de líneas falló (%s). "
                    "Aplica backend/migrations/004_cancelacion_lineas.up.sql. "
                    "No se muestran credenciales.",
                    type(exc).__name__,
                )
                raise RuntimeError(
                    "Esquema de cancelación de líneas incompleto (migración 004). "
                    "Detén el arranque, aplica 004_cancelacion_lineas.up.sql y vuelve a iniciar."
                ) from None
            if any(k in lower for k in ("receta", "cierres", "modulos_json")):
                print(f"[WARN] Migracion fallo: {snippet}... -> {exc}")

    normalizar_roles_usuarios()
    verificar_esquema_cancelacion()
    verificar_esquema_caja()


def verificar_esquema_cancelacion() -> None:
    """Falla el arranque si falta la tabla o columnas de la migración 004."""
    insp = inspect(engine)
    tablas = set(insp.get_table_names())
    if "detalle_pedido" not in tablas:
        return
    faltantes = []
    cols_det = {c["name"] for c in insp.get_columns("detalle_pedido")}
    for col in ("estado_linea", "cantidad_cancelada"):
        if col not in cols_det:
            faltantes.append(f"detalle_pedido.{col}")
    if "pedido_cancelaciones" not in tablas:
        faltantes.append("tabla pedido_cancelaciones")
    else:
        cols_can = {c["name"] for c in insp.get_columns("pedido_cancelaciones")}
        for col in (
            "id_cancelacion",
            "id_pedido",
            "id_detalle_pedido",
            "cantidad",
            "cantidad_anterior",
            "cantidad_nueva",
            "motivo",
            "estado_anterior",
            "estado_nuevo",
            "aviso",
            "aviso_texto",
            "id_usuario",
            "fecha_hora",
            "vista_comandera",
        ):
            if col not in cols_can:
                faltantes.append(f"pedido_cancelaciones.{col}")
    if faltantes:
        logging.error(
            "Esquema 004 incompleto: %s. Aplica backend/migrations/004_cancelacion_lineas.up.sql.",
            ", ".join(faltantes),
        )
        raise RuntimeError(
            "El esquema de cancelación de líneas está incompleto. "
            "No se inicia el backend. Aplica la migración 004 y vuelve a arrancar. "
            "No se muestran credenciales ni la URL de la base."
        )


def verificar_esquema_caja() -> None:
    """Falla el arranque si falta el esquema de la migración 005."""
    insp = inspect(engine)
    tablas = set(insp.get_table_names())
    if "ventas" not in tablas:
        return
    faltantes = []
    if "sesiones_caja" not in tablas:
        faltantes.append("tabla sesiones_caja")
    if "movimientos_caja" not in tablas:
        faltantes.append("tabla movimientos_caja")
    if "arqueo_denominaciones" not in tablas:
        faltantes.append("tabla arqueo_denominaciones")
    if "venta_pagos" not in tablas:
        faltantes.append("tabla venta_pagos")
    cols_ventas = {c["name"] for c in insp.get_columns("ventas")}
    if "id_sesion_caja" not in cols_ventas:
        faltantes.append("ventas.id_sesion_caja")
    if "configuracion" in tablas:
        cols_cfg = {c["name"] for c in insp.get_columns("configuracion")}
        if "tolerancia_efectivo" not in cols_cfg:
            faltantes.append("configuracion.tolerancia_efectivo")
    if faltantes:
        logging.error(
            "Esquema 005 incompleto: %s. Aplica backend/migrations/005_cierre_caja_conciliacion.up.sql.",
            ", ".join(faltantes),
        )
        raise RuntimeError(
            "El esquema de cierre de caja está incompleto. "
            "No se inicia el backend. Aplica la migración 005 y vuelve a arrancar. "
            "No se muestran credenciales ni la URL de la base."
        )


def ensure_cierres_caja_table():
    """Garantiza tabla cierres_caja en BD existentes (Render / SQLite)."""
    from app.models.models import CierreCajaModel

    CierreCajaModel.__table__.create(bind=engine, checkfirst=True)


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


def crear_admin_inicial_si_vacio():
    """En SQLite local crea un admin por defecto si la BD está vacía."""
    if engine.dialect.name != "sqlite":
        return

    from app.models.models import UsuarioModel
    from app.constants.roles import ADMIN
    from app.utils.security import hash_password

    db = SessionLocal()
    try:
        if db.query(UsuarioModel).count() > 0:
            return

        login = os.getenv("LOCAL_ADMIN_LOGIN", "admin")
        password = os.getenv("LOCAL_ADMIN_PASSWORD", "admin123")
        db.add(
            UsuarioModel(
                nombre="Administrador",
                usuario_login=login,
                hash_password=hash_password(password),
                rol=ADMIN,
            )
        )
        db.commit()
        print(f"[LOCAL] Usuario admin creado: {login} / {password}")
    except Exception as exc:
        db.rollback()
        print(f"[WARN] No se pudo crear admin inicial: {exc}")
    finally:
        db.close()


def crear_catalogo_demo_si_vacio():
    """En SQLite local crea categorías y productos de ejemplo si el catálogo está vacío."""
    if engine.dialect.name != "sqlite":
        return
    if os.getenv("LOCAL_SEED_CATALOG", "true").lower() in ("0", "false", "no"):
        return

    from app.models.models import CategoriaModel, ProductoModel

    catalogo_demo = [
        (
            "Bebidas calientes",
            [
                ("Café americano", 35.00),
                ("Capuccino", 45.00),
                ("Latte", 48.00),
                ("Chocolate caliente", 42.00),
            ],
        ),
        (
            "Bebidas frías",
            [
                ("Frappé de vainilla", 55.00),
                ("Limonada natural", 38.00),
                ("Agua embotellada", 20.00),
            ],
        ),
        (
            "Panadería",
            [
                ("Concha", 18.00),
                ("Bolillo", 12.00),
                ("Muffin de arándano", 32.00),
            ],
        ),
        (
            "Comida",
            [
                ("Sandwich de jamón", 65.00),
                ("Ensalada mixta", 72.00),
                ("Sopa del día", 58.00),
            ],
        ),
    ]

    db = SessionLocal()
    try:
        if db.query(CategoriaModel).count() > 0:
            return

        total_productos = 0
        for nombre_categoria, productos in catalogo_demo:
            categoria = CategoriaModel(nombre=nombre_categoria)
            db.add(categoria)
            db.flush()
            for nombre_producto, precio in productos:
                db.add(
                    ProductoModel(
                        nombre=nombre_producto,
                        id_categoria=categoria.id_categoria,
                        precio_venta=precio,
                        activo=True,
                        para_llevar=False,
                    )
                )
                total_productos += 1

        db.commit()
        print(
            f"[LOCAL] Catálogo demo creado: {len(catalogo_demo)} categorías, "
            f"{total_productos} productos"
        )
    except Exception as exc:
        db.rollback()
        print(f"[WARN] No se pudo crear catálogo demo: {exc}")
    finally:
        db.close()


def crear_promocion_lunes_malteadas_si_ausente():
    """Seed local opcional: promoción demo INACTIVA. Nunca en producción."""
    if engine.dialect.name != "sqlite":
        return
    if os.getenv("LOCAL_SEED_PROMO", "false").lower() not in ("1", "true", "yes"):
        return
    from app.models.models import (
        PromocionModel,
        PromocionCategoriaModel,
        CategoriaModel,
    )
    from app.utils.timezone_mx import now_utc_naive
    from datetime import timedelta

    db = SessionLocal()
    try:
        if db.query(PromocionModel).filter(PromocionModel.nombre == "Lunes de Malteadas").first():
            return
        cat = (
            db.query(CategoriaModel)
            .filter(CategoriaModel.nombre.ilike("%maltead%"))
            .first()
        )
        if not cat:
            print("[INFO] Seed promo 'Lunes de Malteadas' omitido: sin categoría Malteadas")
            return
        ahora = now_utc_naive()
        promo = PromocionModel(
            nombre="Lunes de Malteadas",
            descripcion="2 malteadas por $90",
            tipo="CANTIDAD_PRECIO",
            valor=90,
            activa=False,
            cantidad_requerida=2,
            acumulable=False,
            dias_semana="0",
            hora_inicio="11:00",
            hora_fin="16:00",
            fecha_inicio=ahora,
            fecha_fin=ahora + timedelta(days=21),
            fecha_creacion=ahora,
        )
        db.add(promo)
        db.flush()
        db.add(PromocionCategoriaModel(id_promocion=promo.id_promocion, id_categoria=cat.id_categoria))
        db.commit()
        print("[INFO] Promoción demo 'Lunes de Malteadas' creada (INACTIVA)")
    except Exception as exc:
        db.rollback()
        print(f"[WARN] Seed promo malteadas: {exc}")
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
