# music_service/routers/playlists.py
from backend.music_service.serializers import song_serializer
from fastapi import APIRouter, Header, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..dependencies import get_redis
from shared.database import get_db
from shared.token_service import TokenService
from shared.spotify_service import SpotifyService

router = APIRouter(prefix="/playlists", tags=["playlists"])


def _spotify_service() -> SpotifyService:
    return SpotifyService()


@router.get("")
async def list_playlists(
    x_spotify_id: str = Header(...),
    redis=Depends(get_redis),
):
    token = await TokenService(redis).get_token(x_spotify_id)
    playlists = await _spotify_service().get_user_playlists(token)

    owned_playlists = [
        {"id": p["id"], "name": p["name"]}
        for p in playlists
        if p.get("owner", {}).get("id") == x_spotify_id
    ]
    return owned_playlists


@router.get("/{playlist_id}/tracks")
async def get_playlist_tracks(
    playlist_id: str,
    x_spotify_id: str = Header(...),
    redis=Depends(get_redis),
):
    token = await TokenService(redis).get_token(x_spotify_id)
    tracks = await _spotify_service().get_playlist_tracks(playlist_id, token)
    return [song_serializer(track) for track in tracks]

class CreatePlaylistPayload(BaseModel):
    name: str
    description: str = ""
    public: bool = False


@router.post("", status_code=201)
async def create_playlist(
    payload: CreatePlaylistPayload,
    x_spotify_id: str = Header(...),
    redis=Depends(get_redis),
):
    token = await TokenService(redis).get_token(x_spotify_id)
    playlist = await _spotify_service().create_playlist(
    name=payload.name,
    description=payload.description,
    access_token=token,
    public=payload.public,
    )
    return {"id": playlist["id"], "name": playlist["name"]}


class TracksPayload(BaseModel):
    track_ids: list[str]


@router.post("/{playlist_id}/tracks", status_code=201)
async def add_tracks(
    playlist_id: str,
    payload: TracksPayload,
    x_spotify_id: str = Header(...),
    redis=Depends(get_redis),
):
    token = await TokenService(redis).get_token(x_spotify_id)
    await _spotify_service().add_tracks_to_playlist(
        playlist_id, payload.track_ids, token
    )
    return {"detail": f"{len(payload.track_ids)} canciones agregadas"}


@router.delete("/{playlist_id}/tracks", status_code=200)
async def remove_tracks(
    playlist_id: str,
    payload: TracksPayload,
    x_spotify_id: str = Header(...),
    redis=Depends(get_redis),
):
    token = await TokenService(redis).get_token(x_spotify_id)
    await _spotify_service().remove_tracks_from_playlist(
        playlist_id, payload.track_ids, token
    )
    return {"detail": f"{len(payload.track_ids)} canciones eliminadas"}


@router.delete("/{playlist_id}", status_code=200)
async def remove_playlist(
    playlist_id: str,
    x_spotify_id: str = Header(...),
    redis=Depends(get_redis),
):
    token = await TokenService(redis).get_token(x_spotify_id)
    await _spotify_service().remove_playlist_from_library(playlist_id, token)
    return {"detail": "playlist eliminada de la biblioteca"}