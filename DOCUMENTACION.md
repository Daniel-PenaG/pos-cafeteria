# POS Cafetería (Coffe Song) — Documentación

Documento unificado: visión general del negocio, arquitectura técnica, despliegue y mejoras sugeridas.  
**Última revisión:** agosto 2026.

---

## Índice

1. [Documentación general](#1-documentación-general)
2. [Documentación técnica](#2-documentación-técnica)
3. [Despliegue en producción](#3-despliegue-en-producción)
4. [App Android (tablet)](#4-app-android-tablet)
5. [Mejoras recomendadas](#5-mejoras-recomendadas)
6. [Documentos del repositorio](#6-documentos-del-repositorio)

---

## 1. Documentación general

### 1.1 ¿Qué es?

Sistema **punto de venta (POS)** y **back-office** para cafeterías. Marca operativa: **Coffe Song**.

Permite:

- Vender en **mesas** (1–20) y **para llevar**
- Enviar pedidos a **cocina** (comandera)
- Gestionar **catálogo**, **recetas**, **inventario**, **promociones** y **clientes frecuentes**
- Registrar **compras de insumos** y **gastos del día**
- Consultar **reportes** y **capital neto** (ventas − gastos)
- Imprimir tickets en **tablet Android** vía Bluetooth

### 1.2 Roles de usuario

| Rol | Uso típico | Acceso principal |
|-----|------------|------------------|
| **ADMIN** | Dueño / gerente | Todo: catálogo, reportes, usuarios, gastos, configuración |
| **CAJERO** | Mostrador | Ventas, para llevar, clientes, dashboard básico, comanda |
| **COCINA** | Barista / cocina | Solo pantalla de comanda |

Al iniciar sesión, cada rol llega a su pantalla por defecto (dashboard, ventas o comanda).

### 1.3 Flujos de negocio

#### Venta en mesa

1. Cajero elige **mesa**.
2. Agrega productos (extras, promociones, comentarios).
3. **Confirma pedido** → se envía a cocina (comanda).
4. Cocina marca líneas como **listas** en Comandera.
5. **Cierra cuenta / cobra** (efectivo con cálculo de cambio, tarjeta o transferencia).
6. Opcional: asignar **cliente** para puntos de fidelidad.
7. En tablet APK: imprime **ticket de cobro** (marca Coffe Song).

#### Venta para llevar

- Usa la **mesa virtual 99**.
- Mismo catálogo; al cobrar descuenta **receta + extras** del inventario.
- No hay paso de “confirmar comanda” para cocina.

#### Inventario

| Evento | Efecto en stock |
|--------|-----------------|
| Compra de insumos | Sube stock del insumo |
| Venta para llevar | Baja insumos de receta + extras |
| Venta en mesa | Baja solo insumos ligados a **extras** (no receta completa al cobrar) |
| Alertas | Reportes avisan stock bajo; la venta puede completarse con advertencias |

#### Promociones

Tipos: porcentaje, precio fijo, 2×1. Pueden aplicar a productos, categorías o toda la tienda, con horarios y fechas. El sistema valida **margen mínimo** antes de aplicar.

#### Fidelidad

- Clientes con teléfono y código `CAFE-XXXXXX`.
- Puntos al cobrar según configuración (ej. cada $10 MXN = 1 punto).
- Ajustes manuales por admin.

#### Gastos del día

- Admin registra concepto + monto (ej. compra de insumos en tienda, gasolina).
- Se restan del **capital neto** del día en el Dashboard:  
  **Capital neto = Ventas del día − Gastos del día**
- Día calendario en **hora de México** (`America/Mexico_City`).

### 1.4 Dónde se usa cada interfaz

| Interfaz | Uso |
|----------|-----|
| **Web (Vercel)** | Operación diaria en PC/navegador |
| **APK Android** | Tablet en mostrador + impresora Bluetooth MHT-P58D 58 mm |
| **API (Render)** | Backend compartido por web y APK |

La web y la APK usan la **misma API y base de datos**. Cambios de productos/precios en BD se ven al instante; cambios de **código** en frontend requieren redeploy (web) o nueva APK.

---

## 2. Documentación técnica

### 2.1 Stack

| Capa | Tecnología |
|------|------------|
| Backend | Python, FastAPI, SQLAlchemy, Pydantic, JWT (python-jose), Argon2 |
| Frontend | React 19, Vite 8, Tailwind CSS 4, React Router 7, Axios, Zustand |
| Mobile | Capacitor 8 (Android), plugin ESC/POS Bluetooth |
| BD local | SQLite (`backend/pos_cafeteria.db`) |
| BD producción | PostgreSQL (Render u otros) |
| Zona horaria negocio | `America/Mexico_City` (`backend/app/utils/timezone_mx.py`) |

### 2.2 Estructura del repositorio

```
pos-cafeteria/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI + routers
│   │   ├── database.py          # Engine, migraciones ad-hoc, seed
│   │   ├── models/models.py     # Modelos SQLAlchemy
│   │   ├── routers/             # Endpoints REST (~15 módulos)
│   │   ├── schemas/             # DTOs Pydantic
│   │   ├── services/            # Lógica de negocio
│   │   └── utils/               # JWT, roles, timezone MX
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/               # Pantallas (Ventas, Dashboard, Gastos…)
│   │   ├── services/            # Clientes HTTP a la API
│   │   ├── config/permissions.js
│   │   └── store/authStore.js
│   ├── android/                 # Proyecto Capacitor
│   └── capacitor.config.json
├── database/schema.sql          # Esquema inicial PG (desactualizado)
└── docs varios (.md)
```

### 2.3 Modelo de datos (tablas principales)

| Dominio | Tablas |
|---------|--------|
| Catálogo | `categorias`, `productos`, `insumos` |
| Recetas | `recetas`, `receta_insumos` |
| Pedidos | `pedidos`, `detalle_pedido` |
| Ventas | `ventas`, `detalle_venta` |
| Extras POS | `extras_venta`, `extra_tipos_pos`, `producto_extras`, `categoria_extras` |
| Promos | `promociones`, `promocion_productos`, `promocion_categorias` |
| Inventario | `movimientos_inventario`, `compras`, `detalle_compra` |
| Clientes | `clientes`, `fidelidad_movimientos`, `fidelidad_config` |
| Sistema | `usuarios`, `configuracion`, `gastos` |

### 2.4 API — módulos y prefijos

| Prefijo | Archivo | Función |
|---------|---------|---------|
| `/auth` | `auth.py` | Login, registro admin, `/me` |
| `/catalogo` | `productos.py` | Categorías, productos, insumos |
| `/recetas` | `recetas.py` | Recetas e insumos por producto |
| `/pedidos` | `pedidos.py` | Pedidos mesa / para llevar, cobro |
| `/comandera` | `comandera.py` | Cola cocina, marcar listo |
| `/ventas` | `ventas.py` | Venta directa (legacy), extras venta |
| `/promociones` | `promociones.py` | CRUD y cálculo |
| `/extras-venta` | `extras_venta.py` | Catálogo extras, importar insumos |
| `/clientes` | `clientes.py` | CRM + fidelidad |
| `/compras` | `compras.py` | Entrada de inventario |
| `/gastos` | `gastos.py` | Gastos del día (solo admin) |
| `/reportes` | `reportes.py` | Reportes + `resumen-dashboard` |
| `/configuracion` | `configuracion.py` | Margen y gastos fijos (precios) |
| `/usuarios` | `usuarios.py` | CRUD usuarios (admin) |

Documentación interactiva: `{API_URL}/docs` (Swagger FastAPI).

### 2.5 Autenticación y seguridad (estado actual)

- **Login:** `POST /auth/login` → JWT.
- **Hash contraseñas:** Argon2.
- **Frontend:** envía `Authorization: Bearer` en peticiones autenticadas; rutas protegidas por rol en React.
- **Importante:** la mayoría de endpoints **no exigen JWT en el backend**. Un atacante con la URL de la API podría llamar endpoints sin token. **Mejora prioritaria:** exigir auth en todos los routers.

Variables backend (`backend/.env`):

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | SQLite o PostgreSQL |
| `SECRET_KEY` | Firma JWT (obligatorio fuerte en prod) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Vigencia del token |
| `LOCAL_ADMIN_LOGIN` / `LOCAL_ADMIN_PASSWORD` | Admin inicial (solo SQLite vacío) |

Frontend:

| Variable | Descripción |
|----------|-------------|
| `VITE_API_URL` | URL base API sin `/` final |

Archivos ejemplo: `frontend/.env.example`, `.env.production.example`, `.env.capacitor.local` (APK).

### 2.6 Frontend — rutas y permisos

Definidas en `frontend/src/config/permissions.js` y `App.jsx`.

Páginas clave:

- `Ventas.jsx` — mesas, catálogo colapsable, cobro con cambio, impresión APK
- `Dashboard.jsx` — KPIs, capital neto, gastos, config márgenes (admin)
- `Gastos.jsx` — registro de egresos
- `Comandera.jsx` — cocina
- `ExtrasVenta.jsx` — importación múltiple de insumos como extras

Permisos UI: `ProtectedRoute`, `RoleRoute`, `Sidebar` filtrado por rol.

**Sesión:** el token JWT vive solo en memoria (Zustand). **Al refrescar el navegador se pierde la sesión.**

### 2.7 Servicios backend relevantes

| Servicio | Responsabilidad |
|----------|-----------------|
| `pedido_service.py` | Ciclo pedido → comanda → cobro |
| `venta_service.py` | Crear venta, stock, puntos |
| `promocion_service.py` | Validar y calcular promos |
| `receta_service.py` | Costo receta y precio sugerido |
| `fidelidad_service.py` | Puntos |
| `extras_validacion_service.py` | Extras obligatorios con insumo |
| `timezone_mx.py` | Día y timestamps para México |

### 2.8 Migraciones de base de datos

- Arranque: `Base.metadata.create_all()` + `aplicar_migraciones_sqlite()` en `database.py`.
- **No hay Alembic.** Cambios de esquema son parches SQL en código.
- `database/schema.sql` está **muy desactualizado** respecto a `models.py`; no usarlo como única fuente en producción nueva.

### 2.9 Impresión (Capacitor)

| Archivo | Rol |
|---------|-----|
| `printerService.js` | Bluetooth ESC/POS |
| `escposTickets.js` | Formato ticket Coffe Song |
| `PrinterSettings.jsx` | Emparejar impresora |

Impresión activa: **solo al cobrar** (ticket de venta). Comanda en cocina no imprime (por diseño reciente).

Build APK:

```powershell
cd frontend
npm run build:android
npm run cap:open
# Android Studio → Build APK(s)
```

Ver también: [IMPRESION_TABLET.md](IMPRESION_TABLET.md).

---

## 3. Despliegue en producción

### 3.1 Entorno real (Coffe Song)

| Componente | Servicio | URL ejemplo |
|------------|----------|-------------|
| Frontend | **Vercel** | `https://pos-cafeteria-brown.vercel.app` |
| Backend | **Render** | `https://pos-cafeteria-api.onrender.com` |
| Tablet | **APK** | Apunta a `VITE_API_URL` de Render |

### 3.2 Entorno documentado en repo (alternativo)

| Componente | Servicio |
|------------|----------|
| Frontend | AWS Amplify (`amplify.yml`) |
| Backend | AWS Elastic Beanstalk (`.github/workflows/deploy-backend.yml`) |
| BD | RDS PostgreSQL |

Guías: [GITHUB_SETUP.md](GITHUB_SETUP.md), [DEPLOY_AWS.md](DEPLOY_AWS.md), [ENTORNO_LOCAL_Y_PRODUCCION.md](ENTORNO_LOCAL_Y_PRODUCCION.md).

### 3.3 Desarrollo local

**Backend:**

```powershell
cd backend
copy .env.example .env
pip install -r requirements.txt
.\run-dev.ps1
# API: http://127.0.0.1:8000
```

**Frontend:**

```powershell
cd frontend
copy .env.example .env.local
# VITE_API_URL=http://127.0.0.1:8000
npm install
npm run dev
# Web: http://localhost:5173
```

Admin local por defecto (si BD vacía): ver `.env` → `LOCAL_ADMIN_LOGIN` / `LOCAL_ADMIN_PASSWORD`.

---

## 4. App Android (tablet)

- Misma app React empaquetada con Capacitor.
- Nombre: **Coffe Song** (`capacitor.config.json`).
- Impresora: MHT-P58D emparejada en Bluetooth del sistema.
- Configuración API: `frontend/.env.capacitor.local` → `VITE_API_URL=https://pos-cafeteria-api.onrender.com`
- **No** usar URL de Vercel como API.

---

## 5. Mejoras recomendadas

### 5.1 Prioridad alta (seguridad y coherencia)

| # | Mejora | Estado |
|---|--------|--------|
| 1 | **JWT obligatorio en toda la API** | ✅ Implementado (roles por router) |
| 2 | **CORS restringido** | ✅ `CORS_ORIGINS` en `.env` |
| 3 | **SECRET_KEY fuerte en Render** | ✅ Validación con `ENVIRONMENT=production` |
| 4 | **Persistir sesión** | ✅ localStorage + validación `/auth/me` |
| 5 | **Descuento receta en ventas mesa** | ✅ Al cobrar mesa y para llevar |
| 6 | **Actualizar README.md** | ✅ Actualizado |

### 5.2 Prioridad media (mantenimiento)

| # | Mejora | Motivo |
|---|--------|--------|
| 7 | **Alembic** para migraciones | Sustituir parches en `database.py` |
| 8 | **Regenerar `database/schema.sql`** | Baseline PG actual |
| 9 | **Tests pytest** | Pedido → cobro, promos, gastos, timezone |
| 10 | **CI frontend** | `npm run build` + lint en PR |
| 11 | **Doc deploy Vercel+Render** | Nuevo `DEPLOY_VERCEL_RENDER.md` |
| 12 | **Eliminar endpoints muertos en frontend** | `getVentas`, `getCompras` sin backend |
| 13 | **Rate limit en login** | Anti fuerza bruta |

### 5.3 Prioridad baja (evolución)

| # | Mejora | Motivo |
|---|--------|--------|
| 14 | **Multi-sucursal** | Varias cafeterías, precios distintos |
| 15 | **Export PDF/Excel** en reportes | Pedido frecuente en POS |
| 16 | **Modo offline tablet** | Red inestable en local |
| 17 | **Notificaciones comanda** | Push a cocina |
| 18 | **Observabilidad** | Logs estructurados, Sentry |
| 19 | **App iOS** | Requiere Mac + Xcode |
| 20 | **Tests E2E** | Playwright flujo venta completo |

### 5.4 Inconsistencias conocidas (resolver)

| Tema | Situación |
|------|-----------|
| Docs vs prod | Repo dice Amplify+EB; prod real Vercel+Render |
| `gastos_fijos` vs `gastos` | Gastos fijos = precio recetas; gastos del día = capital neto |
| Comanda impresa | Documentación antigua dice que imprime; código solo imprime al cobrar |
| Auth refresh | Sesión se pierde al recargar página |
| `schema.sql` | No refleja modelo actual |

---

## 6. Documentos del repositorio

| Archivo | Contenido | Estado |
|---------|-----------|--------|
| **DOCUMENTACION.md** (este) | General + técnico + mejoras | Actualizado |
| [README.md](README.md) | Intro y endpoints | Desactualizado |
| [ENTORNO_LOCAL_Y_PRODUCCION.md](ENTORNO_LOCAL_Y_PRODUCCION.md) | Local vs prod AWS | Parcialmente útil |
| [DEPLOY_AWS.md](DEPLOY_AWS.md) | Deploy AWS | Válido si usas AWS |
| [GITHUB_SETUP.md](GITHUB_SETUP.md) | Repo + CI EB | Válido |
| [IMPRESION_TABLET.md](IMPRESION_TABLET.md) | APK e impresora | Revisar sección comanda |
| `frontend/.env.capacitor.example` | API Render | Actualizado |

---

## Glosario rápido

| Término | Significado |
|---------|-------------|
| **Capital neto** | Ventas del día − gastos del día (hora MX) |
| **Comanda** | Pedido enviado a cocina (`en_comanda=true`) |
| **Extras** | Modificadores al producto (leche extra, jarabe…) |
| **Gastos fijos** | Costo mensual repartido en precios (config admin) |
| **Mesa 99** | Pedido para llevar |
| **ESC/POS** | Protocolo impresoras térmicas 58 mm |

---

*Proyecto: [Daniel-PenaG/pos-cafeteria](https://github.com/Daniel-PenaG/pos-cafeteria)*
