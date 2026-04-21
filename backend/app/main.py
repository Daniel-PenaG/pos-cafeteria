from fastapi import FastAPI
from app.database import Base, engine
from app.models import models
from app.routers import auth

#Crear tablas automaticamente si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(
    tittle = "POS Cafeteria",
    description="API del sistema de punto de venta",
    version="1.0.0"
)

app.include_router(auth.router)

@app.get("/")
def root():
    return {"message": "POST Cafeteria API funcionando correctamente"}