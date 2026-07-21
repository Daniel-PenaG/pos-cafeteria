# Despliegue automático desde GitHub → AWS

Sí es posible. El flujo recomendado para este proyecto:

| Parte | Servicio AWS | Despliegue automático |
|-------|--------------|------------------------|
| **Frontend** (React) | **Amplify Hosting** | Conectas GitHub en la consola → cada `push` a `main` rebuild |
| **Backend** (FastAPI) | **Elastic Beanstalk** | GitHub Actions (workflow incluido) → cada `push` que toque `backend/` |

Base de datos: **RDS PostgreSQL** (manual la primera vez; la app se conecta con `DATABASE_URL`).

---

## Requisitos previos

1. Código en un repositorio de **GitHub** (público o privado).
2. Cuenta **AWS** con permisos para EB, Amplify, RDS e IAM.
3. Rama principal **`main`** (recomendado; el workflow también acepta `master`).

**Empieza aquí:** [GITHUB_SETUP.md](GITHUB_SETUP.md) → subir a GitHub → luego AWS.

---

## Paso 1 — Base de datos (RDS PostgreSQL)

1. En AWS Console → **RDS** → Create database → PostgreSQL.
2. Anota: host, puerto, usuario, contraseña, nombre de BD.
3. **Security group:** permite tráfico **5432** desde el security group de Elastic Beanstalk.
4. Conecta (Query Editor, DBeaver o `psql`) y ejecuta el script:

   ```
   database/schema.sql
   ```

5. URL de conexión para EB:

   ```
   postgresql+psycopg2://USUARIO:PASSWORD@HOST:5432/NOMBRE_BD
   ```

   (Si la contraseña tiene caracteres especiales, codifícala en URL.)

---

## Paso 2 — Backend (Elastic Beanstalk) — primera vez

1. **Elastic Beanstalk** → Create application → nombre ej. `pos-cafeteria`.
2. Create environment → **Web server** → plataforma **Python 3.11** (o la más reciente disponible).
3. Subdomain ej. `pos-cafeteria-api`.
4. En **Configuration → Software → Environment properties**, agrega:

   | Variable | Ejemplo |
   |----------|---------|
   | `DATABASE_URL` | `postgresql+psycopg2://...` |
   | `SECRET_KEY` | cadena larga aleatoria (32+ chars) |
   | `ALGORITHM` | `HS256` |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |

5. **Primera prueba manual (opcional):**

   ```powershell
   .\package-aws.ps1
   ```

   Sube `deploy-eb.zip` en EB → Upload and deploy.

6. Verifica: `https://TU-ENTORNO.elasticbeanstalk.com/health` → `{"status":"ok"}`.

Anota:

- **Application name** (ej. `pos-cafeteria`)
- **Environment name** (ej. `pos-cafeteria-prod`)
- **Region** (ej. `us-east-1`)

---

## Paso 3 — Backend — despliegue automático (GitHub Actions)

El repo incluye `.github/workflows/deploy-backend.yml`.

### 3.1 Usuario IAM para GitHub

1. IAM → Users → Create user → ej. `github-pos-deploy`.
2. Adjunta política personalizada (ajusta nombres de app/entorno):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "elasticbeanstalk:*",
        "s3:*",
        "cloudformation:*",
        "autoscaling:*",
        "ec2:Describe*",
        "logs:*"
      ],
      "Resource": "*"
    }
  ]
}
```

Para producción real, restringe recursos al ARN de tu aplicación EB.

3. Crea **Access key** (programmatic) y guarda ID y secret.

### 3.2 Secrets en GitHub

Repo → **Settings** → **Secrets and variables** → **Actions** → New repository secret:

| Secret | Valor |
|--------|--------|
| `AWS_ACCESS_KEY_ID` | Access key IAM |
| `AWS_SECRET_ACCESS_KEY` | Secret key IAM |
| `AWS_REGION` | ej. `us-east-1` |
| `EB_APPLICATION_NAME` | nombre app EB |
| `EB_ENVIRONMENT_NAME` | nombre entorno EB |

### 3.3 Activar

1. Haz `push` a `main` con cambios en `backend/`.
2. Pestaña **Actions** en GitHub → workflow **Deploy backend**.
3. EB mostrará una nueva versión desplegada.

También puedes lanzarlo a mano: Actions → Run workflow.

---

## Paso 4 — Frontend (Amplify) — despliegue automático

Amplify se conecta directo a GitHub; **no** usa el workflow de Actions.

1. AWS Console → **Amplify** → **Create new app** → **Host web app**.
2. Elige **GitHub** → autoriza → selecciona repo y rama **`main`**.
3. Amplify detecta **`amplify.yml`** en la raíz (build en `frontend/`).
4. En **Environment variables** (build time):

   | Variable | Valor |
   |----------|--------|
   | `VITE_API_URL` | URL del backend EB **sin** barra final, ej. `https://pos-cafeteria-api.us-east-1.elasticbeanstalk.com` |

