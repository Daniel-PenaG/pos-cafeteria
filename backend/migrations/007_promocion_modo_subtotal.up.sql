-- 007_promocion_modo_subtotal UP (PostgreSQL)
-- Idempotente. No modifica 005 ni 006.
-- sin_promocion NULL = pedido anterior (no adopta promociones nuevas).
-- sin_promocion false + id_promocion NULL = automática.
-- sin_promocion false + id_promocion = seleccionada.
-- sin_promocion true = precio normal explícito.
-- subtotal es la autoridad monetaria de la línea. El backfill conserva
-- cantidad × precio_unitario de las filas viejas; no reescribe historia.

ALTER TABLE detalle_pedido ADD COLUMN IF NOT EXISTS sin_promocion BOOLEAN;
ALTER TABLE detalle_pedido ADD COLUMN IF NOT EXISTS subtotal NUMERIC(10, 2);

UPDATE detalle_pedido
SET subtotal = ROUND(cantidad * precio_unitario, 2)
WHERE subtotal IS NULL;
