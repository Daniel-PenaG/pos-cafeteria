# Validación: pagos, precuenta y Comandera para llevar

Rama: `feature/pagos-precuenta-comandera`

## Flujo de cobro

### Mesa (`/ventas`)

1. **Cerrar cuenta / Cobrar** → imprime **PRECUENTA** (APK Android) → abre modal de pago.
2. Pedido y mesa permanecen abiertos hasta confirmar el pago.
3. Modal: Efectivo / Transferencia / Terminal (`TARJETA` interno).
4. Efectivo: importe recibido y cambio; no permite importe menor al total.
5. Transferencia y Terminal: sin recibido ni cambio.
6. Solo al confirmar se ejecuta `cobrarPedido()`.
7. **Mesa:** no se imprime ticket final al cobrar.

### Para llevar (`/ventas-para-llevar`)

1. **Confirmar pedido / Enviar a comandera** envía solo líneas pendientes.
2. Al cobrar: si hay líneas sin enviar, advertencia con opción de enviar.
3. Tras elegir forma de pago: pregunta **¿Deseas imprimir el ticket?**
4. Si imprime: registra venta → ticket final con forma de pago.
5. Si no imprime: solo registra venta.

## Precuenta (sin forma de pago)

Implementada en `frontend/src/services/escposTickets.js` → `buildPrecuentaTicket`.

**Incluye:** mesa/origen, pedido, productos, extras, comentarios, promos, subtotal, descuento, total, leyenda `PENDIENTE DE PAGO`.

**No incluye:** forma de pago, efectivo, transferencia, terminal, recibido, cambio, folio de venta, puntos.

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
- **Detalle de pagos** con filtro Todos / Efectivo / Transferencia / Terminal.
- Arqueo: `efectivo contado − efectivo registrado` (transferencia y terminal excluidos).

## Cuentas por cajero

Por cajero: total efectivo, transferencia, terminal, cantidades y total general. Filtro por método en detalle.

## Reportes

Sección **Métodos de pago** (`GET /reportes/desglose-pagos`): totales, operaciones y porcentajes por periodo. Respeta filtros de fecha.

## Comandera para llevar

- Backend: `confirmar_comanda_pedido()` acepta pedidos para llevar.
- `GET /comandera/pendientes` incluye `para_llevar` en cada línea.
- UI agrupa por `id_pedido`; encabezado **PARA LLEVAR / Pedido #N**.
- Comanda cocina: `COMANDA COCINA` + `PARA LLEVAR` + `Pedido #N`.

## Pagos mixtos

No implementados. Mejora futura documentada en requerimiento §7.

## Pruebas backend

```bash
cd backend && python -m pytest -q
```

**91 pruebas** (71 existentes + 20 nuevas de pagos/comandera).

Casos cubiertos: efectivo, transferencia, terminal/TARJETA, forma inválida, etiqueta histórica, cierre por método, suma métodos, arqueo solo efectivo, desglose cajero, filtros reportes, comanda para llevar, dos pedidos separados, líneas adicionales sin duplicar, cobro atómico (suite transacciones existente).

## Build frontend

```bash
cd frontend && npm install && npm run build
```

Build Vite OK (dist generado).

## Evidencia visual sugerida

Capturas manuales en APK/dispositivo:

1. Precuenta impresa (sin forma de pago).
2. Modal Efectivo / Transferencia / Terminal.
3. Cierre de caja con tarjetas por método.
4. Detalle filtrado por método.
5. Cuentas por cajero con totales por método.
6. Reportes → Métodos de pago.
7. Ticket para llevar con forma de pago.
8. Comandera: dos pedidos PARA LLEVAR separados.
