# dashboard_service/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.dashboard_router import router as dashboard_router

app = FastAPI(title="Dashboard Service - La Camisa Negra")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# El router ya trae el prefijo "/dashboard".
app.include_router(dashboard_router)


@app.get("/")
def root():
    return {"service": "Dashboard Service", "status": "running"}
