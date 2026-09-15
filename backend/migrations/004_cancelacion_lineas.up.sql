-- 004_cancelacion_lineas UP (PostgreSQL)
-- Orden: 002_pedido_operaciones → 003_usuarios_permisos_auditoria → 004_cancelacion_lineas
-- Idempotente. No ejecutar en producción desde esta rama.

ALTER TABLE detalle_pedido ADD COLUMN IF NOT EXISTS estado_linea VARCHAR(20) NOT NULL DEFAULT 'ACTIVA';
ALTER TABLE detalle_pedido ADD COLUMN IF NOT EXISTS cantidad_cancelada NUMERIC(10, 2) NOT NULL DEFAULT 0;
UPDATE detalle_pedido SET estado_linea = 'ACTIVA' WHERE estado_linea IS NULL;
UPDATE detalle_pedido SET cantidad_cancelada = 0 WHERE cantidad_cancelada IS NULL;

CREATE TABLE IF NOT EXISTS pedido_cancelaciones (
    id_cancelacion SERIAL PRIMARY KEY,
    id_pedido INTEGER NOT NULL REFERENCES pedidos(id_pedido),
    id_detalle_pedido INTEGER NOT NULL REFERENCES detalle_pedido(id_detalle_pedido),
    cantidad NUMERIC(10, 2) NOT NULL,
    cantidad_anterior NUMERIC(10, 2) NOT NULL,
    cantidad_nueva NUMERIC(10, 2) NOT NULL,
    motivo VARCHAR(80) NOT NULL,
    motivo_detalle VARCHAR(300),
    estado_anterior VARCHAR(20) NOT NULL,
    estado_nuevo VARCHAR(20) NOT NULL,
    aviso VARCHAR(40) NOT NULL,
    aviso_texto VARCHAR(80) NOT NULL,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    vista_comandera BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_vista TIMESTAMP,
    id_usuario_vista INTEGER REFERENCES usuarios(id_usuario)
);

CREATE INDEX IF NOT EXISTS idx_cancelaciones_pedido ON pedido_cancelaciones (id_pedido);
CREATE INDEX IF NOT EXISTS idx_cancelaciones_detalle ON pedido_cancelaciones (id_detalle_pedido);
CREATE INDEX IF NOT EXISTS idx_cancelaciones_vista ON pedido_cancelaciones (vista_comandera);
