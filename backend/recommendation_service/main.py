# recommendation_service/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.recommendation_router import router as recommendation_router

app = FastAPI(title="Recommendation Service - La Camisa Negra")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# El router ya trae el prefijo "/recommendations".
app.include_router(recommendation_router)


@app.get("/")
def root():
    return {"service": "Recommendation Service", "status": "running"}
