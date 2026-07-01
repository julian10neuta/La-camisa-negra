# music_service/repositories/recommendation_playlist_repository.py
from datetime import datetime
from sqlalchemy.orm import Session
from shared.models import RecommendationPlaylist


class RecommendationPlaylistRepository:

    @staticmethod
    def get_by_user_and_period(
        db: Session,
        user_id: int,
        period_type: str,
    ) -> RecommendationPlaylist | None:
        """
        Busca la playlist de recomendación de un usuario para un período dado.
        period_type: "weekly" | "monthly"
        """
        return (
            db.query(RecommendationPlaylist)
            .filter_by(user_id=user_id, period_type=period_type)
            .first()
        )

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        spotify_playlist_id: str,
        period_type: str,
    ) -> RecommendationPlaylist:
        """
        Crea el registro la primera vez que se genera la playlist
        de recomendación para este usuario y período.
        """
        playlist = RecommendationPlaylist(
            user_id=user_id,
            spotify_playlist_id=spotify_playlist_id,
            period_type=period_type,
            last_updated=datetime.utcnow(),
        )
        db.add(playlist)
        db.commit()
        db.refresh(playlist)
        return playlist

    @staticmethod
    def update(
        db: Session,
        playlist: RecommendationPlaylist,
        spotify_playlist_id: str | None = None,
    ) -> RecommendationPlaylist:
        """
        Actualiza la playlist cuando el recommendation_service regenera
        las recomendaciones semanales/mensuales.
        spotify_playlist_id es opcional porque normalmente la playlist
        ya existe en Spotify y solo cambia su contenido — no su ID.
        Solo se actualiza si el ID cambió (ej. el usuario la borró y
        el sistema tuvo que crearla de nuevo).
        """
        if spotify_playlist_id:
            playlist.spotify_playlist_id = spotify_playlist_id
        playlist.last_updated = datetime.utcnow()
        db.commit()
        db.refresh(playlist)
        return playlist

    @staticmethod
    def get_or_create(
        db: Session,
        user_id: int,
        spotify_playlist_id: str,
        period_type: str,
    ) -> tuple[RecommendationPlaylist, bool]:
        """
        Devuelve (playlist, created) — el bool indica si fue creada ahora
        o ya existía. Útil para que el recommendation_service no tenga
        que hacer get + create en dos pasos separados.
        """
        existing = RecommendationPlaylistRepository.get_by_user_and_period(
            db, user_id, period_type
        )
        if existing:
            return existing, False

        created = RecommendationPlaylistRepository.create(
            db, user_id, spotify_playlist_id, period_type
        )
        return created, True