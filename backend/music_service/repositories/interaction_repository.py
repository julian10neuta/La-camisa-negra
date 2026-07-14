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
    def get_recent_plays(db: Session, user_id: int, limit: int = 8) -> list[tuple]:
        """
        Para el "Sigue escuchando" del Home: las últimas canciones que el usuario
        reprodujo, **sin repetidos** y de la más reciente a la más antigua.

        Devuelve tuplas (Song, última_fecha_de_reproducción).

        El agrupado importa: `get_user_history` devuelve una fila por
        reproducción, así que quien escuchó la misma canción cinco veces la vería
        cinco veces seguidas. Aquí se agrupa por canción y se ordena por su
        reproducción MÁS reciente, lo que en SQL es un group by + max(date) — una
        sola consulta, sin deduplicar en Python.
        """
        from shared.models import Song
        from sqlalchemy import func

        last_play = func.max(Interaction.date).label("last_play")
        return (
            db.query(Song, last_play)
            .join(Interaction, Interaction.song_id == Song.id)
            .filter(Interaction.user_id == user_id, Interaction.type == "play")
            .group_by(Song.id)
            .order_by(last_play.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_stats(db: Session, user_id: int, since: datetime) -> dict:
        """
        Para el "Tu semana en Wavely" del Home: resumen de la actividad del
        usuario desde `since`.

        Nota sobre los minutos: se suman los segundos de las reproducciones Y de
        los saltos, porque una canción que escuchaste 40 segundos y luego saltaste
        es tiempo que efectivamente escuchaste. Sumar solo los "play" mentiría a
        la baja. Los "like" no tienen `time_reproduced` (es NULL), por eso el
        filtro por tipo y el coalesce.
        """
        from shared.models import Song
        from sqlalchemy import func

        def _plays():
            return db.query(Interaction).filter(
                Interaction.user_id == user_id,
                Interaction.date >= since,
                Interaction.type == "play",
            )

        plays = _plays().count()

        distinct_songs = (
            db.query(func.count(func.distinct(Interaction.song_id)))
            .filter(
                Interaction.user_id == user_id,
                Interaction.date >= since,
                Interaction.type == "play",
            )
            .scalar()
        ) or 0

        seconds = (
            db.query(func.coalesce(func.sum(Interaction.time_reproduced), 0))
            .filter(
                Interaction.user_id == user_id,
                Interaction.date >= since,
                Interaction.type.in_(["play", "skip"]),
            )
            .scalar()
        ) or 0

        top = (
            db.query(Song.artist, func.count(Interaction.id).label("n"))
            .join(Interaction, Interaction.song_id == Song.id)
            .filter(
                Interaction.user_id == user_id,
                Interaction.date >= since,
                Interaction.type == "play",
            )
            .group_by(Song.artist)
            .order_by(func.count(Interaction.id).desc())
            .first()
        )

        return {
            "plays": plays,
            "distinct_songs": int(distinct_songs),
            "seconds_listened": int(seconds),
            "top_artist": top[0] if top else None,
            "top_artist_plays": int(top[1]) if top else 0,
        }

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