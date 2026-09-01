# Validación responsive móvil — Coffe Song POS

Rama: [`ui/responsive-mobile`](https://github.com/Daniel-PenaG/pos-cafeteria/tree/ui/responsive-mobile)
PR base temporal: `performance/optimizar-pos`

## Commits de referencia

| Commit | Contenido |
|--------|-----------|
| `52843c0` | Implementación responsive (focus trap, tablas, CSS, Playwright inicial) |
| `8b6b527` | Script login API local + matriz honesta |
| `cf0192e` | Capturas API real, validaciones de ancho, modal-bottom |
| `215da18` | Hashes de evidencia |
| *(HEAD)* | Espera animación modal, navbar tablet 768–900 px, capturas finales en `:8000` |

## Validación automatizada (2026-09-01)

```bash
cd frontend
npm ci        # OK
npm run lint  # OK — 0 errores
npm run build # OK (VITE_API_URL=http://127.0.0.1:8000)
npm run capture:responsive  # OK — API real: http://127.0.0.1:8000
```

**Bundle principal:** `773.40 KB` minificado · `232.34 KB` gzip (`index-*.js`)

**Validaciones de ancho (script):** todas las rutas pasaron — sin `scrollWidth` de página mayor que `innerWidth`; tablas en `.table-wrap` con scroll horizontal cuando corresponde.

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

### Corrección modal (2026-09-01)

Tras abrir el modal, el script espera `400 ms` post-animación (`fadeIn 0.2s`) antes de `promociones-modal.png`:

- Fondo blanco sólido del modal
- Título «Nueva promoción» y primeros campos visibles
- Overlay oscuro sin mezcla con la página de Promociones
- `promociones-modal-bottom.png` conservado (Guardar/Cancelar visibles en 320×568 y 390×844)

### Navbar tablet 768–900 px

En 768×1024 existía solapamiento entre «Panel de administración», nombre y rol. Ajuste CSS (`responsive.css`):

- Título corto «Coffe Song» en lugar del título largo
- Ocultos nombre de usuario, badge de rol y etiqueta «Cerrar sesión» (solo iconos)
- Sin cambios al sidebar ni al layout principal de tablet

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
| Navbar tablet 768–900 px sin solapamiento | **APROBADO** |

## Matriz visual (API real, `:8000`)

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
| Prueba física tablet/celular real | **PENDIENTE** (opcional) |
| Teclado virtual en Ventas | **PENDIENTE** revisión manual |

## PR

https://github.com/Daniel-PenaG/pos-cafeteria/compare/performance/optimizar-pos...ui/responsive-mobile

**No merge ni deploy.**
