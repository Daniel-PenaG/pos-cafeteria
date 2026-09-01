# Optimización de rendimiento POS — Coffe Song

Documento de validación pre-merge. **No desplegar ni hacer merge hasta aprobar.**

## Ramas y PRs separados

| Rama | Base | PR contra | Contenido |
|------|------|-----------|-----------|
| **`feature/promociones-ticket-level`** | `f2456e0` | `main` | Promos ticket-level, snapshots, transacción atómica *(mergeado en `c3db0ee`)* |
| **`performance/optimizar-pos`** | `c3db0ee` | `main` | Solo commits de rendimiento (middleware, N+1, pool, lazy load, tests, índices). |

**URLs GitHub:**

- Promociones (mergeada): https://github.com/Daniel-PenaG/pos-cafeteria/tree/main
- Rendimiento: https://github.com/Daniel-PenaG/pos-cafeteria/tree/performance/optimizar-pos

**Orden de merge recomendado:** 1) ~~PR promociones → `main`~~ *(hecho: `c3db0ee`)*. 2) PR rendimiento → `main` (Squash and merge).

Pruebas manuales promociones: [`docs/PROMOCIONES_MANUAL_TESTS.md`](PROMOCIONES_MANUAL_TESTS.md)

---

## Commits de rendimiento (rama `performance/optimizar-pos`, post-rebase sobre `c3db0ee`)

| Hash | Mensaje |
|------|---------|
| *(HEAD)* | docs: evidencia post-rebase sobre main con promociones |
| `f8558e2` | docs: hashes completos post-validacion en PERFORMANCE.md |
| `7c5ade4` | docs: ramas separadas, auditoria indices, pruebas manuales promos |
| `cefcead` | fix: omitir indices duplicados en migracion 001_performance_indexes |
| `a5f103f` | docs: benchmark baseline f2456e0 y evidencia completa de validación |
| `27eb0fa` | validación: índices manuales, benchmark before/after y pruebas ampliadas |
| `74e9273` | perf: eliminar N+1 en reportes y dashboard |
| `f3fbd69` | test: pruebas de regresión reportes y documentación de despliegue |
| `6b11c9d` | perf: code-splitting frontend y correcciones ESLint |
| `ccbd652` | perf: pool PostgreSQL conservador e índices de consulta |
| `de01776` | perf: middleware de medición y conteo SQL por petición |

**Respaldo pre-rebase:** `backup/performance-pre-rebase-6ac990b` (local, no remoto).

**Base `main`:** `c3db0ee` (incluye promociones + transacción atómica).

**Benchmark baseline (comparación interna del script):** `f2456e0` (main pre-optimización).

```bash
cd backend && python scripts/benchmark_before_after.py
```

---

## Tabla benchmark

### Post-rebase (2026-09-01, rama rebasada sobre `c3db0ee`)

| Endpoint | SQL antes | SQL después | ms antes | ms después | Reducción |
|----------|-----------|-------------|----------|------------|-----------|
| `GET /reportes/ventas-mes` | 94 | 11 | 113.95 | 25.09 | **88.3%** |
| `GET /reportes/ventas-rango` | 94 | 11 | 70.79 | 17.53 | **88.3%** |
| `GET /reportes/resumen-dashboard` | 19 | 11 | 19.00 | 8.85 | **53.4%** |
| `GET /reportes/consumo-insumos` | 10 | 2 | 9.88 | 4.47 | **80.0%** |
| `GET /reportes/productos-ranking` | 7 | 5 | 10.42 | 4.95 | **52.5%** |
| `GET /pedidos/activos` | 2 | 2 | 7.20 | 4.43 | 38.5% |
| `GET /catalogo/productos` | 2 | 2 | 6.68 | 3.02 | 54.8% |
| `GET /catalogo/insumos` | 2 | 2 | 5.44 | 3.04 | 44.1% |

Sin N+1 en ventas del mes, ventas por rango, dashboard, consumo de insumos ni ranking de productos (consultas acotadas: 11/11/11/2/5 respectivamente).

### Referencia anterior (2026-08-31, baseline `f2456e0`)

| Endpoint | SQL antes | SQL después | ms antes | ms después | Reducción |
|----------|-----------|-------------|----------|------------|-----------|
| `GET /reportes/ventas-mes` | 103 | 11 | 66.77 | 29.49 | **89.3%** |
| `GET /reportes/ventas-rango` | 103 | 11 | 56.93 | 21.37 | **89.3%** |
| `GET /reportes/resumen-dashboard` | 18 | 11 | 12.55 | 10.52 | **38.9%** |
| `GET /reportes/consumo-insumos` | 10 | 2 | 8.08 | 6.08 | **80.0%** |
| `GET /reportes/productos-ranking` | 7 | 5 | 8.72 | 6.98 | **28.6%** |
| `GET /pedidos/activos` | 2 | 2 | 5.74 | 5.16 | 10.1% |
| `GET /catalogo/productos` | 2 | 2 | 4.35 | 3.61 | 17.0% |
| `GET /catalogo/insumos` | 2 | 2 | 6.17 | 3.56 | **42.3%** |

---

## Resultados de pruebas

### Backend

```
python -m pytest -q
→ ver salida en sección «Evidencia última ejecución» al final de este doc
```

### Frontend

```
cd frontend && npm ci && npm run lint && npm run build
→ ver evidencia al final
```

