# Validación responsive móvil — Coffe Song POS

Rama: [`ui/responsive-mobile`](https://github.com/Daniel-PenaG/pos-cafeteria/tree/ui/responsive-mobile)  
**Base `main`:** `1a009dc` (promociones + rendimiento mergeados)  
**Rebase:** `git rebase --onto origin/main 6ac990b` — solo commits responsive, sin reaplicar rendimiento.

## Commits de referencia (post-rebase)

| Commit | Contenido |
|--------|-----------|
| `f1624ba` | Sidebar off-canvas y layout móvil (<768 px) |
| `20781e7` | Tablas responsive, focus trap, Playwright |
| `04469fa` | Capturas API local y matriz honesta |
| `7b420e2` | Capturas API real y validaciones de ancho |
| `21e6687` | Espera animación modal, navbar tablet 768–900 px |
| *(HEAD)* | Rebase sobre `1a009dc`, capturas regeneradas |

**Respaldo pre-rebase:** `backup/responsive-pre-rebase-f5209bb` (local).

## Validación automatizada (2026-09-01, post-rebase)

### Backend (regresión)

```bash
cd backend && python -m pytest -q
# 71 passed in 5.22s
```

Sin cambios backend en el diff responsive.

### Frontend

```bash
cd frontend
npm install   # npm ci falló EPERM lightningcss en Windows
npm run lint  # OK — 0 errores
npm run build # OK (VITE_API_URL=http://127.0.0.1:8000)
npm run capture:responsive  # OK — API real: http://127.0.0.1:8000
```

**Bundle principal:** `773.40 KB` minificado · `232.33 KB` gzip (`index-UbMJDs4z.js`)  
**CSS responsive incluido:** `index-DlzC0Uo5.css` 36.14 KB (incluye `responsive.css`)  
**Viewport:** `viewport-fit=cover` en `index.html`  
**Code splitting:** conservado desde `main` (Ventas eager; Promociones, Reportes, etc. lazy).

**Validaciones de ancho (script):** todas las rutas pasaron.

## Capturas con API local real

Regeneradas post-rebase con Playwright + Chromium contra backend SQLite local (`admin`/`admin123`). **Sin mocks.**

| Resolución | Estado |
|------------|--------|
| 320×568 | **APROBADO** |
| 360×800 | **APROBADO** |
| 390×844 | **APROBADO** |
| 412×915 | **APROBADO** |
| 768×1024 | **APROBADO** (sin solapamiento navbar) |
| 1024×768 | **APROBADO** |
| 1366×768 | **APROBADO** |

Confirmado: sin scroll horizontal global; sidebar cerrado en celular; overlay y cierre; promociones legible; modal inicio/fin; Guardar/Cancelar accesibles; ventas una columna; tablas en `.table-wrap`; escritorio sin regresión.

### Corrección modal

Espera `400 ms` post-animación antes de `promociones-modal.png` (fondo blanco sólido, overlay oscuro). `promociones-modal-bottom.png` en 320×568 y 390×844.

### Navbar tablet 768–900 px

Título corto «Coffe Song»; ocultos nombre/rol/label logout; solo iconos.

## Implementación responsive

| Requisito | Estado |
|-----------|--------|
| Focus trap sidebar | **APROBADO** |
| Restaurar foco al hamburguesa | **APROBADO** |
| Menú cerrado `inert` / no navegable | **APROBADO** |
| Tablas Reportes/Usuarios/Cuentas en `.table-wrap` | **APROBADO** |
| Inputs/selects/textarea ≥16px móvil | **APROBADO** |
| Sin `cart-panel` sticky móvil | **APROBADO** |
| Script + comando Playwright | **APROBADO** |
| Navbar tablet 768–900 px sin solapamiento | **APROBADO** |

## Alcance del diff contra `main`

Solo frontend + docs + capturas. **Sin backend**, middleware de rendimiento, índices PostgreSQL ni lógica de promociones/ventas.

## Pendientes

| Ítem | Estado |
|------|--------|
| Prueba física tablet/celular real | **PENDIENTE** (opcional) |
| Teclado virtual en Ventas | **PENDIENTE** revisión manual |

## PR

https://github.com/Daniel-PenaG/pos-cafeteria/compare/main...ui/responsive-mobile

**No merge ni deploy.**
