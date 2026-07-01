# music_service/services/interaction_service.py
from sqlalchemy.orm import Session
from shared.models import Interaction
from ..repositories.interaction_repository import InteractionRepository
from ..repositories.song_repository import SongRepository
from .spotify_service import SpotifyService
from .song_service import SongService


PLAYBACK_THRESHOLD_SECONDS = 30


class InteractionService:

    def __init__(
        self,
        db: Session,
        song_service: SongService,
        spotify_service: SpotifyService,
    ):
        self.db = db
        self.song_service = song_service
        self.spotify_service = spotify_service

    # ─── Likes ───────────────────────────────────────────────────────────────

    async def add_like(
        self,
        user_id: int,
        spotify_track_id: str,
        access_token: str,
    ) -> Interaction:
        """
        Like explícito del usuario — no requiere umbral de 30s.
        1. Asegura que la canción existe en nuestra BD
        2. Evita duplicados
        3. Refleja el like en Spotify (escritura unidireccional)
        """
        song = await self.song_service.get_or_cache(
            spotify_track_id, access_token
        )

        existing = InteractionRepository.get_favorite(
            self.db, user_id, song.id
        )
        if existing:
            return existing  # ya estaba, no duplicamos

        await self.spotify_service.add_to_liked_songs(
            spotify_track_id, access_token
        )

        return InteractionRepository.create(
            self.db, user_id=user_id, song_id=song.id, type="like"
        )

    async def remove_like(
        self,
        user_id: int,
        spotify_track_id: str,
        access_token: str,
    ) -> None:
        song = SongRepository.get_by_spotify_track_id(
            self.db, spotify_track_id
        )
        if not song:
            return  # si no está en nuestra BD, no hay nada que borrar

        interaction = InteractionRepository.get_favorite(
            self.db, user_id, song.id
        )
        if interaction:
            InteractionRepository.delete(self.db, interaction)

        await self.spotify_service.remove_from_liked_songs(
            spotify_track_id, access_token
        )

    def list_likes(self, user_id: int) -> list[Interaction]:
        return InteractionRepository.list_favorites(self.db, user_id)

    # ─── Playback ────────────────────────────────────────────────────────────

    async def register_playback(
        self,
        user_id: int,
        spotify_track_id: str,
        seconds_played: int,
        reached_end: bool,
        was_skipped: bool,
        access_token: str,
    ) -> Interaction | None:
        """
        Registra el resultado de una reproducción.
        Retorna None si no alcanzó el umbral (no se guarda nada).
        """
        interaction_type = self._classify_playback(
            seconds_played, reached_end, was_skipped
        )
        if interaction_type is None:
            return None

        song = await self.song_service.get_or_cache(
            spotify_track_id, access_token
        )

        return InteractionRepository.create(
            self.db,
            user_id=user_id,
            song_id=song.id,
            type=interaction_type,
            time_reproduced=seconds_played,
        )

    def _classify_playback(
        self,
        seconds_played: int,
        reached_end: bool,
        was_skipped: bool,
    ) -> str | None:
        if seconds_played < PLAYBACK_THRESHOLD_SECONDS:
            return None  # ruido, no cuenta

        if reached_end:
            return "play"  # escuchó completa — señal positiva fuerte

        if was_skipped:
            return "skip"  # dio oportunidad (30s+) pero igual la saltó

        return "play"  # pausó/cerró sin terminar, pero superó el umbral

    # ─── Sincronización de Liked Songs al hacer login ─────────────────────────

    async def sync_liked_songs_from_spotify(
        self,
        user_id: int,
        access_token: str,
    ) -> int:
        """
        Importa las Liked Songs del usuario desde Spotify hacia nuestra BD.
        Se llama en cada login — solo agrega, nunca borra (historial inmutable).
        Retorna el número de likes nuevos añadidos.
        """
        tracks_data = await self.spotify_service.get_liked_songs(access_token)
        songs = await self.song_service.get_or_cache_many(
            tracks_data, access_token
        )

        new_likes = 0
        for song in songs:
            existing = InteractionRepository.get_favorite(
                self.db, user_id, song.id
            )
            if not existing:
                InteractionRepository.create(
                    self.db,
                    user_id=user_id,
                    song_id=song.id,
                    type="like",
                )
                new_likes += 1

        return new_likes