5. Save and deploy.

Cada `push` a `main` que cambie el frontend dispara build + deploy en Amplify.

URL final: `https://main.xxxxx.amplifyapp.com` (o dominio custom).

---

## Paso 5 — Primer usuario administrador

Tras tener backend + BD:

**Opción A — SQL en RDS** (genera hash Argon2 localmente o usa script):

```sql
INSERT INTO usuarios (nombre, usuario_login, hash_password, rol)
VALUES ('Admin', 'admin', '<HASH_ARGON2>', 'ADMIN');
```

**Opción B — API** (si tienes un admin temporal o desbloqueas register):

```bash
curl -X POST https://TU-API/auth/register \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Admin","usuario_login":"admin","password":"TuClaveSegura","rol":"ADMIN"}'
```

El rol debe ser `ADMIN`, `CAJERO` o `COCINA`.

---

## Paso 6 — HTTPS y dominio (recomendado)

| Componente | Opción |
|------------|--------|
| Frontend | Amplify incluye HTTPS; puedes añadir dominio en Amplify → Domain management |
| Backend | EB: Load balancer + certificado ACM, o API Gateway delante |
| CORS | Hoy la API permite `*`; en producción conviene limitar al dominio Amplify |

---

## Resumen del flujo automático

```text
git push origin main
        │
        ├─► Cambios en frontend/  →  Amplify rebuild (automático, consola)
        │
        └─► Cambios en backend/   →  GitHub Actions → ZIP → Elastic Beanstalk
```

---

## Checklist antes de producción

- [ ] RDS con `schema.sql` aplicado
- [ ] Variables EB configuradas (no subir `.env` a git)
- [ ] `VITE_API_URL` en Amplify apunta al backend real
- [ ] `/health` responde OK
- [ ] Login funciona desde la URL de Amplify
- [ ] Secrets de GitHub configurados
- [ ] Security groups: RDS solo accesible desde EB
- [ ] `SECRET_KEY` fuerte y única en producción

---

## Desarrollo local

Ver variables en `backend/.env.example` y `frontend/.env.example`.

```powershell
cd backend; .\run-dev.ps1
cd frontend; npm install; npm run dev
```

---

## Solución de problemas

| Problema | Revisar |
|----------|---------|
| Actions falla “Access Denied” | IAM policy y secrets de GitHub |
| Amplify build OK pero API no conecta | `VITE_API_URL` y redeploy Amplify tras cambiarla |
| ZIP falla: backslashes as path separators | No uses Compress-Archive de Windows. Usa `.\package-aws.ps1` o GitHub Actions |
| EB 502 / gunicorn gthread en logs | Redeploy con ZIP correcto; Procfile debe usar `UvicornWorker` |
| EB 502 general | Logs EB → `/var/log/web.stdout.log`; revisar `DATABASE_URL` |
| CORS en navegador | Origen del front debe estar permitido (hoy `*`) |
| Tablas faltantes | Ejecutar migraciones / `schema.sql` en RDS |

Empaquetado manual del backend: `.\package-aws.ps1` → `deploy-eb.zip`.
