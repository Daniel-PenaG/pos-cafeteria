# Rendimiento de navegación operativa POS

| Campo | Valor |
| --- | --- |
| Rama | `performance/navegacion-operativa-pos` |
| Base | `origin/main` @ `a44cadb98c87e1d5be666a4c1e79269d4143685e` |
| Orquestador E2E | `run-perf-e2e.ps1` (PG `PERF_DATABASE_URL`, seed/teardown, backend :8000, preview :4173) |

## Causa raíz

1. Desmontaje de `/ventas` al navegar → remontaje, chunk lazy y efectos desde cero.
2. Waterfall HTTP en montaje (catálogo → mesas → activos → pedido) sin paralelismo ni caché.
3. `invalidateProductoContextoCache()` en cada montaje.
4. Sin snapshot de sesión (mesa, pedido, categorías, scroll).
5. Diálogos nativos bloqueantes en confirmación, cobro, validaciones y Comandera.

### Waterfall anterior

| Paso | Evento |
| ---: | --- |
| 1 | Chunk lazy `Ventas` |
| 2 | GET productos + categorías + tipos POS |
| 3 | GET mesas config |
| 4 | GET pedidos activos |
| 5 | Invalidar contexto producto |
| 6 | GET pedido mesa |
| 7 | Render |

### Waterfall actual (misma sesión, Comandera → Ventas)

| Paso | Evento |
| ---: | --- |
| 1 | Hidratar `ventasNavStore` + caché TTL |
| 2 | Shell / catálogo / mesas visibles al instante (snapshot) |
| 3 | `bootstrapVentasShell` → `Promise.allSettled` (catálogo ∥ mesas config ∥ activos) |
| 4 | «Actualizando…» solo en SWR |
| 5 | GET pedido con `pedidoEpochRef` |
| 6 | Prefetch idle / hover / focus |

## TTL / SWR / deduplicación

| Recurso | TTL | Módulo |
| --- | ---: | --- |
| Catálogo | 45 s | `operationalCaches.catalogCache` |
| Mesas config | 45 s | `mesasConfigCache` |
| Mesas activas | 3 s | `mesasActivasCache` |
| Snapshot Ventas | sesión | `ventasNavStore` |

- Deduplicación in-flight: `resourceCache.js`.
- SWR: dato stale visible + revalidación en background.
- `operationalSessionEpoch` en `clearOperationalSession()`; `resourceCache.reset()` impide repoblar tras logout/401.
- Sin localStorage para catálogo/pedidos operativos.

## Invalidación

Mutaciones (POST) actualizan pedido y mesas activas; `pedidoEpochRef` evita GET tardíos; 409/401/logout/cambio de usuario limpian caché y snapshot.

## Diálogos nativos eliminados

Sustituidos por `toastStore`, `OperationalConfirmModal`, `CobroExitoModal` y modales existentes (cancelación, cobro, QR). Prueba estática: `noNativeDialogs.test.js` sobre `Ventas.jsx`, `Comandera.jsx`, `CancelacionLineaModal.jsx`.

