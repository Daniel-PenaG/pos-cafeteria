# Rendimiento: agregar producto al pedido

Rama: `performance/agregar-producto-pedido`

## Causa raíz confirmada

### Frontend (flujo lento percibido)

1. **Selección de producto:** `handleProductoClick()` esperaba `GET /promociones/opciones/{id}` antes de abrir el modal.
2. **Apertura del modal:** `abrirModalProducto()` duplicaba promociones con `GET /promociones/aplicables/{id}` además de `GET /ventas/extras`.
3. **Cálculo:** `useEffect` disparaba `POST /promociones/calcular` en cada cambio, incluso cuando cantidad=1 sin extras ya tenía precio conocido.
4. **Agregar:** Tras `POST /pedidos/mesa/{n}/lineas` se ejecutaban `GET /pedidos/mesa/{n}` y `GET /pedidos/activos` de forma **bloqueante** (`await cargarPedidoMesa`).

### Backend

1. **`agregar_linea_pedido()`:** Hasta **3 commits** por operación (insertar/actualizar → recalcular promociones → refresh).
2. **`GET /pedidos/mesa/{n}`:** `pedido_respuesta()` llamaba `recalcular_promociones_pedido()` que **escribía** en BD en una operación de lectura.

---

## Cambios implementados

| Área | Cambio |
|------|--------|
| API | `GET /ventas/productos/{id}/contexto` — producto, extras, promociones, paquetes, `calculo_inicial` |
| POST línea | Respuesta `Pedido` completo (no solo la línea) |
| POST combo | Respuesta `Pedido` completo, un commit |
| GET pedido | `pedido_respuesta_lectura()` — recalcula para mostrar, **sin commit** |
| Frontend | Modal inmediato + “Cargando opciones…” + caché por producto |
| Frontend | `setPedido(respuestaPOST)` sin GET posterior |
| Frontend | Mesas activas: actualización local + refresh en segundo plano |
| Cálculo | Debounce 250 ms; reutiliza `calculo_inicial`; ignora respuestas obsoletas |

---

## Tabla de peticiones HTTP

| Acción | Antes (medido en código) | Después |
|--------|--------------------------|---------|
| Abrir producto (sin promo/combo previo) | 3–4 (`opciones` + `extras` + `aplicables` + `calcular`) | **1** (`contexto`); `calcular` solo si cambian qty/extras/promo |
| Abrir producto (con diálogo promo) | 1 (`opciones`) + luego 3 al abrir modal | **1** (`contexto`, cacheable) |
| Agregar producto (camino crítico) | **3** bloqueantes (`POST lineas` + `GET mesa` + `GET activos`) | **1** bloqueante (`POST lineas` → pedido) |
| Refresh mesas tras agregar | Bloqueante (`await`) | Segundo plano (no bloquea UI) |

*Tiempos wall-clock dependen de red/local/staging; no se inventan ms aquí. Medir con DevTools Network en entorno objetivo.*

---

## Tabla backend (agregar línea)

| Métrica | Antes | Después |
|---------|-------|---------|
| Commits por `agregar_linea` | 2–3 | **1** |
| `flush` | Varios implícitos | 1 antes del commit final |
| `refresh` | 2–4 | 1 tras commit (reload pedido) |
| GET pedido escribe BD | Sí (`recalcular` + commit) | **No** (`pedido_respuesta_lectura`) |
| Transacción atómica | Parcial (commits intermedios) | **Sí** (rollback completo si falla) |

*Conteo SQL: usar `PERF_LOG_SQL=1` en local/staging por endpoint.*

---

## Pruebas

```bash
cd backend && python -m pytest -q
# 111 passed (13 nuevas en test_agregar_producto_pedido.py)
```

```bash
cd frontend && npm run lint && npm run build && npm run build:android
```

---

## Riesgos / pendientes

- **Staging/Render:** medir latencia real con DevTools; no incluida en CI.
- **Caché frontend:** se invalida al recargar catálogo de productos; no persiste entre sesiones.
- **Compatibilidad API:** clientes que esperaban `DetallePedidoLinea` en `POST .../lineas` deben usar el `Pedido` devuelto (frontend POS actualizado).

---

## Validación manual sugerida

1. Seleccionar producto → modal visible al instante con “Cargando opciones…”.
2. Network: una sola petición `contexto` al abrir (segunda vez desde caché si mismo producto).
3. Agregar → una sola petición `POST .../lineas`; **no** debe aparecer `GET .../mesa` inmediato después.
4. Carrito actualizado con total correcto y promociones ticket.
5. Combo y para llevar: mismo comportamiento (POST devuelve pedido completo).
