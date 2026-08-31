# Pruebas manuales — Promociones (pre-producción)

Ejecutar en **staging o SQLite local** antes de merge/deploy de la rama `feature/promociones-ticket-level`.

## Preparación

1. Admin → Promociones: crear o activar promos de prueba (una por tipo).
2. Productos con receta y margen conocido.
3. Extras configurados en al menos un producto.
4. Impresora Bluetooth configurada (opcional) o ver ticket en pantalla.

## Casos

| # | Escenario | Pasos | Verificar |
|---|-----------|-------|-----------|
| 1 | **Venta normal sin promoción** | Mesa → producto sin promo → cobrar efectivo | Total = suma líneas; `detalle_venta.id_promocion` null; ticket muestra precios sin descuento |
| 2 | **Porcentaje** | Promo `PORCENTAJE` activa en producto/categoría → vender 1 unidad | Descuento % correcto; subtotal y total coinciden con POS |
| 3 | **Precio fijo** | Promo `PRECIO_FIJO` → vender producto elegible | Precio unitario = valor promo; margen coherente |
| 4 | **2x1** | Promo `DOS_X_UNO` → agregar 2 unidades elegibles | Segunda unidad con descuento; total = 1 × precio |
| 5 | **Cantidad-precio (ticket)** | Promo `CANTIDAD_PRECIO` (ej. 2×$90) → 2+ unidades elegibles en **mismo ticket** | Descuento a nivel ticket; snapshots en `detalle_venta` (`nombre_promocion`, `tipo_promocion`, `valor_promocion`) |
| 6 | **Paquete** | Promo tipo paquete/combo configurada → productos del paquete | Total paquete; todas las líneas con promo aplicada |
| 7 | **Extras** | Producto con extras de pago → aplicar promo si aplica | Extras suman al subtotal; promo no rompe extras_json |
| 8 | **Mesa** | Flujo completo mesa N → comanda → cobro con promo | Pedido cierra; venta ligada; mesa libre |
| 9 | **Para llevar** | Ventas para llevar (mesa 99) con promo | `para_llevar=true`; total correcto |
| 10 | **Total e impresión ticket** | Cobrar cualquier caso anterior | Total en modal = total venta; ticket impreso/PDF con líneas, descuentos, forma de pago, cambio (efectivo) |

## Seed local opcional (solo SQLite)

```bash
# backend/.env
LOCAL_SEED_PROMO=true
```

Reiniciar API local. Crea promo demo **INACTIVA** «Lunes de Malteadas» si existe categoría Malteadas. **No usar en Render/producción.**

## Regresión reportes

Tras ventas de prueba, en Reportes verificar que promociones aparecen en detalle y totales no cambian vs suma manual.
