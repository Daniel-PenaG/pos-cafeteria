# Optimización de rendimiento POS — Coffe Song

Documento de validación pre-merge. **No desplegar ni hacer merge hasta aprobar esta evidencia.**

## Rama publicada

| Campo | Valor |
|-------|-------|
| **Rama** | `performance/optimizar-pos` |
| **URL GitHub** | https://github.com/Daniel-PenaG/pos-cafeteria/tree/performance/optimizar-pos |
| **PR (crear cuando apruebes)** | https://github.com/Daniel-PenaG/pos-cafeteria/pull/new/performance/optimizar-pos |

## Commits de la rama (más reciente primero)

| Hash completo | Mensaje |
|---------------|---------|
| `f2244eba6659c004b005285770e293a604a33477` | validación: índices manuales, benchmark before/after y pruebas ampliadas |
| `32a45de29db96bb5f8110fa0cced02709ddc9561` | perf: eliminar N+1 en reportes y dashboard |
| `7d67f6a918ff3db1c0d22786a3c3d203351c29e8` | test: pruebas de regresión reportes y documentación de despliegue |
| `aeeb1a4db796610dcbd6aff7155329905e5ea8c7` | perf: code-splitting frontend y correcciones ESLint |
| `165044d59aaa4dbe84af83d1bd19c96089c8fbd0` | perf: pool PostgreSQL conservador e índices de consulta |
| `8c529fb1b4c49e435e5503290cd434fd4ac1fc9d` | perf: middleware de medición y conteo SQL por petición |

**Padre de la rama (local):** `0aa1a667cb63d43fc46016d9975e68fbe53dc757` — promos ticket-level (aún no mergeado a `origin/main` en el momento de esta validación).

### ¿Qué es `0aa1a66` vs `f2456e0`?

| Commit | Descripción |
|--------|-------------|
| **`f2456e0`** | Referencia conocida de **main antes de optimizar** (reporte por hora con promedios/día y filtro weekday). Es el **baseline correcto** del benchmark. |
| **`0aa1a66`** | Commit **posterior** a `f2456e0` en main local: promociones ticket-level (`CANTIDAD_PRECIO`, snapshots en `detalle_venta`). No es el estado pre-optimización; la rama de performance se **desarrolló encima** de este commit, pero el benchmark compara código en **`f2456e0`** vs rama optimizada. |

Reproducir benchmark:

```bash
cd backend
python scripts/benchmark_before_after.py
# baseline por defecto: f2456e0
# override: PERF_BASELINE_COMMIT=f2456e0 python scripts/benchmark_before_after.py
```

---

## Tabla benchmark real (2026-08-31)

**Condiciones:** baseline `f2456e0`, rama `performance/optimizar-pos`, SQLite `:memory:`, seed `120 ventas` (`tests/seed_perf.py`), promedio de 5 ejecuciones, script `benchmark_before_after.py`.

| Endpoint | SQL antes | SQL después | ms antes | ms después | Reducción |
|----------|-----------|-------------|----------|------------|-----------|
| `GET /reportes/ventas-mes` | 103 | 11 | 66.77 | 29.49 | **89.3%** |
| `GET /reportes/ventas-rango` | 103 | 11 | 56.93 | 21.37 | **89.3%** |
| `GET /reportes/resumen-dashboard` | 18 | 11 | 12.55 | 10.52 | **38.9%** |
| `GET /reportes/consumo-insumos` | 10 | 2 | 8.08 | 6.08 | **80.0%** |
| `GET /reportes/productos-ranking` | 7 | 5 | 8.72 | 6.98 | **28.6%** |
| `GET /pedidos/activos` | 2 | 2 | 5.74 | 5.16 | 10.1% |
| `GET /catalogo/productos` | 2 | 2 | 4.35 | 3.61 | 17.0% |
| `GET /catalogo/insumos` | 2 | 2 | 6.17 | 3.56 | 42.3% |

---

## Resultados de pruebas (evidencia)

### Backend — `python -m pytest -q`

```
18 passed, 1 warning in 1.05s
```

**Warning (no fallo):** `SECRET_KEY` débil en entorno local (`app/utils/security.py`).

### Frontend

| Comando | Resultado |
|---------|-----------|
| `npm ci` | **Falló** en Windows (EPERM al reemplazar `lightningcss.win32-x64-msvc.node`; archivo bloqueado por antivirus/IDE). |
| `npm install` + `npm run lint` | **OK** — sin errores ni advertencias ESLint |
| `npm run build` | **OK** — ver bundle abajo |

En CI/Linux (Vercel) `npm ci` debe ejecutarse sin este bloqueo.

---

## Bundle frontend

Medición **antes** con build en worktree `f2456e0` (`vite build`). **Después** en rama optimizada.

| Métrica | Antes (`f2456e0`) | Después (optimizado) | Reducción |
|---------|-------------------|----------------------|-----------|
| Chunk principal (min) | **955.89 KB** (`index-*.js` único) | **770.23 KB** (`index-BtgKAhNN.js`) | **19.4%** |
| Chunk principal (gzip) | **277.31 KB** | **231.42 KB** | **16.5%** |

