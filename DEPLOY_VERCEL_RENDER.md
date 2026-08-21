# Despliegue — Vercel + Render + APK

Guía para **Coffe Song** (producción actual).

| Componente | URL |
|------------|-----|
| Frontend | https://pos-cafeteria-brown.vercel.app |
| API | https://pos-cafeteria-api.onrender.com |

---

## 1. Subir código a GitHub

```powershell
cd c:\workspace\pos-cafeteria
git add backend/ frontend/ README.md DOCUMENTACION.md DEPLOY_VERCEL_RENDER.md IMPRESION_TABLET.md
git commit -m "Seguridad API, sesión persistente, gastos, mesas configurables"
git push origin main
```

Vercel redeploya solo si el repo está conectado a `main`.

---

## 2. Render (backend)

Dashboard: [render.com](https://dashboard.render.com) → servicio **pos-cafeteria-api** → **Environment**.

### Variables obligatorias

| Variable | Valor |
|----------|--------|
| `DATABASE_URL` | *(ya configurada — PostgreSQL de Render)* |
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | Clave aleatoria ≥ 32 caracteres (ver abajo) |
| `CORS_ORIGINS` | `https://pos-cafeteria-brown.vercel.app` |

### Generar SECRET_KEY (en tu PC, una sola vez)

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copia el resultado en Render como `SECRET_KEY`. **No lo subas a git.**

### Opcionales

| Variable | Valor |
|----------|--------|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` (8 h) o `1440` (24 h) |
| `ALGORITHM` | `HS256` |

### Redeploy

Render → **Manual Deploy** → **Deploy latest commit**  
(o espera auto-deploy si está ligado a GitHub).

### Verificar

```powershell
curl https://pos-cafeteria-api.onrender.com/health
# {"status":"ok"}
```

Si el servicio falla al arrancar, revisa logs: casi siempre es `SECRET_KEY` débil o falta `ENVIRONMENT=production`.

---

## 3. Vercel (frontend)

Dashboard: [vercel.com](https://vercel.com) → proyecto **pos-cafeteria** → **Settings → Environment Variables**.

| Variable | Valor |
|----------|--------|
| `VITE_API_URL` | `https://pos-cafeteria-api.onrender.com` |

Sin barra final. Aplica a **Production** (y Preview si quieres).

### Redeploy

**Deployments** → último deploy → **Redeploy**  
(o push a `main` si hay integración Git).

---

## 4. APK tablet (Android)

```powershell
cd c:\workspace\pos-cafeteria\frontend

# API de producción (NO uses la URL de Vercel)
copy .env.capacitor.example .env.capacitor.local
# Edita .env.capacitor.local:
# VITE_API_URL=https://pos-cafeteria-api.onrender.com

npm run build:android
npm run cap:open
```

Android Studio → **Build → Build Bundle(s) / APK(s) → Build APK(s)**  
Instala `android/app/build/outputs/apk/debug/app-debug.apk` en la tablet.

---

## 5. Checklist post-deploy

- [ ] Login en web (Vercel) con admin
- [ ] Sesión persiste al refrescar (F5)
- [ ] Ventas muestra **9 mesas**; admin ve **Gestionar mesas**
- [ ] Dashboard capital neto / gastos (hora México)
- [ ] Tablet APK login + venta + ticket Bluetooth

---

## 6. Prioridad media (siguiente iteración)

No incluido en este deploy:

- Alembic (migraciones versionadas)
- Tests pytest + CI frontend
- `DEPLOY` automatizado con GitHub Actions para Render

Ver [DOCUMENTACION.md](DOCUMENTACION.md) sección 5.2.
