-- 003_usuarios_permisos_auditoria DOWN (PostgreSQL)
-- No borra usuarios ni ventas. Quita auditoría, bloqueos y columnas nuevas.

DROP INDEX IF EXISTS uq_login_bloqueos_usuario_ip;
DROP TABLE IF EXISTS login_bloqueos;
DROP INDEX IF EXISTS idx_auditoria_usuario;
DROP INDEX IF EXISTS idx_auditoria_accion;
DROP INDEX IF EXISTS idx_auditoria_fecha;
DROP TABLE IF EXISTS auditoria;
ALTER TABLE ventas DROP COLUMN IF EXISTS origen_cobro;
ALTER TABLE usuarios DROP COLUMN IF EXISTS permisos_acciones_json;
ALTER TABLE usuarios DROP COLUMN IF EXISTS activo;
