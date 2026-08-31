from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.utils.config import get_cors_origins
from app.database import Base, engine, aplicar_migraciones_sqlite, ensure_cierres_caja_table, crear_admin_inicial_si_vacio, crear_catalogo_demo_si_vacio, crear_promocion_lunes_malteadas_si_ausente
from app.models import models
from app.routers import auth, productos, recetas, ventas, reportes, compras, configuracion, extras_venta, promociones, clientes, pedidos, comandera, usuarios, gastos, cierres

app = FastAPI(
    title="POS Cafetería",
    description="API del sistema de punto de venta",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
aplicar_migraciones_sqlite()
ensure_cierres_caja_table()
crear_admin_inicial_si_vacio()
crear_catalogo_demo_si_vacio()
crear_promocion_lunes_malteadas_si_ausente()


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
app.include_router(gastos.router)
app.include_router(cierres.router)


@app.get("/")
def root():
    return {"message": "POS Cafetería API funcionando"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
