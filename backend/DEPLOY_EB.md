# Despliegue en AWS Elastic Beanstalk

## Estructura correcta del ZIP

Elastic Beanstalk exige que en la **raíz del ZIP** estén `Procfile`, `requirements.txt` y el código Python.

### Opción recomendada (solo API)

Empaqueta el contenido de `backend/`, no la carpeta padre:

```powershell
cd backend
Compress-Archive -Path app, Procfile, requirements.txt, application.py, .ebextensions -DestinationPath ..\deploy-eb.zip -Force
```

El ZIP debe verse así:

```
Procfile
requirements.txt
application.py
app/
  main.py
  ...
.ebextensions/
```

**No** uses `--chdir backend` en el Procfile de esta opción (ya está corregido).

### Opción monorepo (raíz del repositorio)

Si subes todo el repo, usa el `Procfile` de la raíz del proyecto (incluye `--chdir backend`) y `requirements.txt` con `-r backend/requirements.txt`.

Asegúrate de que la carpeta `backend/` exista dentro del ZIP.

## Comandos

```bash
eb deploy
```

## Variables de entorno en EB

Configura en la consola o con `eb setenv`:

- `DATABASE_URL` — PostgreSQL
- `SECRET_KEY`
- `ALGORITHM` — ej. HS256
- `ACCESS_TOKEN_EXPIRE_MINUTES` — ej. 30

## Error "can't chdir to 'backend'"

Ocurre cuando el Procfile hace `cd backend` pero el ZIP no contiene esa carpeta (solo el contenido plano de `backend/`). Solución: usar el Procfile dentro de `backend/` sin `--chdir`, y empaquetar desde `cd backend` como arriba.
