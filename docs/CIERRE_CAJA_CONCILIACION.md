# Fase 3A: Apertura, movimientos, arqueo y conciliación de caja

COFFE SONG. El cierre deja de ser un arqueo por día calendario y pasa a ser una **sesión / turno de caja**.

No ejecutar esta migración en producción desde esta rama. No hay merge, PR, despliegue ni APK.

## 1. Diagnóstico anterior

El cierre previo (`cierres_caja` + `cierre_service`) agrupaba ventas por **usuario y fecha México**. Solo capturaba efectivo contado, comparaba contra ventas en efectivo y permitía **un cierre por usuario y día**.

No existía:

- apertura formal ni fondo inicial;
- sesión o turno;
- libro de entradas/salidas;
- conciliación de transferencia y terminal;
- arqueo por denominaciones;
- revisión administrativa;
- bloqueo de cobro si no hay caja.

`bucket_forma_pago` mandaba métodos desconocidos a **EFECTIVO**, lo que inflaba el efectivo esperado.

El módulo **Gastos** sigue siendo un gasto administrativo del día: no se asume que salió del cajón.

Los cobros (`registrar_venta`) no ataban la venta a una caja. `id_usuario` del cliente ya se sustituye por el token (Fase 2A).

Zona horaria: `timezone_mx` (America/Mexico_City) para día de snapshot y presentación. Las marcas de sesión se guardan en UTC naive y se serializan con `isoformat_utc`.

Impresión: ESC/POS 58 mm existente. El resumen de cierre se genera **después** de persistir; si falla, el cierre permanece.

## 2. Decisiones de diseño

- Se conserva `cierres_caja` como snapshot de compatibilidad. El operativo es `sesiones_caja`.
- Un cajero y una terminal solo pueden tener una sesión `ABIERTA` o `EN_ARQUEO` (índice único parcial + validación de servicio).
- El backend elige la sesión del usuario autenticado. El frontend no elige una sesión ajena.
- Ventas históricas **no** se reasignan a sesiones nuevas (`id_sesion_caja` queda NULL).
- `venta_pagos` se crea ahora (un pago monetario por venta). **PUNTOS no se habilita** en API ni UI.
- `CAJA_REQUERIDA_PARA_COBRAR` default `0` para no romper el APK anterior. Activarla a `1` cuando todos los cajeros abran caja y se haya validado el flujo.
- Métodos nulos/vacíos históricos → EFECTIVO. Un valor explícito desconocido (incl. PUNTOS) → `DESCONOCIDO` y **no** suma al efectivo.
- Gastos del módulo Gastos no se descuentan de caja. `GASTO_CAJA` es un movimiento explícito del cajón; `id_gasto` es referencia única opcional.
- Orden de bloqueo: **sesión de caja primero**, luego pedido/venta. `SELECT FOR UPDATE` solo en PostgreSQL.
- Ajustes (`AJUSTE`) solo ADMIN.
- Un cajero no revisa su propio cierre.
- Forzar cierre con pedidos abiertos no cobra ni cancela.

## 3. Modelo de datos

Tablas nuevas / campos:

| Tabla / campo | Uso |
| --- | --- |
| `sesiones_caja` | Turno: apertura, arqueo, totales congelados, revisión, anulación |
| `movimientos_caja` | Libro: FONDO_INICIAL, ENTRADA, RETIRO, GASTO_CAJA, DEVOLUCION, AJUSTE, REVERSO |
| `arqueo_denominaciones` | Conteo por código (B1000… M050) |
| `venta_pagos` | Componentes de pago (solo monetarios en 3A) |
| `ventas.id_sesion_caja` | Venta nueva → sesión activa |
| `cierres_caja.id_sesion_caja` | Snapshot legado por turno |
| `configuracion.tolerancia_efectivo` | Default $5 MXN |

Estados: `ABIERTA` → `EN_ARQUEO` → `CERRADA_CONCILIADA` \| `CERRADA_CON_DIFERENCIA` → `REVISADA`. También `ANULADA`.

## 4. Fórmula del efectivo esperado

```
fondo inicial
+ ventas en efectivo
+ entradas de efectivo
- retiros de efectivo
- gastos pagados desde caja
- devoluciones en efectivo
± ajustes autorizados
= efectivo esperado
```

Transferencia y terminal se concilian aparte (esperado = ventas de ese método). Diferencia = declarado − esperado. Sin redondeos que oculten faltantes.

Dentro de tolerancia de efectivo **y** diferencia 0.00 en transferencia/terminal → `CERRADA_CONCILIADA`. Fuera → `CERRADA_CON_DIFERENCIA` y observación obligatoria.

## 5. Permisos (Fase 2A)

| Acción | ADMIN | CAJERO | COCINA |
| --- | --- | --- | --- |
| ABRIR_CAJA | sí | sí | no |
| REGISTRAR_MOVIMIENTO_CAJA | sí | sí | no |
| CERRAR_CAJA | sí | sí | no |
| REVISAR_CIERRE_CAJA | sí | no | no |
| ANULAR_CIERRE_CAJA | sí | no | no |
| FORZAR_CIERRE_CON_PEDIDOS_ABIERTOS | sí | no | no |

Módulo `/cierre-caja` para operar. `/cierres-dia` para administración. El backend valida acciones; el frontend solo oculta botones.

## 6. Endpoints

