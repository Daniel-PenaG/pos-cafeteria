-- 005_cierre_caja_conciliacion DOWN
-- ADVERTENCIA: borra sesiones, movimientos, arqueos y venta_pagos.
-- No usar en producción sin respaldo. Los cierres_caja históricos se conservan
-- (solo se quita id_sesion_caja). Las ventas no se eliminan.

DROP TABLE IF EXISTS venta_pagos;
DROP TABLE IF EXISTS arqueo_denominaciones;
DROP TABLE IF EXISTS movimientos_caja;

ALTER TABLE ventas DROP COLUMN IF EXISTS id_sesion_caja;
ALTER TABLE cierres_caja DROP COLUMN IF EXISTS id_sesion_caja;

DROP TABLE IF EXISTS sesiones_caja;

ALTER TABLE configuracion DROP COLUMN IF EXISTS tolerancia_efectivo;
