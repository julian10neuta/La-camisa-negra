# music_service/services/song_service.py
from sqlalchemy.orm import Session
from shared.models import Song
from ..repositories.song_repository import SongRepository
from .spotify_service import SpotifyService


class SongService:

    def __init__(self, db: Session, spotify_service: SpotifyService):
        self.db = db
        self.spotify_service = spotify_service

    async def search(self, query: str, access_token: str, limit:int=20) -> list[dict]:
        """
        Busca canciones en Spotify. No cachea los resultados de búsqueda
        en nuestra BD — solo cacheamos canciones cuando se registra
        una Interaction (ahí sí necesitamos un song_id interno).
        """
        return await self.spotify_service.search_tracks(query, access_token, limit)

    async def get_or_cache(
        self,
        spotify_track_id: str,
        access_token: str,
    ) -> Song:
        """
        Si la canción ya está en nuestra BD, la devuelve directo.
        Si no, la pide a Spotify, la guarda, y la devuelve.

        Este método es el que garantiza que siempre tengamos un song_id
        interno antes de crear cualquier Interaction.
        """
        song = SongRepository.get_by_spotify_track_id(self.db, spotify_track_id)
        if song:
            return song

        track_data = await self.spotify_service.get_track(
            spotify_track_id, access_token
        )

        # Intentamos obtener genres del artista (viven en el artista, no en el track)
        genres = None
        if track_data.get("artists"):
            artist_id = track_data["artists"][0]["id"]
            artist_data = await self.spotify_service.get_artist(
                artist_id, access_token
            )
            genres = ",".join(artist_data.get("genres", []))

        track_data["genres"] = genres
        return SongRepository.create_from_spotify_data(self.db, track_data)

    async def get_or_cache_many(
        self,
        tracks_data: list[dict],
        access_token: str,
    ) -> list[Song]:
        """
        Versión batch de get_or_cache — para la importación de Liked Songs
        donde procesamos muchas canciones de una vez.
        Minimiza llamadas a la BD usando get_many_by_spotify_track_ids.
        """
        spotify_ids = [t["id"] for t in tracks_data]
        existing = SongRepository.get_many_by_spotify_track_ids(
            self.db, spotify_ids
        )
        existing_map = {s.spotify_track_id: s for s in existing}

        result = list(existing)

        for track in tracks_data:
            if track["id"] not in existing_map:
                # genres en batch: usamos lo que venga en el track_data
                # (la importación de liked songs no trae genres del artista,
                # se puede enriquecer después como optimización)
                song = SongRepository.create_from_spotify_data(self.db, track)
                result.append(song)

        return result