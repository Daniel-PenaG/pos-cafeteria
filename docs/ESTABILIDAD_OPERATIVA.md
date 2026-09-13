# Fase 1 — Estabilidad operativa POS COFFE SONG

Rama: `fix/estabilidad-operativa-pos`  
Base: `main` actualizado (`git pull origin main`)  
Fecha de medición: 2026-09-13  

**No merge. No despliegue.** Esta rama espera revisión.

---

## 1. Diagnóstico

| Problema | Causa raíz | Archivos |
|----------|------------|----------|
| Comandera en “0s” | `_segundos_transcurridos` usaba `datetime.now()` local; `GET /comandera/pendientes` enviaba `fecha_envio_comanda` naive sin `Z`. En México, JS interpreta ISO sin zona como hora local → diferencia ~6 h → `max(0, …)` = 0. | `comandera.py`, `schemas/pedido.py`, `ElapsedTimer.jsx` |
| Doble agregado | Solo `isLoading` / `guardandoLinea` (estado React). Dos POST simultáneos o un reintento de red duplicaban. | `pedidos.py`, `pedido_service.py`, `Ventas.jsx` |
| Pedidos vacíos | `GET /pedidos/mesa/{n}` llamaba `obtener_pedido_abierto_mesa`, que hacía `commit` de un pedido sin líneas. Si el primer POST fallaba, el vacío quedaba. | `pedido_service.py`, `pedidos.py` |
| Promos en líneas iguales | `trabajo.index(item)` usa igualdad de dict. Dos líneas con el mismo producto/cantidad/extras (comentarios distintos no iban en el dict de cálculo) se asociaban a `line_index` 0. | `promocion_ticket_service.py` |
| Sin personalizar | Un toque agregaba 1 unidad; no había acción visible para cantidad/comentario. | `Ventas.jsx` |
| Caché de contexto | `Map` de sesión sin expiración. Una promo que empieza o termina podía quedar stale. | `productoContextoService.js` |

**No se tocó:** pago con puntos, WiFi, inventario/merma, permisos generales, Elastic Beanstalk, dependencias masivas.

---

## 2. Rama

`fix/estabilidad-operativa-pos` (creada desde `main` actualizado).

---

## 3. Commits

Se publica en esta rama el conjunto de cambios de la fase (ver `git log origin/main..HEAD`).

---

## 4. Archivos modificados (principales)

**Backend:** `timezone_mx.py`, `schemas/pedido.py`, `models.py`, `pedido_service.py`, `pedidos.py`, `comandera.py`, `promocion_ticket_service.py`, `database.py`, `migrations/002_pedido_operaciones.{up,down}.sql`

**Frontend:** `parseUtcDate.js`, `ElapsedTimer.jsx`, `Comandera.jsx`, `Ventas.jsx`, `productoContextoCache.js`, `agregadoRapido.js`, `operationId.js`, `pedidosService.js` (sin cambio de contrato), `global.css`, `package.json`, `eslint.config.js`

**Pruebas:** `test_estabilidad_*.py`, `*.test.js`, `scripts/test-estabilidad-critico.mjs`

---

## 5. Migraciones (un solo mecanismo)

Hay **un** esquema canónico: `backend/migrations/002_pedido_operaciones.{up,down}.sql`.

`aplicar_migraciones_sqlite()` en el arranque **no es otra migración**. Aplica las mismas sentencias de forma idempotente (`IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`) para bases locales y para el arranque del backend. No hay que elegir entre “manual XOR automático”: el SQL versionado es la fuente; el arranque la replica si falta.

**No se aplicó nada en producción en esta corrección.**

### Qué incluye 002

- Tabla `pedido_operaciones`: `operation_id` único, `tipo`, `payload_hash`, `id_detalle_pedido`, `detalle_ids_json`.
- Índice `uq_pedido_operaciones_operation_id`.
- Índice único parcial `uq_pedidos_abierto_mesa` sobre `(numero_mesa, para_llevar) WHERE estado = 'ABIERTO'`.

### Qué se ejecutará al desplegar (después de merge; no ahora)

1. Arranque del backend: `Base.metadata.create_all()` + `aplicar_migraciones_sqlite()` → crea/altera si falta (idempotente).
2. Ops puede aplicar también el SQL explícito (seguro de repetir):

```bash
# Antes: comprobar que no hay dos ABIERTO en la misma mesa/tipo
# SELECT numero_mesa, para_llevar, COUNT(*) FROM pedidos
# WHERE estado = 'ABIERTO' GROUP BY 1, 2 HAVING COUNT(*) > 1;

psql "$DATABASE_URL" -f backend/migrations/002_pedido_operaciones.up.sql
```

