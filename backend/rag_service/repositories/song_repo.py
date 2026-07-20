# rag_service/repositories/song_repo.py
# Lo único que este servicio le pide a la base de datos: el nombre y el artista
# de una canción. Nada de llamadas a Spotify — esos datos ya están guardados
# localmente desde que la canción entró al historial o a las recomendaciones,
# así que saber de qué canción hablamos cuesta CERO llamadas externas.
from dataclasses import dataclass

from sqlalchemy.orm import Session

from shared.models import Song


def get_song_by_track_id(db: Session, spotify_track_id: str) -> Song | None:
    return (
        db.query(Song)
        .filter(Song.spotify_track_id == spotify_track_id)
        .first()
    )


@dataclass
class SongRef:
    """
    Una canción que NO está en nuestra base de datos.

    Hace falta porque la búsqueda del catálogo va directa a Spotify y no
    persiste nada: si el usuario abre el chat desde un resultado del buscador,
    esa canción no existe todavía en `songs`. Antes eso daba un 404 y el chat
    parecía roto.

    El nombre y el artista los manda el cliente y solo se usan para consultar
    Wikipedia — no se guardan ni se creen para nada más, así que no abre ningún
    agujero. Y sigue sin costar una sola llamada a Spotify.
    """

    spotify_track_id: str
    name: str
    artist: str


def resolve_song(db: Session, track_id: str, name: str | None, artist: str | None):
    """
    La canción de la base si está; si no, una referencia con lo que mandó el
    cliente. Devuelve None solo cuando no hay ni lo uno ni lo otro.
    """
    song = get_song_by_track_id(db, track_id)
    if song is not None:
        return song
    if name and artist:
        return SongRef(spotify_track_id=track_id, name=name, artist=artist)
    return None
