# Validación responsive móvil — Coffe Song POS

Rama: [`ui/responsive-mobile`](https://github.com/Daniel-PenaG/pos-cafeteria/tree/ui/responsive-mobile)
PR base temporal: `performance/optimizar-pos`

## Breakpoints

| Rango | Dispositivo | Ubicación |
|-------|-------------|-----------|
| 0–479 px | Celular pequeño | `frontend/src/styles/responsive.css` |
| 480–767 px | Celular grande | idem |
| 768–1023 px | Tablet | idem + `@media (min-width: 768px)` |
| 1024 px+ | Escritorio | estilos base en `global.css` |

## Archivos modificados (BLOQUE 2)

- `frontend/index.html` — viewport `viewport-fit=cover`
- `frontend/src/layout.jsx` — focus trap, restauración de foco, Escape
- `frontend/src/components/Sidebar.jsx` — `inert`/`aria-hidden` menú cerrado móvil
- `frontend/src/components/Navbar.jsx` — `forwardRef` hamburguesa
- `frontend/src/components/PageHeader.jsx` — columna en móvil
- `frontend/src/pages/Reportes.jsx` — todas las tablas en `.table-wrap`
- `frontend/src/pages/Usuarios.jsx` — `.table-wrap`
- `frontend/src/pages/CuentasCajero.jsx` — `.table-wrap` (×2)
- `frontend/src/styles/responsive.css` — tablas, inputs 16px, sin sticky cart-panel
- `frontend/scripts/capture-responsive.mjs` — capturas Playwright
- `frontend/package.json` / `package-lock.json` — Playwright devDep
- `docs/screenshots/responsive/` — evidencia visual

**Sin cambios en backend ni lógica de negocio.**

## Build y lint (2026-08-31)

```
npm run lint  → 0 errores
npm run build → OK
```

`npm ci` en Windows puede fallar con EPERM en `lightningcss` si hay procesos usando `node_modules`; en ese caso `npm install` + lint/build es válido.

Regenerar capturas:

```bash
cd frontend
npm run build
npm run preview -- --host 127.0.0.1 --port 4173
# otra terminal:
npm run capture:responsive
```

## Matriz de validación visual

Estados: **APROBADO** | **FALLÓ** | **PENDIENTE**

Capturas generadas con **Playwright + Chromium** contra build de producción (`vite preview`).

| Resolución | Menú cerrado | Menú abierto | Promociones | Modal promo | Ventas+carrito | Comandera | Reportes | Usuarios | Cuentas cajero | Tablet | Escritorio | Estado |
|------------|--------------|--------------|-------------|-------------|----------------|-----------|----------|----------|----------------|--------|------------|--------|
| 320×568 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | **APROBADO** |
| 360×800 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | **APROBADO** |
| 390×844 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | **APROBADO** |
| 412×915 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | **APROBADO** |
| 768×1024 | — | — | — | — | — | — | ✓ | — | — | ✓ | — | **APROBADO** |
| 1024×768 | — | — | — | — | — | — | ✓ | — | — | ✓ | — | **APROBADO** |
| 1366×768 | — | — | — | — | — | — | ✓ | — | — | — | ✓ | **APROBADO** |

Rutas de capturas: `docs/screenshots/responsive/{320x568,360x800,390x844,412x915,768x1024,1024x768,1366x768}/`

### Comprobaciones adicionales

| Aspecto | Estado |
|---------|--------|
| Sidebar off-canvas `<768px` | **APROBADO** |
| Overlay + Escape + cierre en ruta | **APROBADO** |
| Focus trap + foco al abrir/cerrar | **APROBADO** |
| Menú cerrado no navegable (`inert`) | **APROBADO** |
| `.table-wrap` en Reportes/Usuarios/Cuentas | **APROBADO** |
| Inputs 16px móvil (anti-zoom iOS) | **APROBADO** |
| `cart-panel` sticky eliminado | **APROBADO** |
| ESLint | **APROBADO** |
| Build producción | **APROBADO** |

## PR

Crear contra: https://github.com/Daniel-PenaG/pos-cafeteria/compare/performance/optimizar-pos...ui/responsive-mobile

**No merge ni deploy** hasta aprobación humana.
