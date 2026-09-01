# Validación: pagos, precuenta y Comandera para llevar

Rama: `feature/pagos-precuenta-comandera`

## Flujo de cobro

### Mesa (`/ventas`)

1. **Cerrar cuenta / Cobrar** → imprime **PRECUENTA** solo en APK Android → abre modal de pago.
2. Botón deshabilitado mientras imprime; un solo modal; doble clic ignorado.
3. En modal (solo APK): **Reimprimir precuenta** (no cobra, no descuenta inventario).
4. Texto *La precuenta ya fue impresa* solo si realmente se imprimió en APK.
5. En **web**: no se imprime precuenta; no se afirma que se imprimió.
6. Modal: Efectivo / Transferencia / Terminal (`TARJETA` interno).
7. Solo al confirmar se ejecuta `cobrarPedido()`.
8. **Mesa:** no se imprime ticket final al cobrar.

### Para llevar (`/ventas-para-llevar`)

1. **Confirmar pedido / Enviar a comandera** envía solo líneas pendientes (sin impresión automática de comanda física).
2. **No imprime precuenta** al cobrar.
3. Al cobrar: si hay líneas sin enviar, advertencia; si el envío falla, no abre modal de pago.
4. Tras elegir forma de pago:
   - **APK Android:** pregunta **¿Deseas imprimir el ticket?**
   - **Web:** cobra directamente sin pregunta de impresión.
5. Si imprime (APK): registra venta → ticket final con forma de pago.
6. Si no imprime: solo registra venta.

## Precuenta (sin forma de pago)

Implementada en `frontend/src/services/escposTickets.js` → `buildPrecuentaTicket`.

**Incluye:** mesa/origen, pedido, productos, extras, comentarios, promos, subtotal, descuento, total, leyenda `PENDIENTE DE PAGO`.

**No incluye:** forma de pago, efectivo, transferencia, terminal, recibido, cambio, folio de venta, puntos.

**Para llevar:** no se imprime precuenta.

## Comandera después de cobrar para llevar

- `GET /comandera/pendientes` incluye pedidos `ABIERTO` y pedidos `COBRADO` con `para_llevar=true` que tengan cantidades pendientes.
- Pedidos mesa `COBRADO` no aparecen.
- Pedidos `CANCELADO` no aparecen ni permiten marcar listo.
- `marcar_listo()` acepta `COBRADO + para_llevar=true`.
- Al marcar todas las unidades, el pedido desaparece de Comandera.

## Comanda cocina (impresión manual futura)

`buildComandaTicket` conserva encabezado PARA LLEVAR pero **no se llama automáticamente** al confirmar pedido.

## Terminal vs TARJETA

| Interno   | UI / tickets / reportes |
|-----------|-------------------------|
| EFECTIVO  | Efectivo                |
| TRANSFERENCIA | Transferencia       |
| TARJETA   | Terminal                |

Utilidades centralizadas:

- Backend: `backend/app/utils/forma_pago.py`
- Frontend: `frontend/src/utils/formaPago.js`

## Cierre de caja

- Tarjetas: total día, número de ventas, desglose Efectivo / Transferencia / Terminal (importe + cantidad).
- `Efectivo + Transferencia + Terminal = Total del día`
- Filtro de día: `fecha_hora >= inicio` y `fecha_hora < fin` (venta a las 00:00 del día siguiente no entra al cierre anterior).
- **Detalle de pagos** con filtro Todos / Efectivo / Transferencia / Terminal.
- Arqueo: `efectivo contado − efectivo registrado` (transferencia y terminal excluidos).

## Cuentas por cajero

Por cajero: total efectivo, transferencia, terminal, cantidades y total general. Filtro por método en detalle.

## Reportes

Sección **Métodos de pago** (`GET /reportes/desglose-pagos`): totales, operaciones y porcentajes por periodo. Respeta filtros de fecha.

## Pagos mixtos

No implementados. Mejora futura documentada en requerimiento §7.

## Pruebas backend

```bash
cd backend && python -m pytest -q
```

**98 pruebas** (71 existentes + 27 nuevas/ajustadas de pagos/comandera).

Casos nuevos relevantes: para llevar visible tras cobro, marcar listo tras cobro, desaparece al completar, cancelado excluido, dos pedidos pagados separados, mesa cobrada excluida, límite medianoche en cierre.

## Build frontend

```bash
cd frontend && npm ci && npm run lint && npm run build && npm run build:android
```

## Evidencia manual (capturas / video)

| Escenario | Estado |
|-----------|--------|
| Mesa: precuenta antes del pago | Pendiente impresora física |
| Precuenta sin forma de pago | Pendiente impresora física |
| Botón Reimprimir precuenta (APK) | Pendiente impresora física |
| Para llevar: sin precuenta | Verificar en UI |
| Pregunta ticket final (APK para llevar) | Pendiente impresora física |
| Para llevar cobrado visible en Comandera | Verificar en UI |
| Desaparece al marcar todo listo | Verificar en UI |
| Cierre de caja desglosado | Verificar en UI |
| Cuentas por cajero | Verificar en UI |
| Reportes por método | Verificar en UI |

**Nota:** prueba física de impresión Bluetooth marcada como pendiente si no hay impresora disponible.
