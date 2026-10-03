-- 008_tesoreria_saldos DOWN
-- ADVERTENCIA: elimina de forma irrevocable el historial de Tesorería
-- (cuentas, operaciones, movimientos, activación y conciliaciones).
-- Solo puede ejecutarse en una base desechable. No usar en producción.
-- No revierte 002–007. No borra ventas, pagos, puntos, caja ni inventario.

DROP TABLE IF EXISTS conciliaciones_tesoreria;
DROP TABLE IF EXISTS movimientos_tesoreria;
DROP TABLE IF EXISTS activacion_tesoreria;
DROP TABLE IF EXISTS operaciones_tesoreria;
DROP TABLE IF EXISTS cuentas_tesoreria;

ALTER TABLE gastos DROP COLUMN IF EXISTS id_cuenta_tesoreria;
ALTER TABLE gastos DROP COLUMN IF EXISTS clasificacion;
ALTER TABLE gastos DROP COLUMN IF EXISTS estado_pago;

ALTER TABLE compras DROP COLUMN IF EXISTS id_cuenta_tesoreria;
ALTER TABLE compras DROP COLUMN IF EXISTS estado_pago;
