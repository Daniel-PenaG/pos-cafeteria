# POS Cafetería (Coffe Song)

Sistema integral de punto de venta y back-office para cafeterías: ventas en mesa y para llevar, comanda de cocina, inventario, promociones, fidelidad, gastos del día y reportes.

**Documentación completa:** [DOCUMENTACION.md](DOCUMENTACION.md)  
**Desarrollo local:** [ENTORNO_LOCAL_Y_PRODUCCION.md](ENTORNO_LOCAL_Y_PRODUCCION.md)  
**Impresión tablet Android:** [IMPRESION_TABLET.md](IMPRESION_TABLET.md)

## Producción (Coffe Song)

| Componente | Servicio | URL |
|------------|----------|-----|
| Frontend web | Vercel | https://pos-cafeteria-brown.vercel.app |
| API | Render | https://pos-cafeteria-api.onrender.com |
| Tablet | APK Capacitor | Apunta a la API de Render |

**Variables en Render (backend):**

- `DATABASE_URL` — PostgreSQL
- `ENVIRONMENT=production`
- `SECRET_KEY` — clave aleatoria ≥ 32 caracteres (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- `CORS_ORIGINS` — `https://pos-cafeteria-brown.vercel.app`

**Variables en Vercel (frontend):**

- `VITE_API_URL` — `https://pos-cafeteria-api.onrender.com`

Despliegue alternativo en AWS: [GITHUB_SETUP.md](GITHUB_SETUP.md) → [DEPLOY_AWS.md](DEPLOY_AWS.md)

## Stack

| Capa | Tecnología |
|------|------------|
| Backend | FastAPI, SQLAlchemy, Pydantic, JWT (Argon2) |
| Frontend | React 19, Vite 8, Tailwind CSS 4, Zustand |
| Mobile | Capacitor 8 (Android) + impresora Bluetooth ESC/POS |
| Base de datos | SQLite (local) / PostgreSQL (producción) |

## Roles

| Rol | Acceso |
|-----|--------|
| **ADMIN** | Todo el sistema |
| **CAJERO** | Ventas, para llevar, clientes, comanda, dashboard |
| **COCINA** | Solo comanda |

La API exige **JWT** en todos los endpoints (excepto login y health). Los permisos por rol se validan en backend y frontend.

## Instalación local

### Backend

```powershell
cd backend
copy .env.example .env
pip install -r requirements.txt
.\run-dev.ps1
```

API: http://127.0.0.1:8000 — Docs: http://127.0.0.1:8000/docs  
Login inicial (BD vacía): `admin` / `admin123`

### Frontend

```powershell
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Web: http://localhost:5173

## Módulos principales

- **Ventas** — Mesas 1–20, para llevar (mesa 99), promociones, extras, cobro con cambio
- **Comandera** — Cola de cocina, tiempos de preparación
- **Catálogo** — Categorías, productos, insumos, recetas
- **Extras de venta** — Modificadores POS vinculados a insumos
- **Promociones** — Porcentaje, precio fijo, 2×1
- **Clientes / fidelidad** — Puntos por compra
- **Compras** — Entrada de inventario
- **Gastos del día** — Egresos operativos (capital neto en dashboard)
- **Reportes** — Ventas, ranking, consumo de insumos, cuentas por cajero

## Inventario al cobrar

Al registrar una venta (mesa o para llevar) se descuentan:

1. Insumos de la **receta** de cada producto
2. Insumos de los **extras** seleccionados

Si hay stock insuficiente, la venta se completa con **advertencias** (no se bloquea).

## Autenticación

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"usuario_login":"admin","password":"admin123"}'
```

Usar el token en peticiones:

```bash
curl http://127.0.0.1:8000/catalogo/productos \
  -H "Authorization: Bearer <token>"
```

La sesión se **persiste en localStorage** en el navegador y la APK.

## Estructura del proyecto

```
backend/app/
├── routers/       # auth, catalogo, pedidos, comandera, reportes, gastos…
├── services/      # venta, pedido, promoción, fidelidad…
├── models/        # SQLAlchemy
└── utils/         # JWT, roles, timezone MX

frontend/src/
├── pages/         # Ventas, Dashboard, Gastos, Comandera…
├── services/      # Clientes HTTP
├── config/        # Permisos por rol
└── store/         # authStore (Zustand + localStorage)
```

## Seguridad

- Contraseñas con **Argon2**
- **JWT** obligatorio en la API (roles: ADMIN, CAJERO, COCINA)
- **CORS** restringido por `CORS_ORIGINS` (no `*`)
- En producción, `ENVIRONMENT=production` exige `SECRET_KEY` fuerte

## APK Android

```powershell
cd frontend
npm run build:android
npm run cap:open
# Android Studio → Build → Build APK(s)
```

Configurar `frontend/.env.capacitor.local`:

```
VITE_API_URL=https://pos-cafeteria-api.onrender.com
```

---

**Última actualización:** agosto 2026
