-- 004_cancelacion_lineas DOWN (PostgreSQL)
-- ADVERTENCIA: elimina el historial de cancelaciones de líneas. No usar en producción
-- sin respaldo. No borra pedidos ni ventas cobradas.

DROP INDEX IF EXISTS idx_cancelaciones_vista;
DROP INDEX IF EXISTS idx_cancelaciones_detalle;
DROP INDEX IF EXISTS idx_cancelaciones_pedido;
DROP TABLE IF EXISTS pedido_cancelaciones;

ALTER TABLE detalle_pedido DROP COLUMN IF EXISTS cantidad_cancelada;
ALTER TABLE detalle_pedido DROP COLUMN IF EXISTS estado_linea;
