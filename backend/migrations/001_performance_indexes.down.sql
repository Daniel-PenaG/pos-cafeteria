-- 001_performance_indexes DOWN (PostgreSQL)
-- Ejecutar MANUALMENTE fuera de transacción, un índice a la vez.
-- Orden inverso al UP para minimizar dependencias en planificador.

DROP INDEX CONCURRENTLY IF EXISTS idx_gastos_fecha_hora;

DROP INDEX CONCURRENTLY IF EXISTS idx_cierres_caja_id_usuario;
DROP INDEX CONCURRENTLY IF EXISTS idx_cierres_caja_fecha;

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
DROP INDEX CONCURRENTLY IF EXISTS idx_pedidos_numero_mesa;
DROP INDEX CONCURRENTLY IF EXISTS idx_pedidos_estado;

DROP INDEX CONCURRENTLY IF EXISTS idx_detalle_venta_id_promocion;
DROP INDEX CONCURRENTLY IF EXISTS idx_detalle_venta_id_producto;
DROP INDEX CONCURRENTLY IF EXISTS idx_detalle_venta_id_venta;

DROP INDEX CONCURRENTLY IF EXISTS idx_ventas_fecha_usuario;
DROP INDEX CONCURRENTLY IF EXISTS idx_ventas_forma_pago;
DROP INDEX CONCURRENTLY IF EXISTS idx_ventas_id_cliente;
DROP INDEX CONCURRENTLY IF EXISTS idx_ventas_id_usuario;
DROP INDEX CONCURRENTLY IF EXISTS idx_ventas_fecha_hora;
