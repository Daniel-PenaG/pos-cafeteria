# Rendimiento integral — latencia operativa POS

| Campo | Valor |
| --- | --- |
| Rama | `performance/latencia-operativa-pos` |
| Commit base (benchmark) | `e648e325dea25d033a4c152f2b706a5b0b54c28a` |
| Commit optimizado (medido) | Mismo hash **con cambios locales sin commit** en el árbol de trabajo |
| Estado | **Sin commit / sin push** |

## Tipos de medición (no mezclar)

| Tipo | Qué mide | Artefacto |
| --- | --- | --- |
| **Endpoint (válido PG)** | Solo HTTP + SQL del handler; prep en `setup_fn` | `docs/benchmark_latencia_operativa.json` |
| **Endpoint (descartado)** | Prep mezclada en contador (582, 203, 572, 413, etc.) | `invalid_prior_measurements` en el JSON |
| **SQLite referencia** | Firmas SQL vía TestClient (`:memory:`) | `docs/sql_profile_operaciones.json` |
| **E2E navegador** | Flujos UI observados (login, modales, capturas); **no** sustituye latencia de API | `docs/screenshots/rendimiento-flujos/` |

## 1. Comparación válida PostgreSQL (base vs optimizado)

**Procedimiento idéntico:** mismo worker (`_benchmark_latencia_worker.py` + `_measure_call_with_setup`), seed `seed_perf_db(num_ventas=120)`, PG `127.0.0.1:5433/pos_bench`, 3 calentamientos, 10 muestras por escenario. `comparison_valid: true` en el JSON.

| Escenario | p50 ms (base → opt) | p95 ms (opt) | max ms (opt) | SQL p50 (base → opt) | bytes p50 (opt) |
| --- | ---: | ---: | ---: | ---: | ---: |
| contexto_producto | 21.3 → **11.8** | 13.0 | 13.2 | 13 → **9** | 736 |
| agregar_primera_linea | 69.6 → **42.5** | 63.2 | 69.5 | 24 → **17** | 1156 |
| agregar_decima_linea | 76.3 → **52.5** | 55.5 | 55.8 | 45 → **17** | 1168 |
| confirmar_10_lineas | 138.5 → **18.5** | 58.3 | 58.5 | 87 → **12** | 7228 |
| marcar_listo | 23.3 → **22.9** (30 muestras, ver `benchmark_marcar_listo_30m.json`) | 28.0 | 29.5 | 6 → **6** | 488 |
| cobrar_1_linea | 72.5 → **14.3** | 16.2 | 16.5 | 45 → **8** | 188 |
| cobrar_10_lineas_receta_extras_promo | 91.7 → **74.9** | 83.0 | 83.3 | 79 → **50** | 719 |

**Confirmar 10 líneas:** las cifras **582 / 203 / 572 / 413** SQL (y mejoras % derivadas) están **invalidadas** — incluían preparación de 10 líneas dentro del contador. Tras aislar el setup, el p50 SQL del POST confirmar es **12** (optimizado).

No usar porcentajes de mejora calculados sobre mediciones listadas en `invalid_prior_measurements`.

## 2. Perfil SQL SQLite (referencia)

Script: `backend/scripts/profile_operaciones_sql.py` con `PERF_LOG_SQL_SIGNATURE=1` → `docs/sql_profile_operaciones.json`.

Escenario `confirmar_10_lineas`: ~**12** consultas contadas (promos lote, recetas, updates detalle, auth/auditoría). Complementa la regresión local; la comparación de producto es **PostgreSQL** arriba.

## 3. E2E autocontenido y capturas

