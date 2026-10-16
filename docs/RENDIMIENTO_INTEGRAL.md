# Rendimiento integral — latencia operativa POS

| Campo | Valor |
| --- | --- |
| Rama | `performance/latencia-operativa-pos` |
| Commit rendimiento POS | `f6b1d8f7789c0cee17ddee9acf7160f80dd44cfa` |
| Commit base (benchmark API) | `e648e325dea25d033a4c152f2b706a5b0b54c28a` |
| Medición E2E navegador | `docs/e2e_latencia_navegador.json` (metodología corregida, ver §3) |

## Tipos de medición (no mezclar)

| Tipo | Qué mide | Artefacto |
| --- | --- | --- |
| **Endpoint (válido PG)** | Solo HTTP + SQL del handler; prep en `setup_fn` | `docs/benchmark_latencia_operativa.json` |
| **Endpoint (descartado)** | Prep mezclada en contador (582, 203, 572, 413, etc.) | `invalid_prior_measurements` en el JSON |
| **SQLite referencia** | Firmas SQL vía TestClient (`:memory:`) | `docs/sql_profile_operaciones.json` |
| **E2E navegador** | Segmentos UI + compuestos (login, modales); **no** sustituye latencia de API | `docs/e2e_latencia_navegador.json`, `docs/screenshots/rendimiento-flujos/` |

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
  - Seed: `backend/scripts/seed_e2e_capture.py` (productos **`E2E Sin Promo`** / **`E2E Con Promo`**, promoción solo en el segundo); teardown: `teardown_e2e_capture.py`.
  - Preview `--mode e2e` con `VITE_API_URL` exportada desde `run-perf-e2e.ps1` (sin archivos `.env` en el repo).
- Capturas: **`npm run capture:perf-flujos`** — 9 flujos × 3 viewports = **27 PNG** (flujo 1 usa producto sin promoción; sin espera de 20 s).
- Latencia E2E: **`npm run measure:perf-e2e`** → `docs/e2e_latencia_navegador.json` (**2** warmup + **10** muestras por segmento; variables `E2E_LATENCY_WARMUP`, `E2E_LATENCY_RUNS`).
- Scripts compartidos: `frontend/scripts/perf-e2e-shared.mjs` (rama UI con `Promise.race` ≤ **800 ms**, nunca timeout de 20 s dentro del cronómetro).
- Tras marcar listo: **sin** `GET /comandera/pendientes` en los 800 ms siguientes (`comandera_sin_get_pendientes_inmediato.cumple: true`).
- Advertencia inventario en medición: **renderizado sintético** (`prueba_renderizado` en el JSON), no cobro real.

### Mediciones invalidadas (E2E)

En el commit `f6b1d8f`, el flujo agregado mezclaba un **timeout negativo de 20 s** esperando el encabezado «Aplicar promoción» aunque el producto buscado no abría ese modal (`producto_toque_pedido_actualizado`: p50 **20 303 ms**). Esa cifra **no** es latencia del POS. Detalle en `mediciones_invalidadas` dentro de `docs/e2e_latencia_navegador.json`.

### Resultados E2E (metodología corregida, PG local)

| Segmento | p50 ms | p95 ms | max ms | Notas |
| --- | ---: | ---: | ---: | --- |
| **Sin promoción** `click_agregar_a_respuesta_post` | 330 | 340 | 340 | Objetivo p95 &lt; 800 ms |
| **Sin promoción** `flujo_total_sin_promo` | 423 | 439 | 442 | Objetivo p95 &lt; 1,5 s |
| **Con promoción** `flujo_total_con_promo` | 705 | 730 | 738 | Incluye modal promo → «No, precio normal» → calcular → agregar |
| `click_confirmar_a_respuesta_post` | 287 | 403 | 404 | Solo POST confirmar |
| `confirmar_to_comandera_visible` (compuesta) | 1 214 | 1 321 | 1 323 | Incluye navegación a Comandera |
| `click_final_cobrar_a_respuesta_post` | 356 | 386 | 393 | Solo POST cobrar |
| `cobrar_modal_y_campos_a_respuesta` (compuesta) | 447 | 481 | 498 | Modal + campos + POST |

**API vs E2E (referencia):** benchmark PG `agregar_primera_linea` p50 **~55 ms** / p95 **~67 ms** (solo HTTP+SQL del handler). El segmento E2E `click_agregar_a_respuesta_post` (~314 ms p50) añade contexto previo en UI, render y red local; la compuesta `flujo_total_sin_promo` (~404 ms p50) incluye contexto + modal + POST + actualización del carrito.

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

## 7. Criterios de medición E2E

| Criterio | Estado |
| --- | --- |
| Sin muestras artificialmente ~20 s | **Cumplido** |
| Mediciones previas invalidadas documentadas | **Cumplido** |
| Productos seed deterministas sin/con promo | **Cumplido** |
| Segmentos POST confirmar/cobrar separados de compuestas | **Cumplido** |
| Inventario UI etiquetado como render sintético | **Cumplido** |
