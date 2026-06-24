#!/bin/bash
# Respaldo: sobrescribe Procfile antes de arrancar la app
set -e
PROCFILE="/var/app/staging/Procfile"
printf '%s\n' 'web: gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000 --workers 2 --timeout 120' > "$PROCFILE"
chmod 644 "$PROCFILE"
echo "Procfile aplicado:"
cat "$PROCFILE"