Si ya existen dos pedidos `ABIERTO` para la misma mesa, el índice único **falla** hasta consolidarlos.

Revertir:

```bash
psql "$DATABASE_URL" -f backend/migrations/002_pedido_operaciones.down.sql
```

---

## 6. Diseño final de idempotencia

Una clave pertenece a **una** intención (mismo tipo + misma huella de payload). Producto y combo no comparten `pendingOpRef`.

**Frontend** (`operationIntent.js` + `Ventas.jsx`):

1. Huella estable por payload (`tipo`, mesa, para_llevar, producto/combo, cantidad, precio, extras, comentario).
2. `beginIntent(huella)` reutiliza el UUID **solo** si esa huella sigue pendiente (timeout/red).
3. Una selección nueva (otro producto, combo o datos) genera UUID nuevo.
4. Tras timeout: un reintento automático con la **misma** clave y los **mismos** datos (`withIntentRetry`).
5. Éxito o error 4xx/409 libera la clave. Doble toque: candado React + misma clave si es el mismo payload.

**Backend**:

1. Guarda `tipo` + `payload_hash` (SHA-256 canónico) + `id_detalle_pedido` / `detalle_ids_json`.
2. Misma clave + misma huella → replay del resultado **de esa operación** (no `lineas[0]`).
3. Misma clave + otro producto, combo, mesa o payload → **409 Conflict**. No se devuelve el resultado de otra operación.
4. Combo: `detalle_ids_json` identifica todas las líneas de esa operación.
5. Sin `operation_id` (cliente viejo): comportamiento previo.

**Un pedido ABIERTO por mesa y tipo:** índice único parcial. Si dos dispositivos crean el primero a la vez, uno inserta y el otro reutiliza el abierto. No 500. No pedido vacío extra. Productos distintos quedan en el mismo pedido.

---

## 7. Manejo UTC

- Persistencia: `now_utc_naive()` (UTC sin tzinfo).
- Intercambio API: `isoformat_utc()` → ISO con sufijo `Z`.
- Segundos: `segundos_desde()` / `elapsedSecondsUtc()`; nunca negativos.
- El frontend **no** usa la zona del dispositivo: ISO sin zona se trata como UTC (`…Z`).
- El timer avanza con `setInterval` local; al recargar se recalcula desde `fecha_envio_comanda`.
- `marcar listo` no cambia `fecha_envio_comanda`.
- Horario comercial de reportes: sigue siendo México (`timezone_mx`, `filtro_*_mx`).

---

## 8–9. Rendimiento (medido, no inventado)

### Consultas SQL (servicio, SQLite de prueba, `PERF_LOG_SQL=1`)

| Operación | Consultas |
|-----------|-----------|
| Contexto producto | 9 |
| POST producto simple | 14 |
| POST con extras | 15 |
| POST combo | 17 |
| GET pedido (lectura, sin write) | 11 |
| GET mesas activas | 1 |

No se añadió caché compleja. El N+1 de recálculo de ticket (producto por línea) ya existía; no se “optimizó” sin prueba de lentitud en staging.

### HTTP TestClient (`X-Process-Time-Ms`, misma máquina)

| Endpoint | ms | Notas |
|----------|-----|--------|
| GET contexto | 6.84 | 2ª vez en el mismo proceso: caché frontend no aplica aquí |
| GET mesa vacía | 9.66 | **0 escrituras de pedido** (`sin_pedido: true`) |
| POST línea simple | 58.81 | Crea pedido + línea atómico |
| POST retry misma clave | 13.80 | No duplica |
| GET pedido | 6.91 | Solo lectura |
| GET activos | 9.69 | |
| DELETE detalle | 39.35 | |

`X-SQL-Query-Count` en TestClient del seed_perf salió 0 porque el listener SQL está en otro engine; los conteos SQL válidos son la tabla de servicio.

### Peticiones frontend (camino crítico)

| Acción | Antes (esta fase) | Después |
|--------|-------------------|---------|
| Abrir mesa sin productos | 1 GET **que escribía** pedido vacío | 1 GET **sin escribir** |
| Agregar simple (caché contexto fría) | 1 GET contexto + 1 POST | Igual |
| Agregar simple (caché caliente, <30 s) | 1 POST | Igual |
| Doble toque / retry red | 2 POST = 2 unidades | 2 POST, **1 unidad** si misma `operation_id` |
| Personalizar | no existía | 1 GET contexto + POST al confirmar |
| Refresh mesas | 1 GET segundo plano | Igual |

