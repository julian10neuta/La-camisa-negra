# music_service/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.song_router import router as song_router
from .routers.interaction_router import router as interaction_router
from .routers.playlist_router import router as playlist_router

app = FastAPI(title="Music Service - La Camisa Negra")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(song_router, prefix="/music")
app.include_router(interaction_router, prefix="/music")
app.include_router(playlist_router, prefix="/music")


@app.get("/")
def root():
    return {"service": "Music Service", "status": "running"}