from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importamos el router que contiene la lógica de login y callback
from .routers.auth_router import router as auth_router

app = FastAPI(title="Authentication Service - La Camisa Negra")

# Habilitamos CORS para que tu frontend en React (puerto 5173) 
# pueda hacer peticiones a este servicio sin bloqueos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Conectamos las rutas del router al servicio principal
app.include_router(auth_router, prefix="/auth")

@app.get("/")
def root():
    return {"service": "Authentication Service", "status": "running"}