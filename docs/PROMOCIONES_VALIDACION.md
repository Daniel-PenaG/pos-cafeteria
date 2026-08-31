# Validación promociones — evidencia (2026-08-31)

Rama: [`feature/promociones-ticket-level`](https://github.com/Daniel-PenaG/pos-cafeteria/tree/feature/promociones-ticket-level)

**Commit validado:** `d25c0a8` — `fix: transaccion atomica en registrar_venta y cobro de pedido`

## Resumen pruebas automatizadas

| Métrica | Valor |
|---------|-------|
| Pruebas anteriores | **53** |
| Pruebas actuales | **58** |
| Agregadas (rollback atómico) | **+5 netas** (+8 nuevas, −3 obsoletas) |
| Aprobadas | **58** |
| Fallidas | **0** |

```bash
cd backend && python -m pytest -q
# 58 passed, ~95 warnings in ~4s (validación externa 2026-08-31)
```

## Transacción atómica (`d25c0a8`)

`registrar_venta` persiste venta, detalles, inventario, fidelidad y cierre de pedido en **una sola transacción**:

1. No hay `commit()` inmediato tras crear `VentaModel`.
2. Se usa `db.flush()` para obtener `id_venta` sin confirmar parcialmente.
3. Se crean detalles, se descuenta receta/extras y se registran movimientos de inventario.
4. Se acumulan puntos de fidelidad cuando aplica.
5. Se asocia y cierra el pedido vía `VentaCreate.id_pedido` cuando corresponde.
6. Un único `db.commit()` al finalizar el flujo exitoso.
7. Ante cualquier excepción se ejecuta `db.rollback()` y la excepción se propaga (sin captura silenciosa).

Las pruebas en `backend/tests/test_promociones_transaccion.py` verifican que **no quedan** ventas, detalles, movimientos de inventario, cambios de puntos ni pedidos parcialmente modificados ante fallos simulados, y que un reintento posterior no duplica la venta.

| Prueba | Qué verifica |
|--------|--------------|
| `test_registrar_venta_un_solo_commit` | Un solo `commit()` en el flujo exitoso |
| `test_fallo_al_crear_detalle_no_persiste_venta` | Fallo al crear detalle → no existe venta |
| `test_fallo_inventario_no_persiste_venta_ni_movimiento` | Fallo en inventario → no venta ni movimiento |
| `test_fallo_fidelidad_no_persiste_venta_ni_puntos` | Fallo en fidelidad → no venta ni cambio de puntos |
| `test_fallo_cerrar_pedido_no_persiste_venta_pedido_abierto` | Fallo al cerrar pedido → no venta; pedido coherente |
| `test_reintento_tras_fallo_no_duplica_venta` | Reintento posterior no duplica venta |
| `test_cobro_correcto_persiste_venta_detalle_inventario_pedido` | Cobro correcto persiste todo |
| `test_doble_cobro_pedido_rechazado` | Doble cobro rechazado |

Dependencias dev: `backend/requirements-dev.txt` (`-r requirements.txt`, `pytest`, `httpx`).

## Casos automatizados (suite completa)

- Venta sin promoción (1, N unidades, varios productos)
- Porcentaje, precio fijo, descuento fijo ticket
- 2×1 (cantidades 1–5)
- Cantidad-precio (1–5 unidades, límite por ticket, varias líneas)
- Paquete/combo y producto faltante
- Promociones superpuestas (auto-selección mejor precio)
- Vigencia: vencida, inactiva, no elegible
- Extras + inventario receta/extra
- Mesa, para llevar, fidelidad, snapshots
- Redondeo Decimal

## Bugs corregidos en validación promociones

1. **`recalcular_lineas_ticket`**: promociones de línea (%, fijo, 2×1) se ignoraban tras expandir unidades sin promo ticket.
2. **`registrar_venta`**: `sin_promocion=True` cuando `id_promocion` era null impedía auto-aplicar promos de línea.

## Riesgos / pendientes

| Ítem | Estado |
|------|--------|
| Transacción no atómica | **Resuelto** en `d25c0a8` |
| `valor_promocion` en líneas | Baja — promos de línea no guardan `valor_promocion` en `detalle_venta` |
| Impresión física del ticket | **PENDIENTE** — requiere tablet e impresora Coffe Song |
| Revisión visual de reportes | **PENDIENTE** — staging o entorno local con ventas reales |

Ver [`PROMOCIONES_MANUAL_TESTS.md`](PROMOCIONES_MANUAL_TESTS.md) para casos manuales.

## Frontend (rama promociones)

```bash
cd frontend && npm run lint && npm run build
```

No modificado en `d25c0a8`; ejecutar antes de merge si cambia el frontend en la misma rama.
