-- 002_pedido_operaciones UP (PostgreSQL)
-- Idempotencia de agregado de producto/combo al pedido.
-- Ejecutar MANUALMENTE después de revisión. No forma parte del arranque automático de producción.
--
--   psql "$DATABASE_URL" -f backend/migrations/002_pedido_operaciones.up.sql
--
-- No borra datos existentes. operation_id es NOT NULL en filas nuevas;
-- no hay filas históricas (tabla nueva). El índice único ignora NULLs si
-- se insertara alguna fila legacy con operation_id NULL (no aplica aquí).

CREATE TABLE IF NOT EXISTS pedido_operaciones (
    id_operacion SERIAL PRIMARY KEY,
    operation_id VARCHAR(64) NOT NULL,
    id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido) ON DELETE CASCADE,
    tipo VARCHAR(20) NOT NULL DEFAULT 'linea',
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pedido_operaciones_operation_id
    ON pedido_operaciones (operation_id);

CREATE INDEX IF NOT EXISTS idx_pedido_operaciones_id_pedido
    ON pedido_operaciones (id_pedido);
