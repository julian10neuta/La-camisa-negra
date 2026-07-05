# recommendation_service/repositories/recommendation_playlist_repo.py
# CRUD sobre RecommendationPlaylist (la playlist real de Spotify por usuario y
# período). Se movió aquí desde music_service: pertenece al recommendation_service,
# que es quien la consume.
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
        Marca la playlist como regenerada (actualiza last_updated). Solo cambia el
        spotify_playlist_id si se pasa (p. ej. si el usuario borró la playlist en
        Spotify y hubo que crearla de nuevo).
        """
        if spotify_playlist_id:
            playlist.spotify_playlist_id = spotify_playlist_id
        playlist.last_updated = datetime.utcnow()
        db.commit()
        db.refresh(playlist)
        return playlist
