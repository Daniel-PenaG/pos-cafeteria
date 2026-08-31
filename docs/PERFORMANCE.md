# Optimización de rendimiento POS — Coffe Song

## Resumen

Rama `performance/optimizar-pos`: medición, eliminación de N+1 en reportes, índices manuales, pool PostgreSQL conservador, code-splitting del frontend y pruebas de regresión.

## Variables de entorno

| Variable | Default | Uso |
|----------|---------|-----|
| `PERF_LOG` | off | Logs estructurados + header `X-Process-Time-Ms` (**solo local/staging**) |
| `PERF_LOG_SQL` | off | Conteo SQL + header `X-SQL-Query-Count` (**solo local/staging; NO producción**) |
| `PERF_LOG_DETAIL` | off | Logs debug por petición |
| `HORA_OPERACION_INICIO` | 9 | Horario operación (reportes por hora) |
| `HORA_OPERACION_FIN` | 21 | Horario operación |
| `DB_POOL_SIZE` | 3 | Pool SQLAlchemy (solo PostgreSQL) |
| `DB_MAX_OVERFLOW` | 2 | Conexiones extra por worker |
| `DB_POOL_TIMEOUT` | 15 | Segundos espera conexión |
| `DB_POOL_RECYCLE` | 300 | Reciclar conexiones (seg) |

**Producción:** no definir `PERF_LOG` ni `PERF_LOG_SQL`. El middleware no añade overhead ni headers de diagnóstico.

## Índices PostgreSQL (manual, NO en arranque FastAPI)

Los índices **no** se aplican al iniciar la API. Ejecutar manualmente en Render SQL shell o `psql`.

### Orden exacto de ejecución (UP)

Archivo: `backend/migrations/001_performance_indexes.up.sql`

1. Ejecutar **cada sentencia por separado** (PostgreSQL no permite `CONCURRENTLY` dentro de una transacción multi-statement).
2. Orden del archivo (ventas → detalle_venta → pedidos → detalle_pedido → recetas → inventario → cierres → gastos).
3. Sintaxis: `CREATE INDEX CONCURRENTLY IF NOT EXISTS ...`
4. Esperar a que cada índice termine antes del siguiente (monitorizar `pg_stat_progress_create_index`).

### Reversión (DOWN)

Archivo: `backend/migrations/001_performance_indexes.down.sql`

1. Mismo criterio: **una sentencia a la vez**, fuera de transacción.
2. Orden inverso al UP: `DROP INDEX CONCURRENTLY IF EXISTS ...`

### SQLite (desarrollo)

Opcional: `backend/migrations/001_performance_indexes.sqlite.sql` (sin CONCURRENTLY).

## Despliegue Render (backend) — cuando apruebes merge

1. Merge/deploy rama `performance/optimizar-pos`.
2. Pool recomendado:
   ```
   DB_POOL_SIZE=3
   DB_MAX_OVERFLOW=2
   DB_POOL_TIMEOUT=15
   DB_POOL_RECYCLE=300
   ```
3. **Conexiones máximas teóricas:** 2 workers × (`DB_POOL_SIZE` + `DB_MAX_OVERFLOW`) = 2 × 5 = **10 conexiones** al PostgreSQL (sin PgBouncer).
4. Ejecutar índices UP manualmente (ver arriba).
5. Mantener **2 workers Gunicorn** con 512 MB.
6. **PgBouncer** (opcional): Render Dashboard → PostgreSQL → connection pooling; usar URL interna pooler como `DATABASE_URL`.

## Despliegue Vercel (frontend)

Deploy automático al merge; sin env nuevas.

## Caché en memoria

No implementada (invalidación multi-worker > beneficio TTL corto).

## Extras e insumos

`/reportes/consumo-insumos` agrupa recetas de productos vendidos. Extras con insumo origen no incluidos aún.

## Benchmark before/after

```bash
cd backend
python -m pytest -q
python scripts/benchmark_before_after.py   # compara 0aa1a66 vs rama actual, 120 ventas seed
```

Baseline configurable: `PERF_BASELINE_COMMIT=0aa1a66`

## Rollback con git revert

Hashes de la rama (más reciente primero): ver `git log performance/optimizar-pos`.

Revertir en orden inverso al merge (del más reciente al más antiguo):

```bash
git revert 7d67f6a --no-edit
git revert aeeb1a4 --no-edit
git revert 165044d --no-edit
git revert 32a45de --no-edit
git revert 8c529fb --no-edit
```

Si ya se aplicaron índices en PostgreSQL, ejecutar `001_performance_indexes.down.sql` manualmente (opcional; conservarlos suele ser seguro).

Quitar en Render vars `PERF_*` y `DB_*` si se habían agregado para prueba.

## Workers (512 MB)

2 workers × (~120–180 MB) + pool conservador es adecuado para la instancia $7 USD.
