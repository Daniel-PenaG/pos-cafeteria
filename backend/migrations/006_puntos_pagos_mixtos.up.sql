-- Fase 3B. Idempotente. No reescribe ventas históricas.
-- El backend la aplica y verifica automáticamente durante el arranque.
-- También puede ejecutarse explícitamente por operaciones; es seguro repetirla.

ALTER TABLE venta_pagos ALTER COLUMN operation_id TYPE VARCHAR(80);

DO $$
BEGIN
    ALTER TABLE venta_pagos
        ADD CONSTRAINT ck_venta_pago_componente CHECK (
            (metodo = 'PUNTOS' AND importe_monetario = 0 AND cantidad_puntos > 0 AND equivalencia_puntos > 0)
            OR
            (metodo <> 'PUNTOS' AND importe_monetario >= 0
                AND COALESCE(cantidad_puntos, 0) = 0
                AND COALESCE(equivalencia_puntos, 0) = 0)
        );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_venta_pago_un_puntos
    ON venta_pagos (id_venta) WHERE metodo = 'PUNTOS';
CREATE UNIQUE INDEX IF NOT EXISTS uq_venta_pago_un_monetario
    ON venta_pagos (id_venta) WHERE metodo <> 'PUNTOS';

CREATE INDEX IF NOT EXISTS ix_fidelidad_movimientos_id_cliente
    ON fidelidad_movimientos (id_cliente);
CREATE INDEX IF NOT EXISTS ix_fidelidad_movimientos_id_venta
    ON fidelidad_movimientos (id_venta);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fidelidad_venta_tipo
    ON fidelidad_movimientos (id_venta, tipo)
    WHERE id_venta IS NOT NULL AND tipo IN ('REDENCION', 'ACUMULACION');

CREATE TABLE IF NOT EXISTS cobro_operaciones (
    id_operacion SERIAL PRIMARY KEY,
    operation_id VARCHAR(64) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    id_pedido INTEGER REFERENCES pedidos(id_pedido),
    id_venta INTEGER REFERENCES ventas(id_venta),
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario),
    saldo_anterior INTEGER,
    saldo_final INTEGER,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cobro_operaciones_operation_id
    ON cobro_operaciones (operation_id);
