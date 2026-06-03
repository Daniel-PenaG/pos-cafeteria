# Solo si despliegas el ZIP desde la raíz del monorepo (debe existir la carpeta backend/).
web: gunicorn -k uvicorn.workers.UvicornWorker app.main:app --chdir backend --bind 0.0.0.0:8000
