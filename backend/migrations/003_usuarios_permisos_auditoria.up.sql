-- 003_usuarios_permisos_auditoria UP (PostgreSQL)
-- Fuente versionada: usuarios.activo, permisos de acción, auditoría, bloqueo de login.
-- El arranque (aplicar_migraciones_sqlite) aplica las mismas sentencias IF NOT EXISTS.
-- NO aplicar en producción durante la revisión de security/permisos-pos.
--
-- Verificar antes: SELECT COUNT(*) FROM usuarios WHERE activo IS NULL;
-- Después: usuarios.activo = true en filas existentes.
--
--   psql "$DATABASE_URL" -f backend/migrations/003_usuarios_permisos_auditoria.up.sql

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS permisos_acciones_json TEXT;
UPDATE usuarios SET activo = TRUE WHERE activo IS NULL;

ALTER TABLE ventas ADD COLUMN IF NOT EXISTS origen_cobro VARCHAR(20);

CREATE TABLE IF NOT EXISTS auditoria (
    id_auditoria SERIAL PRIMARY KEY,
    id_usuario INTEGER REFERENCES usuarios(id_usuario),
    usuario_login_intentado VARCHAR(80),
    accion VARCHAR(40) NOT NULL,
    entidad VARCHAR(40),
    entidad_id INTEGER,
    detalles_json VARCHAR(2000),
    origen VARCHAR(40),
    fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip VARCHAR(64),
    user_agent VARCHAR(300)
);

CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria (fecha_hora);
CREATE INDEX IF NOT EXISTS idx_auditoria_accion ON auditoria (accion);
CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria (id_usuario);

CREATE TABLE IF NOT EXISTS login_bloqueos (
    id SERIAL PRIMARY KEY,
    usuario_login VARCHAR(80) NOT NULL,
    ip VARCHAR(64) NOT NULL DEFAULT '',
    intentos INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta TIMESTAMP,
    actualizado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_login_bloqueos_usuario_ip
    ON login_bloqueos (usuario_login, ip);
