-- 001_performance_indexes DOWN (PostgreSQL)
-- Ejecutar MANUALMENTE fuera de transacción, un índice a la vez.
-- Orden inverso al UP para minimizar dependencias en planificador.

DROP INDEX CONCURRENTLY IF EXISTS idx_gastos_fecha_hora;

-- idx_cierres_caja_* no se crean en UP; no dropear ix_* ni idx_cierres_usuario_fecha

DROP INDEX CONCURRENTLY IF EXISTS idx_movimientos_inventario_fecha;
DROP INDEX CONCURRENTLY IF EXISTS idx_movimientos_inventario_id_insumo;

DROP INDEX CONCURRENTLY IF EXISTS idx_receta_insumos_id_insumo;
DROP INDEX CONCURRENTLY IF EXISTS idx_receta_insumos_id_receta;
DROP INDEX CONCURRENTLY IF EXISTS idx_recetas_id_producto;

DROP INDEX CONCURRENTLY IF EXISTS idx_detalle_pedido_fecha_envio;
DROP INDEX CONCURRENTLY IF EXISTS idx_detalle_pedido_en_comanda;
DROP INDEX CONCURRENTLY IF EXISTS idx_detalle_pedido_id_producto;
DROP INDEX CONCURRENTLY IF EXISTS idx_detalle_pedido_id_pedido;

DROP INDEX CONCURRENTLY IF EXISTS idx_pedidos_id_venta;
DROP INDEX CONCURRENTLY IF EXISTS idx_pedidos_fecha_apertura;
DROP INDEX CONCURRENTLY IF EXISTS idx_pedidos_estado;
-- idx_pedidos_numero_mesa no creado en UP

DROP INDEX CONCURRENTLY IF EXISTS idx_detalle_venta_id_promocion;
DROP INDEX CONCURRENTLY IF EXISTS idx_detalle_venta_id_producto;
DROP INDEX CONCURRENTLY IF EXISTS idx_detalle_venta_id_venta;

DROP INDEX CONCURRENTLY IF EXISTS idx_ventas_fecha_usuario;
DROP INDEX CONCURRENTLY IF EXISTS idx_ventas_forma_pago;
DROP INDEX CONCURRENTLY IF EXISTS idx_ventas_id_cliente;
DROP INDEX CONCURRENTLY IF EXISTS idx_ventas_id_usuario;
DROP INDEX CONCURRENTLY IF EXISTS idx_ventas_fecha_hora;