## Medición E2E

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
$env:PERF_DATABASE_URL="postgresql+psycopg2://pos_test@127.0.0.1:5433/pos_bench"
.\run-perf-e2e.ps1          # medición + capturas
.\run-perf-e2e.ps1 -NavOnly # solo docs/e2e_latencia_navegacion.json
```

Requisitos: puertos **8000** y **4173** libres (el script no mata procesos ajenos). Credenciales sintéticas `capture_*` generadas por seed (no se imprimen).

Salida: `docs/e2e_latencia_navegacion.json` (meta, objetivos, p50/p95/max, duplicados, GET pendientes post-listo).

### Carga fría vs navegación caliente

| Contexto | Métrica | Aceptación p95 | Notas |
| --- | --- | ---: | --- |
| **Fría** (primer `/ventas`, chunk + bootstrap) | `ventas_fria_shell_visible` | &lt; **1,2 s** | No confundir con shell caliente |
| **Fría** | `ventas_fria_catalogo_visible` | &lt; **500 ms** | Skeleton / `data-nav-*` nunca pantalla en blanco |
| **Caliente** (SPA Comandera ↔ Ventas) | `comandera_click_ventas_a_shell_visible` | &lt; **300 ms** | Objetivo operativo principal |
| **Caliente** | `comandera_a_ventas_total_utilizable` | &lt; **1,5 s** | Pedido restaurado incluido |
| **Caliente** | `ventas_a_comandera_total_utilizable` | &lt; **1,5 s** | |
| **Caliente** | pedido restaurado (`comandera_a_ventas_total_utilizable`) | &lt; **1 s** | sub-objetivo de restauración |

El umbral **300 ms** aplica a **navegación caliente dentro de la SPA**, no al primer arranque con descarga del chunk de Ventas.

**Referencia fría (corrida local previa, sin ocultar outliers):** shell p95 ≈ **942,9 ms**, catálogo p95 ≈ **314,2 ms** (ambos bajo aceptación 1,2 s / 500 ms). La corrida más reciente en `docs/e2e_latencia_navegacion.json` puede variar (p. ej. shell p95 ~835 ms con un max ~1015 ms); siempre revisar `meta.date` y `objectives`.

### Marcar listo (30 muestras, latencia **interna del navegador**)

Bloque `marcar_listo_fases_interno` en `docs/e2e_latencia_navegacion.json`. Marcas con `performance.now()` + `pointerdown`/`click` (`event.timeStamp`); `PerformanceObserver` (`longtask`) por muestra en `listo_longtasks_por_muestra`.

| Fase interna | Objetivo p95 |
| --- | ---: |
| `pointerdown_a_dom_optimista` («Sincronizando…» en DOM) | &lt; **150 ms** |
| `click_a_dom_optimista` | &lt; **150 ms** |
| `handler_a_dom_optimista` | &lt; **16,7 ms** (1 frame) |
| `request_a_respuesta_http` | &lt; **500 ms** |
| `total` (pointerdown → reconciliación) | &lt; **500 ms** |

**Automatización Playwright (no usar para feedback visual):** `playwright_dispatch_wall_clock` (retorno de `page.click`) y `playwright_click_to_dom_syncing_wall` (reloj externo hasta ver texto en DOM). Si difieren mucho de las fases internas, la demora es IPC/automatización salvo que `listo_longtasks_por_muestra` registre long tasks en el mismo intervalo.

Además: cero GET `/comandera/pendientes` en 800 ms post-listo; un solo POST por toque.

### Cobro y cierre de resumen

| Métrica | Tipo | Objetivo p95 |
| --- | --- | ---: |
| `cobrar_click_final_a_respuesta` | HTTP + UI | &lt; 1 s |
| `cerrar_resumen_click_a_modal_oculto` | **interno** (`performance.now`, overlay `display:none`) | &lt; **150 ms** |
| `cerrar_resumen_cobro_limpieza_wall_clock` | wall clock Playwright (click → rAFs) | informativo; limpieza **no bloqueante** |

Resultados numéricos: `docs/e2e_latencia_navegacion.json` (no confundir con `docs/e2e_latencia_navegador.json`, legacy).

### Objetivos p95 (local)

| Métrica | Objetivo |
| --- | ---: |
| `comandera_click_ventas_a_shell_visible` | &lt; 300 ms |
| `ventas_shell_a_catalogo_visible` (caliente) | &lt; 500 ms |
| `comandera_a_ventas_total_utilizable` | &lt; 1,5 s |
| `ventas_a_comandera_total_utilizable` | &lt; 1,5 s |
| `marcar_listo` (ver fases) | visual &lt; 150 ms; POST &lt; 500 ms |
| `cobrar_click_final_a_respuesta` | &lt; 1 s |

Resultados numéricos: ver `docs/e2e_latencia_navegacion.json` tras ejecutar el orquestador con puertos libres.

## Capturas

`npm run capture:navegacion-operativa` (vía `run-perf-e2e.ps1`) → `docs/screenshots/navegacion-operativa/{390x844,768x1024,1366x768}/`.

## Regresión (última ejecución)

| Comando | Resultado |
| --- | --- |
| `python -m pytest -q` (`DATABASE_URL` → PG desechable `5433/pos_bench`) | **379 passed** |
| `npm test` | **114 passed** |
| `npm run lint` | OK |
| `npm run build` / `build:android` | OK |

## Riesgos pendientes

- E2E completo exige stack local alineado (backend en la misma `PERF_DATABASE_URL` que el seed).
- Snapshot Ventas no sobrevive F5.
- Objetivos p95 deben revalidarse en hardware objetivo tras generar JSON.
