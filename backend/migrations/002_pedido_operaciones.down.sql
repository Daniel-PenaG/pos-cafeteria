-- 002_pedido_operaciones DOWN (PostgreSQL)
-- Revierte la tabla de idempotencia. No toca pedidos ni detalle_pedido.

DROP INDEX IF EXISTS idx_pedido_operaciones_id_pedido;
DROP INDEX IF EXISTS uq_pedido_operaciones_operation_id;
DROP TABLE IF EXISTS pedido_operaciones;
