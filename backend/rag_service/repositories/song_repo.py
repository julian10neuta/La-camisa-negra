# rag_service/repositories/song_repo.py
# Lo único que este servicio le pide a la base de datos: el nombre y el artista
# de una canción. Nada de llamadas a Spotify — esos datos ya están guardados
# localmente desde que la canción entró al historial o a las recomendaciones,
# así que saber de qué canción hablamos cuesta CERO llamadas externas.
from sqlalchemy.orm import Session

from shared.models import Song


def get_song_by_track_id(db: Session, spotify_track_id: str) -> Song | None:
    return (
        db.query(Song)
        .filter(Song.spotify_track_id == spotify_track_id)
        .first()
    )
