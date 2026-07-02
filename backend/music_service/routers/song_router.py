# music_service/routers/songs.py
from fastapi import APIRouter, Header, Query, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends
from ..dependencies import get_redis
from shared.database import get_db
from ..services.token_service import TokenService
from ..services.spotify_service import SpotifyService
from ..services.song_service import SongService

router = APIRouter(prefix="/songs", tags=["songs"])


@router.get("/search")
async def search_songs(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=10),
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    token_service = TokenService(redis)
    spotify_service = SpotifyService()
    song_service = SongService(db, spotify_service)

    access_token = await token_service.get_token(x_spotify_id)
    results = await song_service.search(q, access_token, limit)

    return [{"spotify_track_id": track["id"]} for track in results]