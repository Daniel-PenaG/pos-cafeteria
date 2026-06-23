# Subir a GitHub y desplegar en AWS

Orden recomendado: **1) GitHub → 2) AWS (RDS + EB + Amplify) → 3) Secrets → 4) Push automático**

Guía detallada de AWS: [DEPLOY_AWS.md](DEPLOY_AWS.md)

---

## Parte A — Subir el proyecto a GitHub

### 1. Verificar que no subes secretos

Estos archivos **no** deben ir al repo (ya están en `.gitignore`):

- `backend/.env`
- `frontend/.env.local`
- `frontend/.env.production`
- `backend/venv/`, `node_modules/`, `*.db`, `*.zip`

Sí se suben las plantillas: `backend/.env.example`, `frontend/.env.example`

### 2. Crear el repositorio en GitHub (si aún no existe)

1. https://github.com/new
2. Nombre: `pos-cafeteria`
3. **No** marques “Add README” si ya tienes código local
4. Copia la URL: `https://github.com/TU_USUARIO/pos-cafeteria.git`

Tu remote actual:

```
https://github.com/Daniel-PenaG/pos-cafeteria.git
```

### 3. Unificar rama principal (recomendado: `main`)

GitHub Actions y Amplify usan `main` por defecto. Si estás en `master`:

```powershell
cd c:\workspace\pos-cafeteria
git branch -M main
```

### 4. Primer push (o actualizar GitHub)

```powershell
cd c:\workspace\pos-cafeteria

# Ver qué se va a subir
git status

# Agregar todo el proyecto (respeta .gitignore)
git add .

# Commit
git commit -m "POS cafetería: listo para despliegue AWS desde GitHub"

# Subir (primera vez)
git push -u origin main
```

Si `origin` ya tiene historial y hay conflictos, revisa con `git pull origin main --rebase` antes de push.

### 5. Comprobar en GitHub

- [ ] Código visible en la rama `main`
- [ ] Existe `.github/workflows/deploy-backend.yml`
- [ ] Existe `amplify.yml` en la raíz
- [ ] **No** aparece `backend/.env` ni `frontend/.env.production`

---

## Parte B — Configurar AWS (una sola vez)

Haz esto **después** de tener el código en GitHub.

### Resumen rápido

| Paso | Servicio | Acción |
|------|----------|--------|
| 1 | **RDS** | PostgreSQL + ejecutar `database/schema.sql` |
| 2 | **Elastic Beanstalk** | App Python, variables de entorno, probar `/health` |
| 3 | **Amplify** | Conectar repo GitHub, rama `main`, `VITE_API_URL` |
| 4 | **GitHub Secrets** | Keys para despliegue automático del backend |

Detalle paso a paso: [DEPLOY_AWS.md](DEPLOY_AWS.md)

### Variables importantes

**Elastic Beanstalk (backend):**

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL RDS |
| `SECRET_KEY` | Clave JWT larga y aleatoria |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |

**Amplify (frontend, build time):**

| Variable | Descripción |
|----------|-------------|
| `VITE_API_URL` | URL pública del backend EB (sin `/` final) |

---

## Parte C — Despliegue automático desde GitHub

### Frontend → Amplify (automático al hacer push)

1. AWS Console → **Amplify** → Create app → **GitHub**
2. Repo: `Daniel-PenaG/pos-cafeteria` (o el tuyo)
3. Rama: **`main`**
4. Build: detecta `amplify.yml` automáticamente
5. Agrega `VITE_API_URL` en Environment variables
6. Deploy

Cada `git push` a `main` que cambie `frontend/` → Amplify reconstruye.

### Backend → GitHub Actions → Elastic Beanstalk

1. Crea usuario IAM con permisos EB (ver [DEPLOY_AWS.md](DEPLOY_AWS.md))
2. En GitHub → repo → **Settings → Secrets and variables → Actions**:

| Secret | Valor |
|--------|--------|
| `AWS_ACCESS_KEY_ID` | Access key IAM |
| `AWS_SECRET_ACCESS_KEY` | Secret IAM |
| `AWS_REGION` | ej. `us-east-1` |
| `EB_APPLICATION_NAME` | Nombre app en EB |
| `EB_ENVIRONMENT_NAME` | Nombre entorno EB |

3. Haz un push que toque `backend/` o ejecuta manualmente:
   - GitHub → **Actions** → **Deploy backend** → **Run workflow**

---

## Parte D — Verificación final

```text
https://TU-API.elasticbeanstalk.com/health     → {"status":"ok"}
https://TU-APP.amplifyapp.com                    → login del POS
```

Crear primer admin: ver sección en [DEPLOY_AWS.md](DEPLOY_AWS.md#paso-5--primer-usuario-administrador).

---

## Flujo de trabajo diario

```text
Editas código en local
    ↓
git add . && git commit -m "..." && git push origin main
    ↓
    ├─ Cambios en frontend/  →  Amplify despliega solo
    └─ Cambios en backend/   →  GitHub Actions → EB
```

---

## Desarrollo local (sin afectar AWS)

```powershell
# Backend
cd backend
copy .env.example .env    # editar DATABASE_URL, SECRET_KEY
.\run-dev.ps1

# Frontend (otra terminal)
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Empaquetado manual del backend (opcional): `.\package-aws.ps1`
