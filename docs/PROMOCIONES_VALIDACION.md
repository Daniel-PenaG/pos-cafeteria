# Validación promociones — evidencia (2026-08-31)

Rama: [`feature/promociones-ticket-level`](https://github.com/Daniel-PenaG/pos-cafeteria/tree/feature/promociones-ticket-level)

## Resumen pruebas automatizadas

| Métrica | Valor |
|---------|-------|
| Pruebas anteriores | **5** |
| Pruebas actuales | **53** |
| Agregadas | **48** |
| Aprobadas | **53** |
| Fallidas | **0** |

```bash
cd backend && python -m pytest -q
# 53 passed
```

## Casos automatizados agregados

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
- Transacción: documentación doble commit + venta huérfana simulada

## Bugs corregidos en esta validación

1. **`recalcular_lineas_ticket`**: promociones de línea (%, fijo, 2×1) se ignoraban tras expandir unidades sin promo ticket.
2. **`registrar_venta`**: `sin_promocion=True` cuando `id_promocion` era null impedía auto-aplicar promos de línea.

## Riesgos documentados (sin cambio en esta tarea)

| Riesgo | Severidad | Detalle |
|--------|-----------|---------|
| Transacción no atómica | **Alta** | `registrar_venta` hace 2× `commit`. Fallo post-venta puede dejar venta sin detalles. Ver `test_fallo_segundo_commit_deja_venta_huerfana`. |
| `valor_promocion` en líneas | Baja | Promos de línea no guardan `valor_promocion` en `detalle_venta` (solo ticket). `nombre_promocion` y `tipo_promocion` sí. |
| Impresión ticket | — | No validada en CI; requiere hardware Coffe Song. |

## Pruebas manuales pendientes

Ver [`PROMOCIONES_MANUAL_TESTS.md`](PROMOCIONES_MANUAL_TESTS.md):

- Caso 12: impresión física → **PENDIENTE**
- Reportes en staging → **PENDIENTE**

## Frontend (rama promociones)

```bash
cd frontend && npm run lint && npm run build
```

*(Ejecutar tras commit; ver salida en push)*

## Commits

Ver `git log feature/promociones-ticket-level` tras push.
