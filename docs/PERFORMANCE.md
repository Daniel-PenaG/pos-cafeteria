# Optimización de rendimiento POS — Coffe Song

Documento de validación pre-merge. **No desplegar ni hacer merge hasta aprobar.**

## Ramas y PRs separados

| Rama | Base | PR contra | Contenido |
|------|------|-----------|-----------|
| **`feature/promociones-ticket-level`** | `f2456e0` | `main` | Solo commit `0aa1a66`: promos `CANTIDAD_PRECIO`/`DESCUENTO_FIJO` a nivel ticket, snapshots en `detalle_venta`, APIs reporte promo. |
| **`performance/optimizar-pos`** | `feature/promociones-ticket-level` | `feature/promociones-ticket-level` (o `main` tras merge promos) | Solo commits de rendimiento (middleware, N+1, pool, lazy load, tests, índices). |

**URLs GitHub:**

- Promociones: https://github.com/Daniel-PenaG/pos-cafeteria/tree/feature/promociones-ticket-level
- Rendimiento: https://github.com/Daniel-PenaG/pos-cafeteria/tree/performance/optimizar-pos

**Orden de merge recomendado:** 1) PR promociones → `main` (Squash and merge). 2) Rebase `performance/optimizar-pos` sobre `main` actualizado. 3) PR rendimiento → `main` (Squash and merge).

Pruebas manuales promociones: [`docs/PROMOCIONES_MANUAL_TESTS.md`](PROMOCIONES_MANUAL_TESTS.md)

---

## Commits de rendimiento (rama `performance/optimizar-pos`)

| Hash completo | Mensaje |
|---------------|---------|
| `3fea37d90a58a333a3c90aa3531b987c3772c887` | docs: ramas separadas, auditoría índices, pruebas manuales |
| `6bd59782465fcdd6e8340b543f16b8d65c1c14fc` | fix: omitir índices duplicados en migración 001 |
| `09f6aeb04cde21f91cadaf817b397311687434be` | fix: seed promo comercial solo LOCAL_SEED_PROMO SQLite |
| `bce261ddd49603e595d6c82a22125af9403fbd0d` | docs: benchmark baseline f2456e0 y evidencia completa *(rebase de `9c124b7`)* |
| `b29c73ad77c0cc3809340a35cce88d5073a13488` | validación: índices manuales, benchmark, pruebas |
| `f37afc4ac81435082bf87d39db529b453a31bba1` | perf: eliminar N+1 en reportes y dashboard |
| `827238bcc31e4eb4eb8b646079717bdefe1ed671` | test: pruebas de regresión reportes |
| `9ad12f67cf76f97ff9077101137234a99fed5172` | perf: code-splitting frontend y ESLint |
| `08237d78cb828cce4effda39b108a146064fa82e` | perf: pool PostgreSQL e índices |
| `7e422a8178bb4976098c6a5c2e12d4009aecf3dd` | perf: middleware medición SQL |

**Rama `feature/promociones-ticket-level`:** `013281c` promos *(de `0aa1a66`)* + `5e1d1ce` seed fix + `57249de` pruebas manuales

**Benchmark baseline:** `f2456e0` (main pre-optimización, sin promos ticket-level).

```bash
cd backend && python scripts/benchmark_before_after.py
```

---

## Tabla benchmark (2026-08-31, baseline f2456e0)

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

**Fecha:** 2026-08-31 (post-separación de ramas)

### Backend

```
cd backend && python -m pytest -q
..................                                                       [100%]
18 passed, 1 warning in 3.27s
```

Warning esperado: `SECRET_KEY` débil en entorno local.

### Frontend

```
cd frontend && npm ci && npm run lint && npm run build
```

| Comando | Resultado |
|---------|-----------|
| `npm ci` | OK en entorno del usuario; en este agente Windows falló EPERM en `lightningcss` (archivo bloqueado). `npm install` + lint/build OK como alternativa local. |
| `npm run lint` | OK — sin errores ESLint |
| `npm run build` | OK — `index-BtgKAhNN.js` 770.23 KB / 231.42 KB gzip |
