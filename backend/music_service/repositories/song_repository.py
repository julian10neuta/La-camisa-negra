# music_service/repositories/song_repository.py
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from shared.models import Song


def _normalize_genres(value) -> str | None:
    """
    Acepta el género tanto como lista (data cruda de Spotify) como string ya
    unido (cuando el SongService lo pre-procesó). Evita el bug de hacer
    ",".join(un_string), que explotaba el género carácter por carácter.
    """
    if isinstance(value, str):
        return value or None
    if value:  # lista/tupla no vacía
        return ",".join(value)
    return None


class SongRepository:

    @staticmethod
    def get_by_id(db: Session, song_id: int) -> Song | None:
        return db.get(Song, song_id)

    @staticmethod
    def get_by_spotify_track_id(db: Session, spotify_track_id: str) -> Song | None:
        return (
            db.query(Song)
            .filter(Song.spotify_track_id == spotify_track_id)
            .first()
        )

    @staticmethod
    def get_many_by_spotify_track_ids(db: Session, spotify_track_ids: list[str]) -> list[Song]:
        """
        Útil cuando el resultado de una búsqueda en Spotify trae varias
        canciones y quieres saber cuáles ya tenemos cacheadas, en una sola query
        en vez de N queries sueltas.
        """
        return (
            db.query(Song)
            .filter(Song.spotify_track_id.in_(spotify_track_ids))
            .all()
        )

    @staticmethod
    def get_many_by_ids(db: Session, song_ids: list[int]) -> list[Song]:
        """
        Para el recommendation_service: dado un set de song_id que salieron
        de las Interaction de un usuario, trae su metadata completa de una vez.
        """
        return (
            db.query(Song)
            .filter(Song.id.in_(song_ids))
            .all()
        )

    @staticmethod
    def set_genres(db: Session, song: Song, genres: str | None) -> Song:
        """Actualiza el género de una canción ya existente (auto-sanado/backfill)."""
        song.genres = genres
        db.commit()
        db.refresh(song)
        return song

    @staticmethod
    def get_missing_genres(db: Session) -> list[Song]:
        """Canciones sin género poblado (null o vacío) — para el backfill."""
        return (
            db.query(Song)
            .filter(or_(Song.genres.is_(None), Song.genres == ""))
            .all()
        )

    @staticmethod
    def get_all_with_genres(db: Session) -> list[Song]:
        """
        Para entrenar KMeans necesitas el universo completo de canciones
        que tienen genres pobladas (no null/vacío) — son tu feature principal
        para clustering si no guardas audio features de Spotify.
        """
        return (
            db.query(Song)
            .filter(Song.genres.isnot(None), Song.genres != "")
            .all()
        )

    @staticmethod
    def create_from_spotify_data(db: Session, track_data: dict) -> Song:
        """
        Crea una canción basada en la data cruda de Spotify.
        Ahora optimizado para el enfoque de 'memoria de preferencias'.
        """
        song = Song(
            spotify_track_id=track_data["id"],
            name=track_data["name"],
            # Manejamos el artista igual que antes por seguridad
            artist=track_data["artists"][0]["name"] if track_data.get("artists") else "Unknown",
            # Guardamos los géneros (lista o string ya unido) sin corromperlos.
            genres=_normalize_genres(track_data.get("genres")),
            # Guardamos duración para lógica de 'skip' o 'reproducción completa'
            duration_ms=track_data.get("duration_ms"),
        )
        db.add(song)
        db.commit()
        db.refresh(song)
        return song

    @staticmethod
    def get_or_create_many(db: Session, tracks_data: list[dict]) -> list[Song]:
        """
        Batch insert/lookup: dado un set de resultados de búsqueda de Spotify,
        determina cuáles ya existen y cuáles hay que crear, en pocas queries
        en vez de N idas y vueltas.
        """
        spotify_ids = [t["id"] for t in tracks_data]
        existing = SongRepository.get_many_by_spotify_track_ids(db, spotify_ids)
        existing_ids = {s.spotify_track_id for s in existing}

        new_songs = []
        for track in tracks_data:
            if track["id"] not in existing_ids:
                song = SongRepository.create_from_spotify_data(db, track)
                new_songs.append(song)

        return existing + new_songs
    

