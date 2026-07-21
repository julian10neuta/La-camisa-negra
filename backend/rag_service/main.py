# rag_service/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.rag_router import router as rag_router

app = FastAPI(title="RAG Service - La Camisa Negra")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# El router ya trae el prefijo "/rag".
app.include_router(rag_router)


@app.get("/")
def root():
    return {"service": "RAG Service", "status": "running"}
