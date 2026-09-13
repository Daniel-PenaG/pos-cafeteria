-- 002_pedido_operaciones UP (PostgreSQL)
-- Fuente versionada de idempotencia + un pedido ABIERTO por mesa/tipo.
--
-- Estrategia del proyecto:
--   1. Este archivo es el esquema canónico (revisión, rollback, ops).
--   2. El arranque del backend (aplicar_migraciones_sqlite) aplica las MISMAS
--      sentencias de forma idempotente (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
--      No hay una segunda migración distinta: son el mismo cambio.
--   3. NO aplicar en producción durante la revisión de esta rama.
--
-- Al desplegar (después de merge):
--   - El backend, al iniciar, ejecutará CREATE/ALTER idempotentes.
--   - Ops puede aplicar también este SQL de forma explícita; es seguro repetirlo.
--   - Antes del índice único de mesa, verificar que no haya dos ABIERTO:
--       SELECT numero_mesa, para_llevar, COUNT(*)
--       FROM pedidos WHERE estado = 'ABIERTO'
--       GROUP BY numero_mesa, para_llevar HAVING COUNT(*) > 1;
--
--   psql "$DATABASE_URL" -f backend/migrations/002_pedido_operaciones.up.sql

UPDATE pedidos SET para_llevar = FALSE WHERE para_llevar IS NULL;

CREATE TABLE IF NOT EXISTS pedido_operaciones (
    id_operacion SERIAL PRIMARY KEY,
    operation_id VARCHAR(64) NOT NULL,
    id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
    tipo VARCHAR(20) NOT NULL DEFAULT 'linea',
    payload_hash VARCHAR(64) NOT NULL DEFAULT '',
    id_detalle_pedido INTEGER REFERENCES detalle_pedido(id_detalle_pedido),
    detalle_ids_json VARCHAR(500),
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE pedido_operaciones ADD COLUMN IF NOT EXISTS payload_hash VARCHAR(64) NOT NULL DEFAULT '';
ALTER TABLE pedido_operaciones ADD COLUMN IF NOT EXISTS id_detalle_pedido INTEGER REFERENCES detalle_pedido(id_detalle_pedido);
ALTER TABLE pedido_operaciones ADD COLUMN IF NOT EXISTS detalle_ids_json VARCHAR(500);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pedido_operaciones_operation_id
    ON pedido_operaciones (operation_id);

CREATE INDEX IF NOT EXISTS idx_pedido_operaciones_id_pedido
    ON pedido_operaciones (id_pedido);

-- Un solo pedido ABIERTO por mesa y tipo (salon vs para llevar).
CREATE UNIQUE INDEX IF NOT EXISTS uq_pedidos_abierto_mesa
    ON pedidos (numero_mesa, para_llevar)
    WHERE estado = 'ABIERTO';
