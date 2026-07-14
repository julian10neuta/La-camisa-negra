# music_service/routers/interactions.py
from datetime import datetime, timedelta
from fastapi import APIRouter, Header, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..dependencies import get_redis
from shared.database import get_db
from shared.token_service import TokenService
from shared.spotify_service import SpotifyService
from ..services.song_service import SongService
from ..services.interaction_service import InteractionService
from ..repositories.interaction_repository import InteractionRepository

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
    user_id = _get_user_id(db, x_spotify_id)
    results = InteractionRepository.list_favorites(db, user_id)
    return [{"spotify_track_id": song.spotify_track_id} for _, song in results]


# ─── Dislikes ──────────────────────────────────────────────────────────────────

@router.post("/dislikes/{spotify_track_id}", status_code=201)
async def add_dislike(
    spotify_track_id: str,
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    service = get_interaction_service(db, redis)
    token = await TokenService(redis).get_token(x_spotify_id)
    user_id = _get_user_id(db, x_spotify_id)

    await service.add_dislike(user_id, spotify_track_id, token)
    return {"detail": "dislike agregado"}


@router.delete("/dislikes/{spotify_track_id}", status_code=200)
async def remove_dislike(
    spotify_track_id: str,
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    service = get_interaction_service(db, redis)
    user_id = _get_user_id(db, x_spotify_id)

    service.remove_dislike(user_id, spotify_track_id)
    return {"detail": "dislike eliminado"}


@router.get("/dislikes")
async def list_dislikes(
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    user_id = _get_user_id(db, x_spotify_id)
    results = InteractionRepository.list_by_type(db, user_id, "dislike")
    return [{"spotify_track_id": song.spotify_track_id} for _, song in results]


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
        return {"detail": "reproducción ignorada, demasiado corta"}
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


# ─── Historial y estadísticas (Home) ──────────────────────────────────────────

@router.get("/history")
async def recent_plays(
    limit: int = Query(8, ge=1, le=50),
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
):
    """
    "Sigue escuchando": las últimas canciones reproducidas, sin repetidos.

    Devuelve la misma forma que las recomendaciones (spotify_track_id, name,
    artist, album, cover_url, duration_ms) para que el reproductor pueda
    consumirlas igual, más `last_played`.

    **Cero llamadas a Spotify.** Sale entero de nuestra base.

    Antes esto pedía la carátula de cada canción a Spotify y la cacheaba en Redis
    (un helper _track_meta de ~40 líneas), porque `Song` no guardaba ni álbum ni
    portada. Era una ráfaga de hasta 8 llamadas por visita al Home — la pantalla de
    entrada de la app — y contribuyó al segundo baneo. Ahora las columnas existen y
    se rellenan al cachear la canción, con el dato que Spotify ya nos había dado.
    Ver la migración b1c4e7d9f2a3.
    """
    user_id = _get_user_id(db, x_spotify_id)
    rows = InteractionRepository.get_recent_plays(db, user_id, limit)

    return [
        {
            "spotify_track_id": song.spotify_track_id,
            "name": song.name,
            "artist": song.artist,
            "album": song.album,
            "cover_url": song.cover_url,
            "duration_ms": song.duration_ms,
            "last_played": last_played.isoformat() if last_played else None,
        }
        for song, last_played in rows
    ]


@router.get("/top")
async def top_of_window(
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(5, ge=1, le=20),
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
):
    """
    Los tres rankings del Dashboard para una ventana de tiempo: canciones,
    artistas y álbumes más escuchados. El diseño pide 24h y 7 días, que aquí son
    `days=1` y `days=7`.

    Van los tres en una sola respuesta a propósito: el Dashboard los pinta juntos,
    siempre de la misma ventana. Tres endpoints separados serían tres viajes para
    montar una pantalla que es una.

    **Cero llamadas a Spotify.** Sale entero de nuestra base — incluidas las
    carátulas, desde que Song las guarda (ver migración b1c4e7d9f2a3).
    """
    user_id = _get_user_id(db, x_spotify_id)
    since = datetime.utcnow() - timedelta(days=days)

    songs = InteractionRepository.get_top_songs(db, user_id, since, limit)

    return {
        "days": days,
        "since": since.isoformat(),
        "songs": [
            {
                "spotify_track_id": s.spotify_track_id,
                "name": s.name,
                "artist": s.artist,
                "album": s.album,
                "cover_url": s.cover_url,
                "duration_ms": s.duration_ms,
                "plays": int(plays),
            }
            for s, plays in songs
        ],
        "artists": InteractionRepository.get_top_artists(db, user_id, since, limit),
        "albums": InteractionRepository.get_top_albums(db, user_id, since, limit),
    }


@router.get("/stats")
async def listening_stats(
    days: int = Query(7, ge=1, le=365),
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
):
    """
    "Tu semana en Wavely": cuántas canciones escuchó el usuario, cuánto tiempo y
    quién fue su artista más escuchado en los últimos `days` días.

    Todo sale de nuestra propia base de datos: cero llamadas a Spotify.
    """
    user_id = _get_user_id(db, x_spotify_id)
    since = datetime.utcnow() - timedelta(days=days)
    stats = InteractionRepository.get_stats(db, user_id, since)
    return {**stats, "days": days, "since": since.isoformat()}


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