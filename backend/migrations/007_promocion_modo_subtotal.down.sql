-- 007_promocion_modo_subtotal DOWN (PostgreSQL)
-- Solo en una base desechable. No ejecutar en producción.
-- Pérdida irreversible:
--   sin_promocion (AUTOMATICA, SELECCIONADA, PRECIO_NORMAL o LEGACY)
--   subtotal exacto de la línea
-- No se puede reconstruir un subtotal que no coincida con
-- cantidad × precio_unitario. El resto de columnas de la línea se conserva.

ALTER TABLE detalle_pedido DROP COLUMN IF EXISTS subtotal;
ALTER TABLE detalle_pedido DROP COLUMN IF EXISTS sin_promocion;
