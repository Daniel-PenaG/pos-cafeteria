"""Punto de entrada WSGI para Elastic Beanstalk (fallback si no usa Procfile)."""
from app.main import app

application = app
