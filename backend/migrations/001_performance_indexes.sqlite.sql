-- 001_performance_indexes (SQLite — desarrollo/pruebas locales)
-- Ejecutar manualmente si se desea; IF NOT EXISTS es seguro.

CREATE INDEX IF NOT EXISTS idx_ventas_fecha_hora ON ventas (fecha_hora);
CREATE INDEX IF NOT EXISTS idx_detalle_venta_id_venta ON detalle_venta (id_venta);
CREATE INDEX IF NOT EXISTS idx_pedidos_estado ON pedidos (estado);
CREATE INDEX IF NOT EXISTS idx_pedidos_id_venta ON pedidos (id_venta);
CREATE INDEX IF NOT EXISTS idx_recetas_id_producto ON recetas (id_producto);
