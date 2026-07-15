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
    read_cached,
    serialize_track,
    write_cached,
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
    Devuelve las recomendaciones que el usuario YA tiene. **Nunca regenera.**

    Antes, si la lista había caducado, esta ruta lanzaba una regeneración: una
    ráfaga de 30-50 llamadas a Spotify. Y como la lee el Home —la pantalla de
    entrada de la app— bastaba con abrir la app para dispararla. Fue una de las
    causas del segundo baneo por rate limit. Regenerar es caro y lento (~17s), así
    que ahora es un acto explícito: POST /refresh, que el frontend ofrece con un
    botón cuando la respuesta viene marcada como `stale`.

    Coste en llamadas a Spotify:
      - lista en caché  -> CERO (el caso normal)
      - caché fría      -> UNA (se rellena la caché y las siguientes son cero)
      - sin playlist    -> CERO
    """
    user_id = _get_user_id(db, x_spotify_id)
    pl = RecommendationPlaylistRepository.get_by_user_and_period(db, user_id, period)

    if not pl or not pl.last_updated:
        # Nunca se ha generado. Que el usuario lo pida cuando quiera.
        return build_response(
            tracks=[], playlist_id=None, period=period,
            last_updated=None, generated=False, stale=True,
        )

    stale_after = period_config(period)["stale_after"]
    caducada = (datetime.utcnow() - pl.last_updated) >= stale_after

    # 1) La caché: las canciones tal cual se generaron. Cero llamadas.
    cached = read_cached(redis, user_id, period)
    tracks = cached["tracks"] if cached else None

    # 2) Caché fría (Redis reiniciado, o lista generada antes de que existiera
    #    esta caché): se paga UNA llamada, y se rellena para no repetirla.
    if tracks is None:
        try:
            token = await TokenService(redis).get_token(x_spotify_id)
            tracks_raw = await SpotifyService().get_playlist_tracks(
                pl.spotify_playlist_id, token
            )
            tracks = [serialize_track(t) for t in tracks_raw if t.get("id")]
            write_cached(redis, user_id, period, tracks, pl.spotify_playlist_id, pl.last_updated)
        except Exception:
            # Spotify caído o limitándonos: mejor una lista vacía marcada como
            # "hay que actualizar" que un error en la cara del usuario.
            tracks = []

    # Si el usuario subió el número en Ajustes, la lista guardada se queda corta:
    # se sirve lo que hay y se marca para que ofrezca actualizar. Antes esto
    # regeneraba en el acto, sin avisar.
    corta = len(tracks) < limit

    return build_response(
        tracks=tracks[:limit],
        playlist_id=pl.spotify_playlist_id,
        period=period,
        last_updated=pl.last_updated,
        generated=False,
        stale=caducada or corta or not tracks,
    )


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