---

## Bundle frontend

| Métrica | Antes (`f2456e0`) | Después | Reducción |
|---------|-------------------|---------|-----------|
| Chunk principal (min) | 955.89 KB | 770.23 KB | **19.4%** |
| Chunk principal (gzip) | 277.31 KB | 231.42 KB | **16.5%** |

**Chunks lazy:** Reportes, Promociones, Recetas, Insumos, Productos, Dashboard, Clientes, Compras, Gastos, Usuarios, CierresDia, CierreCaja, CuentasCajero, ExtrasVenta, ParaLlevar, Categorias, VentasParaLlevar, PageHeader (+ shared).

---

## Índices PostgreSQL — auditoría vs existentes

SQLAlchemy `index=True` crea índices `ix_<tabla>_<columna>`. Migraciones en `database.py` añaden índices con prefijo `idx_`.

### Ya existían (no duplicar en UP)

| Tabla.columna(s) | Índice existente | Origen |
|------------------|------------------|--------|
| `pedidos.numero_mesa` | `ix_pedidos_numero_mesa` | `index=True` en modelo |
| `pedidos.(numero_mesa, estado)` | `idx_pedidos_mesa_estado` | migración `database.py` |
| `cierres_caja.fecha` | `ix_cierres_caja_fecha` | `index=True` |
| `cierres_caja.id_usuario` | `ix_cierres_caja_id_usuario` | `index=True` |
| `cierres_caja.(id_usuario, fecha)` | `idx_cierres_usuario_fecha` UNIQUE | migración `database.py` |

### Eliminados del UP (duplicados)

- `idx_pedidos_numero_mesa`
- `idx_cierres_caja_fecha`
- `idx_cierres_caja_id_usuario`

### Nuevos en `001_performance_indexes.up.sql` (21 índices)

`ventas` (5), `detalle_venta` (3), `pedidos` (3: estado, fecha_apertura, id_venta), `detalle_pedido` (4), `recetas`/`receta_insumos` (3), `movimientos_inventario` (2), `gastos` (1).

**No se ejecutan al arrancar FastAPI.** Aplicar manualmente (CONCURRENTLY, una sentencia a la vez). Ver archivos `.up.sql` / `.down.sql`.

---

## Seed promoción comercial

- **Eliminado** de `app/main.py`: no se inserta «Lunes de Malteadas» en producción.
- Función `crear_promocion_lunes_malteadas_si_ausente()` solo corre si `LOCAL_SEED_PROMO=true` **y** SQLite local.
- Invocación manual en dev (con variable en `.env`):

  ```bash
  cd backend
  set LOCAL_SEED_PROMO=true
  python -c "from app.database import crear_promocion_lunes_malteadas_si_ausente; crear_promocion_lunes_malteadas_si_ausente()"
  ```

---

## Variables de entorno

| Variable | Default | Uso |
|----------|---------|-----|
| `PERF_LOG` / `PERF_LOG_SQL` | off | **Solo local/staging. NO producción.** |
| `LOCAL_SEED_PROMO` | false | Seed promo demo SQLite |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / … | 3 / 2 / … | Pool PostgreSQL |

**Conexiones máx. (2 workers):** 2 × (3 + 2) = **10**

---

## Despliegue (cuando apruebes)

1. Merge PR promociones (squash) → `main`
2. Merge PR rendimiento (squash) → `main`
3. **Índices UP** manual en PostgreSQL + verificar `pg_indexes`
4. Deploy Render (backend) sin `PERF_*`
5. Deploy Vercel (frontend)
6. Smoke tests + [`PROMOCIONES_MANUAL_TESTS.md`](PROMOCIONES_MANUAL_TESTS.md)

---

## Rollback con Squash and merge

Usar **Squash and merge** en GitHub para cada PR. Tras deploy, un solo commit por PR en `main`.

```bash
# Revertir PR de rendimiento (sustituir HASH por el commit squash en main)
git revert <hash-squash-rendimiento> --no-edit

# Revertir PR de promociones (si necesario, en orden inverso al merge)
git revert <hash-squash-promociones> --no-edit
```

Redeploy backend + frontend. Índices UP opcionalmente revertir con `.down.sql`.

---

## Evidencia última ejecución

**Fecha:** 2026-09-01 (post-rebase `performance/optimizar-pos` sobre `c3db0ee`)

### Backend

```
cd backend && python -m pytest -q
.......................................................................  [100%]
71 passed in 8.21s
```

Incluye 58 pruebas de promociones/transacción + 13 de rendimiento/reportes.

### Frontend

```
cd frontend && npm run lint && npm run build
```

| Comando | Resultado |
|---------|-----------|
| `npm ci` | Falló EPERM en Windows (`lightningcss` bloqueado). `npm install` + lint/build OK. |
| `npm run lint` | OK — 0 errores ESLint |
| `npm run build` | OK — `index-BtgKAhNN.js` 770.23 KB / 231.42 KB gzip |

Chunks lazy confirmados: Reportes, Promociones, Dashboard, Usuarios, etc. Ventas/Mesas/Comandera en bundle operativo principal.

### Transacción atómica

Verificado en `venta_service.py`: `flush()` → detalles/inventario/fidelidad/pedido → un solo `commit()`; `rollback()` en excepción. Doble cobro rechazado en `_cerrar_pedido_tras_venta`.
