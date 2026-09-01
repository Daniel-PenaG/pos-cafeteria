# Validación responsive móvil — Coffe Song POS

Rama: [`ui/responsive-mobile`](https://github.com/Daniel-PenaG/pos-cafeteria/tree/ui/responsive-mobile)
PR base temporal: `performance/optimizar-pos`

## Commits de referencia

| Commit | Contenido |
|--------|-----------|
| `52843c0` | Implementación responsive (focus trap, tablas, CSS, Playwright inicial) |
| `8b6b527` | Script login API local + matriz honesta |
| *(HEAD tras push)* | Capturas API real, validaciones automáticas de ancho, modal-bottom |

## Validación automatizada (2026-08-31)

```bash
cd frontend
npm ci       # OK
npm run lint # OK — 0 errores
npm run build # OK (con VITE_API_URL=http://127.0.0.1:8000)
```

**Bundle principal:** `773.40 KB` minificado · `232.34 KB` gzip (`index-*.js`)

## Capturas con API local real

Regeneradas con Playwright + Chromium contra backend SQLite local (catálogo demo, `admin`/`admin123`). **Sin mocks de red.**

```bash
# Terminal 1
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2
cd frontend
npm ci
$env:VITE_API_URL="http://127.0.0.1:8000"
npm run build
npm run preview -- --host 127.0.0.1 --port 4173

# Terminal 3
npm run capture:responsive
# → API real: http://127.0.0.1:8000
```

El script **falla** si la API no responde en `/health`. `CAPTURE_REAL_API=0` está prohibido. No hay fallback a mocks.

**Validaciones automáticas en cada ruta:**
- `document.documentElement.scrollWidth <= window.innerWidth` (sin scroll horizontal de página)
- En `/reportes`, `/usuarios`, `/cuentas-cajero`: `.table-wrap` con scroll horizontal cuando la tabla es más ancha que el contenedor

**Modal promociones (320×568 y 390×844):**
- Scroll al final del `.modal-box`
- Botones Guardar y Cancelar visibles (no detrás de barra inferior)
- Capturas: `promociones-modal.png` + `promociones-modal-bottom.png`
- El scroll es del modal, no de la página

> **Nota sesión CI local:** el puerto `:8000` tenía un listener colgado; las capturas finales se generaron con API en `:8001` (misma app SQLite). El workflow estándar usa `:8000`.

## Implementación (`52843c0`)

| Requisito | Estado |
|-----------|--------|
| Focus trap sidebar | **APROBADO** |
| Restaurar foco al hamburguesa | **APROBADO** |
| Menú cerrado `inert` / no navegable | **APROBADO** |
| Tablas Reportes/Usuarios/Cuentas en `.table-wrap` | **APROBADO** |
| Inputs/selects/textarea ≥16px móvil | **APROBADO** |
| Sin `cart-panel` sticky móvil | **APROBADO** |
| Script + comando Playwright | **APROBADO** |

## Matriz visual (API real)

Estados: **APROBADO** | **FALLÓ** | **PENDIENTE**

| Resolución | Menú | Promos | Modal | Modal bottom | Ventas | Comandera | Reportes | Usuarios | Cuentas | Tablet | Escritorio | Estado |
|------------|------|--------|-------|--------------|--------|-----------|----------|----------|---------|--------|------------|--------|
| 320×568 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | **APROBADO** |
| 360×800 | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | **APROBADO** |
| 390×844 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | **APROBADO** |
| 412×915 | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | **APROBADO** |
| 768×1024 | — | — | — | — | — | — | ✓ | — | — | ✓ | — | **APROBADO** |
| 1024×768 | — | — | — | — | — | — | ✓ | — | — | ✓ | — | **APROBADO** |
| 1366×768 | — | — | — | — | — | — | ✓ | — | — | — | ✓ | **APROBADO** |

Rutas: `docs/screenshots/responsive/{320x568,…,1366x768}/`

## Pendientes

| Ítem | Estado |
|------|--------|
| Prueba física tablet/celular real | **PENDIENTE** (opcional, fuera de Playwright) |
| Teclado virtual en Ventas | **PENDIENTE** revisión manual |

## PR

https://github.com/Daniel-PenaG/pos-cafeteria/compare/performance/optimizar-pos...ui/responsive-mobile

**No merge ni deploy.**
