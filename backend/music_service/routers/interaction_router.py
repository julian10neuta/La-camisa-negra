# music_service/routers/interactions.py
import json
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

# 30 días: la carátula y el álbum de una canción no cambian. El mismo TTL que usa
# el motor para su caché de emparejados (recommendation_service/services/engine.py).
TRACK_META_TTL = 60 * 60 * 24 * 30


async def _track_meta(redis, spotify_ids: list[str], token: str) -> dict[str, dict]:
    """
    Carátula y álbum de cada canción, cacheados en Redis.

    Por qué de una en una y no en lote: **GET /tracks?ids= devuelve 403** para
    esta app (probado el 2026-07-14 con token real) — otra de las restricciones de
    Spotify de 2024. Solo funciona /tracks/{id}, individual.

    Y por qué la caché no es opcional: sin ella, cada visita al Home dispararía una
    ráfaga de llamadas, que es exactamente lo que hizo que banearan la app (ver
    Explicacion/09). Con ella, una canción se pregunta una vez cada 30 días. La
    clave es global (no por usuario) porque la carátula de una canción es la misma
    para todo el mundo.
    """
    out: dict[str, dict] = {}
    missing: list[str] = []

    for tid in spotify_ids:
        cached = redis.get(f"spotify:track_meta:{tid}")
        if cached is not None:
            out[tid] = json.loads(cached)
        else:
            missing.append(tid)

    if missing:
        spotify = SpotifyService()
        for tid in missing:
            try:
                track = await spotify.get_track(tid, token)
            except Exception:
                continue  # esta canción se queda sin carátula; las demás no sufren
            album = track.get("album") or {}
            images = album.get("images") or []
            meta = {
                "album": album.get("name"),
                "cover_url": images[0]["url"] if images else None,
            }
            redis.setex(f"spotify:track_meta:{tid}", TRACK_META_TTL, json.dumps(meta))
            out[tid] = meta

    return out


@router.get("/history")
async def recent_plays(
    limit: int = Query(8, ge=1, le=50),
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    "Sigue escuchando": las últimas canciones reproducidas, sin repetidos.

    Devuelve la misma forma que las recomendaciones (spotify_track_id, name,
    artist, album, cover_url, duration_ms) para que el reproductor pueda
    consumirlas igual, más `last_played`.

    La carátula y el álbum NO están en nuestra tabla `Song` (ver shared/models.py),
    así que se piden a Spotify y se cachean. Si Spotify falla, se devuelve lo local
    sin carátula en vez de romper el Home: la portada es decoración, no vale la
    pena tumbar la pantalla por ella.
    """
    user_id = _get_user_id(db, x_spotify_id)
    rows = InteractionRepository.get_recent_plays(db, user_id, limit)
    if not rows:
        return []

    meta: dict = {}
    try:
        token = await TokenService(redis).get_token(x_spotify_id)
        meta = await _track_meta(redis, [s.spotify_track_id for s, _ in rows], token)
    except Exception:
        pass  # sin token no hay carátulas, pero el historial se devuelve igual

    result = []
    for song, last_played in rows:
        m = meta.get(song.spotify_track_id) or {}
        result.append({
            "spotify_track_id": song.spotify_track_id,
            "name": song.name,
            "artist": song.artist,
            "album": m.get("album"),
            "cover_url": m.get("cover_url"),
            "duration_ms": song.duration_ms,
            "last_played": last_played.isoformat() if last_played else None,
        })
    return result


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