**Chunks lazy generados (después):** VentasParaLlevar, Categorias, CierresDia, ParaLlevar, Compras, Gastos, CierreCaja, CuentasCajero, Usuarios, Productos, Clientes, Insumos, Recetas, Dashboard, Promociones, ExtrasVenta, Reportes, PageHeader (+ shared: datetimeMx, insumosService, reportesService, permissions, etc.).

**Carga inicial:** Login, Ventas, Mesas activas, Comandera permanecen en el bundle principal.

---

## Variables de entorno

| Variable | Default | Uso |
|----------|---------|-----|
| `PERF_LOG` | off | Logs + `X-Process-Time-Ms` — **solo local/staging** |
| `PERF_LOG_SQL` | off | Conteo SQL — **solo local/staging; NO producción** |
| `PERF_LOG_DETAIL` | off | Debug por petición |
| `HORA_OPERACION_INICIO` / `FIN` | 9 / 21 | Horario reportes por hora |
| `DB_POOL_SIZE` | 3 | Pool PostgreSQL |
| `DB_MAX_OVERFLOW` | 2 | Overflow por worker |
| `DB_POOL_TIMEOUT` | 15 | seg |
| `DB_POOL_RECYCLE` | 300 | seg |

**Producción:** no definir `PERF_LOG` ni `PERF_LOG_SQL`.

**Conexiones máximas (2 workers Gunicorn):** 2 × (3 + 2) = **10** conexiones PostgreSQL (sin PgBouncer).

---

## Índices PostgreSQL — manual, NO FastAPI

Los índices **no** se ejecutan al arrancar FastAPI (confirmado: no existe `aplicar_indices_performance()` en `database.py`).

### Orden exacto (UP)

Archivo: `backend/migrations/001_performance_indexes.up.sql`

1. Conectar a PostgreSQL de Render (SQL shell o `psql`).
2. Ejecutar **cada línea por separado** (CONCURRENTLY no admite transacción multi-statement).
3. Esperar fin de cada índice (`pg_stat_progress_create_index`) antes del siguiente.
4. Sintaxis: `CREATE INDEX CONCURRENTLY IF NOT EXISTS ...`

### Verificar que terminaron

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE indexname LIKE 'idx_%'
ORDER BY indexname;
```

Comprobar que aparecen los 24 índices del archivo UP.

### Reversión (DOWN)

Archivo: `backend/migrations/001_performance_indexes.down.sql` — una sentencia `DROP INDEX CONCURRENTLY IF EXISTS` a la vez, orden inverso.

### SQLite (dev)

Opcional: `backend/migrations/001_performance_indexes.sqlite.sql`

---

## Procedimiento de despliegue (cuando apruebes merge)

**No ejecutar hasta completar revisión de este documento.**

### 1. Índices (PostgreSQL) — antes del backend

1. Backup o ventana de bajo tráfico.
2. Ejecutar UP manual (sección anterior).
3. Verificar con consulta `pg_indexes`.
4. Confirmar que no hay índices `INVALID` (`pg_index.indisvalid`).

### 2. Backend (Render)

1. Merge `performance/optimizar-pos` → `main` (cuando apruebes).
2. Variables de pool (opcional recomendado):
   ```
   DB_POOL_SIZE=3
   DB_MAX_OVERFLOW=2
   DB_POOL_TIMEOUT=15
   DB_POOL_RECYCLE=300
   ```
3. **No** agregar `PERF_LOG` / `PERF_LOG_SQL` en producción.
4. Deploy manual o auto-deploy desde `main`.
5. Verificar `GET /health` → `{"status":"ok"}`.

### 3. Frontend (Vercel)

1. Deploy desde `main` tras merge.
2. Confirmar build exitoso (`npm ci` en Vercel).
3. Verificar carga de `/login` y chunks lazy en Network tab.

### 4. Smoke tests post-despliegue

| # | Acción | Esperado |
|---|--------|----------|
| 1 | Login cajero/admin | 200, token válido |
| 2 | `GET /catalogo/productos` | Lista productos |
| 3 | Abrir Ventas / Mesas | Carga rápida, pedido activo |
| 4 | Comandera | Líneas en comanda |
| 5 | `GET /reportes/resumen-dashboard` (admin) | JSON con `top_productos`, `cuentas_hoy` |
| 6 | Reportes → ventas mes | Sin error, totales coherentes |
| 7 | Cobro de prueba (staging) | Venta registrada, totales correctos |

---

## Caché

No implementada (invalidación multi-worker > beneficio).

## Extras e insumos

Consumo agrupa recetas de productos vendidos. Extras con insumo origen no incluidos aún.

---

## Rollback (`git revert`)

Revertir en orden **del más reciente al más antiguo**:

```bash
git revert f2244eb --no-edit
git revert 7d67f6a --no-edit
git revert aeeb1a4 --no-edit
git revert 165044d --no-edit
git revert 32a45de --no-edit
git revert 8c529fb --no-edit
```

Redeploy backend + frontend desde `main` revertido. Índices UP son seguros de conservar; opcional DOWN manual.

Quitar vars `PERF_*` y `DB_*` de Render si se agregaron para prueba.

---

## Workers (512 MB Render)

2 workers Gunicorn + pool conservador es adecuado para plan ~$7 USD. No aumentar workers sin medir RAM.
