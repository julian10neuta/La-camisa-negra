# recommendation_service/routers/recommendation_router.py
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Header, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.database import get_db
from shared.models import User
from shared.spotify_service import SpotifyService
from shared.token_service import TokenService
from ..dependencies import get_redis
from ..repositories.recommendation_playlist_repo import RecommendationPlaylistRepository
from ..services.engine import (
    RecommendationEngine,
    build_response,
    period_config,
    serialize_track,
    DEFAULT_PERIOD,
    MAX_RECOMMENDATIONS,
    MIN_RECOMMENDATIONS,
    N_RECOMMENDATIONS,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

# Cada cuánto se regenera ya NO es una constante: depende del período que el
# usuario haya elegido (7 días si es semanal, 30 si es mensual). Vive en
# engine.PERIODS.

# El período llega como query param y lo valida FastAPI contra este Literal: un
# valor raro devuelve 422 solo, sin que tengamos que comprobarlo a mano.
PeriodParam = Literal["weekly", "monthly"]


def _get_user_id(db: Session, spotify_id: str) -> int:
    user = db.query(User).filter(User.spotify_id == spotify_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user.id


@router.get("/list")
async def get_recommendations(
    period: PeriodParam = DEFAULT_PERIOD,
    limit: int = Query(
        N_RECOMMENDATIONS, ge=MIN_RECOMMENDATIONS, le=MAX_RECOMMENDATIONS
    ),
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Devuelve las recomendaciones del usuario para el período pedido. Si ya existe
    una playlist reciente (según la caducidad de ESE período) devuelve su
    contenido sin regenerar; si no, la genera.
    """
    user_id = _get_user_id(db, x_spotify_id)
    token = await TokenService(redis).get_token(x_spotify_id)

    pl = RecommendationPlaylistRepository.get_by_user_and_period(db, user_id, period)
    stale_after = period_config(period)["stale_after"]

    if pl and pl.last_updated and (datetime.utcnow() - pl.last_updated) < stale_after:
        try:
            tracks_raw = await SpotifyService().get_playlist_tracks(
                pl.spotify_playlist_id, token
            )
            tracks = [serialize_track(t) for t in tracks_raw if t.get("id")]
            # Si la lista guardada tiene AL MENOS lo que se pide, se sirve tal
            # cual (recortada). Si el usuario subió el número en Ajustes y la
            # guardada se queda corta, caemos a regenerar: pedir más y recibir
            # menos en silencio sería peor que esperar unos segundos.
            if tracks and len(tracks) >= limit:
                return build_response(
                    tracks=tracks[:limit],
                    playlist_id=pl.spotify_playlist_id,
                    period=period,
                    last_updated=pl.last_updated,
                    generated=False,
                )
        except Exception:
            pass  # si la playlist ya no existe en Spotify, caemos a regenerar

    engine = RecommendationEngine(db, redis)
    return await engine.generate(user_id, token, period=period, limit=limit)


@router.post("/refresh")
async def refresh_recommendations(
    period: PeriodParam = DEFAULT_PERIOD,
    limit: int = Query(
        N_RECOMMENDATIONS, ge=MIN_RECOMMENDATIONS, le=MAX_RECOMMENDATIONS
    ),
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    """Fuerza la regeneración de las recomendaciones del período pedido."""
    user_id = _get_user_id(db, x_spotify_id)
    token = await TokenService(redis).get_token(x_spotify_id)
    engine = RecommendationEngine(db, redis)
    return await engine.generate(user_id, token, period=period, limit=limit)
