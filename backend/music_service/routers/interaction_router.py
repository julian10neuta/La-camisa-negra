# music_service/routers/interactions.py
from fastapi import APIRouter, Header, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..dependencies import get_redis
from shared.database import get_db
from ..services.token_service import TokenService
from ..services.spotify_service import SpotifyService
from ..services.song_service import SongService
from ..services.interaction_service import InteractionService

router = APIRouter(prefix="/interactions", tags=["interactions"])


def get_interaction_service(
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
) -> InteractionService:
    spotify_service = SpotifyService()
    song_service = SongService(db, spotify_service)
    return InteractionService(db, song_service, spotify_service)


# ─── Likes ───────────────────────────────────────────────────────────────────

@router.post("/likes/{spotify_track_id}", status_code=201)
async def add_like(
    spotify_track_id: str,
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    service = get_interaction_service(db, redis)
    token = await TokenService(redis).get_token(x_spotify_id)
    user_id = _get_user_id(db, x_spotify_id)

    await service.add_like(user_id, spotify_track_id, token)
    return {"detail": "like agregado"}


@router.delete("/likes/{spotify_track_id}", status_code=200)
async def remove_like(
    spotify_track_id: str,
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    service = get_interaction_service(db, redis)
    token = await TokenService(redis).get_token(x_spotify_id)
    user_id = _get_user_id(db, x_spotify_id)

    await service.remove_like(user_id, spotify_track_id, token)
    return {"detail": "like eliminado"}


@router.get("/likes")
async def list_likes(
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    service = get_interaction_service(db, redis)
    user_id = _get_user_id(db, x_spotify_id)
    interactions = service.list_likes(user_id)

    return [{"spotify_track_id": i.song.spotify_track_id} for i in interactions]


# ─── Playback ─────────────────────────────────────────────────────────────────

class PlaybackPayload(BaseModel):
    spotify_track_id: str
    seconds_played: int
    reached_end: bool
    was_skipped: bool


@router.post("/playback", status_code=201)
async def register_playback(
    payload: PlaybackPayload,
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    service = get_interaction_service(db, redis)
    token = await TokenService(redis).get_token(x_spotify_id)
    user_id = _get_user_id(db, x_spotify_id)

    result = await service.register_playback(
        user_id=user_id,
        spotify_track_id=payload.spotify_track_id,
        seconds_played=payload.seconds_played,
        reached_end=payload.reached_end,
        was_skipped=payload.was_skipped,
        access_token=token,
    )

    if result is None:
        return {"detail": "reproducción ignorada, no alcanzó el umbral de 30s"}
    return {"detail": "interacción registrada", "type": result.type}


# ─── Sync login ───────────────────────────────────────────────────────────────

@router.post("/sync", status_code=200)
async def sync_liked_songs(
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Se llama desde el frontend justo después del login exitoso.
    Importa las Liked Songs del usuario desde Spotify hacia nuestra BD.
    """
    service = get_interaction_service(db, redis)
    token = await TokenService(redis).get_token(x_spotify_id)
    user_id = _get_user_id(db, x_spotify_id)

    new_likes = await service.sync_liked_songs_from_spotify(user_id, token)
    return {"detail": f"{new_likes} canciones nuevas sincronizadas"}


# ─── Helper interno ───────────────────────────────────────────────────────────

def _get_user_id(db: Session, spotify_id: str) -> int:
    """
    Obtiene el user_id interno a partir del spotify_id inyectado por el gateway.
    Centralizado aquí para no repetir esta lógica en cada endpoint.
    """
    from shared.models import User
    user = db.query(User).filter(User.spotify_id == spotify_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user.id