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

## Archivos modificados

- `frontend/index.html` — viewport `viewport-fit=cover`
- `frontend/src/layout.jsx` — estado `sidebarOpen`, overlay, Escape, ruta, popstate
- `frontend/src/components/Sidebar.jsx` — off-canvas, cierre, navegación cierra menú
- `frontend/src/components/Navbar.jsx` — hamburguesa 44×44, título corto
- `frontend/src/components/PageHeader.jsx` — columna en móvil
- `frontend/src/styles/responsive.css` — **nuevo**
- `frontend/src/styles/global.css` — `.table-wrap`, `.page-header__row`
- `frontend/src/main.jsx` — import responsive.css

**Sin cambios en backend ni lógica de negocio.**

## Build y lint (ejecutado 2026-08-31)

```
npm run lint  → 0 errores
npm run build → OK
  index-CfQU4iNj.js  772.24 KB / 231.90 KB gzip
  CSS total          35.86 KB / 7.76 KB gzip
```

Sin dependencias nuevas. Bundle inicial similar a `performance/optimizar-pos`.

## Matriz de validación visual

Estados: **APROBADO** | **FALLÓ** | **PENDIENTE**

Validación visual en navegador real no ejecutada en CI de este agente → filas marcadas **PENDIENTE** salvo comprobaciones estáticas de CSS/componentes.

| Resolución | Ruta | Menú | Tabla | Modal | Scroll global | Estado |
|------------|------|------|-------|-------|---------------|--------|
| 360×800 | `/login` | N/A | N/A | N/A | — | **PENDIENTE** |
| 360×800 | `/ventas` | off/on | N/A | N/A | — | **PENDIENTE** |
| 390×844 | `/promociones` | — | scroll | modal | — | **PENDIENTE** |
| 390×844 | `/comandera` | — | — | — | — | **PENDIENTE** |
| 768×1024 | `/dashboard` | fijo | — | — | — | **PENDIENTE** |
| 1024×768 | `/ventas` | fijo | — | — | — | **PENDIENTE** |
| 1366×768 | `/reportes` | fijo | scroll | — | — | **PENDIENTE** |

### Comprobado estáticamente (sin navegador)

| Aspecto | Estado |
|---------|--------|
| Sidebar off-canvas `<768px` | **APROBADO** (código + CSS) |
| Overlay + Escape + cierre en ruta | **APROBADO** (layout.jsx) |
| Hamburguesa 44×44 + `aria-*` | **APROBADO** (Navbar.jsx) |
| `.table-wrap` scroll horizontal | **APROBADO** (responsive.css) |
| Modales full-width móvil | **APROBADO** (responsive.css) |
| ESLint | **APROBADO** |
| Build producción | **APROBADO** |

## Capturas requeridas — PENDIENTES

Generar en dispositivo real o Chrome DevTools:

1. 360×800 — menú cerrado  
2. 360×800 — menú abierto  
3. 390×844 — Promociones  
4. 390×844 — modal Promoción  
5. 390×844 — Ventas  
6. 390×844 — Comandera  
7. 768×1024 — tablet  
8. 1024×768 — tablet horizontal  
9. 1366×768 — escritorio  

Guardar en `docs/screenshots/responsive/` (crear al capturar).

### Instrucciones capturas

```bash
cd frontend
npm run dev
# Chrome → F12 → Toggle device toolbar
# Resolución → captura PNG
# Rutas: /login, /ventas, /promociones, /comandera
```

Login local: usuario de prueba en SQLite (admin demo de `database.py`).

## Prueba física tablet/celular

1. `npm run build && npm run preview` o instalar APK Capacitor debug.
2. Verificar menú abre/cierra, overlay, sin scroll horizontal en página.
3. Tablas desplazan solo dentro de `.table-wrap`.
4. Modal promoción completo con teclado virtual.
5. Botones táctiles ≥44 px.

## PR

Crear contra: https://github.com/Daniel-PenaG/pos-cafeteria/compare/performance/optimizar-pos...ui/responsive-mobile

**No merge ni deploy** hasta aprobación.
