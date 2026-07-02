# music_service/repositories/interaction_repository.py
from datetime import datetime
from sqlalchemy.orm import Session
from shared.models import Interaction


class InteractionRepository:

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        song_id: int,
        type: str,
        time_reproduced: int | None = None,
    ) -> Interaction:
        interaction = Interaction(
            user_id=user_id,
            song_id=song_id,
            type=type,
            date=datetime.utcnow(),
            time_reproduced=time_reproduced,
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        return interaction

    @staticmethod
    def get_favorite(db: Session, user_id: int, song_id: int) -> Interaction | None:
        return (
            db.query(Interaction)
            .filter_by(user_id=user_id, song_id=song_id, type="like")
            .first()
        )

    @staticmethod
    def get_by_type(
        db: Session,
        user_id: int,
        song_id: int,
        type: str,
    ) -> Interaction | None:
        """Versión genérica de get_favorite para cualquier tipo (like/dislike/...)."""
        return (
            db.query(Interaction)
            .filter_by(user_id=user_id, song_id=song_id, type=type)
            .first()
        )

    @staticmethod
    def list_by_type(db: Session, user_id: int, type: str) -> list[tuple]:
        """Devuelve tuplas (Interaction, Song) del tipo dado (p. ej. 'dislike')."""
        from shared.models import Song
        return (
            db.query(Interaction, Song)
            .join(Song, Interaction.song_id == Song.id)
            .filter(Interaction.user_id == user_id, Interaction.type == type)
            .order_by(Interaction.date.desc())
            .all()
        )

    @staticmethod
    def list_favorites(db: Session, user_id: int) -> list[tuple]:
        """
        Devuelve tuplas (Interaction, Song) para evitar N+1 queries
        y el problema de acceder a song desde interaction sin relationship.
        """
        from shared.models import Song
        return (
            db.query(Interaction, Song)
            .join(Song, Interaction.song_id == Song.id)
            .filter(Interaction.user_id == user_id, Interaction.type == "like")
            .order_by(Interaction.date.desc())
            .all()
        )

    @staticmethod
    def delete(db: Session, interaction: Interaction) -> None:
        db.delete(interaction)
        db.commit()

    @staticmethod
    def get_song_ids_interacted(
        db: Session,
        user_id: int,
        types: list[str],
    ) -> list[int]:
        """
        Para el recommendation_service: devuelve los song_id con los que
        el usuario ya tuvo interacciones de los tipos indicados.
        Típicamente se llama con types=["like", "play"] para excluir
        canciones que el usuario ya conoce bien de las recomendaciones nuevas.
        """
        rows = (
            db.query(Interaction.song_id)
            .filter(
                Interaction.user_id == user_id,
                Interaction.type.in_(types),
            )
            .distinct()
            .all()
        )
        return [row[0] for row in rows]

    @staticmethod
    def get_user_history(
        db: Session,
        user_id: int,
        type: str | None = None,
        limit: int | None = None,
    ) -> list[Interaction]:
        """
        Historial completo del usuario, opcionalmente filtrado por tipo.
        Para el recommendation_service: construir el dataset de comportamiento
        (qué escucha, cuánto tiempo, qué saltea con 30s+).
        """
        query = (
            db.query(Interaction)
            .filter(Interaction.user_id == user_id)
        )
        if type:
            query = query.filter(Interaction.type == type)
        query = query.order_by(Interaction.date.desc())
        if limit:
            query = query.limit(limit)
        return query.all()

    @staticmethod
    def count_plays(db: Session, user_id: int, song_id: int) -> int:
        """
        Cuántas veces el usuario escuchó 30s+ esta canción específica.
        Señal de intensidad de gusto más allá del like explícito.
        """
        return (
            db.query(Interaction)
            .filter_by(user_id=user_id, song_id=song_id, type="play")
            .count()
        )