| Método | Ruta | Uso |
| --- | --- | --- |
| GET | `/caja/terminales` | CAJA-1, CAJA-2, CAJA-3, BARRA |
| GET | `/caja/sesion` | Sesión activa del token (ciego si EN_ARQUEO) |
| POST | `/caja/abrir` | Fondo, terminal, observación, operation_id |
| POST | `/caja/movimientos` | Entrada/retiro/gasto/devolución |
| POST | `/caja/arqueo` | Pasa a EN_ARQUEO (sin mostrar esperados) |
| POST | `/caja/cerrar` | Denominaciones o captura directa + declarados |
| GET | `/caja/sesiones` | Admin: filtro estado / cajero |
| GET | `/caja/sesiones/{id}` | Detalle / trazabilidad |
| POST | `/caja/sesiones/{id}/revisar` | Admin distinto al cajero |
| POST | `/caja/sesiones/{id}/anular` | Motivo obligatorio |

`/cierres` legado se conserva para snapshots diarios históricos.

Conflictos de estado e idempotencia inconsistente → **409**.

## 7. Migración 005

Archivos:

- `backend/migrations/005_cierre_caja_conciliacion.up.sql`
- `backend/migrations/005_cierre_caja_conciliacion.down.sql`

UP: idempotente en PostgreSQL. Crea tablas/índices, quita el único `(id_usuario, fecha)` de `cierres_caja` para permitir varios turnos el mismo día, backfill de `venta_pagos` con `operation_id = backfill-venta-{id}` (no se duplica).

DOWN: **borra** sesiones, movimientos, arqueos y `venta_pagos`. Las ventas y los `cierres_caja` históricos se conservan (solo se quita `id_sesion_caja`). No usar en producción sin respaldo.

SQLite de pruebas: `create_all` + ALTER idempotentes. **No** simula `FOR UPDATE`.

No se aplica en producción en este trabajo.

## 8. Compatibilidad y feature flag

- Pedidos, Comandera, cancelaciones, impresión de venta y seguridad Fase 2A no cambian de contrato.
- Ventas sin sesión siguen consultables.
- APK anterior: si `CAJA_REQUERIDA_PARA_COBRAR=0` el cobro sigue. Si se activa (`1`), el cobro sin caja responde 422: `Abre una caja antes de cobrar.`
- Activar el flag **después** del despliegue, de abrir caja en cada terminal y de validar el flujo manual. No dejar un bypass silencioso permanente.

## 9. Preparación para puntos

`venta_pagos` ya admite `cantidad_puntos` y `equivalencia_puntos` nulos. En 3A solo EFECTIVO / TRANSFERENCIA / TARJETA. No hay UI ni validación de canje. Un método `PUNTOS` explícito no infla efectivo.

## 10. Auditoría

Eventos: `CAJA_ABIERTA`, `CAJA_MOVIMIENTO`, `CAJA_ARQUEO`, `CAJA_CERRADA`, `CAJA_DIFERENCIA`, `CAJA_REVISADA`, `CAJA_ANULADA`, `CAJA_FORZAR`. Sin tokens, contraseñas ni `DATABASE_URL`.

## 11. Pruebas

Backend SQLite: `tests/test_caja.py` (apertura, flag, movimientos, fórmula, arqueo, diferencia, pedidos, forzar, revisión propia, ajeno, doble cierre, idempotencia, desconocido, histórico, TZ México).

PostgreSQL desechable: `tests/test_caja_postgres.py` (únicos, apertura/cierre/movimientos concurrentes, venta vs cierre, 005 dos veces, pre-005 → UP, guarda contra `DATABASE_URL`).

Frontend: denominaciones, `bucketFormaPago`, permisos de caja, ticket ESC/POS.

## 12. Despliegue futuro (no en esta rama)

Riesgo de APK: si se activa `CAJA_REQUERIDA_PARA_COBRAR=1` antes de actualizar el APK, un APK anterior que no permita abrir caja puede quedar imposibilitado para cobrar. **No activar el flag en producción desde este trabajo.**

Orden futuro obligatorio:

1. Respaldo PostgreSQL.
2. Deploy backend con flag en `0`.
3. Verificar migración 005.
4. Deploy web nuevo.
5. Generar e instalar APK nuevo.
6. Probar apertura y cobro.
7. Solo después cambiar el flag a `1`.
8. Reiniciar/verificar backend.
9. Ejecutar una venta controlada.

Rollback de código: DOWN solo con respaldo (borra sesiones, movimientos, arqueos y `venta_pagos`).

## 13. Validación manual

Resoluciones: 320×568, 360×800, 390×844, 412×915, 768×1024, 1024×768, 1366×768.

Perfiles: ADMIN, CAJERO, COCINA.

Flujo: abrir con fondo → cobrar efectivo, transferencia y terminal → entrada, retiro, gasto de caja → arqueo ciego por denominaciones → declarar transferencia/terminal → cerrar → conciliación → revisar como ADMIN → imprimir → confirmar que el cierre no se modifica.

## 14. Riesgos

- Activar el flag demasiado pronto bloquea el APK viejo.
- Dos turnos el mismo día ya no chocan con el único histórico; los reportes diarios antiguos no equivalen a un turno.
- SQLite de pruebas no demuestra carreras reales.
- Un gasto del módulo Gastos **no** reduce el cajón salvo que se registre `GASTO_CAJA`.
- DOWN destruye el libro de caja.
