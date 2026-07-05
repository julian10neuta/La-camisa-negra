# music_service/routers/songs.py
from fastapi import APIRouter, Header, Query, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends
from ..dependencies import get_redis
from shared.database import get_db
from shared.token_service import TokenService
from shared.spotify_service import SpotifyService
from ..services.song_service import SongService
from ..repositories.song_repository import SongRepository

router = APIRouter(prefix="/songs", tags=["songs"])


def _serialize_track(track: dict) -> dict:
    """
    Aplana el objeto crudo de Spotify a solo los campos que el frontend
    necesita para pintar un resultado de búsqueda (diseño de la pantalla
    Search): carátula, título, artista, álbum y duración.

    Todos estos campos son metadata básica de catálogo que Spotify sigue
    entregando en /v1/search — NO son las 'audio features' restringidas
    desde nov-2024. No se persisten: se devuelven en vivo tal como llegan.
    """
    artists = track.get("artists") or []
    album = track.get("album") or {}
    images = album.get("images") or []

    return {
        "spotify_track_id": track["id"],
        "name": track.get("name", "Unknown"),
        "artist": artists[0]["name"] if artists else "Unknown",
        "album": album.get("name"),
        # images viene ordenado de mayor a menor; la primera es la de más resolución
        "cover_url": images[0]["url"] if images else None,
        "duration_ms": track.get("duration_ms"),
    }


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

    return [_serialize_track(track) for track in results]


@router.post("/refresh-genres")
async def refresh_genres(
    x_spotify_id: str = Header(...),
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Mantenimiento: rellena el género de las canciones que se cachearon sin él
    (típicamente las importadas del login antes de este arreglo). Se puede
    llamar una vez para "sanar" la biblioteca existente. Enriquece de a una
    (las nuevas ya se enriquecen solas al interactuar o en el sync por lote).
    """
    token = await TokenService(redis).get_token(x_spotify_id)
    song_service = SongService(db, SpotifyService())

    pending = SongRepository.get_missing_genres(db)
    updated = 0
    for song in pending:
        genres = await song_service.fetch_track_genres(song.spotify_track_id, token)
        if genres:
            SongRepository.set_genres(db, song, genres)
            updated += 1

    return {"detail": f"{updated} canciones enriquecidas", "revisadas": len(pending)}