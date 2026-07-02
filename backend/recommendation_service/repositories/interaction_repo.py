# recommendation_service/repositories/interaction_repo.py
# Lecturas de interacciones para construir el perfil de gustos. El
# recommendation_service es un servicio independiente, así que consulta
# shared.models directamente (no importa los repos de music_service).
from sqlalchemy.orm import Session
from shared.models import Interaction, Song


class InteractionReadRepository:

    @staticmethod
    def get_interactions_with_songs(db: Session, user_id: int) -> list[tuple]:
        """
        Todas las interacciones del usuario junto con su canción (para tener
        género y artista). Devuelve tuplas (Interaction, Song). De aquí el motor
        deriva el perfil de géneros, los artistas favoritos y el conjunto de
        canciones ya vistas (a excluir de las recomendaciones).
        """
        return (
            db.query(Interaction, Song)
            .join(Song, Interaction.song_id == Song.id)
            .filter(Interaction.user_id == user_id)
            .all()
        )
