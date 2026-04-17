from fastapi import FastAPI
app = FastAPI(
    tittle = "POS Cafeteria",
    description="API del sistema de punto de venta",
    version="1.0.0"
)

@app.get("/")
def root():
    return {"message": "POST Cafeteria API funcionando correctamente"}