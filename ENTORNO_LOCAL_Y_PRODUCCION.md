# Entorno local vs producción

Guía para trabajar en tu laptop y cambiar a AWS cuando quieras desplegar.

---

## Resumen rápido

| Qué cambia | Local (laptop) | Producción (AWS) |
|------------|----------------|------------------|
| **Base de datos** | SQLite (`pos_cafeteria.db`) o PostgreSQL local | RDS PostgreSQL |
| **Backend URL** | `http://127.0.0.1:8000` | URL de Elastic Beanstalk |
| **Config backend** | Archivo `backend/.env` | Variables en EB → Software → Environment properties |
| **Config frontend** | Archivo `frontend/.env.local` | Variable `VITE_API_URL` en Amplify |
| **Arranque backend** | `.\run-dev.ps1` (uvicorn con reload) | Gunicorn + UvicornWorker (Procfile) |
| **Deploy** | No aplica | Push a `main` → GitHub Actions + Amplify |

**Regla:** los archivos `.env` y `.env.local` **no se suben a git**. En producción las variables viven en la consola de AWS.

---

## Instalación local (tu laptop)

### 1. Backend

```powershell
cd backend
copy .env.example .env
.\setup-dev.ps1    # solo la primera vez (instala dependencias)
.\run-dev.ps1
```

El entorno virtual se guarda en **`%USERPROFILE%\.venvs\pos-cafeteria`** (fuera del proyecto) para evitar errores de permisos en Windows con `backend\venv`.

Comprueba: http://127.0.0.1:8000/health → `{"status":"ok"}`

**Usuario inicial (SQLite):** si la base está vacía, se crea automáticamente:

| Campo | Valor por defecto |
|-------|-------------------|
| Usuario | `admin` |
| Contraseña | `admin123` |

Puedes cambiarlos en `backend/.env` con `LOCAL_ADMIN_LOGIN` y `LOCAL_ADMIN_PASSWORD` (solo antes del primer arranque).

### 2. Frontend

```powershell
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Abre la URL que muestre Vite (normalmente http://localhost:5173) e inicia sesión con `admin` / `admin123`.

### 3. Base de datos local

**Opción A — SQLite (recomendada, ya configurada en `.env.example`):**

```env
DATABASE_URL=sqlite:///./pos_cafeteria.db
```

El archivo `backend/pos_cafeteria.db` se crea solo al arrancar. Para empezar de cero, bórralo y reinicia el backend.

**Opción B — PostgreSQL local:**

1. Instala PostgreSQL en tu PC.
2. Crea la base `cafeteria_db` y ejecuta `database/schema.sql`.
3. En `backend/.env`, comenta SQLite y usa:

```env
DATABASE_URL=postgresql+psycopg2://usuario:password@localhost:5432/cafeteria_db
```

4. Reinicia el backend. En PostgreSQL **no** se crea admin automático; créalo con SQL o la API (ver [DEPLOY_AWS.md](DEPLOY_AWS.md#paso-5--primer-usuario-administrador)).

---

## Cambiar de local → producción

Haz estos pasos **antes** de desplegar o cuando quieras que la app en AWS use datos reales.

### Backend (Elastic Beanstalk)

1. En **AWS Console → Elastic Beanstalk → tu entorno → Configuration → Software → Environment properties**, configura:

   | Variable | Valor en producción |
   |----------|---------------------|
   | `DATABASE_URL` | `postgresql+psycopg2://USUARIO:PASSWORD@HOST_RDS:5432/cafeteria_db` |
   | `SECRET_KEY` | Clave larga y aleatoria (distinta a la local) |
   | `ALGORITHM` | `HS256` |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |

2. **No** subas `backend/.env` al repositorio. EB no lo usa; usa las variables de la consola.

3. Asegura que el **security group de RDS** permita puerto **5432** desde el security group de Elastic Beanstalk.

4. Ejecuta `database/schema.sql` en RDS si es la primera vez.

5. Push a `main` (con cambios en `backend/`) → GitHub Actions despliega el ZIP a EB.

6. Crea el primer usuario admin en RDS (ver [DEPLOY_AWS.md](DEPLOY_AWS.md)).

### Frontend (Amplify)

1. En **Amplify → App → Environment variables**, agrega:

   ```text
   VITE_API_URL = https://tu-entorno.elasticbeanstalk.com
   ```

   (Sin barra final. Usa la URL real de tu backend EB.)

2. **No** dependas de `frontend/.env.local` en producción; Amplify usa sus propias variables al hacer `npm run build`.

