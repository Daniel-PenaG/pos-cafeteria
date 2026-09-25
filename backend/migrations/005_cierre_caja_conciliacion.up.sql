-- 005_cierre_caja_conciliacion UP (PostgreSQL)
-- Orden: 004_cancelacion_lineas → 005_cierre_caja_conciliacion
-- Idempotente. NO ejecutar en producción desde esta rama.
--
-- Transformación de cierres históricos:
--   La tabla cierres_caja se conserva. Los arqueos por día/usuario siguen consultables.
--   Las nuevas sesiones viven en sesiones_caja. No se asignan ventas históricas
--   a sesiones nuevas. venta_pagos se rellena una vez por venta (anti doble backfill).

ALTER TABLE configuracion ADD COLUMN IF NOT EXISTS tolerancia_efectivo NUMERIC(10, 2) NOT NULL DEFAULT 5;
UPDATE configuracion SET tolerancia_efectivo = 5 WHERE tolerancia_efectivo IS NULL;

CREATE TABLE IF NOT EXISTS sesiones_caja (
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
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_sesion_caja_operation_id ON sesiones_caja (operation_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sesion_caja_usuario_activa
    ON sesiones_caja (id_usuario) WHERE estado IN ('ABIERTA', 'EN_ARQUEO');
CREATE UNIQUE INDEX IF NOT EXISTS uq_sesion_caja_terminal_activa
    ON sesiones_caja (terminal) WHERE estado IN ('ABIERTA', 'EN_ARQUEO');
CREATE INDEX IF NOT EXISTS idx_sesiones_caja_estado ON sesiones_caja (estado);
CREATE INDEX IF NOT EXISTS idx_sesiones_caja_usuario ON sesiones_caja (id_usuario);

ALTER TABLE ventas ADD COLUMN IF NOT EXISTS id_sesion_caja INTEGER REFERENCES sesiones_caja(id_sesion_caja);
CREATE INDEX IF NOT EXISTS idx_ventas_sesion_caja ON ventas (id_sesion_caja);

ALTER TABLE cierres_caja ADD COLUMN IF NOT EXISTS id_sesion_caja INTEGER REFERENCES sesiones_caja(id_sesion_caja);
-- Varios turnos el mismo día: el índice único histórico (usuario+fecha) deja de aplicar.
DROP INDEX IF EXISTS idx_cierres_usuario_fecha;
CREATE INDEX IF NOT EXISTS idx_cierres_usuario_fecha ON cierres_caja (id_usuario, fecha);

CREATE TABLE IF NOT EXISTS movimientos_caja (
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
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_movimiento_caja_operation_id ON movimientos_caja (operation_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_movimiento_caja_gasto ON movimientos_caja (id_gasto) WHERE id_gasto IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_movimientos_caja_sesion ON movimientos_caja (id_sesion_caja);

CREATE TABLE IF NOT EXISTS arqueo_denominaciones (
    id_denominacion SERIAL PRIMARY KEY,
    id_sesion_caja INTEGER NOT NULL REFERENCES sesiones_caja(id_sesion_caja),
    codigo VARCHAR(10) NOT NULL,
    valor NUMERIC(10, 2) NOT NULL,
    cantidad INTEGER NOT NULL DEFAULT 0,
    UNIQUE (id_sesion_caja, codigo)
);

CREATE TABLE IF NOT EXISTS venta_pagos (
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
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_venta_pago_operation_id ON venta_pagos (operation_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_venta_pago_backfill ON venta_pagos (id_venta)
    WHERE operation_id LIKE 'backfill-venta-%';
CREATE INDEX IF NOT EXISTS idx_venta_pagos_venta ON venta_pagos (id_venta);

INSERT INTO venta_pagos (
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
);
