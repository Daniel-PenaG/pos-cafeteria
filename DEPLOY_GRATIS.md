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

1. Código en **GitHub** en la rama `main` ([GITHUB_SETUP.md](GITHUB_SETUP.md)).
   Repo: `https://github.com/Daniel-PenaG/pos-cafeteria`
2. Cuenta gratis en [Neon](https://neon.tech), [Render](https://render.com) y [Vercel](https://vercel.com) (puedes usar “Sign in with GitHub”).

**Tiempo estimado:** 30–45 minutos la primera vez.

---

## Guía paso a paso (clic a clic)

### A. Neon — base de datos (≈10 min)

1. Entra a [console.neon.tech](https://console.neon.tech) → **Sign up** (GitHub).
2. **New Project** → nombre ej. `pos-cafeteria` → región cercana a ti → **Create**.
3. En el dashboard, copia la **Connection string** (pestaña *Connection details*).
4. Cámbiala a formato SQLAlchemy:

   ```text
   postgresql+psycopg2://USUARIO:PASSWORD@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require
   ```

   Solo cambia el inicio de `postgresql://` a `postgresql+psycopg2://`.

5. Menú izquierdo → **SQL Editor** → **New query**.
6. Abre en tu repo el archivo `database/schema.sql`, copia todo, pégalo en Neon → **Run**.
7. Guarda la `DATABASE_URL` en un bloc de notas (la usarás en Render).

### B. Render — backend FastAPI (≈15 min)

1. Entra a [dashboard.render.com](https://dashboard.render.com) → **Sign up** (GitHub).
2. **New +** → **Blueprint**.
3. Conecta el repo `Daniel-PenaG/pos-cafeteria` → rama **`main`**.
4. Render lee `render.yaml` y muestra el servicio `pos-cafeteria-api`.
5. Cuando pida variables:
   - **`DATABASE_URL`** → pega la URL de Neon (paso A.4).
   - **`SECRET_KEY`** → deja que Render la genere o pega una clave aleatoria de 40+ caracteres.
6. **Apply** → espera el deploy (5–10 min).
7. Abre la URL que te da Render, ej. `https://pos-cafeteria-api.onrender.com/health`.
   - Debe responder: `{"status":"ok"}`
8. Si falla: **Logs** en Render → revisa que `DATABASE_URL` sea correcta.

**Si no usas Blueprint (manual):** New → Web Service → mismo repo → Root Directory `backend` → ver tabla en sección siguiente.

### C. Vercel — frontend React (≈10 min)

1. Entra a [vercel.com](https://vercel.com) → **Sign up** (GitHub).
2. **Add New…** → **Project** → importa `pos-cafeteria`.
3. **Configure Project:**

   | Campo | Valor |
   |-------|--------|
   | Framework Preset | Vite |
   | Root Directory | `frontend` (clic en Edit) |
   | Build Command | `npm run build` |
   | Output Directory | `dist` |

4. **Environment Variables** → agrega:

   | Name | Value |
   |------|--------|
   | `VITE_API_URL` | `https://pos-cafeteria-api.onrender.com` (tu URL de Render, **sin** `/` final) |

5. **Deploy** → espera 2–5 min.
6. Abre la URL, ej. `https://pos-cafeteria.vercel.app`.

### D. Primer login (≈5 min)

Sigue el [Paso 4 — Primer usuario administrador](#paso-4--primer-usuario-administrador) más abajo.

### E. Verificación final

| Prueba | Resultado esperado |
|--------|-------------------|
| `https://TU-API.onrender.com/health` | `{"status":"ok"}` |
| Abrir URL de Vercel | Pantalla de login |
| Login con admin | Entras al dashboard |
| Primera carga lenta (~1 min) | Normal en Render Free (API despertando) |

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

`/auth/register` **solo lo puede usar un administrador ya logueado**. El primer admin se crea en la base de datos:

1. En tu PC, desde la carpeta `backend`:

   ```bash
   pip install passlib argon2-cffi
   python scripts/crear_admin.py --login admin --password "TuClaveSegura123"
   ```

2. Copia el `INSERT` que imprime el script.
3. Pégalo en el **SQL Editor de Neon** y ejecútalo.
4. Entra en tu app Vercel con ese usuario y contraseña.

Después, desde el panel **Usuarios** (como admin) puedes crear más cuentas.

---

## ¿Es seguro?

**Sí, para empezar y para una cafetería pequeña/mediana** — si sigues estas prácticas:

| Qué protege tu app | Estado |
|--------------------|--------|
| HTTPS en frontend, API y BD | Automático (Vercel, Render, Neon) |
| Contraseñas con **Argon2** (no texto plano) | Ya implementado |
| Tokens **JWT** con expiración | Ya implementado |
| Secretos en variables de entorno (no en Git) | `.env` está en `.gitignore` |
| Registro de usuarios solo para admin | Ya implementado |
| Conexión a PostgreSQL cifrada (`sslmode=require`) | Configúralo en `DATABASE_URL` |

**Buenas prácticas al desplegar:**

1. **`SECRET_KEY`**: usa una cadena larga y aleatoria (Render puede generarla). No uses `cambia-esta-clave`.
2. **Contraseña del admin**: mínimo 12 caracteres, mezcla letras y números.
3. **No subas** `backend/.env` ni contraseñas a GitHub.
4. **Neon**: no compartas la connection string públicamente.

**Limitaciones del plan gratis (no son fallos de seguridad, pero conviene saberlo):**

- La API en Render Free se “duerme”; no es un riesgo, solo latencia.
- CORS permite cualquier origen (`*`); para una cafetería real puedes limitarlo al dominio Vercel más adelante.
- Los proveedores gratuitos compuyen recursos; para datos muy sensibles o alto volumen, sube a planes de pago.

**Resumen:** es tan seguro como la mayoría de startups que arrancan en la nube. Lo crítico es **SECRET_KEY fuerte**, **contraseñas buenas** y **no exponer credenciales**.

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
