# music_service/services/song_service.py
from sqlalchemy.orm import Session
from shared.models import Song
from ..repositories.song_repository import SongRepository
from shared.spotify_service import SpotifyService


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

    async def _genres_from_track(
        self,
        track_data: dict,
        access_token: str,
    ) -> str | None:
        """Los géneros viven en el artista, no en el track. Devuelve string o None."""
        artists = track_data.get("artists") or []
        if not artists or not artists[0].get("id"):
            return None
        artist_data = await self.spotify_service.get_artist(
            artists[0]["id"], access_token
        )
        genres = artist_data.get("genres") or []
        return ",".join(genres) if genres else None

    async def fetch_track_genres(
        self,
        spotify_track_id: str,
        access_token: str,
    ) -> str | None:
        """Consulta a Spotify los géneros de una canción dada por su id."""
        track_data = await self.spotify_service.get_track(
            spotify_track_id, access_token
        )
        return await self._genres_from_track(track_data, access_token)

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

        # No pedimos géneros a Spotify: los devuelve vacíos para esta app (por eso
        # el motor usa Deezer). Guardar sin género evita una llamada inútil por
        # canción. El enriquecimiento manual sigue en POST /music/songs/refresh-genres.
        track_data = await self.spotify_service.get_track(
            spotify_track_id, access_token
        )
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

        new_tracks = [t for t in tracks_data if t["id"] not in existing_map]

        # No pedimos géneros a Spotify: los devuelve vacíos para esta app (el motor
        # usa Deezer). Antes esto hacía una tanda de /artists?ids= por cada import;
        # eran llamadas puro desperdicio que sumaban al rate limit. Guardamos sin
        # género (la columna queda inerte; el motor no depende de ella).
        for track in new_tracks:
            result.append(SongRepository.create_from_spotify_data(self.db, track))

        return result