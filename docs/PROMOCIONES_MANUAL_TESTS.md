# Pruebas manuales — Promociones (pre-producción)

Rama: `feature/promociones-ticket-level`  
**Commit de referencia:** `d25c0a8` (transacción atómica en `registrar_venta`)  
Ejecutar en **staging o SQLite local**. No usar credenciales ni datos de producción.

La suite automatizada (**58 pruebas aprobadas**) cubre cálculo de promos, inventario, fidelidad, mesa/cobro y rollback transaccional. Las pruebas manuales siguientes complementan lo que CI no puede validar (impresión física, revisión visual de reportes).

## Leyenda de estados

| Estado | Significado |
|--------|-------------|
| **APROBADO** | Ejecutado y verificado |
| **FALLÓ** | Ejecutado con resultado incorrecto |
| **PENDIENTE** | Requiere usuario, tablet, impresora o staging |
| **NO APLICA** | No aplica en este entorno |

## Matriz de casos

| Caso | Total esperado | Total obtenido | Estado | Evidencia | Observaciones |
|------|---------------:|---------------:|--------|-----------|---------------|
| 1. Venta normal sin promoción | Suma de subtotales | — | **APROBADO** (automatizado) | `test_venta_normal_varios_productos` | API: total=165, `id_promocion` null |
| 2. Porcentaje (20 % sobre $65) | $52.00 | — | **APROBADO** (automatizado) | `test_venta_porcentaje`, `test_porcentaje_una_y_varias_unidades` | Descuento $13/u |
| 3. Precio fijo ($49) | $49.00 | — | **APROBADO** (automatizado) | `test_venta_precio_fijo`, `test_precio_fijo_con_snapshot` | Snapshot nombre promo |
| 4. Descuento fijo ticket ($10) | $55.00 | — | **APROBADO** (automatizado) | `test_descuento_fijo_ticket` | Tipo `DESCUENTO_FIJO`, cantidad_requerida=1 |
| 5. 2×1 (2×$65) | $65.00 | — | **APROBADO** (automatizado) | `test_venta_dos_x_uno`, `test_dos_x_uno_cantidades` | Ver tabla cantidades abajo |
| 6. Cantidad-precio (2×$90) | 1→$65, 2→$90, 3→$155, 4→$180 | — | **APROBADO** (automatizado) | `test_cantidad_precio_malteadas`, `test_venta_cantidad_precio_ticket` | Distribuye en varias líneas |
| 7. Paquete/combo | $60 paquete | — | **APROBADO** (automatizado) | `test_combo_paquete` | 2 productos, suma partes = total paquete |
| 8. Extras | base + extra | — | **APROBADO** (automatizado) | `test_venta_con_extras`, `test_inventario_extra` | Promo aplica solo al producto, extra suma aparte |
| 9. Mesa (comanda → cobro) | Según promo | — | **APROBADO** (automatizado) | `test_flujo_mesa_cobro`, `test_doble_cobro_pedido_rechazado`, `test_cobro_correcto_persiste_venta_detalle_inventario_pedido` | Pedido COBRADO en un solo commit; doble cobro rechazado |
| 10. Para llevar (mesa 99) | $52 con 20 % | — | **APROBADO** (automatizado) | `test_para_llevar_mesa_99` | `para_llevar=true` |
| 11. Cliente y puntos | floor(total/10) | — | **APROBADO** (automatizado) | `test_fidelidad_sobre_total_con_descuento` | Puntos sobre total pagado ($32.50→3 pts) |
| 12. Total e impresión ticket | Modal = venta | — | **PENDIENTE** | — | Requiere tablet e impresora Coffe Song |

## 2×1 — regla de cobro (documentada en pruebas)

Precio base unitario $100:

| Unidades | Unidades pagadas | Total ticket |
|---------:|-----------------:|-------------:|
| 1 | 1 | $100 |
| 2 | 1 | $100 |
| 3 | 2 | $200 |
| 4 | 2 | $200 |
| 5 | 3 | $300 |

Fórmula: `unidades_pagadas = ceil(cantidad / 2)`; total = unidades_pagadas × precio_base.

## Instrucciones — impresión ticket (caso 12)

1. Levantar backend local: `cd backend && uvicorn app.main:app --reload`
2. Levantar frontend: `cd frontend && npm run dev`
3. Login cajero en tablet Android o Chrome DevTools (390×844).
4. Crear venta con promo visible (ej. 20 % malteada).
5. Cobrar en efectivo; verificar total en modal de cobro.
6. Imprimir ticket Bluetooth o PDF.
7. Verificar: líneas, descuentos por promo, forma de pago, cambio (si efectivo).
8. Registrar en columna «Total obtenido» y cambiar estado a APROBADO o FALLÓ.

## Transacción atómica (automatizado en `d25c0a8`)

| Escenario | Estado | Prueba |
|-----------|--------|--------|
| Fallo al crear detalle → no queda venta | **APROBADO** (automatizado) | `test_fallo_al_crear_detalle_no_persiste_venta` |
| Fallo inventario → no venta ni movimiento | **APROBADO** (automatizado) | `test_fallo_inventario_no_persiste_venta_ni_movimiento` |
| Fallo fidelidad → no venta ni puntos | **APROBADO** (automatizado) | `test_fallo_fidelidad_no_persiste_venta_ni_puntos` |
| Fallo cerrar pedido → pedido coherente | **APROBADO** (automatizado) | `test_fallo_cerrar_pedido_no_persiste_venta_pedido_abierto` |
| Reintento no duplica venta | **APROBADO** (automatizado) | `test_reintento_tras_fallo_no_duplica_venta` |

## Regresión reportes

**PENDIENTE** en staging: Reportes → verificar promociones en detalle y totales vs suma manual.

## Seed local opcional

```bash
# backend/.env
LOCAL_SEED_PROMO=true
```

Solo SQLite. Reiniciar API local. Crea promo demo **INACTIVA** «Lunes de Malteadas» si existe categoría Malteadas. **No usar en Render/producción.**
