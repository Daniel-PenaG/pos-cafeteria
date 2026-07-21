# POS Cafetería - Sistema de Punto de Venta

Sistema integral de gestión para cafeterías con control de inventario, recetas, ventas y reportes.

**Desarrollo local:** [ENTORNO_LOCAL_Y_PRODUCCION.md](ENTORNO_LOCAL_Y_PRODUCCION.md)  
**Despliegue AWS:** [GITHUB_SETUP.md](GITHUB_SETUP.md) → [DEPLOY_AWS.md](DEPLOY_AWS.md)

## 📋 Tabla de Contenidos

- [Características](#características)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [API Endpoints](#api-endpoints)
- [Autenticación](#autenticación)

## ✨ Características

### ✅ Implementadas

- **CRUD Completo**: Productos, Categorías, Insumos, Recetas, Ventas, Compras
- **Autenticación JWT**: Registro y login con tokens seguros (Argon2)
- **Gestión de Recetas**: Asociación de productos con insumos
- **Control de Inventario**: Descuento automático de insumos en ventas
- **Reportes**: Ventas diarias, consumo de insumos, dashboard
- **Configuración de Márgenes**: Porcentaje de ganancia configurable (15% por defecto)
- **Validaciones Avanzadas**: Stock insuficiente, precios positivos, datos inválidos
- **Movimientos de Inventario**: Registro de todas las transacciones

## 🏗️ Estructura del Proyecto

```
backend/
├── app/
│   ├── models/models.py        # Base de datos (SQLAlchemy)
│   ├── routers/
│   │   ├── auth.py             # Autenticación
│   │   ├── productos.py        # Catálogo (CRUD completo)
│   │   ├── recetas.py          # Recetas
│   │   ├── ventas.py           # Ventas + descuento automático
│   │   ├── compras.py          # Compras
│   │   ├── reportes.py         # Reportes
│   │   └── configuracion.py    # Márgenes + cálculo de precio
│   ├── schemas/                # Validación con Pydantic
│   ├── utils/security.py       # JWT + Argon2
│   ├── exceptions.py           # Excepciones personalizadas
│   └── main.py                 # Aplicación FastAPI
└── requerimientos.txt

frontend/
├── src/
│   ├── services/               # Servicios API mejorados
│   ├── pages/                  # Componentes de página
│   ├── components/             # Componentes reutilizables
│   └── store/authStore.js      # Zustand
└── package.json
```

## 🚀 Instalación Rápida

Guía completa (local ↔ producción): **[ENTORNO_LOCAL_Y_PRODUCCION.md](ENTORNO_LOCAL_Y_PRODUCCION.md)**

### Backend

```powershell
cd backend
copy .env.example .env
.\setup-dev.ps1   # primera vez
.\run-dev.ps1
```

API: http://127.0.0.1:8000 — Login inicial: `admin` / `admin123`

### Frontend

```powershell
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

## 📡 API Endpoints (31 Total)

### Autenticación (2)
- `POST   /auth/register`
- `POST   /auth/login`

### Catálogo (15)
- `GET/POST/PUT/DELETE /catalogo/categorias{/id}`
- `GET/POST/PUT/DELETE /catalogo/productos{/id}`
- `GET/POST/PUT/DELETE /catalogo/insumos{/id}`

### Recetas (5)
- `GET/POST/PUT/DELETE /recetas{/id}`
- Incluye descuento automático de insumos

### Ventas (3)
- `POST   /ventas/`
- `GET    /ventas/`
- `GET    /ventas/{id}`

### Compras (3)
- `POST   /compras/`
- `GET    /compras/`
- `GET    /compras/{id}`

### Reportes (3)
- `GET    /reportes/ventas-dia?fecha=...`
- `GET    /reportes/consumo-insumos?fecha=...`
- `GET    /reportes/resumen-dashboard`

### Configuración (3)
- `GET    /configuracion/`
- `PUT    /configuracion/`
- `POST   /configuracion/calcular-precio`

## 🔐 Autenticación

```bash
# Login (SQLite local)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "usuario_login": "admin",
    "password": "admin123"
  }'

# Usar en otros endpoints
curl -X GET http://localhost:8000/catalogo/productos \
  -H "Authorization: Bearer <token>"
```

## ⚠️ Validaciones Implementadas

✅ Stock insuficiente (bloquea venta)
✅ Precios positivos
✅ Campos requeridos
✅ Margen 0-100%
✅ Stock no negativo
✅ Productos/categorías/insumos activos

## 📊 Servicios Frontend

Se han mejorado todos los servicios con métodos completos:

- `productosService.js` - CRUD de productos, categorías e insumos
- `recetasService.js` - CRUD de recetas
- `ventasService.js` - Crear y listar ventas
- `comprasService.js` - Crear y listar compras
- `reportesService.js` - Obtener reportes
- `configuracionService.js` - Gestionar márgenes y cálculo de precios

## 🛠️ Tecnologías

- **Backend**: FastAPI, SQLAlchemy, Pydantic, JWT
- **Frontend**: React, Axios, Zustand
- **Database**: SQLite (dev) / Oracle (prod)
- **Auth**: Argon2 + JWT

## 📈 Estado del Proyecto

| Tarea | Estado | Descripción |
|-------|--------|-------------|
| CRUD Productos | ✅ | 15 endpoints completos |
| Descuento Insumos | ✅ | Automático en ventas |
| Márgenes | ✅ | Configurable (0-100%) |
| Servicios Frontend | ✅ | Todos mejorados |
| Validaciones | ✅ | Excepciones personalizadas |
| Documentación | ✅ | README + inline |

## 🚀 Próximos Pasos

- [ ] Integración frontend completa
- [ ] Tests unitarios (pytest)
- [ ] CI/CD (GitHub Actions)
- [ ] Paginación
- [ ] Exportar reportes PDF
- [ ] Gráficas

## 📚 Documentación API

Docs interactivos: `http://localhost:8000/docs`

---

**Última actualización**: Mayo 2024
