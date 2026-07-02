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
            # Auto-sanado: si se cacheó sin género (p. ej. importada del login),
            # aprovechamos esta interacción para llenarlo — el motor lo necesita.
            if not song.genres:
                genres = await self.fetch_track_genres(spotify_track_id, access_token)
                if genres:
                    SongRepository.set_genres(self.db, song, genres)
            return song

        track_data = await self.spotify_service.get_track(
            spotify_track_id, access_token
        )
        track_data["genres"] = await self._genres_from_track(track_data, access_token)
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

        # Enriquecer géneros EN LOTE para las nuevas: los géneros viven en el
        # artista, así que pedimos /artists?ids= (hasta 50 por llamada) en vez de
        # una llamada por canción. Antes el sync guardaba sin género y eso dejaba
        # ciego al motor de recomendación sobre la biblioteca del usuario.
        artist_ids = [
            t["artists"][0]["id"]
            for t in new_tracks
            if t.get("artists") and t["artists"][0].get("id")
        ]
        genres_by_artist: dict = {}
        if artist_ids:
            artists = await self.spotify_service.get_artists_batch(
                artist_ids, access_token
            )
            genres_by_artist = {a["id"]: (a.get("genres") or []) for a in artists}

        for track in new_tracks:
            aid = track["artists"][0]["id"] if track.get("artists") else None
            g = genres_by_artist.get(aid, [])
            track["genres"] = ",".join(g) if g else None
            result.append(SongRepository.create_from_spotify_data(self.db, track))

        return result