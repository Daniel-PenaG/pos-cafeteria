-- 008_tesoreria_saldos UP (PostgreSQL)
-- Idempotente. No modifica 002–007. No reconstruye ventas históricas.
-- Tesorería queda desactivada: no inserta filas en activacion_tesoreria.
-- ADVERTENCIA DE DOWN: 008_tesoreria_saldos.down.sql borra el historial
-- de Tesorería de forma irrevocable. Solo en una base desechable.

ALTER TABLE usuarios ALTER COLUMN permisos_acciones_json TYPE VARCHAR(2000);

CREATE TABLE IF NOT EXISTS cuentas_tesoreria (
    id_cuenta SERIAL PRIMARY KEY,
    codigo VARCHAR(40) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    moneda VARCHAR(3) NOT NULL DEFAULT 'MXN',
    activa BOOLEAN NOT NULL DEFAULT TRUE,
    es_sistema BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operaciones_tesoreria (
    id_operacion SERIAL PRIMARY KEY,
    operation_id VARCHAR(80) NOT NULL UNIQUE,
    payload_hash VARCHAR(64) NOT NULL,
    tipo VARCHAR(40) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'CONFIRMADA',
    fecha_operacion TIMESTAMP NOT NULL,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    origen_tipo VARCHAR(40),
    origen_id INTEGER,
    referencia VARCHAR(80),
    concepto VARCHAR(200) NOT NULL,
    observacion VARCHAR(500),
    id_operacion_revertida INTEGER REFERENCES operaciones_tesoreria(id_operacion),
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tesoreria_origen_confirmada
    ON operaciones_tesoreria (origen_tipo, origen_id)
    WHERE origen_tipo IS NOT NULL
      AND origen_id IS NOT NULL
      AND tipo <> 'REVERSA'
      AND estado = 'CONFIRMADA';

CREATE TABLE IF NOT EXISTS movimientos_tesoreria (
    id_movimiento SERIAL PRIMARY KEY,
    id_operacion INTEGER NOT NULL REFERENCES operaciones_tesoreria(id_operacion),
    id_cuenta INTEGER NOT NULL REFERENCES cuentas_tesoreria(id_cuenta),
    direccion VARCHAR(10) NOT NULL CHECK (direccion IN ('ENTRADA', 'SALIDA')),
    importe NUMERIC(12, 2) NOT NULL CHECK (importe > 0),
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activacion_tesoreria (
    id_activacion SERIAL PRIMARY KEY,
    fecha_corte TIMESTAMP NOT NULL,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    fecha_confirmacion TIMESTAMP NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVA',
    efectivo_cafeteria NUMERIC(12, 2) NOT NULL,
    efectivo_casa NUMERIC(12, 2) NOT NULL,
    saldo_banco NUMERIC(12, 2) NOT NULL,
    observacion VARCHAR(500),
    unica INTEGER NOT NULL DEFAULT 1 UNIQUE
);

CREATE TABLE IF NOT EXISTS conciliaciones_tesoreria (
    id_conciliacion SERIAL PRIMARY KEY,
    id_cuenta INTEGER NOT NULL REFERENCES cuentas_tesoreria(id_cuenta),
    saldo_sistema NUMERIC(12, 2) NOT NULL,
    saldo_fisico NUMERIC(12, 2) NOT NULL,
    diferencia NUMERIC(12, 2) NOT NULL,
    observacion VARCHAR(500),
    estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    id_usuario_revision INTEGER REFERENCES usuarios(id_usuario),
    fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_revision TIMESTAMP,
    id_operacion_ajuste INTEGER REFERENCES operaciones_tesoreria(id_operacion)
);

ALTER TABLE gastos ADD COLUMN IF NOT EXISTS estado_pago VARCHAR(20) NOT NULL DEFAULT 'PAGADO';
ALTER TABLE gastos ADD COLUMN IF NOT EXISTS clasificacion VARCHAR(40) NOT NULL DEFAULT 'GASTO_OPERATIVO';
ALTER TABLE gastos ADD COLUMN IF NOT EXISTS id_cuenta_tesoreria INTEGER;

ALTER TABLE compras ADD COLUMN IF NOT EXISTS estado_pago VARCHAR(20) NOT NULL DEFAULT 'PAGADO';
ALTER TABLE compras ADD COLUMN IF NOT EXISTS id_cuenta_tesoreria INTEGER;

INSERT INTO cuentas_tesoreria (codigo, nombre, tipo, moneda, activa, es_sistema)
SELECT 'EFECTIVO_CAFETERIA', 'Efectivo en cafetería', 'EFECTIVO', 'MXN', TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM cuentas_tesoreria WHERE codigo = 'EFECTIVO_CAFETERIA');

INSERT INTO cuentas_tesoreria (codigo, nombre, tipo, moneda, activa, es_sistema)
SELECT 'EFECTIVO_CASA', 'Efectivo del negocio en casa', 'EFECTIVO', 'MXN', TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM cuentas_tesoreria WHERE codigo = 'EFECTIVO_CASA');

INSERT INTO cuentas_tesoreria (codigo, nombre, tipo, moneda, activa, es_sistema)
SELECT 'BANCO', 'Cuenta bancaria', 'BANCO', 'MXN', TRUE, TRUE
WHERE NOT EXISTS (SELECT 1 FROM cuentas_tesoreria WHERE codigo = 'BANCO');
