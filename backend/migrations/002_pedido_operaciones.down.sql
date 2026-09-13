-- 002_pedido_operaciones DOWN (PostgreSQL)
-- Revierte idempotencia e índice de un pedido abierto por mesa.
-- No borra pedidos ni detalle_pedido.

DROP INDEX IF EXISTS uq_pedidos_abierto_mesa;
DROP INDEX IF EXISTS idx_pedido_operaciones_id_pedido;
DROP INDEX IF EXISTS uq_pedido_operaciones_operation_id;
DROP TABLE IF EXISTS pedido_operaciones;
