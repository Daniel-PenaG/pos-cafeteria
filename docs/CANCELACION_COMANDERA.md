# Cancelación de líneas enviadas a comandera

Rama: `fix/eliminar-linea-duplicada`

Base: `main` (Fase 2A ya integrada)

Migración: `004_cancelacion_lineas`

**No merge. No despliegue. No aplicar migraciones en producción. No publicar APK.**

---

## Diagnóstico

Pedido Mesa 3, Waffle sencillo con badge **en comanda**. Al quitar la línea, Ventas mostraba solo «Error al eliminar línea».

### 1. Duplicado / cantidad 2

No era un fallo de la idempotencia de Fase 1 (misma UUID pendiente).

El flujo real:

1. Primer toque completa el intent (`completeIntent`) y deja cantidad 1, aún sin confirmar.
2. Un segundo toque **intencional** (o un toque que llegó después de que el primero ya respondió) genera **otra UUID**.
3. El backend fusiona la misma `line_key` y suma cantidad → **una línea con cantidad 2**.
4. «Confirmar pedido» marca esa línea `en_comanda`.

Si la primera unidad ya estaba en comanda y el segundo agregado va con `enviar_comanda=false`, se crea una línea nueva (`line_key` con sufijo `-n{timestamp}`). En el caso observado de Mesa 3 el síntoma compatible es **una sola línea con cantidad 2** ya enviada.

El candado global del botón de producto (`addLockRef`) no causaba el duplicado; sí impedía agregar un producto B mientras A estaba en vuelo. Eso se cambió a un candado **por producto**.

Inventario: se descuenta al **cobrar**, no al agregar ni al enviar a comanda. Cancelar antes del cobro no genera movimientos de stock.

### 2. Error al eliminar (reproducido)

| Campo | Valor |
|-------|--------|
| Request | `DELETE /pedidos/lineas/{id_detalle_pedido}` |
| Status original | **500** en PostgreSQL |
| Body original | HTML/texto de servidor (sin `detail` JSON de FastAPI) |
| Frontend | `err.response?.data?.detail \|\| "Error al eliminar línea"` → mensaje genérico |

Causa: `DELETE` borraba el `detalle_pedido` aunque `en_comanda=true`. `pedido_operaciones.id_detalle_pedido` es FK **sin ON DELETE SET NULL**. En PostgreSQL el `IntegrityError` subía como 500. En SQLite la FK suele no aplicarse, por eso el test anterior no lo veía.

Regla que faltaba: una línea **en comanda no se borra**. Hay que registrar una cancelación explícita.

---

## Diseño elegido

| Situación | Operación |
|-----------|-----------|
| Línea **no** enviada | `DELETE` o `PATCH` cantidad. Se anula el FK de `pedido_operaciones` antes de borrar. Módulo `/ventas` o `/ventas-para-llevar` según el pedido real. |
| Línea **en comanda** | `POST /pedidos/lineas/{id}/cancelar`. No borra el registro. Motivo obligatorio. |
| Cancelar 1 de 2 | Cantidad activa 1 + aviso `CANTIDAD CAMBIÓ DE 2 A 1`. |
| Cancelar toda | `estado_linea=CANCELADA`, cantidad 0. Historial conservado. Aviso `CANCELADO`. |
| Comandera | El aviso permanece hasta «Vi / Atendí», también si el pedido ya está COBRADO o CANCELADO. Refresco 8 s. Sin WebSocket. PARA LLEVAR y mesa se conservan. |
| Cobrado / cancelado | Cancelar o editar la línea → 422. El aviso pendiente no se oculta. |
| Concurrencia | `SELECT … FOR UPDATE` en PostgreSQL, orden Pedido → Detalle. Datos desfasados → **409**. |
| Auditoría | `CANCELACION`. Fallo de auditoría (savepoint) no revierte, igual que Fase 2A. Usuario desde JWT. |

### Acción `CANCELAR_PRODUCTO_EN_COMANDA`

No existía un permiso equivalente. No se reutilizó `COBRAR_DESDE_COMANDERA`.

- ADMIN: la tiene (todas las acciones).
- CAJERO: hay que asignarla en Usuarios.
- COCINA: no se concede por defecto (solo marca el aviso visto con `/comandera`).

---

## Migración 004

Orden: **002 → 003 → 004**.

Archivos: `backend/migrations/004_cancelacion_lineas.{up,down}.sql`

- Columnas `detalle_pedido.estado_linea`, `cantidad_cancelada`.
- Tabla `pedido_cancelaciones`.
- Idempotente (`IF NOT EXISTS`).
- El arranque replica las sentencias; **no se ejecutó en producción**.
- DOWN **borra el historial de cancelaciones**. No usarlo en producción sin respaldo.
- Tras aplicar 004, `verificar_esquema_cancelacion()` comprueba columnas y tabla. Si falta algo crítico el backend no arranca. Los logs citan el tipo de error, nunca `DATABASE_URL`, usuario ni contraseña.

### Recuperación si el esquema 004 está incompleto

1. Detener el backend (no continúa con un esquema a medias).
2. En mantenimiento, aplicar solo el UP: `backend/migrations/004_cancelacion_lineas.up.sql` (no copiar la URL ni credenciales a tickets o capturas).
3. Verificar `detalle_pedido.estado_linea`, `detalle_pedido.cantidad_cancelada`, tabla `pedido_cancelaciones` y sus columnas.
4. Volver a iniciar. Si 004 ya estaba aplicada, repetir el UP es seguro (`IF NOT EXISTS`).
5. No ejecutar el DOWN salvo en una base desechable.

---

## Avisos después del cobro

`GET /comandera/pendientes` lista toda fila con `vista_comandera = false`. No usa `_pedido_visible_en_comandera()` para cancelaciones.

El aviso conserva mesa, PARA LLEVAR, producto, cantidad cancelada y puede marcar `CUENTA COBRADA`. Recargar, cobrar o cancelar el pedido no lo quita. Solo desaparece con «Vi / Atendí». Una segunda llamada a visto es idempotente (200, `ya_atendida`, mismos usuario y fecha iniciales).

---

## Orden de bloqueos

Siempre:

1. `PedidoModel` (`SELECT … FOR UPDATE`)
2. `DetallePedidoModel` (`SELECT … FOR UPDATE`, por `id_detalle_pedido`)

Mismo orden en cancelar, PATCH, DELETE, marcar listo y cobro (el cobro bloquea el pedido y después todos los detalles ordenados por id). Tras el bloqueo se vuelve a validar estado, pertenencia, `CANCELADA`, cantidades y pendiente. Si el dispositivo traía datos viejos: 409, rollback, el frontend refresca.

Invariantes: `cantidad >= 0`, `cantidad_lista >= 0`, `cantidad_lista <= cantidad`, `cantidad_cancelada >= 0`. Una línea `CANCELADA` no vuelve a marcarse lista.

---

## Endpoints

- `GET /pedidos/motivos-cancelacion`
- `POST /pedidos/lineas/{id}/cancelar`
- `POST /comandera/cancelaciones/{id}/visto`
- `GET /comandera/pendientes` incluye `tipo: CANCELACION` además de pendientes normales.

---

## Validación

Backend: `python -m pytest -q`

Frontend: `npm test`, `npm run lint`, `npm run build`, `npm run build:android` (solo sync; sin APK).

PostgreSQL (solo si `POSTGRES_TEST_URL` apunta a una base de prueba, nunca producción):

- `python -m pytest -q tests/test_estabilidad_postgres.py`
- `python -m pytest -q tests/test_cancelacion_postgres.py`
