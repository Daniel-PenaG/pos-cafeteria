DROP TABLE IF EXISTS cobro_operaciones;
DROP INDEX IF EXISTS uq_fidelidad_venta_tipo;
DROP INDEX IF EXISTS ix_fidelidad_movimientos_id_venta;
DROP INDEX IF EXISTS ix_fidelidad_movimientos_id_cliente;
DROP INDEX IF EXISTS uq_venta_pago_un_monetario;
DROP INDEX IF EXISTS uq_venta_pago_un_puntos;
ALTER TABLE venta_pagos DROP CONSTRAINT IF EXISTS ck_venta_pago_componente;
