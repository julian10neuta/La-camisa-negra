# recommendation_service/routers/recommendation_router.py
from datetime import datetime, timedelta
from fastapi import APIRouter, Header, Depends, HTTPException
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.models import User
from shared.spotify_service import SpotifyService
from shared.token_service import TokenService
from ..dependencies import get_redis
from ..repositories.recommendation_playlist_repo import RecommendationPlaylistRepository
from ..services.engine import RecommendationEngine, serialize_track, PERIOD

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

# Cada cuánto se regenera. Si la playlist es más nueva que esto, se devuelve tal
# cual (sin volver a llamar a Spotify para recalcular).
STALE_AFTER = timedelta(days=7)


def _get_user_id(db: Session, spotify_id: str) -> int:
    user = db.query(User).filter(User.spotify_id == spotify_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user.id


@router.get("/list")
async def get_recommendations(
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Devuelve las recomendaciones del usuario. Si ya existe una playlist reciente
    (< STALE_AFTER), devuelve su contenido sin regenerar; si no, la genera.
    """
    user_id = _get_user_id(db, x_spotify_id)
    token = await TokenService(redis).get_token(x_spotify_id)

    pl = RecommendationPlaylistRepository.get_by_user_and_period(db, user_id, PERIOD)
    if pl and pl.last_updated and (datetime.utcnow() - pl.last_updated) < STALE_AFTER:
        try:
            tracks_raw = await SpotifyService().get_playlist_tracks(
                pl.spotify_playlist_id, token
            )
            tracks = [serialize_track(t) for t in tracks_raw if t.get("id")]
            if tracks:
                return {
                    "tracks": tracks,
                    "playlist_id": pl.spotify_playlist_id,
                    "playlist_url": f"https://open.spotify.com/playlist/{pl.spotify_playlist_id}",
                    "generated": False,
                }
        except Exception:
            pass  # si la playlist ya no existe en Spotify, caemos a regenerar

    engine = RecommendationEngine(db, redis)
    return await engine.generate(user_id, token)


@router.post("/refresh")
async def refresh_recommendations(
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    """Fuerza la regeneración de las recomendaciones."""
    user_id = _get_user_id(db, x_spotify_id)
    token = await TokenService(redis).get_token(x_spotify_id)
    engine = RecommendationEngine(db, redis)
    return await engine.generate(user_id, token)
