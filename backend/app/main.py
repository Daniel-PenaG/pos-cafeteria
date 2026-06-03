from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine, aplicar_migraciones_sqlite
from app.models import models
from app.routers import auth, productos, recetas, ventas, reportes, compras, configuracion, extras_venta

app = FastAPI(
    title="POS Cafetería",
    description="API del sistema de punto de venta",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
aplicar_migraciones_sqlite()


app.include_router(auth.router)
app.include_router(productos.router)
app.include_router(recetas.router)
app.include_router(ventas.router)
app.include_router(reportes.router)
app.include_router(compras.router)
app.include_router(configuracion.router)
app.include_router(extras_venta.router)


@app.get("/")
def root():
    return {"message": "POS Cafetería API funcionando"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
