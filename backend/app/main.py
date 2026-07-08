from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from app.database import Base, engine, aplicar_migraciones_sqlite
from app.models import models
from app.routers import auth, productos, recetas, ventas, reportes, compras, configuracion, extras_venta, promociones, clientes, pedidos, comandera, usuarios

app = FastAPI(
    title="POS Cafetería",
    description="API del sistema de punto de venta",
    version="1.0.0"
)

# JWT va en header Authorization; no hace falta allow_credentials=True.
# Con credentials=True el navegador rechaza allow_origins=["*"].
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*").strip()
if _raw_origins == "*":
    _cors_origins = ["*"]
    _cors_credentials = False
else:
    _cors_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    _cors_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
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
app.include_router(promociones.router)
app.include_router(clientes.router)
app.include_router(pedidos.router)
app.include_router(comandera.router)
app.include_router(usuarios.router)


@app.get("/")
def root():
    return {"message": "POS Cafetería API funcionando"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
