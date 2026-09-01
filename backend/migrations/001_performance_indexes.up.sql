-- 001_performance_indexes UP (PostgreSQL)
-- Ejecutar MANUALMENTE fuera de transacción, un índice a la vez.
-- Requiere PostgreSQL 9.5+ (CONCURRENTLY) y soporte IF NOT EXISTS.
-- NO incluir en el arranque de FastAPI.

-- Orden recomendado: tablas de lectura frecuente primero, luego detalle/joins.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ventas_fecha_hora ON ventas (fecha_hora);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ventas_id_usuario ON ventas (id_usuario);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ventas_id_cliente ON ventas (id_cliente);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ventas_forma_pago ON ventas (forma_pago);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ventas_fecha_usuario ON ventas (fecha_hora, id_usuario);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detalle_venta_id_venta ON detalle_venta (id_venta);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detalle_venta_id_producto ON detalle_venta (id_producto);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detalle_venta_id_promocion ON detalle_venta (id_promocion);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pedidos_estado ON pedidos (estado);
-- idx_pedidos_numero_mesa: omitido — ya existe ix_pedidos_numero_mesa (index=True) y idx_pedidos_mesa_estado
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pedidos_fecha_apertura ON pedidos (fecha_apertura);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pedidos_id_venta ON pedidos (id_venta);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detalle_pedido_id_pedido ON detalle_pedido (id_pedido);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detalle_pedido_id_producto ON detalle_pedido (id_producto);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detalle_pedido_en_comanda ON detalle_pedido (en_comanda);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detalle_pedido_fecha_envio ON detalle_pedido (fecha_envio_comanda);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_recetas_id_producto ON recetas (id_producto);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_receta_insumos_id_receta ON receta_insumos (id_receta);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_receta_insumos_id_insumo ON receta_insumos (id_insumo);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_movimientos_inventario_id_insumo ON movimientos_inventario (id_insumo);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_movimientos_inventario_fecha ON movimientos_inventario (fecha_hora);

-- cierres_caja.fecha / id_usuario: omitidos — ya existen ix_cierres_caja_* (index=True)
-- y idx_cierres_usuario_fecha UNIQUE (id_usuario, fecha) vía migraciones en database.py

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gastos_fecha_hora ON gastos (fecha_hora);