3. Push a `main` → Amplify reconstruye el frontend.

### Qué NO tocar en el repo para producción

- `backend/Procfile` — ya apunta a Gunicorn/Uvicorn para EB.
- `.github/workflows/deploy-backend.yml` — deploy automático del backend.
- `amplify.yml` — build del frontend en Amplify.

---

## Cambiar de producción → local

Cuando vuelvas a desarrollar en tu laptop:

### 1. Backend — editar `backend/.env`

```env
DATABASE_URL=sqlite:///./pos_cafeteria.db
SECRET_KEY=supersecreto123
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
LOCAL_ADMIN_LOGIN=admin
LOCAL_ADMIN_PASSWORD=admin123
```

**Importante:** comenta o elimina cualquier `DATABASE_URL` que apunte a RDS. Si dejas la URL de AWS, el backend intentará conectarse a RDS y fallará (timeout o acceso denegado).

### 2. Frontend — editar `frontend/.env.local`

```env
VITE_API_URL=http://127.0.0.1:8000
```

Si tenías `frontend/.env.production` con la URL de AWS, no afecta a `npm run dev` (Vite prioriza `.env.local` en desarrollo).

### 3. Arrancar servicios

```powershell
# Terminal 1
cd backend
.\run-dev.ps1

# Terminal 2
cd frontend
npm run dev
```

### 4. Datos locales vs datos de producción

- **Local (SQLite):** datos en `backend/pos_cafeteria.db` — independientes de RDS.
- **Producción:** datos solo en RDS — no se sincronizan solos con tu laptop.

Para probar con datos parecidos a producción puedes exportar/importar PostgreSQL, pero lo habitual es usar SQLite local con datos de prueba.

---

## Checklist por escenario

### Quiero desarrollar en mi laptop

- [ ] `backend/.env` → `DATABASE_URL=sqlite:///./pos_cafeteria.db`
- [ ] `frontend/.env.local` → `VITE_API_URL=http://127.0.0.1:8000`
- [ ] `.\run-dev.ps1` + `npm run dev`
- [ ] Login: `admin` / `admin123` (primera vez con SQLite vacía)

### Quiero desplegar o actualizar producción

- [ ] Variables en **EB** (no en `.env` del repo)
- [ ] `VITE_API_URL` en **Amplify**
- [ ] RDS accesible desde EB (security groups)
- [ ] `SECRET_KEY` de producción distinta a la local
- [ ] Push a `main`

### Volví de AWS y quiero local otra vez

- [ ] Restaurar `backend/.env` a SQLite (ver arriba)
- [ ] Restaurar `frontend/.env.local` a `127.0.0.1:8000`
- [ ] No hace falta cambiar código ni Procfile

---

## Archivos de configuración (referencia)

| Archivo | Entorno | ¿En git? |
|---------|---------|----------|
| `backend/.env` | Local | No |
| `backend/.env.example` | Plantilla | Sí |
| `frontend/.env.local` | Local dev | No |
| `frontend/.env.example` | Plantilla | Sí |
| `frontend/.env.production.example` | Plantilla Amplify | Sí |
| EB Environment properties | Producción backend | Solo en AWS |
| Amplify env vars | Producción frontend | Solo en AWS |

---

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `WinError 5` al instalar en `backend\venv` | Windows/antivirus bloquea `.pyd` en la carpeta del proyecto | Usar `.\setup-dev.ps1` (venv en `%USERPROFILE%\.venvs\pos-cafeteria`) |
| `No module named uvicorn` | Instalación incompleta | `.\setup-dev.ps1` y luego `.\run-dev.ps1` |
| Backend no arranca: `DATABASE_URL no está configurada` | Falta `.env` | `copy .env.example .env` |
| Timeout al conectar BD | `.env` apunta a RDS | Cambiar a SQLite local |
| Login devuelve 400 | Usuario/contraseña incorrectos | Local: **admin** / **admin123** (no `password123` del README viejo) |
| Frontend no carga datos / CORS | API URL incorrecta | Revisar `VITE_API_URL` en `.env.local` |
| Login falla tras borrar `.db` | BD nueva sin usuarios | Reiniciar backend (crea admin automático) |
| Menú vacío tras login | Rol legacy en BD | Reiniciar backend (migración normaliza roles) |

---

## Más información

- Subir código a GitHub: [GITHUB_SETUP.md](GITHUB_SETUP.md)
- Despliegue completo en AWS: [DEPLOY_AWS.md](DEPLOY_AWS.md)