TTL caché contexto: **30 segundos**. Documentado en `productoContextoCache.js`. El backend revalida precio/promo al POST.

---

## 10. Resultados de pruebas

```text
cd backend && python -m pytest -q
# 149 passed, 2 skipped (test_estabilidad_postgres.py sin POSTGRES_TEST_URL)

cd frontend && npm test
# 25 passed (node:test)

cd frontend && npm run lint
# OK

cd frontend && npm run build
# OK

cd frontend && npm run build:android
# OK — vite capacitor + cap sync android (no se instaló ni publicó APK)
```

`npm ci` no se forzó: en este entorno Windows ya hay `node_modules` y `npm ci` ha fallado antes por EPERM/lightningcss. Lint y build usaron las dependencias existentes.

Playwright: `npm run test:estabilidad-critico` (requiere API + preview). Ver §11.

---

## 11. Capturas

Generar con API local y preview:

```bash
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run build && npm run test:estabilidad-critico
```

Salida: `docs/screenshots/estabilidad/` (Ventas/Personalizar, Comandera, sidebar 390×844, 768×1024, 1024×600, 1366×768).

---

## 12. Pendientes / riesgos

- Caché de contexto de 30 s: una promo que arranca en el segundo 0 puede verse hasta 30 s tarde en el modal; el POST la revalida.
- Clientes antiguos sin `operation_id` siguen pudiendo duplicar con doble POST real.
- `GET /pedidos/mesa/{n}` ahora puede devolver `id_pedido: null` y `estado: "SIN_PEDIDO"`. Transición compatible: el POS ya usa `pedido?.id_pedido`.
- `validar_mesa_operacion` puede crear fila de `configuracion` si no existe (comportamiento previo, no es pedido).
- Editar nota de una línea ya enviada a cocina no reimprime comanda.
- Playwright crítico no corre en CI sin API.
- SQLite no reproduce bloqueos de PostgreSQL. `tests/test_estabilidad_postgres.py` queda **preparada** y se omite sin `POSTGRES_TEST_URL`. **Pendiente ejecutarla contra PostgreSQL antes del despliegue.**

---

## 13. Pruebas manuales

1. **Comandera:** confirmar pedido → ~0s; esperar 65 s → ~1m 05s; recargar; zona del navegador `America/Mexico_City`; marcar listo no reinicia el cronómetro.
2. **Doble toque:** internet lento / DevTools “Slow 3G”; un toque repetido no duplica; dos toques **después** de terminar sí suman 2.
3. **Mesa vacía:** abrir mesa y salir → no hay pedido en BD / no aparece en mesas activas.
4. **Primer producto inválido / extra inválido:** no queda pedido.
5. **Dos malteadas** con comentarios distintos: líneas y promos correctas al recalcular.
6. **Agregado rápido** en producto simple; **Personalizar** abre modal (cantidad + comentario) sin agregar.
7. **Sidebar:** 390×844 off-canvas; 768 / 1024×600 / 1366 scroll del menú independiente.

---

## 14. Despliegue futuro (después de revisión)

1. Merge a `main` (no en esta entrega).
2. Ejecutar `tests/test_estabilidad_postgres.py` con `POSTGRES_TEST_URL` de un entorno de prueba (no producción).
3. Comprobar que no hay dos pedidos `ABIERTO` por mesa/tipo; luego el arranque aplicará 002 de forma idempotente (ops puede lanzar el `.up.sql` explícito).
4. Desplegar backend y frontend en el orden habitual.
5. Publicar APK solo si se decide en otra fase.
6. No reactivar ni modificar Elastic Beanstalk.

---

## 15. Confirmaciones

- **No merge** en esta entrega.
- **No despliegue** en Render, Vercel ni tienda Android.
- **Pago con puntos:** no implementado.
- **Control de WiFi:** no implementado.
- **Inventario y merma:** no modificados.
- **Elastic Beanstalk:** no modificado.
- **Permisos / dependencias masivas:** no.

### Contrato GET mesa (transición)

Antes: `GET /pedidos/mesa/{n}` siempre devolvía un `id_pedido` real (creaba si no había).  
Ahora: si no hay pedido abierto, `200` con `sin_pedido: true`, `id_pedido: null`, `lineas: []`, `total: 0`.  
El POST de la primera línea crea pedido + detalle en una transacción.
