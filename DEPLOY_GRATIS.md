# Despliegue gratuito (FastAPI + React + PostgreSQL)

Sí: puedes subir **todo el stack** sin pagar al inicio y **escalar a planes de pago** cuando crezca el uso.

| Componente | Tecnología | Servicio recomendado | Plan gratis | Plan de pago (cuando lo necesites) |
|------------|------------|----------------------|-------------|-------------------------------------|
| **Frontend** | React + Vite | [Vercel](https://vercel.com) | $0, sin límite de “sueño” | Pro ~$20/mes (más builds, equipo) |
| **Backend** | FastAPI | [Render](https://render.com) | $0 (se duerme tras inactividad) | Starter ~$7/mes (siempre activo) |
| **Base de datos** | PostgreSQL | [Neon](https://neon.tech) | $0 (~0.5 GB) | Scale ~$19/mes (más almacenamiento y cómputo) |

**Costo inicial real: $0/mes.** Solo pagas cuando superas los límites del plan gratis o necesitas que la API esté siempre despierta.

---

## ¿Qué significa “gratis” en la práctica?

### Lo que SÍ tienes gratis
- Frontend en internet con HTTPS (Vercel).
- API FastAPI con todos tus endpoints (Render).
- PostgreSQL real, no SQLite (Neon).
- Despliegue automático al hacer `push` a GitHub.
- Suficiente para **demo, portafolio o una cafetería pequeña** con poco tráfico.

### Limitaciones del plan gratis
| Limitación | Impacto |
|------------|---------|
| Render “duerme” la API tras ~15 min sin peticiones | La primera carga tarda 30–60 s en despertar |
| Neon gratis: ~0.5 GB de datos | Miles de ventas/productos; no millones |
| Render gratis: 750 h/mes de cómputo | Suficiente si la API duerme cuando no se usa |
| Sin SLA ni soporte prioritario | Normal en planes gratuitos |

### Cuándo conviene pagar
| Situación | Qué actualizar |
|-----------|----------------|
| La cafetería abre todos los días y no quieres esperar al “despertar” | Render Starter (~$7/mes) |
| Más ventas, más productos, más historial | Neon Scale (~$19/mes) |
| Dominio propio + más builds en CI | Vercel Pro (~$20/mes) |

Puedes pagar **solo una pieza** (por ejemplo solo el backend) y dejar el resto gratis.

---

## Arquitectura

```text
Usuario (navegador)
        │
        ▼
   Vercel ──────────────► React (frontend/dist)
        │
        │  VITE_API_URL
        ▼
   Render ──────────────► FastAPI (backend/)
        │
        │  DATABASE_URL
        ▼
   Neon ────────────────► PostgreSQL
```

---

## Requisitos previos

1. Código en **GitHub** ([GITHUB_SETUP.md](GITHUB_SETUP.md)).
2. Cuenta gratis en [Neon](https://neon.tech), [Render](https://render.com) y [Vercel](https://vercel.com).

---

## Paso 1 — PostgreSQL en Neon (gratis)

1. Crea un proyecto en Neon.
2. Copia la **connection string** (formato `postgresql://...`).
3. Conviértela al formato que usa SQLAlchemy en este proyecto:

   ```text
   postgresql+psycopg2://USUARIO:PASSWORD@HOST/BD?sslmode=require
   ```

   (Neon suele incluir `?sslmode=require`; si la contraseña tiene caracteres especiales, codifícala en URL.)

4. En el **SQL Editor** de Neon, pega y ejecuta el contenido de:

   ```text
   database/schema.sql
   ```

5. Guarda esa URL: será tu `DATABASE_URL`.

---

## Paso 2 — Backend en Render (gratis)

### Opción A — Blueprint (recomendada)

El repo incluye `render.yaml` en la raíz. En Render:

1. **New** → **Blueprint** → conecta tu repo de GitHub.
2. Render detecta `render.yaml` y crea el servicio web.
3. Te pedirá el valor de `DATABASE_URL` (pega la URL de Neon).
4. `SECRET_KEY` puede generarse automáticamente o pon una cadena larga aleatoria.

### Opción B — Manual

1. **New** → **Web Service** → conecta GitHub.
2. Configuración:

   | Campo | Valor |
   |-------|--------|
   | Root Directory | `backend` |
   | Runtime | Python 3 |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120` |

3. **Environment variables:**

   | Variable | Valor |
   |----------|--------|
   | `DATABASE_URL` | URL de Neon (`postgresql+psycopg2://...`) |
   | `SECRET_KEY` | Cadena aleatoria de 32+ caracteres |
   | `ALGORITHM` | `HS256` |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |

4. Plan: **Free**.
5. Deploy.

6. Verifica: `https://TU-SERVICIO.onrender.com/health` → `{"status":"ok"}`.

Anota la URL del backend (sin `/` al final).

---

## Paso 3 — Frontend en Vercel (gratis)

1. [vercel.com](https://vercel.com) → **Add New Project** → importa tu repo.
2. Configuración:

   | Campo | Valor |
   |-------|--------|
   | Framework Preset | Vite |
   | Root Directory | `frontend` |
   | Build Command | `npm run build` |
   | Output Directory | `dist` |

3. **Environment variables** (producción):

   | Variable | Valor |
   |----------|--------|
   | `VITE_API_URL` | `https://TU-SERVICIO.onrender.com` |

4. Deploy.

El archivo `frontend/vercel.json` redirige rutas de React Router a `index.html`.

URL final: `https://tu-proyecto.vercel.app`

---

## Paso 4 — Primer usuario administrador

Con backend y BD listos:

```bash
curl -X POST https://TU-SERVICIO.onrender.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Admin","usuario_login":"admin","password":"TuClaveSegura","rol":"ADMIN"}'
```

O inserta un usuario en Neon con hash Argon2 vía SQL.

---

## Despliegue automático

```text
git push origin main
        │
        ├─► Cambios en frontend/  →  Vercel rebuild
        │
        └─► Cambios en backend/   →  Render redeploy
```

Neon no se redeploya con el código; solo cambia cuando migras datos o escalas el plan.

---

## Ruta de escalado (de gratis a pago)

| Etapa | Frontend | Backend | Base de datos | Costo aprox. |
|-------|----------|---------|---------------|--------------|
| **0 — Prueba / demo** | Vercel Free | Render Free | Neon Free | **$0** |
| **1 — Cafetería real** | Vercel Free | Render Starter | Neon Free | **~$7/mes** |
| **2 — Más datos / tráfico** | Vercel Free | Render Starter | Neon Scale | **~$26/mes** |
| **3 — Producción seria** | Vercel Pro o AWS Amplify | Render o AWS EB | Neon o AWS RDS | **$40+/mes** |

No hace falta migrar de stack: subes de plan en el mismo proveedor.

---

## Checklist

- [ ] `schema.sql` ejecutado en Neon
- [ ] `DATABASE_URL` en Render apunta a Neon
- [ ] `/health` responde OK
- [ ] `VITE_API_URL` en Vercel apunta al backend Render
- [ ] Login funciona desde la URL de Vercel
- [ ] Usuario ADMIN creado

---

## Solución de problemas

| Problema | Qué revisar |
|----------|-------------|
| La app tarda mucho al abrir | Render Free dormido; espera ~1 min o pasa a Starter |
| Error de conexión a BD | `DATABASE_URL` con `postgresql+psycopg2://` y `sslmode=require` |
| Frontend no llega al API | `VITE_API_URL` correcta y **redeploy** de Vercel tras cambiarla |
| 404 al recargar una ruta | `frontend/vercel.json` debe estar en el repo |
| CORS | La API ya permite `*`; en producción puedes limitar al dominio Vercel |

---

## Comparación con AWS

| | AWS ([DEPLOY_AWS.md](DEPLOY_AWS.md)) | Gratis ([este doc](DEPLOY_GRATIS.md)) |
|---|--------------------------------------|----------------------------------------|
| Complejidad | Alta (RDS, EB, Amplify, IAM) | Baja (3 cuentas, pocos clics) |
| Costo inicial | Free tier 12 meses, luego de pago | $0 estable en capa gratuita |
| Escalado | Muy alto | Bueno hasta mediana escala |
| Ideal para | Empresa / alto tráfico | Empezar, aprender, cafetería pequeña |

Puedes empezar gratis y migrar a AWS más adelante si lo necesitas; el código no cambia, solo las URLs y `DATABASE_URL`.
