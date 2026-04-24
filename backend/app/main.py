from fastapi import FastAPI
from app.database import Base, engine
from app.models import models
from app.routers import auth, productos

app = FastAPI(
    title="POS Cafetería",
    description="API del sistema de punto de venta",
    version="1.0.0"
)

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(productos.router)

@app.get("/")
def root():
    return {"message": "POS Cafetería API funcionando"}
