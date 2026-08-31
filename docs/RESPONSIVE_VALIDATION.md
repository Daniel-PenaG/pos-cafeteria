# Validación responsive móvil — Coffe Song POS

Rama: [`ui/responsive-mobile`](https://github.com/Daniel-PenaG/pos-cafeteria/tree/ui/responsive-mobile)
PR base temporal: `performance/optimizar-pos`

> **Estado de publicación:** el commit `52843c0` (local) incluye la implementación y capturas; debe publicarse con `git push origin ui/responsive-mobile`. Hasta que el remoto supere `c1a4e34`, este documento no debe leerse como aprobación en producción.

## Breakpoints

| Rango | Dispositivo | Ubicación |
|-------|-------------|-----------|
| 0–479 px | Celular pequeño | `frontend/src/styles/responsive.css` |
| 480–767 px | Celular grande | idem |
| 768–1023 px | Tablet | idem + `@media (min-width: 768px)` |
| 1024 px+ | Escritorio | estilos base en `global.css` |

## Implementación verificada en código (`52843c0`)

| Requisito | Archivo | Estado código |
|-----------|---------|---------------|
| Focus trap sidebar | `layout.jsx` | Implementado |
| Restaurar foco al hamburguesa | `layout.jsx` + `Navbar.jsx` (`forwardRef`) | Implementado |
| Menú cerrado no navegable | `Sidebar.jsx` (`inert`, `aria-hidden`, `tabIndex=-1`) | Implementado |
| Tablas Reportes en `.table-wrap` | `Reportes.jsx` | Implementado (11 tablas) |
| Tabla Usuarios en `.table-wrap` | `Usuarios.jsx` | Implementado |
| Dos tablas CuentasCajero | `CuentasCajero.jsx` | Implementado |
| Inputs/selects/textarea ≥16px móvil | `responsive.css` | Implementado |
| Sin `cart-panel` sticky móvil | `responsive.css` | Eliminado (sidebar tablet conserva `sticky`) |
| Script Playwright | `scripts/capture-responsive.mjs` | Implementado (login API local) |
| Comando npm | `package.json` → `capture:responsive` | Implementado |
| Dependencia Playwright | `package.json` devDependencies | Implementado |

## Validación ejecutada (2026-08-31)

```bash
cd frontend
npm ci          # FALLÓ — EPERM/EBUSY lightningcss (Windows, archivo bloqueado)
npm run lint    # PENDIENTE re-ejecución tras npm ci exitoso
npm run build   # PENDIENTE re-ejecución tras npm ci exitoso
npm run capture:responsive  # PENDIENTE con API local (ver abajo)
```

**Promociones (rama separada):** no modificada en esta rama.

## Regenerar capturas con API real (obligatorio para APROBADO visual)

Las capturas incluidas en `52843c0` se generaron inicialmente con mocks de red. Para cumplir criterio de aprobación visual, regenerar contra backend local con catálogo demo:

```bash
# Terminal 1 — API local (SQLite + admin admin123 + catálogo demo)
cd backend
# Añadir a CORS si hace falta: http://127.0.0.1:4173
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — build apuntando a API local
cd frontend
npm ci
$env:VITE_API_URL="http://127.0.0.1:8000"   # PowerShell
npm run build
npm run preview -- --host 127.0.0.1 --port 4173

# Terminal 3
$env:CAPTURE_REAL_API="1"
npm run capture:responsive
```

Revisar manualmente PNG en `docs/screenshots/responsive/` antes de marcar **APROBADO**.

## Matriz de validación visual

Estados: **APROBADO** | **FALLÓ** | **PENDIENTE**

| Resolución | Menú cerrado | Menú abierto | Promociones | Modal | Ventas+carrito | Comandera | Reportes | Usuarios | Cuentas cajero | Tablet | Escritorio | Estado |
|------------|--------------|--------------|-------------|-------|----------------|-----------|----------|----------|----------------|--------|------------|--------|
| 320×568 | PNG en repo | PNG en repo | PNG en repo | PNG en repo | PNG en repo | PNG en repo | PNG en repo | PNG en repo | PNG en repo | — | — | **PENDIENTE** revisión API real |
| 360×800 | idem | idem | idem | idem | idem | idem | idem | idem | idem | — | — | **PENDIENTE** |
| 390×844 | idem | idem | idem | idem | idem | idem | idem | idem | idem | — | — | **PENDIENTE** |
| 412×915 | idem | idem | idem | idem | idem | idem | idem | idem | idem | — | — | **PENDIENTE** |
| 768×1024 | — | — | — | — | — | — | PNG | — | — | PNG | — | **PENDIENTE** |
| 1024×768 | — | — | — | — | — | — | PNG | — | — | PNG | — | **PENDIENTE** |
| 1366×768 | — | — | — | — | — | — | PNG | — | — | — | PNG | **PENDIENTE** |

Rutas: `docs/screenshots/responsive/{320x568,360x800,390x844,412x915,768x1024,1024x768,1366x768}/`

### Comprobaciones estáticas (código)

| Aspecto | Estado |
|---------|--------|
| Sidebar off-canvas `<768px` | **APROBADO** (código) |
| Overlay + Escape + cierre en ruta | **APROBADO** (código) |
| Focus trap + foco hamburguesa | **APROBADO** (código) |
| Menú cerrado `inert` | **APROBADO** (código) |
| `.table-wrap` Reportes/Usuarios/Cuentas | **APROBADO** (código) |
| Inputs 16px móvil | **APROBADO** (código) |
| `cart-panel` sticky eliminado | **APROBADO** (código) |
| ESLint / build / capturas API real | **PENDIENTE** |

## PR

https://github.com/Daniel-PenaG/pos-cafeteria/compare/performance/optimizar-pos...ui/responsive-mobile

**No merge ni deploy** hasta aprobación humana con capturas API real verificadas.
