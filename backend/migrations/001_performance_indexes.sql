-- Índices de rendimiento POS (PostgreSQL)
-- Ejecutar manualmente en producción tras revisión. Reversible con DOWN.

-- UP
CREATE INDEX IF NOT EXISTS idx_ventas_fecha_hora ON ventas (fecha_hora);
CREATE INDEX IF NOT EXISTS idx_ventas_id_usuario ON ventas (id_usuario);
CREATE INDEX IF NOT EXISTS idx_ventas_id_cliente ON ventas (id_cliente);
CREATE INDEX IF NOT EXISTS idx_ventas_forma_pago ON ventas (forma_pago);
CREATE INDEX IF NOT EXISTS idx_detalle_venta_id_venta ON detalle_venta (id_venta);
CREATE INDEX IF NOT EXISTS idx_detalle_venta_id_producto ON detalle_venta (id_producto);
CREATE INDEX IF NOT EXISTS idx_detalle_venta_id_promocion ON detalle_venta (id_promocion);
CREATE INDEX IF NOT EXISTS idx_pedidos_estado ON pedidos (estado);
CREATE INDEX IF NOT EXISTS idx_pedidos_numero_mesa ON pedidos (numero_mesa);
CREATE INDEX IF NOT EXISTS idx_pedidos_fecha_apertura ON pedidos (fecha_apertura);
CREATE INDEX IF NOT EXISTS idx_pedidos_id_venta ON pedidos (id_venta);
CREATE INDEX IF NOT EXISTS idx_detalle_pedido_id_pedido ON detalle_pedido (id_pedido);
CREATE INDEX IF NOT EXISTS idx_detalle_pedido_id_producto ON detalle_pedido (id_producto);
CREATE INDEX IF NOT EXISTS idx_detalle_pedido_en_comanda ON detalle_pedido (en_comanda);
CREATE INDEX IF NOT EXISTS idx_detalle_pedido_fecha_envio ON detalle_pedido (fecha_envio_comanda);
CREATE INDEX IF NOT EXISTS idx_recetas_id_producto ON recetas (id_producto);
CREATE INDEX IF NOT EXISTS idx_receta_insumos_id_receta ON receta_insumos (id_receta);
CREATE INDEX IF NOT EXISTS idx_receta_insumos_id_insumo ON receta_insumos (id_insumo);
CREATE INDEX IF NOT EXISTS idx_movimientos_inventario_id_insumo ON movimientos_inventario (id_insumo);
CREATE INDEX IF NOT EXISTS idx_movimientos_inventario_fecha ON movimientos_inventario (fecha_hora);
CREATE INDEX IF NOT EXISTS idx_cierres_caja_fecha ON cierres_caja (fecha);
CREATE INDEX IF NOT EXISTS idx_cierres_caja_id_usuario ON cierres_caja (id_usuario);
CREATE INDEX IF NOT EXISTS idx_gastos_fecha_hora ON gastos (fecha_hora);

-- Compuesto: ventas por día y usuario (dashboard cajero)
CREATE INDEX IF NOT EXISTS idx_ventas_fecha_usuario ON ventas (fecha_hora, id_usuario);

-- DOWN (reversible)
-- DROP INDEX IF EXISTS idx_ventas_fecha_hora;
-- DROP INDEX IF EXISTS idx_ventas_id_usuario;
-- ... (ver función aplicar_indices_performance en database.py)