- Orquestador: **`run-perf-e2e.ps1`**
  - `CAPTURE_LOGIN` / `CAPTURE_PASSWORD` opcionales; si faltan, usuario `capture_*` + contraseña aleatoria (no se imprime).
  - Solo `PERF_DATABASE_URL` (local); rechaza producción e igualdad con `DATABASE_URL`; no toca `test_pos.db`.
  - Seed: `backend/scripts/seed_e2e_capture.py`; teardown: `teardown_e2e_capture.py`.
  - Preview `--mode e2e` con `VITE_API_URL` exportada desde `run-perf-e2e.ps1` (sin archivos `.env` en el repo).
- Capturas: **`npm run capture:perf-flujos`** — 9 flujos × 3 viewports = **27 PNG**.
- Latencia E2E navegador: **`npm run measure:perf-e2e`** → `docs/e2e_latencia_navegador.json` (5+ repeticiones; preview `--mode e2e` + reescritura de API Render → local en Playwright).
- Tras marcar listo: **sin** `GET /comandera/pendientes` en los 800 ms siguientes (`comandera_sin_get_pendientes_inmediato.cumple: true` en el JSON E2E).
- Validaciones en script: sin scroll horizontal relevante, modales con `.modal-box`, alertas acotadas, Comandera sin “Actualizando…” tras marcar listo, flujo promo → precio normal → agregar.

### Rutas de las 27 capturas

Resolución **390×844** (`docs/screenshots/rendimiento-flujos/390x844/`):

`01-producto-sencillo.png`, `02-producto-con-extras.png`, `03-confirmar-pedido.png`, `04-comandera-antes-listo.png`, `05-comandera-despues-listo.png`, `06-cobro.png`, `07-advertencia-inventario.png`, `08-para-llevar.png`, `09-puntos.png`

Resolución **768×1024** (`docs/screenshots/rendimiento-flujos/768x1024/`): mismos nombres `01`–`09`.

Resolución **1366×768** (`docs/screenshots/rendimiento-flujos/1366x768/`): mismos nombres `01`–`09`.

## 4. Cambios técnicos principales

- Confirmar comanda: respuesta `pedido_respuesta_lectura` (sin re-persistir promos en el POST).
- `_lineas_desde_pedido`: promociones precargadas con `IN (...)`.
- Benchmark/capturas: setup fuera de SQL y cronómetro donde aplica.

## 5. Regresión (última ejecución)

| Suite | Resultado |
| --- | --- |
| `python -m pytest -q` (PG `POSTGRES_TEST_URL` + SQLite) | **379 passed** |
| `npm test` | **88 passed** |
| `npm run lint` | OK |
| `npm run build` | OK |
| `npm run build:android` | OK (sync Capacitor; **sin APK**) |

## 6. Reproducir

```powershell
# Perfil firmas (SQLite)
cd backend
$env:DATABASE_URL="sqlite:///:memory:"
$env:PERF_LOG_SQL_SIGNATURE="1"
python scripts/profile_operaciones_sql.py > ..\docs\sql_profile_operaciones.json

# Pytest + PostgreSQL desechable
$env:DATABASE_URL="sqlite:///:memory:"
$env:POSTGRES_TEST_URL="postgresql+psycopg2://pos_test@127.0.0.1:5433/postgres"
python -m pytest -q

# Benchmark PG comparable
$env:PERF_DATABASE_URL="postgresql+psycopg2://pos_test@127.0.0.1:5433/pos_bench"
python scripts/benchmark_latencia_operativa.py --compare

# Capturas E2E (sin credenciales reales)
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
$env:PERF_DATABASE_URL="postgresql+psycopg2://pos_test@127.0.0.1:5433/pos_bench"
.\run-perf-e2e.ps1
```

## 7. Antes de commit

| Criterio | Estado |
| --- | --- |
| Benchmark PG comparable documentado | **Cumplido** |
| Mediciones contaminadas marcadas | **Cumplido** (JSON) |
| 27 capturas E2E | **Cumplido** |
| E2E sin credenciales embebidas | **Cumplido** |
| Regresión pytest + FE | **Cumplido** |
| Sin commit / push / PR / deploy | **Cumplido** |
