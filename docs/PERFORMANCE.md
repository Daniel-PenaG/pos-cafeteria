# Optimización de rendimiento POS — Coffe Song

## Resumen

Rama `performance/optimizar-pos`: medición, eliminación de N+1 en reportes, índices, pool PostgreSQL conservador, code-splitting del frontend y pruebas de regresión.

## Variables de entorno nuevas

| Variable | Default | Uso |
|----------|---------|-----|
| `PERF_LOG` | off | Logs estructurados + header `X-Process-Time-Ms` |
| `PERF_LOG_SQL` | off | Conteo SQL + header `X-SQL-Query-Count` |
| `PERF_LOG_DETAIL` | off | Logs debug por petición |
| `HORA_OPERACION_INICIO` | 9 | Horario operación (reportes por hora) |
| `HORA_OPERACION_FIN` | 21 | Horario operación |
| `DB_POOL_SIZE` | 3 | Pool SQLAlchemy (solo PostgreSQL) |
| `DB_MAX_OVERFLOW` | 2 | Conexiones extra |
| `DB_POOL_TIMEOUT` | 15 | Segundos espera conexión |
| `DB_POOL_RECYCLE` | 300 | Reciclar conexiones (seg) |

## Despliegue Render (backend)

1. Merge/deploy rama `performance/optimizar-pos`.
2. En Environment, agregar (opcional medición temporal):
   - `PERF_LOG=1` y `PERF_LOG_SQL=1` solo en staging o 24h diagnóstico.
3. Pool (recomendado producción):
   ```
   DB_POOL_SIZE=3
   DB_MAX_OVERFLOW=2
   DB_POOL_TIMEOUT=15
   DB_POOL_RECYCLE=300
   ```
4. **Índices PostgreSQL**: ejecutar manualmente `backend/migrations/001_performance_indexes.sql` en la BD de Render (SQL shell) o dejar que `aplicar_indices_performance()` los cree al arrancar (idempotente).
5. Mantener **2 workers Gunicorn** con 512 MB; no aumentar sin medir RAM.
6. **PgBouncer** (opcional futuro): en Render Dashboard → PostgreSQL → enable connection pooling; usar URL interna `...-pooler...` como `DATABASE_URL` en el servicio web. No cambiar desde código.

## Despliegue Vercel (frontend)

1. Deploy automático al merge; no requiere env nuevas.
2. Verificar carga inicial: Login/Ventas/Mesas/Comandera en bundle principal; Reportes y admin en chunks lazy.

## Caché en memoria

**No implementada.** Con 2 workers Gunicorn la invalidación coherente (ventas, gastos, compras, promos) en todos los procesos añade complejidad superior al beneficio de TTL 15–60s. Las consultas agregadas + índices cubren el objetivo en instancia $7.

## Extras e insumos

`/reportes/consumo-insumos` agrega consumo por receta de productos vendidos. Los **extras** con insumo origen no están en recetas estándar; su consumo no se incluye hasta modelar receta de extras (documentado, sin cambio de contrato).

## Revertir

```bash
git revert <commits-de-la-rama>   # o
git checkout main && git branch -D performance/optimizar-pos
```

En Render: quitar vars `PERF_*` y `DB_*` si se agregaron. Los índices son seguros de conservar; para revertir: sección DOWN en `001_performance_indexes.sql`.

## Benchmark local

```bash
cd backend
python -m pytest -q
PERF_LOG=1 PERF_LOG_SQL=1 python scripts/benchmark_endpoints.py
```

## Workers (512 MB)

2 workers × (~120–180 MB c/u) + pool 3+2 conexiones es adecuado. Pasar a 1 worker reduce concurrencia bajo picos de cobro; no recomendado sin métricas de memoria en Render.
